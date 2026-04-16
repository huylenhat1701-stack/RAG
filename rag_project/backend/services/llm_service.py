"""
LLM Service - Wrapper cho CodexOAuth và LocalRAG
Import trực tiếp từ codex_oauth_module (không viết lại).
"""

import sys
from pathlib import Path
from typing import Optional, List

# Thêm đường dẫn của TH MỤC CHA của codex_oauth_module vào sys.path
# Để có thể import: "import codex_oauth_module"
_CODEX_MODULE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # → codex_oauth_module/
_CODEX_PARENT_DIR = _CODEX_MODULE_DIR.parent  # → thư mục chứa codex_oauth_module/

_FALLBACK_DIR = Path(r"C:\Users\HACOM\Documents\openai\codex_oauth_module")
_FALLBACK_PARENT = _FALLBACK_DIR.parent

if not (_CODEX_MODULE_DIR / "client.py").exists() and (_FALLBACK_DIR / "client.py").exists():
    _CODEX_MODULE_DIR = _FALLBACK_DIR
    _CODEX_PARENT_DIR = _FALLBACK_PARENT

for _p in [str(_CODEX_MODULE_DIR), str(_CODEX_PARENT_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Import từ codex_oauth_module như một package
try:
    import codex_oauth_module as _codex_pkg  # noqa # type: ignore
    from codex_oauth_module.client import CodexOAuth  # type: ignore
    from codex_oauth_module.local_rag import LocalRAG, LocalKnowledgeBase, SearchResult  # type: ignore
    _CODEX_AVAILABLE = True
    print("✅ codex_oauth_module import thành công.")
except ImportError:
    # Fallback: import trực tiếp từ module_root nếu không có __init__.py đúng
    try:
        import importlib.util as _ilu
        def _load(name, path):
            spec = _ilu.spec_from_file_location(name, path)
            m = _ilu.module_from_spec(spec)
            sys.modules[name] = m
            spec.loader.exec_module(m)
            return m
        # Load các file cần thiết
        _load("codex_oauth_module.constants", str(_CODEX_MODULE_DIR / "constants.py"))
        _load("codex_oauth_module.exceptions", str(_CODEX_MODULE_DIR / "exceptions.py"))
        _load("codex_oauth_module.models", str(_CODEX_MODULE_DIR / "models.py"))
        _load("codex_oauth_module.sse_utils", str(_CODEX_MODULE_DIR / "sse_utils.py"))
        _load("codex_oauth_module.reasoning", str(_CODEX_MODULE_DIR / "reasoning.py"))
        _load("codex_oauth_module.tools", str(_CODEX_MODULE_DIR / "tools.py"))
        _load("codex_oauth_module.instructions", str(_CODEX_MODULE_DIR / "instructions.py"))
        _load("codex_oauth_module.client", str(_CODEX_MODULE_DIR / "client.py"))
        _load("codex_oauth_module.vector_store", str(_CODEX_MODULE_DIR / "vector_store.py"))
        _load("codex_oauth_module.local_rag", str(_CODEX_MODULE_DIR / "local_rag.py"))
        from codex_oauth_module.client import CodexOAuth  # type: ignore
        from codex_oauth_module.local_rag import LocalRAG, LocalKnowledgeBase, SearchResult  # type: ignore
        _CODEX_AVAILABLE = True
        print("✅ codex_oauth_module import thành công (fallback loader).")
    except Exception as e:
        print(f"⚠️ Không thể import codex_oauth_module: {e}")
        _CODEX_AVAILABLE = False
        CodexOAuth = None
        LocalRAG = None
        LocalKnowledgeBase = None
        SearchResult = None

from ..core.config import (
    CODEX_AUTH_FILE,
    CODEX_CLIENT_ID,
    CODEX_TOKEN_URL,
    CODEX_MODEL,
    CODEX_REASONING_EFFORT,
    CHROMA_PERSIST_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    RAG_SYSTEM_PROMPT,
)

if _CODEX_AVAILABLE:
    import codex_oauth_module.constants as _codex_constants  # type: ignore

    _codex_constants.CLIENT_ID = CODEX_CLIENT_ID
    _codex_constants.TOKEN_URL = CODEX_TOKEN_URL


class LLMService:
    """
    Service quản lý CodexOAuth và LocalRAG.
    Là lớp singleton, dùng chung trong suốt vòng đời ứng dụng.
    """

    def __init__(self):
        self._codex: Optional[CodexOAuth] = None
        self._rag: Optional[LocalRAG] = None
        self._kb: Optional[LocalKnowledgeBase] = None
        self._kb_name = "rag_knowledge_base"

    def _get_codex(self) -> "CodexOAuth":
        """Lazy-load Codex client."""
        if self._codex is None:
            if not _CODEX_AVAILABLE:
                raise RuntimeError(
                    "CodexOAuth không khả dụng. Kiểm tra lại module."
                )
            try:
                from pathlib import Path
                auth_path = Path(CODEX_AUTH_FILE)
                print(f"🔍 Tìm file auth: {CODEX_AUTH_FILE}")
                print(f"   Tồn tại: {auth_path.exists()}")
                
                if not auth_path.exists():
                    raise FileNotFoundError(f"File không tồn tại: {CODEX_AUTH_FILE}")
                
                self._codex = CodexOAuth.from_file(CODEX_AUTH_FILE)
                print(f"✅ CodexOAuth đã kết nối: {self._codex.email or 'unknown'}")
                
                # Kiểm tra authentication status
                if hasattr(self._codex, 'is_authenticated'):
                    print(f"   Authentication status: {self._codex.is_authenticated}")
                    
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"❌ Không tìm thấy file auth: {CODEX_AUTH_FILE}\n"
                    f"   Chi tiết: {str(e)}\n"
                    "   Hãy chạy: python browser_login.py"
                )
            except Exception as e:
                error_type = type(e).__name__
                raise RuntimeError(
                    f"❌ Không thể tải token ({error_type}): {str(e)}\n"
                    "   Hãy chạy: python browser_login.py --refresh hoặc python browser_login.py"
                )
        return self._codex

    def _refresh_token_if_needed(self):
        """Thử refresh token nếu hết hạn."""
        if self._codex is None:
            return
        try:
            # Kiểm tra xem token còn hiệu lực không
            if hasattr(self._codex, 'is_authenticated') and not self._codex.is_authenticated:
                print("🔄 Token hết hạn, thử làm mới...")
                if hasattr(self._codex, 'refresh_token'):
                    self._codex.refresh_token()
                    print("✅ Token đã làm mới thành công")
                else:
                    print("⚠️ Không thể tự động làm mới token, vui lòng đăng nhập lại")
                    self._codex = None
        except Exception as e:
            print(f"⚠️ Lỗi khi làm mới token: {e}")
            self._codex = None

    def _get_rag(self) -> "LocalRAG":
        """Lazy-load RAG client."""
        if self._rag is None:
            codex = self._get_codex()
            self._rag = LocalRAG(
                codex_client=codex,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )

            # Bật semantic search với ChromaDB (persist directory)
            success = self._rag.enable_semantic_search(
                persist_directory=str(CHROMA_PERSIST_DIR),
                embedding_profile="balanced",  # paraphrase-multilingual-MiniLM-L12-v2
            )
            if not success:
                print("⚠️ Không bật được semantic search, dùng fuzzy search thay thế.")

        return self._rag

    def load_files_into_kb(self, file_paths: List[str]) -> int:
        """
        Nạp danh sách file vào knowledge base, index vào ChromaDB.
        Trả về số chunk đã được index.
        """
        rag = self._get_rag()

        # Tải file vào KB
        kb = rag.load_files(file_paths, name=self._kb_name)
        self._kb = kb

        # Index vào ChromaDB
        indexed = rag.index_knowledge_base(kb, force_reindex=True)
        print(f"✅ Đã index {indexed} chunks từ {len(file_paths)} file.")
        return indexed

    def reload_all_files(self, file_paths: List[str]) -> int:
        """
        Tải lại toàn bộ file đã INDEXED từ danh sách đường dẫn.
        Dùng khi khởi động lại server.
        """
        if not file_paths:
            return 0
        return self.load_files_into_kb(file_paths)

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Tìm kiếm các chunk liên quan đến câu hỏi.
        Dùng semantic search nếu có, fallback về fuzzy search.
        """
        rag = self._get_rag()
        if self._kb is None:
            return []

        # Thử semantic search trước
        if rag.has_semantic_search:
            results = rag.semantic_search(self._kb, query, limit=top_k, min_score=0.3)
        else:
            results = rag.search(self._kb, query, limit=top_k, min_score=0.2)

        return results

    def generate_answer(
        self,
        question: str,
        context_chunks: List[SearchResult],
        model: str = None,
    ) -> str:
        """
        Gọi Codex để sinh câu trả lời dựa trên context.
        Có retry logic để xử lý token hết hạn.
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                codex = self._get_codex()
                model = model or CODEX_MODEL

                # Xây dựng context từ các chunk tìm thấy
                if not context_chunks:
                    context = "⚠️ Không tìm thấy thông tin liên quan trong tài liệu."
                else:
                    context_parts = []
                    for i, result in enumerate(context_chunks, 1):
                        context_parts.append(
                            f"--- Nguồn {i}: {result.chunk.filename} (độ phù hợp: {result.score:.0%}) ---\n"
                            f"{result.chunk.text}"
                        )
                    context = "\n\n".join(context_parts)

                # Build prompt
                full_prompt = (
                    f"NGỮ CẢNH TỪ TÀI LIỆU:\n"
                    f"{context}\n\n"
                    f"---\n\n"
                    f"CÂU HỎI: {question}"
                )

                # Gọi CodexOAuth.chat()
                answer = codex.chat(
                    message=full_prompt,
                    model=model,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    reasoning_effort=CODEX_REASONING_EFFORT,
                )
                return answer
            except Exception as e:
                error_msg = str(e).lower()
                # Nếu lỗi liên quan tới token, thử làm mới và retry
                if "token" in error_msg and "expired" in error_msg and attempt < max_retries - 1:
                    print(f"⚠️ Lần {attempt + 1}: Token hết hạn, thử làm mới...")
                    self._refresh_token_if_needed()
                    continue
                # Nếu không phải token, hoặc đã retry hết lần, ném lỗi
                raise RuntimeError(f"❌ Lỗi từ AI: {str(e)}")

    def is_healthy(self) -> dict:
        """Kiểm tra trạng thái kết nối."""
        status = {"codex_connected": False, "rag_ready": False, "kb_loaded": False}
        try:
            codex = self._get_codex()
            status["codex_connected"] = codex.is_authenticated
        except Exception as e:
            status["codex_error"] = str(e)

        status["rag_ready"] = self._rag is not None
        status["kb_loaded"] = self._kb is not None
        if self._kb:
            status["kb_file_count"] = self._kb.file_count
            status["kb_chunk_count"] = len(self._kb.documents)

        return status


# ============================================================
# Singleton instance - dùng chung toàn bộ ứng dụng
# ============================================================
_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """FastAPI dependency - trả về singleton LLMService."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
