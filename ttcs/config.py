import os

from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r")

# Embedding
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# Storage
DATABASE_PATH = os.getenv("DATABASE_PATH", "storage/rag_database.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "storage/chroma_db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "storage/uploads")

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "5"))


def validate_config() -> None:
    provider = LLM_PROVIDER.lower()
    if provider == "openai" and not OPENAI_API_KEY:
        raise ValueError("Thiếu OPENAI_API_KEY cho provider openai.")
    if provider == "gemini" and not GEMINI_API_KEY:
        raise ValueError("Thiếu GEMINI_API_KEY cho provider gemini.")
    if provider == "cohere" and not COHERE_API_KEY:
        raise ValueError("Thiếu COHERE_API_KEY cho provider cohere.")
    if provider not in {"openai", "gemini", "cohere"}:
        raise ValueError(f"LLM_PROVIDER không hợp lệ: {LLM_PROVIDER}")

    emb = EMBEDDING_PROVIDER.lower()
    if emb == "openai" and not OPENAI_API_KEY:
        raise ValueError("Thiếu OPENAI_API_KEY cho EMBEDDING_PROVIDER=openai.")
    if emb == "cohere" and not COHERE_API_KEY:
        raise ValueError("Thiếu COHERE_API_KEY cho EMBEDDING_PROVIDER=cohere.")
    if emb == "gemini" and not GEMINI_API_KEY:
        raise ValueError("Thiếu GEMINI_API_KEY cho EMBEDDING_PROVIDER=gemini.")
    if emb not in {"openai", "cohere", "gemini"}:
        raise ValueError(f"EMBEDDING_PROVIDER không hợp lệ: {EMBEDDING_PROVIDER}")
