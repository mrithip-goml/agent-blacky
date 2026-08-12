from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich import box
from config.settings import GEMINI_MODEL, THEME_PRIMARY, THEME_SECONDARY, THEME_SUCCESS, THEME_WARNING

console = Console()

def display_banner():
    """Renders the top banner for BLACKY AI CLI."""
    title = f"[bold {THEME_PRIMARY}]✦ BLACKY AI ✦[/bold {THEME_PRIMARY}]"
    subtitle = "[dim]Niri Terminal Companion[/dim]"
    badges = (
        f"[cyan]/stock[/cyan] Market Analyst  •  "
        f"[yellow]/yt[/yellow] YouTube Agent  •  "
        f"[cyan]/doc[/cyan] Document RAG  •  "
        f"[blue]MCP[/blue] Automatic Search  •  "
        f"[green]/help[/green] Commands"
    )
    footer = f"[dim]model:[/dim] [bold white]{GEMINI_MODEL}[/bold white]"
    banner = Table.grid(padding=(0, 1))
    banner.add_column(justify="center")
    banner.add_column(justify="left")
    banner.add_row(title, footer)
    banner.add_row(subtitle, badges)
    console.print(Panel(banner, border_style=THEME_PRIMARY, box=box.ROUNDED, expand=False, padding=(1, 2)))

def print_help():
    """Prints the command directory table."""
    help_table = Table(
        title="[bold cyan]Blacky AI Command Directory[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
        header_style="bold white on dark_cyan",
        expand=False,
        padding=(0, 1)
    )
    help_table.add_column("Command", style="bold green", no_wrap=True)
    help_table.add_column("Description", style="white")

    help_table.add_row("[bold yellow]General Chat[/bold yellow]", "Ask any natural-language question. Real-time topics automatically trigger MCP DuckDuckGo search.")
    help_table.add_row("[bold yellow]/search <query>[/bold yellow]", "Perform explicit web search via MCP DuckDuckGo tool")
    help_table.add_row("[bold yellow]/stock <ticker>[/bold yellow]", "Deep fundamental & market analysis for a ticker (e.g. `/stock NVDA` or `/stock AAPL`)")
    help_table.add_row("[bold yellow]/stock compare <t1> <t2> ...[/bold yellow]", "Side-by-side comparative analysis with chart (e.g. `/stock compare AAPL MSFT GOOGL`)")
    help_table.add_row("[bold yellow]/yt <link>[/bold yellow]", "Load, index, and summarize a YouTube video")
    help_table.add_row("[bold yellow]/yt list[/bold yellow]", "List all stored YouTube videos")
    help_table.add_row("[bold yellow]/yt switch <number/id>[/bold yellow]", "Switch active YouTube session")
    help_table.add_row("[bold yellow]/doc <path>[/bold yellow]", "Load & index PDF, DOCX, PPTX, EPUB, MD, TXT, HTML")
    help_table.add_row("[bold yellow]/doc list[/bold yellow]", "List all stored documents in vector store")
    help_table.add_row("[bold yellow]/doc switch <number/id>[/bold yellow]", "Switch active document session")
    help_table.add_row("[bold yellow]/exit[/bold yellow]  or  [bold yellow]q[/bold yellow]", "Exit active mode back to General Chat")
    help_table.add_row("[bold yellow]/clear[/bold yellow]", "Clear terminal screen")
    help_table.add_row("[bold yellow]/help[/bold yellow]", "Show this command directory")

    console.print(help_table)
    console.print()
    console.print("[dim]Tip: Simply ask any question! Real-time queries automatically invoke web search via MCP.[/dim]")
    console.print()

def render_panel(content: str, title: str = "", border_style: str = "cyan"):
    """Renders markdown content inside a Rich Panel."""
    console.print(Panel(Markdown(content), title=f"[bold {border_style}]{title}[/bold {border_style}]", border_style=border_style))

def render_markdown(text: str):
    """Renders raw Markdown text."""
    console.print(Markdown(text))
