import sys
from typing import Optional, Tuple
from ui.console import console, display_banner, print_help, render_panel
from core.thinking import thinking_status
from tools.youtube_summary import YouTubeAgent
from tools.doc_rag import DocumentAgent
from tools.stock_agent import StockAgent

class CommandHandler:
    """Manages slash command routes and active RAG session states."""

    def __init__(self, mcp_manager=None):
        self.mcp_manager = mcp_manager
        self.yt_agent = YouTubeAgent()
        self.doc_agent = DocumentAgent()
        self.stock_agent = StockAgent()

        self.active_yt_id: Optional[str] = None
        self.active_doc_id: Optional[str] = None

    def clear_active_sessions(self):
        """Clears active RAG sessions."""
        self.active_yt_id = None
        self.active_doc_id = None

    async def handle_search_route(self, query: str):
        """Explicit MCP search command handler."""
        if not query:
            console.print("[red]Usage:[red] /search <query>")
            return

        if not self.mcp_manager or not self.mcp_manager.is_connected:
            console.print("[bold red]MCP Search Server is not active.[/bold red]")
            return

        console.print(f"[bold blue][MCP Search][/bold blue] Executing DuckDuckGo web search for: [white]'{query}'[/white]...")
        with thinking_status():
            try:
                results = await self.mcp_manager.execute_tool("search", {"query": query, "max_results": 5})
            except Exception as e:
                results = f"[ERROR] Search failed: {str(e)}"

        render_panel(results, title=f"Search Results ({query})", border_style="blue")

    def handle_doc_route(self, payload: str):
        """Document RAG handler."""
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
                self.active_yt_id = None
                console.print(f"[bold green]{res}[/bold green]")
            else:
                console.print(f"[bold red]{res}[/bold red]")
            return

        # 3. Process document question or ingest file
        if self.active_doc_id and not payload.startswith("/") and not (payload.startswith("./") or payload.startswith("~/") or payload.startswith("C:")):
            console.print(f"[bold cyan][Document RAG][/bold cyan] Querying context for [{self.active_doc_id}]...")
            with thinking_status():
                answer = self.doc_agent.process_doc_query(
                    file_or_input=self.active_doc_id,
                    user_question=payload
                )
            render_panel(answer, title=f"Document Response ({self.active_doc_id})", border_style="cyan")
        else:
            console.print(f"[bold cyan][RAG Ingestion][/bold cyan] Reading and embedding document...")
            with thinking_status():
                summary = self.doc_agent.process_doc_query(file_or_input=payload)

            if not summary.startswith("[ERROR]"):
                self.active_doc_id = self.doc_agent.current_doc_id
                self.active_yt_id = None
                render_panel(summary, title=f"Document Overview ({self.active_doc_id})", border_style="cyan")
                console.print("[dim]Document Mode active. Ask any question about this document or type '/exit'.[/dim]\n")
            else:
                console.print(f"[bold red]{summary}[/bold red]")

    def handle_youtube_route(self, payload: str):
        """YouTube transcript RAG handler."""
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
                self.active_doc_id = None
                console.print(f"[bold green]{res}[/bold green]")
            else:
                console.print(f"[bold red]{res}[/bold red]")
            return

        # 3. Process video question or load URL
        if self.active_yt_id and not payload.startswith("http") and len(payload) != 11:
            console.print(f"[bold magenta][YouTube RAG][/bold magenta] Querying context for [{self.active_yt_id}]...")
            with thinking_status():
                answer = self.yt_agent.process_youtube_query(
                    url_or_input=self.active_yt_id,
                    user_question=payload
                )
            render_panel(answer, title=f"YouTube Response ({self.active_yt_id})", border_style="magenta")
        else:
            console.print(f"[bold magenta][Transcript Ingestion][/bold magenta] Fetching and embedding video...")
            with thinking_status():
                summary = self.yt_agent.process_youtube_query(url_or_input=payload)

            if not summary.startswith("[ERROR]"):
                self.active_yt_id = self.yt_agent.current_video_id
                self.active_doc_id = None
                render_panel(summary, title=f"Video Overview ({self.active_yt_id})", border_style="magenta")
                console.print("[dim]YouTube Mode active. Ask any question about this video or type '/exit'.[/dim]\n")
            else:
                console.print(f"[bold red]{summary}[/bold red]")

    def handle_stock_route(self, payload: str):
        """Stock equity analysis handler."""
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

            render_panel(analysis, title=f"Stock Comparison ({', '.join(tickers)})", border_style="green")
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

        render_panel(analysis, title=f"Equity Analysis ({ticker})", border_style="green")
