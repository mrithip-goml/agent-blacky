import sys
import os
import asyncio
from pathlib import Path
from typing import Any, Dict, List
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import warnings

warnings.filterwarnings("ignore", category=Warning)

class MCPClientManager:
    """Manages connections to MCP servers over stdio and maps them to Gemini API tool calls."""

    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        self.server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=merged_env
        )
        self.session: ClientSession | None = None
        self._exit_stack = None

    async def connect(self):
        """Establishes stdio connection to the MCP server process."""
        self._exit_stack = stdio_client(self.server_params)
        read, write = await self._exit_stack.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def close(self):
        """Cleanly closes session and shuts down the MCP server process."""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
        if self._exit_stack:
            await self._exit_stack.__aexit__(None, None, None)
            self._exit_stack = None

    async def get_gemini_tools(self) -> List[types.FunctionDeclaration]:
        """Retrieves tools from the MCP server and converts them into Gemini FunctionDeclarations."""
        if not self.session:
            raise RuntimeError("MCP Session is not initialized. Call connect() first.")

        mcp_tools = await self.session.list_tools()
        gemini_functions = []

        for tool in mcp_tools.tools:
            parameters = tool.inputSchema if tool.inputSchema else {"type": "OBJECT", "properties": {}}
            fn_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or f"MCP tool: {tool.name}",
                parameters=parameters
            )
            gemini_functions.append(fn_decl)

        return gemini_functions

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executes a tool call requested by Gemini on the MCP server."""
        if not self.session:
            return "[ERROR] MCP Session is not active."

        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            outputs = []
            for content in result.content:
                if hasattr(content, "text"):
                    outputs.append(content.text)
                elif hasattr(content, "data"):
                    outputs.append(str(content.data))

            return "\n".join(outputs) if outputs else "Tool executed successfully with no text output."
        except Exception as e:
            return f"[ERROR] Failed to execute MCP tool '{tool_name}': {str(e)}"


async def _test_runner():
    print("[Blacky] Testing DuckDuckGo MCP Server...")
    
    # Locate the executable in the active pyenv environment
    venv_bin = Path(sys.executable).parent
    duckduckgo_executable = str(venv_bin / "duckduckgo-mcp-server")

    manager = MCPClientManager(
        command=duckduckgo_executable,
        args=[]
    )
    
    try:
        await manager.connect()
        tools = await manager.get_gemini_tools()
        print(f"[Success] Connected! Loaded {len(tools)} tools:")
        for t in tools:
            print(f" - {t.name}: {t.description}")
            
        print("\nTesting Search Query...")
        res = await manager.execute_tool("search", {"query": "Niri Wayland compositor", "max_results": 2})
        print(res[:300] + "...")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(_test_runner())