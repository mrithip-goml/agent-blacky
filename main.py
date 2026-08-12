import config.settings
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from core.thinking import thinking_status
from tools.cli_assistant import CLIAssistant

console = Console()

SYSTEM_KEYWORDS = ["disk", "usage", "storage", "ram", "memory", "file", "folder", "process", "cpu", "directory", "run", "cmd", "find"]

def display_banner():
    banner = "[bold magenta]BLACKY AI[/bold magenta] - [dim]Niri Terminal Companion[/dim]"
    console.print(Panel(banner, border_style="magenta", expand=False))

def main():
    display_banner()
    
    try:
        cli_agent = CLIAssistant()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    console.print("[dim]Type 'exit' or 'q' to quit.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold green]Blacky > [/bold green]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "q"]:
                break

            # The background thread will now cycle phrases every 1 second while waiting
            with thinking_status():
                is_system_query = any(kw in user_input.lower() for kw in SYSTEM_KEYWORDS) or user_input.lower().startswith("run:") or user_input.lower().startswith("cmd:")

                if is_system_query:
                    clean_query = user_input.replace("run:", "").replace("cmd:", "").strip()
                    response = cli_agent.process_smart_query(clean_query)
                else:
                    response = cli_agent.client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=user_input,
                        config={"system_instruction": "You are Blacky, a concise Linux terminal assistant running on Ubuntu Niri. Keep responses brief, direct, and well-structured."}
                    ).text

            console.print("\n[bold magenta]Blacky:[/bold magenta]")
            console.print(Markdown(response))
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting Blacky...[/yellow]")
            sys.exit(0)

if __name__ == "__main__":
    main()