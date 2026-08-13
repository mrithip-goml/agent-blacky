import sys
import asyncio
import argparse
from pathlib import Path
from rich.rule import Rule
from ui.console import console, display_banner, print_help, render_markdown
from core.commands import CommandHandler
from core.thinking import thinking_status
from mcp_agent.client import MCPClientManager
from tools.cli_assistant import CLIAssistant
from voice import WhisperSTT, speak_response

class BlackyApp:
    """Main CLI application orchestrating MCP connections, commands, and interactive chat loop."""

    def __init__(self, stt_enabled=False, tts_enabled=False):
        venv_bin = Path(sys.executable).parent
        duckduckgo_executable = str(venv_bin / "duckduckgo-mcp-server")

        self.mcp_manager = MCPClientManager(command=duckduckgo_executable, args=[])
        self.cmd_handler = CommandHandler(mcp_manager=self.mcp_manager)
        self.cli_agent = CLIAssistant(mcp_manager=self.mcp_manager)

        # Voice Pipeline State
        self.stt_enabled = stt_enabled
        self.tts_enabled = tts_enabled or stt_enabled # Default TTS on if STT is on
        self.stt_engine = None  # Lazy-loaded

    async def run(self):
        try:
            console.print("[dim]Booting up MCP DuckDuckGo Search Server...[/dim]")
            await self.mcp_manager.connect()
            console.print("[bold green]✓ MCP Search Agent Ready[/bold green]\n")
        except Exception as e:
            console.print(f"[bold yellow]⚠ MCP Startup Warning:[/bold yellow] {e}")

        display_banner(self.stt_enabled, self.tts_enabled)
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

                # Step 1: Input Collection
                if self.stt_enabled:
                    if self.stt_engine is None:
                        self.stt_engine = WhisperSTT()
                    user_input = self.stt_engine.listen_and_transcribe()
                    
                    # Check voice-only exit keywords
                    if user_input.lower() in ["exit voice", "stop voice", "quiet", "text mode", "/text", "/voice off"]:
                        self.stt_enabled = False
                        console.print("[bold magenta]✦ Switched to Text Mode.[/bold magenta]")
                        display_banner(self.stt_enabled, self.tts_enabled)
                        continue
                    
                    if not user_input:
                        # Fallback to text if silence or error
                        user_input = console.input(prompt_label).strip()
                else:
                    user_input = console.input(prompt_label).strip()

                if not user_input:
                    continue

                # Step 2: Command & Toggle Handling
                cmd_lower = user_input.lower().strip()
                
                if cmd_lower in ["/voice", "/voice on"]:
                    self.stt_enabled = True
                    console.print("[bold magenta]✦ Voice Input (Microphone) Enabled.[/bold magenta]")
                    display_banner(self.stt_enabled, self.tts_enabled)
                    continue
                elif cmd_lower in ["/text", "/voice off"]:
                    self.stt_enabled = False
                    console.print("[bold magenta]✦ Switched to Text Mode (Keyboard Input).[/bold magenta]")
                    display_banner(self.stt_enabled, self.tts_enabled)
                    continue
                elif cmd_lower in ["/mute", "/tts off"]:
                    self.tts_enabled = False
                    console.print("[bold magenta]✦ Audio Output Muted.[/bold magenta]")
                    display_banner(self.stt_enabled, self.tts_enabled)
                    continue
                elif cmd_lower in ["/talk", "/speak", "/tts on"]:
                    self.tts_enabled = True
                    console.print("[bold magenta]✦ Audio Output (TTS Speaking) Enabled.[/bold magenta]")
                    display_banner(self.stt_enabled, self.tts_enabled)
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

                # Step 3: Conditional Audio Playback
                if self.tts_enabled:
                    await speak_response(response)

            except (KeyboardInterrupt, EOFError):
                if self.stt_enabled:
                    console.print("\n[yellow]✦ Operation interrupted. Reverting to text prompt...[/yellow]")
                    self.stt_enabled = False
                    display_banner(self.stt_enabled, self.tts_enabled)
                    continue
                else:
                    console.print("\n[yellow]Exiting Blacky...[/yellow]")
                sys.exit(0)

        await self.mcp_manager.close()

async def main():
    parser = argparse.ArgumentParser(description="BLACKY AI - Niri Terminal Companion")
    parser.add_argument("--voice", action="store_true", help="Enable voice input (STT) on startup")
    parser.add_argument("--speak", "--tts", action="store_true", help="Enable voice output (TTS) on startup")
    args = parser.parse_args()

    try:
        app = BlackyApp(stt_enabled=args.voice, tts_enabled=args.speak)
        await app.run()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
