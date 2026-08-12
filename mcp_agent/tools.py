from typing import Any, Dict
from mcp import ClientSession

async def execute_mcp_tool(session: ClientSession | None, tool_name: str, arguments: Dict[str, Any]) -> str:
    """Executes a tool call on the connected MCP server session."""
    if not session:
        return "[ERROR] MCP Session is not active."

    try:
        result = await session.call_tool(tool_name, arguments=arguments)
        outputs = []
        for content in result.content:
            if hasattr(content, "text"):
                outputs.append(content.text)
            elif hasattr(content, "data"):
                outputs.append(str(content.data))

        return "\n".join(outputs) if outputs else "Tool executed successfully with no text output."
    except Exception as e:
        return f"[ERROR] Failed to execute MCP tool '{tool_name}': {str(e)}"

def format_mcp_output(tool_name: str, query_args: Dict[str, Any], result: str) -> str:
    """Formats MCP tool output for display or logging."""
    return f"[MCP Tool Execution - {tool_name}]\nArgs: {query_args}\nResult:\n{result}"
