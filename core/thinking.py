import random
import threading
from contextlib import contextmanager
from rich.console import Console

console = Console()

THINKING_PHRASES = [
    "Fanthoming system state...",
    "Synthesizing bash logic...",
    "Scanning local environment...",
    "Evaluating subshell output...",
    "Consulting Gemini neural weights...",
    "Optimizing CLI execution pipeline...",
    "Checking system permissions...",
    "Parsing local bash context..."
]

@contextmanager
def thinking_status(spinner_style="magenta"):
    """
    Spawns a background thread that rotates through status messages
    every 1 second while heavy tasks (like Gemini API calls) execute.
    """
    stop_event = threading.Event()

    def update_phrase_loop(status_ctx):
        phrases = THINKING_PHRASES.copy()
        random.shuffle(phrases)
        index = 0
        
        while not stop_event.is_set():
            phrase = phrases[index % len(phrases)]
            status_ctx.update(f"[{spinner_style}]{phrase}[/{spinner_style}]")
            index += 1
            # Wait for 1 second, but exit immediately if stop_event is set
            stop_event.wait(3.0)

    # Start Rich console status
    with console.status(THINKING_PHRASES[0], spinner="dots") as status:
        # Start background thread to shift phrases
        t = threading.Thread(target=update_phrase_loop, args=(status,), daemon=True)
        t.start()
        try:
            yield status
        finally:
            stop_event.set()
            t.join(timeout=0.5)