import config.settings
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from core.thinking import thinking_status
from tools.cli_assistant import CLIAssistant

console = Console()

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

            with thinking_status():
                response = cli_agent.handle_user_query(user_input)

            console.print("\n[bold magenta]Blacky:[/bold magenta]")
            console.print(Markdown(response))
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting Blacky...[/yellow]")
            sys.exit(0)

if __name__ == "__main__":
    main()