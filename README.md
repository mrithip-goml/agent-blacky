# Blacky AI

Blacky AI is a modular, high-performance terminal companion engineered for Linux systems. Powered by the Google Gemini API (`google-genai` SDK), Model Context Protocol (MCP), and ChromaDB vector search, Blacky AI integrates real-time web search, document Retrieval-Augmented Generation (RAG), YouTube transcript analysis, stock equity evaluation, and safe local CLI execution into a unified terminal interface.

---

## Key Features

### 1. Automatic Real-Time Web Search via MCP
- **Native Gemini Function Calling**: Automatically detects when user queries require current events, breaking news, weather, or real-time data beyond the model knowledge cutoff.
- **DuckDuckGo MCP Integration**: Connects over stdio to the `duckduckgo-mcp-server` tool definition schema.
- **Multi-Turn Roundtrip Execution**: Formulates precise, multi-keyword search queries, executes tool calls, logs execution parameters in the terminal, and synthesizes itemized factual answers.
- **Strict Fallback Rules**: States explicitly when search results lack sufficient details rather than outputting generic placeholders.

### 2. Document Retrieval-Augmented Generation (RAG)
- **Multi-Format Support**: Reads and parses PDF (`pypdf`), Word (`python-docx`), PowerPoint (`python-pptx`), EPUB (`ebooklib`), Markdown, plain text, and HTML (`beautifulsoup4`).
- **Persistent Vector Indexing**: Stores document embeddings persistently in ChromaDB using default vector embeddings.
- **Isolated RAG Context**: When a document session is active (`[DOC:<doc_id>]`), MCP web search tools are strictly disabled to ensure answers rely exclusively on retrieved document chunks.
- **Session Management**: Lists stored documents (`/doc list`) and switches active document context (`/doc switch <id>`).

### 3. YouTube Video Intelligence Agent
- **Transcript Extraction & Chunking**: Automatically fetches YouTube video transcripts (`youtube_transcript_api`) and chunks content with timestamp metadata.
- **Timestamped Semantic Search**: Stores transcript chunks in ChromaDB, enabling question-answering with timestamp citations.
- **Video Overview Summaries**: Generates structured executive summaries highlighting core takeaways.
- **Session Isolation**: Disables external MCP tools during active video sessions (`[YT:<video_id>]`) to guarantee answers derive strictly from the transcript context.

### 4. Equity & Market Financial Analyst
- **Fundamental Market Analysis**: Retrieves real-time stock quotes, valuation multiples (P/E, P/B, P/S), margins, revenue growth, and analyst recommendations via Yahoo Finance (`yfinance`).
- **Single Ticker Deep Dive**: Generates equity research reports with valuation verdicts, bullish catalysts, and risk factors (`/stock <ticker>`).
- **Comparative Analysis**: Compares multiple stock tickers side-by-side in structured Markdown comparison tables (`/stock compare <t1> <t2> ...`).

### 5. Safe System Execution Assistant
- **Automated Routing**: Determines when a user query requires local Linux system inspection (checking files, dotfiles, hardware specs, or process states).
- **Security Blacklisting**: Enforces strict pattern checks blocking destructive commands (`sudo`, `rm -rf /`, `chown`, disk format operations).
- **Output Summarization**: Executes safe commands in a subshell and synthesizes execution results cleanly for the user.

### 6. Persistent Conversation History
- **Automatic Memory**: Every user/assistant exchange is stored in memory and fed back to Gemini on subsequent turns, giving the AI conversational context within a session.
- **Disk Persistence**: History is saved to `history/chat_history.json` after every turn and automatically reloaded on startup, so conversations survive restarts.
- **Review & Reset**: View the full conversation log with `/history` (or `/hist`) and start fresh with `/new` (or `/reset`).

### 7. Optional Voice Interaction (F.R.I.D.A.Y. Mode)
- **Text-First, Voice-Optional**: Text I/O remains the primary mode; voice is strictly opt-in and never interferes when disabled.
- **Speech-to-Text (STT)**: Uses `faster-whisper` (base model, CPU, int8) with energy-threshold silence detection. Lazy-loaded only when voice input is first activated.
- **Text-to-Speech (TTS)**: Uses `edge-tts` (Irish `en-IE-EmilyNeural` voice, fallback `en-GB-SoniaNeural`) with offline `pyttsx3` fallback on network errors. Long responses are chunked to reduce latency.
- **Dual Toggles**: `/voice` / `/text` control microphone input; `/talk` / `/mute` control audio output. CLI flags `--voice` and `--speak` enable them at startup.
- **Graceful Exits**: Saying "exit voice", "stop voice", or "text mode" (or pressing Ctrl+C) reverts to standard text input without crashing.

---

## Architecture Overview

```text
blacky_ai/
├── config/
│   └── settings.py          Environment configuration, model definitions, and UI theme constants
├── ui/
│   └── console.py           Rich terminal formatting, banners, command tables, and panel renderers
├── mcp_agent/
│   ├── client.py            Stdio MCP client connection, session management, and schema mapping
│   └── tools.py             MCP tool execution handlers and response formatting
├── core/
│   ├── llm.py               GeminiEngine managing Gemini API calls, Function Calling roundtrips, and persistent chat history
│   ├── commands.py          CommandHandler managing slash routes and active RAG sessions
│   └── thinking.py          Status spinner and phrase rotation context manager
├── voice/
│   ├── stt.py               WhisperSTT speech-to-text engine (lazy-loaded, silence detection)
│   └── tts.py               edge-tts / pyttsx3 text-to-speech with markdown stripping and chunking
├── tools/
│   ├── cli_assistant.py     System execution router and general assistant wrapper
│   ├── doc_rag.py           Document RAG ingestion and ChromaDB vector agent
│   ├── youtube_summary.py   YouTube transcript fetching and semantic search agent
│   ├── stock_agent.py       Market analysis and comparative evaluation agent
│   └── mcp_client.py        Backward-compatibility re-export wrapper
├── prompts/
│   ├── general_chat.txt     Upgraded general chat instructions with query formulation directives
│   ├── search_agent.txt     Specialized search synthesis prompt instructions
│   ├── stock_analysis.txt   Equity research prompt template
│   ├── stock_compare.txt    Side-by-side stock comparison prompt template
│   ├── cli_router.txt       System execution routing classifier prompt
│   ├── cli_generator.txt    Safe bash command generator prompt
│   └── cli_summarizer.txt   Bash execution output summarizer prompt
├── vectorstore/             Persistent ChromaDB storage for document and YouTube vector indices
├── history/                 Persistent JSON conversation history (chat_history.json)
└── main.py                  Slim CLI entry point handling argument loop and async lifecycle
```

---

## Installation and Requirements

### System Prerequisites
- Operating System: Linux (Ubuntu, Debian, Fedora, Arch, etc.)
- Python Version: 3.10 or higher
- DuckDuckGo MCP Server: Executable `duckduckgo-mcp-server` installed in your Python environment.

### Setup Instructions

1. **Clone Repository & Navigate to Workspace**:
   ```bash
   cd blacky_ai
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the project root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```

---

## Usage Guide

Run the main application:
```bash
python main.py
```

### General Chat & Real-Time Search
Type any natural-language question directly into the prompt:
- `"what is list comprehension in python?"`
  - Answers directly without tool execution.
- `"what are today's top global news headlines?"`
  - Automatically formulates a search query, invokes DuckDuckGo MCP search, logs execution, and outputs itemized breaking headlines.

---

### Command Directory

| Command | Arguments | Description |
| :--- | :--- | :--- |
| **`/stock`** | `<ticker>` | Performs a fundamental equity analysis for a given stock symbol (e.g., `/stock NVDA`). |
| **`/stock compare`** | `<t1> <t2> ...` | Side-by-side metrics comparison table for multiple stocks (e.g., `/stock compare AAPL MSFT GOOGL`). |
| **`/yt`** | `<url_or_id>` | Fetches, chunks, indexes, and summarizes a YouTube video transcript. Switches active session to this video. |
| **`/yt list`** | None | Lists all YouTube videos stored in the local vector database. |
| **`/yt switch`** | `<number_or_id>` | Switches the active RAG session to a previously indexed YouTube video. |
| **`/doc`** | `<file_path>` | Ingests, parses, and indexes a local document (PDF, DOCX, PPTX, EPUB, MD, TXT, HTML). |
| **`/doc list`** | None | Lists all documents stored in the local vector database. |
| **`/doc switch`** | `<number_or_id>` | Switches the active RAG session to a previously indexed document. |
| **`/search`** | `<query>` | Manually triggers an explicit DuckDuckGo MCP web search query. |
| **`/history`** or **`/hist`** | None | Displays the persistent conversation history log. |
| **`/new`** or **`/reset`** | None | Clears the conversation history (memory + disk) and starts fresh. |
| **`/voice`** or **`/text`** | None | Toggles Speech-to-Text (microphone) input mode. |
| **`/talk`** or **`/mute`** | None | Toggles Text-to-Speech (audio output) mode. |
| **`/clear`** | None | Clears the terminal screen and re-displays the banner. |
| **`/help`** | None | Displays the command directory table. |
| **`/exit`** or **`q`** | None | Exits an active RAG session back to general chat mode, or exits the application if in general chat mode. |

---

## Technical Details and Safety

### RAG Session Isolation
When a YouTube (`[YT:<id>]`) or Document (`[DOC:<id>]`) session is active:
- User queries bypass general chat and trigger ChromaDB vector similarity search.
- Gemini is called with `tools=[]`, preventing unwanted MCP web search executions.
- Dynamic system instruction headers are injected into prompt requests enforcing strict reliance on retrieved transcript or document context.

### Security Framework
Commands generated for local system execution are parsed against a forbidden pattern regex list (`sudo`, `su`, `chown`, `rm -rf /`, `rm -rf ~`, raw disk writes). Unsafe commands are blocked prior to subshell invocation.

### Conversation History Storage
- **Location**: `history/chat_history.json` in the project root.
- **Format**: JSON array of `{"user": "...", "assistant": "..."}` pairs.
- **Persistence**: Saved automatically after every completed exchange and loaded on startup.
- **Privacy**: The `history/` directory is excluded from version control via `.gitignore`. Use `/new` to wipe it at any time.

### Voice Mode Quick Start
```bash
# Text-only (default)
python main.py

# Enable microphone input (STT) on startup
python main.py --voice

# Enable audio output (TTS) on startup
python main.py --speak

# Enable both
python main.py --voice --speak
```

---

## License

This project is open-source and available under the MIT License.
