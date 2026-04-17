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
# Giống codex_oauth_module/constants.py — OAuth app id công khai của Codex CLI
# ============================================================
CODEX_CLIENT_ID: str = os.getenv(
    "CODEX_CLIENT_ID",
    "app_EMoamEEZ73f0CkXaXp7hrann",
)
CODEX_TOKEN_URL: str = os.getenv(
    "CODEX_TOKEN_URL",
    "https://auth.openai.com/oauth/token",
)
CODEX_AUTH_FILE: str = str(
    Path(os.path.expanduser(os.getenv("CODEX_AUTH_FILE", "~/.codex/auth.json"))).expanduser()
)
CODEX_MODEL: str = os.getenv("CODEX_MODEL", "gpt-5.2-codex")
CODEX_REASONING_EFFORT: str = os.getenv("CODEX_REASONING_EFFORT", "medium")
EMBEDDING_PROFILE: str = os.getenv("EMBEDDING_PROFILE", "fast")

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
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
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

# ============================================================
# System Prompt cho Tóm Tắt Tài Liệu
# ============================================================
SUMMARY_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên tóm tắt tài liệu.

Nhiệm vụ:
1. Đọc kỹ nội dung tài liệu được cung cấp.
2. Tóm tắt ngắn gọn, rõ ràng bằng tiếng Việt.
3. Nêu các ý chính, thông tin quan trọng.
4. Giữ bố cục: Chủ đề chính → Các điểm nổi bật → Kết luận.
5. Tóm tắt không quá 500 từ.
6. Sử dụng bullet points để dễ đọc."""
