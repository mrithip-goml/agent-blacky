import subprocess
import re
import asyncio
from pathlib import Path
from core.llm import GeminiEngine
from config.settings import GEMINI_API_KEY, GEMINI_MODEL

def load_prompt(filename: str) -> str:
    """Helper to load system prompts from the prompts/ directory."""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"Prompt file missing: {prompt_path}")

class CLIAssistant:
    def __init__(self, api_key: str = None, mcp_manager=None):
        self.api_key = api_key or GEMINI_API_KEY
        self.engine = GeminiEngine(api_key=self.api_key, mcp_manager=mcp_manager)
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

    def is_safe_command(self, command: str) -> tuple[bool, str]:
        for pattern in self.forbidden_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Forbidden command pattern detected: {pattern}"
        return True, "Safe"

    def requires_system_execution(self, user_prompt: str) -> bool:
        prompt = f"{self.router_prompt}\n\nUser Prompt: {user_prompt}"
        res = self.engine.call_gemini_safe(contents=prompt, temperature=0.0)
        if isinstance(res, str):
            return False
        return "EXEC" in res.text.strip().upper()

    def generate_command(self, user_prompt: str) -> str:
        res = self.engine.call_gemini_safe(
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

            res = self.engine.call_gemini_safe(
                contents=summary_prompt,
                system_instruction=self.summarizer_prompt
            )
            return res if isinstance(res, str) else res.text.strip()

        # 2. General Chat Route with MCP Tool Integration via GeminiEngine
        return await self.engine.generate_chat_response_async(
            user_input=user_input,
            system_instruction=self.general_prompt
        )

    def handle_user_query(self, user_input: str) -> str:
        """Synchronous wrapper for legacy invocations."""
        return asyncio.run(self.handle_user_query_async(user_input))