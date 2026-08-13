import asyncio
import os
import re
import tempfile
import edge_tts
import pygame
from ui.console import console
from config.settings import TTS_VOICE_PRIMARY, TTS_VOICE_FALLBACK, TTS_CHUNK_SIZE

def strip_markdown(text: str) -> str:
    """Strips markdown formatting for cleaner TTS synthesis."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Remove bold/italic
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # Remove headers
    text = re.sub(r'#+\s+', '', text)
    # Remove links
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered lists
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Remove emojis or special characters if needed, but edge-tts handles them mostly
    
    return text.strip()

def chunk_text(text: str, max_size: int = 250) -> list[str]:
    """Chunks text into smaller pieces by sentence, ensuring each chunk is under max_size."""
    if len(text) <= max_size:
        return [text]
    
    # Split by sentence boundaries but keep the delimiters
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_size:
            current_chunk = (current_chunk + " " + sentence).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            # If a single sentence is longer than max_size, split by comma or space
            if len(sentence) > max_size:
                parts = re.split(r'(?<=,) +', sentence)
                for part in parts:
                    if len(current_chunk) + len(part) + 1 <= max_size:
                        current_chunk = (current_chunk + " " + part).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part[:max_size] # Hard cut if still too long
            else:
                current_chunk = sentence
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

async def speak_with_edge_tts(text: str, voice: str, tmp_path: str) -> bool:
    """Attempts to synthesize speech using edge-tts."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)
        return True
    except Exception as e:
        # Catching SSL/Connection errors specifically if possible
        console.print(f"[dim]edge-tts failed: {e}[/dim]")
        return False

def speak_with_pyttsx3(text: str):
    """Fallback offline TTS using pyttsx3."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except ImportError:
        console.print("[dim]pyttsx3 not installed, cannot use offline fallback.[/dim]")
    except Exception as e:
        console.print(f"[dim]pyttsx3 failed: {e}[/dim]")
    return False

async def speak_response(text: str):
    """Synthesizes text to speech and plays it back, with chunking and fallbacks."""
    clean_text = strip_markdown(text)
    if not clean_text:
        return

    chunks = chunk_text(clean_text, TTS_CHUNK_SIZE)
    
    for chunk in chunks:
        # Use a temporary file for the audio
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        success = False
        # Try primary voice
        if await speak_with_edge_tts(chunk, TTS_VOICE_PRIMARY, tmp_path):
            success = True
        # Try fallback voice
        elif await speak_with_edge_tts(chunk, TTS_VOICE_FALLBACK, tmp_path):
            success = True
        
        if success:
            try:
                # Play using pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                
                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                    
                pygame.mixer.music.unload()
            except Exception as e:
                console.print(f"[bold red]Audio playback error:[/bold red] {e}")
                # If playback failed, maybe try pyttsx3 as a last resort
                speak_with_pyttsx3(chunk)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
        else:
            # edge-tts failed completely (likely connection error), use pyttsx3
            speak_with_pyttsx3(chunk)

    if pygame.mixer.get_init():
        pygame.mixer.quit()
