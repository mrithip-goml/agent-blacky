import config.settings
import sys
import re
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from core.thinking import thinking_status
from tools.cli_assistant import CLIAssistant
from tools.youtube_summary import YouTubeAgent

console = Console()

class BlackyApp:
    def __init__(self):
        self.cli_agent = CLIAssistant()
        self.yt_agent = YouTubeAgent()
        # Auto-connect to the last indexed YouTube video if present in ChromaDB
        self.active_yt_id = None
        self.active_doc = None

    def display_banner(self):
        banner = "[bold magenta]BLACKY AI[/bold magenta] - [dim]Niri Terminal Companion[/dim]\n" \
                 "[cyan]/yt[/cyan] YouTube Agent  |  [cyan]/doc[/cyan] Document RAG  |  [cyan]/help[/cyan] Commands"
        console.print(Panel(banner, border_style="magenta", expand=False))

    def print_help(self):
        help_text = """
            ### Blacky AI Command Directory
            * **`/yt <link>`** : Load, index, and summarize a YouTube video.
            * **`/yt list`** or **`/yt ls`** : List all YouTube videos saved in ChromaDB.
            * **`/yt switch <number/id>`** : Switch active video session.
            * **`<any prompt>` (while in YT Mode)** : Directly query active video RAG context.
            * **`/exit` or `q`** : Exit YouTube Mode back to General Chat.
            * **`/clear`** : Clear terminal screen.
            * **`<any prompt>` (in General Mode)** : Standard General Gemini Chat.
        """
        console.print(Panel(Markdown(help_text.strip()), title="[bold cyan]Help & Syntax[/bold cyan]", border_style="cyan"))

    def handle_youtube_route(self, payload: str):
        if not payload:
            if self.active_yt_id:
                console.print(f"[yellow]Active YouTube Session:[yellow] {self.active_yt_id}. Ask any question or use '/exit'.")
            else:
                console.print("[red]Usage:[red] /yt <URL> | /yt list | /yt switch <number_or_id>")
            return

        # 1. COMMAND: /yt list
        if payload.lower() in ["list", "ls"]:
            videos = self.yt_agent.list_indexed_videos()
            if not videos:
                console.print("[yellow]No YouTube videos found in local ChromaDB.[/yellow]")
                return

            console.print("\n[bold magenta]=== Stored YouTube Videos in Vector DB ===[/bold magenta]")
            for idx, vid in enumerate(videos, 1):
                active_flag = " [bold green](Active)[/bold green]" if vid['video_id'] == self.active_yt_id else ""
                console.print(f"{idx}. [bold cyan]{vid['title']}[/bold cyan] [dim](ID: {vid['video_id']})[/dim]{active_flag}")
            console.print("\n[dim]Switch active video using: /yt switch <number>[/dim]\n")
            return

        # 2. COMMAND: /yt switch <index_or_video_id>
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
                console.print(f"[bold green]{res}[/bold green]")
            else:
                console.print(f"[bold red]{res}[/bold red]")
            return

        # 3. Process new YouTube URL or query active video
        extracted_id = self.yt_agent.extract_video_id(payload)

        if extracted_id:
            console.print(f"[bold cyan][RAG][/bold cyan] Loading YouTube Video [[bold yellow]{extracted_id}[/bold yellow]]...")
            with thinking_status():
                summary = self.yt_agent.process_youtube_query(url_or_input=payload)

            if not summary.startswith("[ERROR]"):
                self.active_yt_id = extracted_id
                console.print(Panel(Markdown(summary), title=f"[bold magenta]YouTube Summary ({extracted_id})[/bold magenta]", border_style="magenta"))
                console.print("[dim]YouTube Mode active. Ask any question about this video or type '/exit'.[/dim]\n")
            else:
                console.print(f"[bold red]{summary}[/bold red]")
        
        elif self.active_yt_id:
            # Query active video directly
            console.print(f"[bold cyan][RAG Search][/bold cyan] Querying transcript for [{self.active_yt_id}]...")
            with thinking_status():
                answer = self.yt_agent.process_youtube_query(
                    url_or_input=self.active_yt_id,
                    user_question=payload
                )
            console.print(Panel(Markdown(answer), title=f"[bold magenta]YouTube RAG Response[/bold magenta]", border_style="magenta"))
        else:
            console.print("[bold red]No active YouTube session.[/bold red] Load a video using: [cyan]/yt <URL>[/cyan]")

    def run(self):
        self.display_banner()
        console.print("[dim]Type '/help' for commands, or 'exit' / 'q' to quit.[/dim]\n")

        while True:
            try:
                # Dynamic terminal prompt indicator
                if self.active_yt_id:
                    prompt_label = f"[bold magenta]Blacky [YT:{self.active_yt_id}] > [/bold magenta]"
                elif self.active_doc:
                    prompt_label = f"[bold cyan]Blacky [DOC:{self.active_doc}] > [/bold cyan]"
                else:
                    prompt_label = "[bold green]Blacky > [/bold green]"

                user_input = console.input(prompt_label).strip()

                if not user_input:
                    continue

                # 1. Exit Commands
                if user_input.lower() in ["exit", "q", "/exit"]:
                    if self.active_yt_id or self.active_doc:
                        console.print(f"[yellow]Exited active RAG session. Back to General Chat.[/yellow]")
                        self.active_yt_id = None
                        self.active_doc = None
                        self.yt_agent.current_collection = None
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

                # 3. Explicit /yt commands (/yt list, /yt switch, /yt <URL>)
                if user_input.startswith("/yt"):
                    payload = user_input[3:].strip()
                    self.handle_youtube_route(payload)
                    continue

                # 4. Auto-detect bare YouTube URL pasted into terminal
                extracted_id = self.yt_agent.extract_video_id(user_input)
                if extracted_id:
                    self.handle_youtube_route(user_input)
                    continue

                # 5. AUTOMATIC ROUTING: If in YT mode, send ALL regular questions to YouTube RAG
                if self.active_yt_id:
                    console.print(f"[bold cyan][RAG Search][/bold cyan] Querying video transcript...")
                    with thinking_status():
                        answer = self.yt_agent.process_youtube_query(
                            url_or_input=self.active_yt_id,
                            user_question=user_input
                        )
                    console.print(Panel(Markdown(answer), title=f"[bold magenta]YouTube RAG Response[/bold magenta]", border_style="magenta"))
                    continue

                # 6. Standard General Chat (when not in YT or DOC mode)
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