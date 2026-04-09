"""
Core Configuration - RAG Project
Đọc cấu hình từ file .env
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ============================================================
# Đường dẫn để import codex_oauth_module từ thư mục cha
# ============================================================
# Thư mục cha của rag_project chính là codex_oauth_module
MODULE_ROOT = Path(__file__).parent.parent.parent  # → codex_oauth_module/
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

# ============================================================
# Cấu hình Codex OAuth (LLM)
# ============================================================
CODEX_AUTH_FILE: str = os.getenv("CODEX_AUTH_FILE", "~/.codex/auth.json")
CODEX_MODEL: str = os.getenv("CODEX_MODEL", "gpt-5.2-codex")
CODEX_REASONING_EFFORT: str = os.getenv("CODEX_REASONING_EFFORT", "medium")

# ============================================================
# Cấu hình lưu trữ file
# ============================================================
BASE_DIR = Path(__file__).parent.parent  # → backend/
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_db")))
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'rag.db'}")

# Tạo thư mục nếu chưa có
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Cấu hình RAG / Chunking
# ============================================================
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "5"))

# ============================================================
# System Prompt cho RAG (tiếng Việt)
# ============================================================
RAG_SYSTEM_PROMPT = """Bạn là trợ lý AI thông minh, được hỗ trợ bởi hệ thống RAG (Retrieval-Augmented Generation).

Nhiệm vụ của bạn:
1. Trả lời câu hỏi DỰA TRÊN TÀI LIỆU được cung cấp trong phần "NGỮ CẢNH".
2. Nếu thông tin KHÔNG CÓ trong tài liệu, hãy nói rõ: "Thông tin này không có trong tài liệu đã tải lên."
3. Trích dẫn rõ nguồn tài liệu khi trả lời.
4. Trả lời rõ ràng, súc tích và chính xác bằng tiếng Việt.
5. KHÔNG bịa đặt thông tin ngoài tài liệu."""
