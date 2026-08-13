import asyncio
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError
from ui.console import console
from config.settings import GEMINI_API_KEY, GEMINI_MODEL

class GeminiEngine:
    """Core LLM engine managing Gemini API interactions and MCP Function Calling loops."""

    def __init__(self, api_key: str = None, mcp_manager=None, model: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Check your .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = model or GEMINI_MODEL
        self.mcp_manager = mcp_manager
    #     self.history: List[types.Content] = []
    #     self.chat_log: List[Dict[str, str]] = []

    # def clear_history(self):
    #     """Clears conversation history and chat logs."""
    #     self.history = []
    #     self.chat_log = []

    def call_gemini_safe(
        self,
        contents: Any,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        tools: Optional[List[types.Tool]] = None
    ) -> Any:
        """Wrapper around Gemini API calls to gracefully catch and handle API errors."""
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

    async def generate_chat_response_async(
        self,
        user_input: str,
        system_instruction: str,
        enable_mcp: bool = True,
        max_turns: int = 5
    ) -> str:
        """Executes Gemini chat with optional automatic multi-turn MCP Function Calling loop."""
        mcp_tools = None
        if enable_mcp and self.mcp_manager and self.mcp_manager.is_connected:
            try:
                declarations = await self.mcp_manager.get_gemini_tools()
                if declarations:
                    mcp_tools = [types.Tool(function_declarations=declarations)]
            except Exception as e:
                console.print(f"[dim yellow]Warning: Failed to load MCP tool declarations: {e}[/dim yellow]")
                mcp_tools = None

        # Initialize contents with existing session history
        contents = list(self.history)
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))
        current_turn = 0
        final_text = ""

        while current_turn < max_turns:
            current_turn += 1
            response = self.call_gemini_safe(
                contents=contents,
                system_instruction=system_instruction,
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
                final_text = response.text.strip() if (hasattr(response, "text") and response.text) else "No response generated."
                break

            # Execute tool calls requested by Gemini
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

        if current_turn >= max_turns and not final_text:
            final_text = "Reached maximum turn limit for tool calls."

        # Keep successfully completed multi-turn interaction in the session history
        self.history = contents
        self.chat_log.append({"user": user_input, "assistant": final_text})
        return final_text
