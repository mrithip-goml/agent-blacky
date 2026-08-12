import sys
import asyncio
from pathlib import Path
from rich.rule import Rule
from ui.console import console, display_banner, print_help, render_markdown
from core.commands import CommandHandler
from core.thinking import thinking_status
from mcp_agent.client import MCPClientManager
from tools.cli_assistant import CLIAssistant

class BlackyApp:
    """Main CLI application orchestrating MCP connections, commands, and interactive chat loop."""

    def __init__(self):
        venv_bin = Path(sys.executable).parent
        duckduckgo_executable = str(venv_bin / "duckduckgo-mcp-server")

        self.mcp_manager = MCPClientManager(command=duckduckgo_executable, args=[])
        self.cmd_handler = CommandHandler(mcp_manager=self.mcp_manager)
        self.cli_agent = CLIAssistant(mcp_manager=self.mcp_manager)

    async def run(self):
        try:
            console.print("[dim]Booting up MCP DuckDuckGo Search Server...[/dim]")
            await self.mcp_manager.connect()
            console.print("[bold green]✓ MCP Search Agent Ready[/bold green]\n")
        except Exception as e:
            console.print(f"[bold yellow]⚠ MCP Startup Warning:[/bold yellow] {e}")

        display_banner()
        console.print("[dim]Type '/help' for commands, or 'exit' / 'q' to quit.[/dim]\n")

        while True:
            try:
                # Dynamic prompt indicator based on active session
                if self.cmd_handler.active_doc_id:
                    prompt_label = f"[bold cyan]📄 Blacky [DOC:{self.cmd_handler.active_doc_id}] ❯ [/bold cyan]"
                elif self.cmd_handler.active_yt_id:
                    prompt_label = f"[bold magenta]▶ Blacky [YT:{self.cmd_handler.active_yt_id}] ❯ [/bold magenta]"
                else:
                    prompt_label = "[bold green]✦ Blacky ❯ [/bold green]"

                user_input = console.input(prompt_label).strip()
                if not user_input:
                    continue

                if user_input.lower() in ["exit", "q", "/exit"]:
                    if self.cmd_handler.active_yt_id or self.cmd_handler.active_doc_id:
                        console.print("[yellow]Exited active RAG session. Back to General Chat.[/yellow]")
                        self.cmd_handler.clear_active_sessions()
                        continue
                    break

                if user_input.lower() == "/clear":
                    console.clear()
                    display_banner()
                    continue

                if user_input.lower() == "/help":
                    print_help()
                    continue

                if user_input.startswith("/doc"):
                    self.cmd_handler.handle_doc_route(user_input[4:].strip())
                    continue

                if user_input.startswith("/yt"):
                    self.cmd_handler.handle_youtube_route(user_input[3:].strip())
                    continue

                if user_input.startswith("/stock"):
                    self.cmd_handler.handle_stock_route(user_input[6:].strip())
                    continue

                if user_input.startswith("/search"):
                    await self.cmd_handler.handle_search_route(user_input[7:].strip())
                    continue

                # Automatic Context Routing for Active RAG Sessions
                if self.cmd_handler.active_doc_id:
                    self.cmd_handler.handle_doc_route(user_input)
                    continue

                if self.cmd_handler.active_yt_id:
                    self.cmd_handler.handle_youtube_route(user_input)
                    continue

                # Standard General Chat Execution with Automatic MCP Search
                with thinking_status():
                    response = await self.cli_agent.handle_user_query_async(user_input)

                console.print(Rule(style="dim"))
                render_markdown(response)
                console.print(Rule(style="dim"))
                console.print()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exiting Blacky...[/yellow]")
                sys.exit(0)

        await self.mcp_manager.close()

async def main():
    try:
        app = BlackyApp()
        await app.run()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())