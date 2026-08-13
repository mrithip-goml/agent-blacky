import numpy as np
import sounddevice as sd
import tempfile
import wave
import os
from ui.console import console
from config.settings import (
    STT_MODEL, STT_DEVICE, STT_COMPUTE_TYPE,
    STT_SAMPLE_RATE, STT_SILENCE_THRESHOLD,
    STT_SILENCE_DURATION, STT_MAX_RECORD_SECONDS
)


class WhisperSTT:
    """Speech-to-Text engine using faster-whisper with lazy model loading."""

    def __init__(self):
        self._model = None

    def _load_model(self):
        """Lazily loads the Whisper model on first use to avoid startup overhead."""
        if self._model is not None:
            return

        console.print(f"[dim]Loading Whisper STT model ({STT_MODEL}, {STT_COMPUTE_TYPE})...[/dim]")
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                STT_MODEL,
                device=STT_DEVICE,
                compute_type=STT_COMPUTE_TYPE
            )
            console.print("[bold green]Whisper STT model loaded.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Failed to load Whisper model:[/bold red] {e}")
            raise

    def listen_and_transcribe(self) -> str:
        """Records audio from microphone with silence detection and transcribes via Whisper.

        Returns the transcribed text string, or empty string on failure.
        """
        try:
            self._load_model()
        except KeyboardInterrupt:
            return "exit voice"

        sample_rate = STT_SAMPLE_RATE
        silence_threshold = STT_SILENCE_THRESHOLD
        silence_duration = STT_SILENCE_DURATION
        max_seconds = STT_MAX_RECORD_SECONDS
        chunk_duration = 0.1  # 100ms chunks for silence detection

        chunk_samples = int(sample_rate * chunk_duration)
        max_chunks = int(max_seconds / chunk_duration)
        silence_chunks_needed = int(silence_duration / chunk_duration)

        console.print("[bold cyan][Voice Input][/bold cyan] Listening... (speak now, silence to stop)")

        recorded_chunks = []
        silence_counter = 0
        speech_detected = False

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                                blocksize=chunk_samples) as stream:
                for _ in range(max_chunks):
                    audio_chunk, _ = stream.read(chunk_samples)
                    recorded_chunks.append(audio_chunk.copy())

                    energy = np.sqrt(np.mean(audio_chunk ** 2))

                    if energy > silence_threshold:
                        speech_detected = True
                        silence_counter = 0
                    else:
                        if speech_detected:
                            silence_counter += 1

                    if speech_detected and silence_counter >= silence_chunks_needed:
                        break

        except KeyboardInterrupt:
            console.print("\n[yellow]Listening cancelled.[/yellow]")
            return "exit voice"
        except sd.PortAudioError as e:
            console.print(f"[bold red]Microphone error:[/bold red] {e}")
            console.print("[yellow]Falling back to text input.[/yellow]")
            return ""
        except Exception as e:
            console.print(f"[bold red]Audio capture error:[/bold red] {e}")
            return ""

        if not recorded_chunks or not speech_detected:
            console.print("[dim]No speech detected.[/dim]")
            return ""

        audio_data = np.concatenate(recorded_chunks, axis=0)
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Write to temporary WAV file for Whisper
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                with wave.open(tmp_file, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())

            segments, info = self._model.transcribe(tmp_path, beam_size=5)
            transcription = " ".join(segment.text.strip() for segment in segments).strip()

            if transcription:
                console.print(f"[bold cyan][Transcribed][/bold cyan] {transcription}")

            return transcription

        except Exception as e:
            console.print(f"[bold red]Transcription error:[/bold red] {e}")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
