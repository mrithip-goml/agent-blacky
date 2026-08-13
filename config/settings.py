import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically find and load the .env file in the project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

if not GEMINI_API_KEY:
    print("[WARN] GEMINI_API_KEY not found in .env file!")

# UI & Terminal Aesthetics Theme
THEME_PRIMARY = "magenta"
THEME_SECONDARY = "cyan"
THEME_SUCCESS = "green"
THEME_WARNING = "yellow"
THEME_ERROR = "red"
THEME_MUTED = "dim"

# Voice Pipeline Configuration
VOICE_ENABLED_DEFAULT = False
TTS_ENABLED_DEFAULT = False
TTS_VOICE_PRIMARY = "en-IE-EmilyNeural"
TTS_VOICE_FALLBACK = "en-GB-SoniaNeural"
TTS_CHUNK_SIZE = 250
STT_MODEL = "base"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"
STT_SAMPLE_RATE = 16000
STT_SILENCE_THRESHOLD = 0.01
STT_SILENCE_DURATION = 1.5
STT_MAX_RECORD_SECONDS = 10
