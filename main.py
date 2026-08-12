from pathlib import Path
import config.settings
import asyncio
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box
from config.settings import GEMINI_MODEL
from core.thinking import thinking_status
from tools import stock_agent
from tools.cli_assistant import CLIAssistant
from tools.youtube_summary import YouTubeAgent
from tools.doc_rag import DocumentAgent
from tools.stock_agent import StockAgent
from tools.mcp_client import MCPClientManager

console = Console()

class BlackyApp:
    def __init__(self):
        venv_bin = Path(sys.executable).parent
        duckduckgo_executable = str(venv_bin / "duckduckgo-mcp-server")

        self.mcp_manager = MCPClientManager(
            command=duckduckgo_executable,
            args=[]
        )
        self.mcp_connected = False

        self.cli_agent = CLIAssistant(mcp_manager=self.mcp_manager)
        self.yt_agent = YouTubeAgent()
        self.doc_agent = DocumentAgent()
        self.stock_agent = StockAgent()

        # Restore active RAG states if present in ChromaDB
        self.active_yt_id = None
        self.active_doc_id = None

    async def initialize_mcp(self):
        """Connects to the DuckDuckGo MCP Server process on startup."""
        try:
            console.print("[dim]Booting up MCP DuckDuckGo Search Server...[/dim]")
            await self.mcp_manager.connect()
            self.mcp_connected = True
            console.print("[bold green]✓ MCP Search Agent Ready[/bold green]\n")
        except Exception as e:
            console.print(f"[bold yellow]⚠ MCP Startup Warning:[/bold yellow] {e}")
            self.mcp_connected = False

    async def close_mcp(self):
        """Cleanly terminates the MCP subprocess on exit."""
        if self.mcp_connected:
            await self.mcp_manager.close()
            self.mcp_connected = False

    def display_banner(self):
        title = "[bold magenta]✦ BLACKY AI ✦[/bold magenta]"
        subtitle = "[dim]Niri Terminal Companion[/dim]"
        badges = (
            "[cyan]/stock[/cyan] Market Analyst  •  "
            "[yellow]/yt[/yellow] YouTube Agent  •  "
            "[cyan]/doc[/cyan] Document RAG  •  "
            "[blue]MCP[/blue] Automatic Search  •  "
            "[green]/help[/green] Commands"
        )
        footer = f"[dim]model:[/dim] [bold white]{GEMINI_MODEL}[/bold white]"
        banner = Table.grid(padding=(0, 1))
        banner.add_column(justify="center")
        banner.add_column(justify="left")
        banner.add_row(title, footer)
        banner.add_row(subtitle, badges)
        console.print(Panel(banner, border_style="magenta", box=box.ROUNDED, expand=False, padding=(1, 2)))

    def print_help(self):
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

    async def handle_search_route(self, query: str):
        if not query:
            console.print("[red]Usage:[red] /search <query>")
            return

        if not self.mcp_connected:
            console.print("[bold red]MCP Search Server is not active.[/bold red]")
            return

        console.print(f"[bold blue][MCP Search][/bold blue] Executing DuckDuckGo web search for: [white]'{query}'[/white]...")
        with thinking_status():
            try:
                results = await self.mcp_manager.execute_tool("search", {"query": query, "max_results": 5})
            except Exception as e:
                results = f"[ERROR] Search failed: {str(e)}"

        console.print(Panel(Markdown(results), title=f"[bold blue]Search Results ({query})[/bold blue]", border_style="blue"))

    def handle_doc_route(self, payload: str):
        if not payload:
            if self.active_doc_id:
                console.print(f"[yellow]Active Document Session:[yellow] {self.active_doc_id}. Ask any question or use '/exit'.")
            else:
                console.print("[red]Usage:[red] /doc <file_path> | /doc list | /doc switch <number_or_id>")
            return

        # 1. COMMAND: /doc list
        if payload.lower() in ["list", "ls"]:
            docs = self.doc_agent.list_indexed_docs()
            if not docs:
                console.print("[yellow]No documents found in local ChromaDB.[/yellow]")
                return

            console.print("\n[bold cyan]=== Stored Documents in Vector DB ===[/bold cyan]")
            for idx, d in enumerate(docs, 1):
                active_flag = " [bold green](Active)[/bold green]" if d['doc_id'] == self.active_doc_id else ""
                console.print(f"{idx}. [bold white]{d['title']}[/bold white] [dim](ID: {d['doc_id']} | Chunks: {d['chunk_count']})[/dim]{active_flag}")
            console.print("\n[dim]Switch active document using: /doc switch <number>[/dim]\n")
            return

        # 2. COMMAND: /doc switch <index_or_id>
        if payload.lower().startswith("switch"):
            target = payload[6:].strip()
            if not target:
                console.print("[red]Usage:[red] /doc switch <number or doc_id>")
                return

            docs = self.doc_agent.list_indexed_docs()
            target_id = target

            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(docs):
                    target_id = docs[idx]["doc_id"]
                else:
                    console.print(f"[bold red]Invalid selection number: {target}[/bold red]")
                    return

            res = self.doc_agent.switch_active_doc(target_id)
            if res.startswith("[SUCCESS]"):
                self.active_doc_id = self.doc_agent.current_doc_id
                self.active_yt_id = None  # Mutual exclusion
                console.print(f"[bold green]{res}[/bold green]")
            else:
                console.print(f"[bold red]{res}[/bold red]")
            return

        # 3. Process new document path or ask direct question
        if self.active_doc_id and not payload.startswith("/") and not (payload.startswith("./") or payload.startswith("~/") or payload.startswith("C:")):
            # Query active document
            console.print(f"[bold cyan][Document RAG][/bold cyan] Querying context for [{self.active_doc_id}]...")
            with thinking_status():
                answer = self.doc_agent.process_doc_query(
                    file_or_input=self.active_doc_id,
                    user_question=payload
                )
            console.print(Panel(Markdown(answer), title=f"[bold cyan]Document Response ({self.active_doc_id})[/bold cyan]", border_style="cyan"))
        else:
            # Load new file
            console.print(f"[bold cyan][RAG Ingestion][/bold cyan] Reading and embedding document...")
            with thinking_status():
                summary = self.doc_agent.process_doc_query(file_or_input=payload)

            if not summary.startswith("[ERROR]"):
                self.active_doc_id = self.doc_agent.current_doc_id
                self.active_yt_id = None  # Deactivate YouTube mode when document is loaded
                console.print(Panel(Markdown(summary), title=f"[bold cyan]Document Overview ({self.active_doc_id})[/bold cyan]", border_style="cyan"))
                console.print("[dim]Document Mode active. Ask any question about this document or type '/exit'.[/dim]\n")
            else:
                console.print(f"[bold red]{summary}[/bold red]")

    def handle_youtube_route(self, payload: str):
        if not payload:
            if self.active_yt_id:
                console.print(f"[yellow]Active YouTube Session:[yellow] {self.active_yt_id}. Ask any question or use '/exit'.")
            else:
                console.print("[red]Usage:[red] /yt <url_or_id> | /yt list | /yt switch <number_or_id>")
            return

        # 1. COMMAND: /yt list
        if payload.lower() in ["list", "ls"]:
            videos = self.yt_agent.list_indexed_videos()
            if not videos:
                console.print("[yellow]No YouTube videos found in local ChromaDB.[/yellow]")
                return

            console.print("\n[bold magenta]=== Stored YouTube Videos in Vector DB ===[/bold magenta]")
            for idx, v in enumerate(videos, 1):
                active_flag = " [bold green](Active)[/bold green]" if v['video_id'] == self.active_yt_id else ""
                console.print(f"{idx}. [bold white]{v['title']}[/bold white] [dim](ID: {v['video_id']} | Chunks: {v['chunk_count']})[/dim]{active_flag}")
            console.print("\n[dim]Switch active video using: /yt switch <number>[/dim]\n")
            return

        # 2. COMMAND: /yt switch <index_or_id>
        if payload.lower().startswith("switch"):
            target = payload[6:].strip()
            if not target:
                console.print("[red]Usage:[red] /yt switch <number or video_id>")
                return

            videos = self.yt_agent.list_indexed_videos()
            target_id = target

            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(videos):
                    target_id = videos[idx]["video_id"]
                else:
                    console.print(f"[bold red]Invalid selection number: {target}[/bold red]")
                    return

            res = self.yt_agent.switch_active_video(target_id)
            if res.startswith("[SUCCESS]"):
                self.active_yt_id = self.yt_agent.current_video_id
                self.active_doc_id = None  # Deactivate document mode when YouTube is activated
                console.print(f"[bold green]{res}[/bold green]")
            else:
                console.print(f"[bold red]{res}[/bold red]")
            return

        # 3. Process new YouTube video or direct question
        if self.active_yt_id and not payload.startswith("http") and len(payload) != 11:
            # Query active video
            console.print(f"[bold magenta][YouTube RAG][/bold magenta] Querying context for [{self.active_yt_id}]...")
            with thinking_status():
                answer = self.yt_agent.process_youtube_query(
                    url_or_input=self.active_yt_id,
                    user_question=payload
                )
            console.print(Panel(Markdown(answer), title=f"[bold magenta]YouTube Response ({self.active_yt_id})[/bold magenta]", border_style="magenta"))
        else:
            # Load new URL
            console.print(f"[bold magenta][Transcript Ingestion][/bold magenta] Fetching and embedding video...")
            with thinking_status():
                summary = self.yt_agent.process_youtube_query(url_or_input=payload)

            if not summary.startswith("[ERROR]"):
                self.active_yt_id = self.yt_agent.current_video_id
                self.active_doc_id = None
                console.print(Panel(Markdown(summary), title=f"[bold magenta]Video Overview ({self.active_yt_id})[/bold magenta]", border_style="magenta"))
                console.print("[dim]YouTube Mode active. Ask any question about this video or type '/exit'.[/dim]\n")
            else:
                console.print(f"[bold red]{summary}[/bold red]")

    def handle_stock_route(self, payload: str):
        if not payload:
            console.print("[red]Usage:[red] /stock <ticker>  OR  /stock compare <ticker1> <ticker2> ...")
            return

        tokens = payload.split()
        
        # 1. Comparative Analysis Command: /stock compare T1 T2 ...
        if tokens[0].lower() in ["compare", "comp", "vs"]:
            tickers = [t.strip(",").upper() for t in tokens[1:]]
            if len(tickers) < 2:
                console.print("[bold red]Please specify at least two tickers to compare. Example: /stock compare AAPL MSFT[/bold red]")
                return

            console.print(f"[bold green][Stock Analyst][/bold green] Comparing stocks: [bold white]{', '.join(tickers)}[/bold white]...")
            analysis = ""
            widget = ""
            with thinking_status():
                analysis, widget = self.stock_agent.compare_stocks(tickers)

            if analysis.startswith("[ERROR]"):
                console.print(f"[bold red]{analysis}[/bold red]")
                return

            console.print(Panel(Markdown(analysis), title=f"[bold green]Stock Comparison ({', '.join(tickers)})[/bold green]", border_style="green"))
            if widget:
                console.print(widget)
            return

        # 2. Single Stock Deep Dive: /stock <ticker>
        ticker = tokens[0].upper()
        console.print(f"[bold green][Stock Analyst][/bold green] Fetching live financial metrics for [bold white]{ticker}[/bold white]...")
        with thinking_status():
            analysis, _ = self.stock_agent.analyze_single_stock(ticker)

        if analysis.startswith("[ERROR]"):
            console.print(f"[bold red]{analysis}[/bold red]")
            return

        console.print(Panel(Markdown(analysis), title=f"[bold green]Equity Analysis ({ticker})[/bold green]", border_style="green"))

    async def run(self):
        await self.initialize_mcp()
        self.display_banner()
        console.print("[dim]Type '/help' for commands, or 'exit' / 'q' to quit.[/dim]\n")

        while True:
            try:
                # Prompt Indicator
                if self.active_doc_id:
                    prompt_label = f"[bold cyan]📄 Blacky [DOC:{self.active_doc_id}] ❯ [/bold cyan]"
                elif self.active_yt_id:
                    prompt_label = f"[bold magenta]▶ Blacky [YT:{self.active_yt_id}] ❯ [/bold magenta]"
                else:
                    prompt_label = "[bold green]✦ Blacky ❯ [/bold green]"

                user_input = console.input(prompt_label).strip()

                if not user_input:
                    continue

                # 1. Exit Commands
                if user_input.lower() in ["exit", "q", "/exit"]:
                    if self.active_yt_id or self.active_doc_id:
                        console.print(f"[yellow]Exited active RAG session. Back to General Chat.[/yellow]")
                        self.active_yt_id = None
                        self.active_doc_id = None
                        continue
                    else:
                        break

                # 2. Utility commands
                if user_input.lower() == "/clear":
                    console.clear()
                    self.display_banner()
                    continue

                if user_input.lower() == "/help":
                    self.print_help()
                    continue

                # 3. Explicit Document Command
                if user_input.startswith("/doc"):
                    payload = user_input[4:].strip()
                    self.handle_doc_route(payload)
                    continue

                # 4. Explicit YouTube Command
                if user_input.startswith("/yt"):
                    payload = user_input[3:].strip()
                    self.handle_youtube_route(payload)
                    continue

                if user_input.startswith("/stock"):
                    payload = user_input[6:].strip()
                    self.handle_stock_route(payload)
                    continue

                # 5. Explicit MCP Search Command
                if user_input.startswith("/search"):
                    payload = user_input[7:].strip()
                    await self.handle_search_route(payload)
                    continue

                # 6. Automatic Context Routing
                if self.active_doc_id:
                    console.print(f"[bold cyan][Document RAG][/bold cyan] Querying context...")
                    with thinking_status():
                        answer = self.doc_agent.process_doc_query(
                            file_or_input=self.active_doc_id,
                            user_question=user_input
                        )
                    console.print(Panel(Markdown(answer), title=f"[bold cyan]Document Response[/bold cyan]", border_style="cyan"))
                    continue

                if self.active_yt_id:
                    console.print(f"[bold magenta][YouTube RAG][/bold magenta] Querying transcript...")
                    with thinking_status():
                        answer = self.yt_agent.process_youtube_query(
                            url_or_input=self.active_yt_id,
                            user_question=user_input
                        )
                    console.print(Panel(Markdown(answer), title=f"[bold magenta]YouTube RAG Response[/bold magenta]", border_style="magenta"))
                    continue

                # 7. Standard General Chat
                with thinking_status():
                    response = await self.cli_agent.handle_user_query_async(user_input)

                console.print(Rule(style="dim"))
                console.print(Markdown(response))
                console.print(Rule(style="dim"))
                console.print()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exiting Blacky...[/yellow]")
                sys.exit(0)

        await self.close_mcp()

async def main():
    try:
        app = BlackyApp()
        await app.run()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())