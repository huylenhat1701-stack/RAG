"""
Core Configuration - RAG Project (Full-Context Edition)
Chạy hoàn toàn offline — Full-Context Mode, không giới hạn token.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ============================================================
# Đường dẫn gốc
# ============================================================
MODULE_ROOT = Path(__file__).parent.parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

# ============================================================
# Cấu hình Local LLM (LM Studio / Ollama)
# API tương thích OpenAI — LM Studio cổng 1234, Ollama cổng 11434/v1
# ============================================================
LOCAL_LLM_API_BASE: str = os.getenv("LOCAL_LLM_API_BASE", "http://localhost:1234/v1")
LOCAL_LLM_API_KEY: str = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")
LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "local-model")

# ============================================================
# FULL-CONTEXT MODE — Không giới hạn token
# Đọc toàn bộ tài liệu, trả lời chính xác nhất có thể.
# Giá trị rất lớn để không cắt xén nội dung tài liệu.   
# Model LM Studio sẽ tự xử lý giới hạn context window của nó.
# ============================================================
# Số ký tự tối đa đưa vào prompt (500,000 ≈ toàn bộ sách 400 trang)
LLM_MAX_CONTENT_CHARS: int = int(os.getenv("LLM_MAX_CONTENT_CHARS", "500000"))

# Token output tối đa — để lớn để AI trả lời đầy đủ, chi tiết
LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))

# Ngưỡng tự động chọn Full-Context vs RAG (ký tự)
# Tài liệu nhỏ hơn ngưỡng này → đưa toàn bộ vào context (chính xác 100%)
# Tài liệu lớn hơn → dùng RAG với max chunks (vẫn rất tốt)
FULL_CONTEXT_THRESHOLD_CHARS: int = int(os.getenv("FULL_CONTEXT_THRESHOLD_CHARS", "400000"))

# ============================================================
# Cấu hình ChromaDB & Embedding (chạy offline hoàn toàn)
# ============================================================
EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-small")
NLI_MODEL_NAME: str = os.getenv("NLI_MODEL_NAME", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")

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
# Chunk lớn hơn = ngữ cảnh phong phú hơn, ít mất thông tin hơn
# ============================================================
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "600"))       # 600 từ ≈ 1 trang A4
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "80"))  # Overlap lớn hơn = ít mất đoạn chuyển tiếp
TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "15"))  # Lấy nhiều chunks hơn khi dùng RAG mode

# ============================================================
# Relevance Thresholds cho RAG Q&A
# Score = 1.0 / (1.0 + L2_distance), dao động 0–1 (cao = liên quan hơn)
# Cần đo thực nghiệm để hiệu chỉnh chính xác, giá trị dưới là tạm thời.
# ============================================================
# Lọc chunks có score thấp hơn ngưỡng này trước khi đưa vào context LLM
RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))

# Nếu max score của mọi chunk thấp hơn ngưỡng này → không có thông tin liên quan
# → trả fallback thay vì gọi LLM generate (tiết kiệm thời gian + tránh hallucination)
NO_CONTEXT_THRESHOLD: float = float(os.getenv("NO_CONTEXT_THRESHOLD", "0.4"))

# ============================================================
# System Prompt cho RAG — Yêu cầu AI đọc kỹ, trả lời đầy đủ
# ============================================================
RAG_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên đọc và phân tích tài liệu. 
Hãy đọc TOÀN BỘ nội dung tài liệu được cung cấp một cách kỹ lưỡng và trả lời câu hỏi một cách ĐẦY ĐỦ, CHI TIẾT và CHÍNH XÁC bằng tiếng Việt.
Trả lời dựa HOÀN TOÀN vào nội dung tài liệu. Nếu thông tin không có trong tài liệu, hãy nói rõ điều đó.
Không bịa đặt hay suy đoán ngoài phạm vi tài liệu."""

# ============================================================
# System Prompt cho Tóm Tắt — Toàn diện hơn
# ============================================================
SUMMARY_SYSTEM_PROMPT = """Tóm tắt tài liệu sau bằng tiếng Việt một cách đầy đủ và toàn diện.
Nêu tất cả ý chính, các điểm quan trọng, và kết luận. Dùng bullet points rõ ràng."""
