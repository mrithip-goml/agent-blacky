import config.settings
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from core.thinking import thinking_status
from tools.cli_assistant import CLIAssistant
from tools.youtube_summary import YouTubeAgent
from tools.doc_rag import DocumentAgent

console = Console()

class BlackyApp:
    def __init__(self):
        self.cli_agent = CLIAssistant()
        self.yt_agent = YouTubeAgent()
        self.doc_agent = DocumentAgent()

        # Restore active RAG states if present in ChromaDB
        self.active_yt_id = None
        self.active_doc_id = None

    def display_banner(self):
        banner = "[bold magenta]BLACKY AI[/bold magenta] - [dim]Niri Terminal Companion[/dim]\n" \
                 "[cyan]/yt[/cyan] YouTube Agent  |  [cyan]/doc[/cyan] Document RAG  |  [cyan]/help[/cyan] Commands"
        console.print(Panel(banner, border_style="magenta", expand=False))

    def print_help(self):
        help_text = """
            ### Blacky AI Command Directory
            * **`/yt <link>`** : Load, index, and summarize a YouTube video.
            * **`/yt list`** : List stored YouTube videos.
            * **`/yt switch <number/id>`** : Switch active YouTube session.
            * **`/doc <path>`** : Load & index PDF, DOCX, PPTX, EPUB, MD, TXT, HTML.
            * **`/doc list`** : List all stored local documents in vector store.
            * **`/doc switch <number/id>`** : Switch active document session.
            * **`/exit` or `q`** : Exit active mode back to General Chat.
            * **`/clear`** : Clear terminal screen.
        """
        console.print(Panel(Markdown(help_text.strip()), title="[bold cyan]Help & Syntax[/bold cyan]", border_style="cyan"))

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

    def run(self):
        self.display_banner()
        console.print("[dim]Type '/help' for commands, or 'exit' / 'q' to quit.[/dim]\n")

        while True:
            try:
                # Prompt Indicator
                if self.active_doc_id:
                    prompt_label = f"[bold cyan]Blacky [DOC:{self.active_doc_id}] > [/bold cyan]"
                elif self.active_yt_id:
                    prompt_label = f"[bold magenta]Blacky [YT:{self.active_yt_id}] > [/bold magenta]"
                else:
                    prompt_label = "[bold green]Blacky > [/bold green]"

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

                # 5. Automatic Context Routing
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

                # 6. Standard General Chat
                with thinking_status():
                    response = self.cli_agent.handle_user_query(user_input)

                console.print(Rule(style="magenta"))
                console.print(Markdown(response))
                console.print(Rule(style="magenta"))
                console.print()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exiting Blacky...[/yellow]")
                sys.exit(0)

def main():
    try:
        app = BlackyApp()
        app.run()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()