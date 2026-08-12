import re
import math
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import chromadb
from chromadb.utils import embedding_functions
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError
from config.settings import GEMINI_API_KEY

def load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"Prompt file missing: {prompt_path}")

class YouTubeAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Check your .env file.")

        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-3.1-flash-lite"
        
        self.summary_prompt = load_prompt("yt_summary.txt")
        self.qa_prompt = load_prompt("yt_qa.txt")

        # Initialize ChromaDB client (VectorStore)
        db_path = str(Path(__file__).parent.parent / "vectorstore" / "youtube_db")
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Default lightweight embedding function
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        self.current_video_id = None
        self.current_collection = None

    def extract_video_id(self, url_or_id: str) -> str | None:
        """Extracts YouTube 11-character video ID from various URL formats."""
        patterns = [
            r"(?:v=|\/|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$"
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return None

    def _format_timestamp(self, seconds: float) -> str:
        """Converts seconds into MM:SS or HH:MM:SS format."""
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def fetch_and_index_transcript(self, video_id: str) -> str:
        """Fetches transcript, chunks text with timestamps, and embeds into ChromaDB."""
        collection_name = f"yt_{video_id}"
        
        # Check if already indexed
        try:
            self.current_collection = self.chroma_client.get_collection(
                name=collection_name, 
                embedding_function=self.embedding_fn
            )
            self.current_video_id = video_id
            return "ALREADY_INDEXED"
        except Exception:
            pass  # Collection doesn't exist yet, build it

        try:
            # YouTubeTranscriptApi is used directly via static method get_transcript or list_transcripts
            fetched = YouTubeTranscriptApi.get_transcript(video_id)
        except (TranscriptsDisabled, NoTranscriptFound):
            return "[ERROR] Transcripts are disabled or unavailable for this video."
        except Exception as e:
            # Fallback to fetch() if get_transcript is deprecated in your version
            try:
                fetched = YouTubeTranscriptApi().fetch(video_id)
            except Exception:
                return f"[ERROR] Failed to fetch transcript: {str(e)}"

        # Chunk transcript into ~250 word windows with timestamp tracking
        documents = []
        metadatas = []
        ids = []

        chunk_text = ""
        start_time = 0.0
        word_count = 0
        chunk_idx = 0

        for item in fetched:
            # Handle both object attributes (.start, .text) and dictionary keys (['start'], ['text'])
            item_start = getattr(item, 'start', None) if not isinstance(item, dict) else item.get('start')
            item_text = getattr(item, 'text', None) if not isinstance(item, dict) else item.get('text')

            if item_text is None:
                continue

            if not chunk_text:
                start_time = item_start or 0.0
            
            chunk_text += item_text + " "
            word_count += len(item_text.split())

            if word_count >= 250:
                time_str = self._format_timestamp(start_time)
                documents.append(f"[{time_str}] {chunk_text.strip()}")
                metadatas.append({"timestamp": time_str, "video_id": video_id})
                ids.append(f"chunk_{chunk_idx}")
                
                chunk_idx += 1
                chunk_text = ""
                word_count = 0

        # Residual chunk
        if chunk_text.strip():
            time_str = self._format_timestamp(start_time)
            documents.append(f"[{time_str}] {chunk_text.strip()}")
            metadatas.append({"timestamp": time_str, "video_id": video_id})
            ids.append(f"chunk_{chunk_idx}")

        if not documents:
            return "[ERROR] Empty transcript content."

        # Create collection and add vector embeddings
        self.current_collection = self.chroma_client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn
        )
        self.current_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        self.current_video_id = video_id
        return "INDEX_SUCCESS"

    def query_rag(self, query: str, top_k: int = 4) -> str:
        """Retrieves top_k relevant transcript chunks from ChromaDB for the user query."""
        if not self.current_collection:
            return "[ERROR] No active video collection loaded."

        results = self.current_collection.query(
            query_texts=[query],
            n_results=top_k
        )
        retrieved_chunks = results["documents"][0]
        context = "\n\n".join(retrieved_chunks)
        return context

    def process_youtube_query(self, url_or_input: str, user_question: str = None) -> str:
        video_id = self.extract_video_id(url_or_input)
        
        if video_id:
            status = self.fetch_and_index_transcript(video_id)
            if status.startswith("[ERROR]"):
                return status

            # If no specific question provided, deliver a complete video summary using RAG sampling
            if not user_question:
                context = self.query_rag(query="main topic executive summary key takeaways takeaways conclusion", top_k=6)
                contents = f"Context Chunks:\n{context}"
                prompt = self.summary_prompt
            else:
                context = self.query_rag(query=user_question, top_k=4)
                contents = f"Question: {user_question}\n\nRetrieved Context Chunks:\n{context}"
                prompt = self.qa_prompt
        elif self.current_collection and user_question:
            # Multi-turn Q&A on the previously loaded video
            context = self.query_rag(query=user_question, top_k=4)
            contents = f"Question: {user_question}\n\nRetrieved Context Chunks:\n{context}"
            prompt = self.qa_prompt
        else:
            return "Please provide a valid YouTube URL."

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=prompt,
                    temperature=0.1
                )
            )
            return response.text
        except ClientError as e:
            if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                return "[ERROR] Gemini API Quota Exceeded (429 Rate Limit)."
            return f"[ERROR] API Client Error: {str(e)}"
        except Exception as e:
            return f"[ERROR] Generation failed: {str(e)}"

    def list_indexed_videos(self) -> list[dict]:
        """Lists all YouTube video collections currently stored in ChromaDB."""
        collections = self.chroma_client.list_collections()
        video_list = []
        for col in collections:
            if col.name.startswith("yt_"):
                video_id = col.name.replace("yt_", "")
                video_list.append({
                    "video_id": video_id,
                    "collection_name": col.name,
                    "chunk_count": col.count()
                })
        return video_list

    def switch_active_video(self, url_or_id: str) -> str:
        """Switches session to an existing indexed video in ChromaDB."""
        video_id = self.extract_video_id(url_or_id) or url_or_id
        collection_name = f"yt_{video_id}"

        # Verify collection exists in ChromaDB
        existing_cols = [c.name for c in self.chroma_client.list_collections()]
        if collection_name in existing_cols:
            self.current_collection = self.chroma_client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_fn
            )
            self.current_video_id = video_id
            return f"[SUCCESS] Switched active session to YouTube Video [{video_id}]."
        else:
            return f"[ERROR] Video [{video_id}] is not indexed yet. Load it using: /yt <URL>"

    def auto_load_latest(self) -> str | None:
        """Automatically loads the most recent indexed video on CLI startup."""
        indexed = self.list_indexed_videos()
        if indexed:
            latest_id = indexed[-1]["video_id"]
            self.switch_active_video(latest_id)
            return latest_id
        return None