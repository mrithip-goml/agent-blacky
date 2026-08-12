import subprocess
import re
import asyncio
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError
from rich.console import Console
from config.settings import GEMINI_API_KEY, GEMINI_MODEL

console = Console()

def load_prompt(filename: str) -> str:
    """Helper to load system prompts from the prompts/ directory."""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"Prompt file missing: {prompt_path}")

class CLIAssistant:
    def __init__(self, api_key: str = None, mcp_manager=None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Check your .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = GEMINI_MODEL
        self.mcp_manager = mcp_manager

        self.router_prompt = load_prompt("cli_router.txt")
        self.generator_prompt = load_prompt("cli_generator.txt")
        self.summarizer_prompt = load_prompt("cli_summarizer.txt")
        self.general_prompt = load_prompt("general_chat.txt")

        self.forbidden_patterns = [
            r"\bsudo\b", r"\bsu\b", r"\bchown\b",
            r"rm\s+-rf\s+/", r"rm\s+-rf\s+~",
            r">\s*/dev/sd", r"mkfs", r"dd\s+if="
        ]

    def _call_gemini_safe(self, contents, system_instruction=None, temperature=0.1, tools=None):
        """Wrapper around Gemini API calls to catch errors gracefully."""
        config_kwargs = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if tools:
            config_kwargs["tools"] = tools

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
        except ClientError as e:
            if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                return "[ERROR] Gemini API Quota Exceeded (429 Rate Limit)."
            return f"[ERROR] API Client Error: {str(e)}"
        except APIError as e:
            return f"[ERROR] Gemini API Exception: {str(e)}"
        except Exception as e:
            return f"[ERROR] Unexpected Error: {str(e)}"

    def is_safe_command(self, command: str) -> tuple[bool, str]:
        for pattern in self.forbidden_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Forbidden command pattern detected: {pattern}"
        return True, "Safe"

    def requires_system_execution(self, user_prompt: str) -> bool:
        prompt = f"{self.router_prompt}\n\nUser Prompt: {user_prompt}"
        res = self._call_gemini_safe(contents=prompt, temperature=0.0)
        if isinstance(res, str):
            return False
        return "EXEC" in res.text.strip().upper()

    def generate_command(self, user_prompt: str) -> str:
        res = self._call_gemini_safe(
            contents=user_prompt,
            system_instruction=self.generator_prompt,
            temperature=0.1
        )
        if isinstance(res, str):
            return res
        return res.text.replace("```bash", "").replace("```", "").strip()

    def execute_command(self, command: str) -> str:
        is_safe, reason = self.is_safe_command(command)
        if not is_safe:
            return f"[ERROR] Security Triggered: {reason}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                executable="/bin/bash"
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            output = stdout
            if stderr:
                output += f"\n[STDERR]: {stderr}" if output else stderr
            return output if output else "[Command executed cleanly with no output]"

        except subprocess.TimeoutExpired:
            return "[ERROR] Command timed out after 15 seconds."
        except Exception as e:
            return f"[ERROR] Execution failed: {str(e)}"

    async def handle_user_query_async(self, user_input: str) -> str:
        """Asynchronous handler that automatically routes tools to MCP when needed."""
        # 1. System Execution Route
        if self.requires_system_execution(user_input):
            cmd = self.generate_command(user_input)
            if cmd.startswith("[ERROR]"):
                return cmd

            is_safe, reason = self.is_safe_command(cmd)
            if not is_safe:
                return f"I cannot execute that command due to security restrictions ({reason})."

            output = self.execute_command(cmd)

            summary_prompt = (
                f"User Query: '{user_input}'\n"
                f"Executed Command: `{cmd}`\n"
                f"Command Output:\n{output}\n\n"
                "Summarize the command output clearly and directly to answer the user's question. "
                "Include the executed command at the end in parentheses."
            )

            res = self._call_gemini_safe(
                contents=summary_prompt,
                system_instruction=self.summarizer_prompt
            )
            return res if isinstance(res, str) else res.text.strip()

        # 2. General Chat Route with MCP Tool Integration
        mcp_tools = None
        if self.mcp_manager and self.mcp_manager.is_connected:
            try:
                declarations = await self.mcp_manager.get_gemini_tools()
                if declarations:
                    mcp_tools = [types.Tool(function_declarations=declarations)]
            except Exception as e:
                console.print(f"[dim yellow]Warning: Failed to load MCP tool declarations: {e}[/dim yellow]")
                mcp_tools = None

        # Build initial turn contents
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_input)])]

        max_turns = 5
        current_turn = 0

        while current_turn < max_turns:
            current_turn += 1
            response = self._call_gemini_safe(
                contents=contents,
                system_instruction=self.general_prompt,
                tools=mcp_tools
            )

            if isinstance(response, str):
                return response

            candidate = response.candidates[0] if (hasattr(response, "candidates") and response.candidates) else None
            if not candidate or not candidate.content:
                return "No response generated."

            contents.append(candidate.content)

            function_calls = getattr(response, "function_calls", None)
            if not function_calls and candidate.content.parts:
                function_calls = [p.function_call for p in candidate.content.parts if p.function_call]

            if not function_calls:
                return response.text.strip() if (hasattr(response, "text") and response.text) else "No response generated."

            # Execute tool calls and append response parts
            fn_parts = []
            for call in function_calls:
                tool_name = call.name
                tool_args = dict(call.args) if call.args else {}

                console.print(f"[bold blue][MCP Search][/bold blue] Executing [white]'{tool_name}'[/white] with query: [dim]{tool_args}[/dim]...")

                tool_result = await self.mcp_manager.execute_tool(tool_name, tool_args)
                fn_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result}
                    )
                )

            contents.append(types.Content(role="user", parts=fn_parts))

        return "Reached maximum turn limit for tool calls."

    def handle_user_query(self, user_input: str) -> str:
        """Synchronous wrapper for legacy invocations."""
        return asyncio.run(self.handle_user_query_async(user_input))