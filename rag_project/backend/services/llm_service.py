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
    print("[OK] codex_oauth_module import thanh cong.")
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
        print("[OK] codex_oauth_module import thanh cong (fallback loader).")
    except Exception as e:
        print(f"[WARN] Khong the import codex_oauth_module: {e}")
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
    EMBEDDING_PROFILE,
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
                print(f"[INFO] Tim file auth: {CODEX_AUTH_FILE}")
                print(f"   Ton tai: {auth_path.exists()}")
                
                if not auth_path.exists():
                    raise FileNotFoundError(f"File không tồn tại: {CODEX_AUTH_FILE}")
                
                self._codex = CodexOAuth.from_file(CODEX_AUTH_FILE)
                print(f"[OK] CodexOAuth da ket noi: {self._codex.email or 'unknown'}")
                
                # Kiểm tra authentication status
                if hasattr(self._codex, 'is_authenticated'):
                    print(f"   Auth status: {self._codex.is_authenticated}")
                    
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"[ERROR] Khong tim thay file auth: {CODEX_AUTH_FILE}\n"
                    f"   Chi tiet: {str(e)}\n"
                    "   Hay chay: python browser_login.py"
                )
            except Exception as e:
                error_type = type(e).__name__
                raise RuntimeError(
                    f"[ERROR] Khong the tai token ({error_type}): {str(e)}\n"
                    "   Hay chay: python browser_login.py --refresh hoac python browser_login.py"
                )
        return self._codex

    def _refresh_token_if_needed(self):
        """Thử refresh token nếu hết hạn."""
        if self._codex is None:
            return
        try:
            # Kiểm tra xem token còn hiệu lực không
            if hasattr(self._codex, 'is_authenticated') and not self._codex.is_authenticated:
                print("[INFO] Token het han, thu lam moi...")
                if hasattr(self._codex, 'refresh_token'):
                    self._codex.refresh_token()
                    print("[OK] Token da lam moi thanh cong")
                else:
                    print("[WARN] Khong the tu dong lam moi token, vui long dang nhap lai")
                    self._codex = None
        except Exception as e:
            print(f"[WARN] Loi khi lam moi token: {e}")
            self._codex = None

    def _get_rag(self) -> "LocalRAG":
        """Lazy-load RAG client (fuzzy search only, no embedding model needed)."""
        if self._rag is None:
            codex = self._get_codex()
            self._rag = LocalRAG(
                codex_client=codex,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
            # Dung fuzzy search - khong can sentence-transformers hay ChromaDB
            print("[INFO] LocalRAG khoi tao xong (fuzzy search mode).")

        return self._rag

    def load_files_into_kb(self, file_paths: List[str]) -> int:
        """
        Nap danh sach file vao knowledge base (fuzzy search, khong can index ChromaDB).
        Tra ve so chunk da load.
        """
        rag = self._get_rag()

        # Tai file vao KB (chi can load, khong can index vector)
        kb = rag.load_files(file_paths, name=self._kb_name)
        self._kb = kb

        chunk_count = len(kb.documents)
        print(f"[OK] Da load {chunk_count} chunks tu {len(file_paths)} file (fuzzy search mode).")
        return chunk_count

    def reload_all_files(self, file_paths: List[str]) -> int:
        """
        Tải lại toàn bộ file đã INDEXED từ danh sách đường dẫn.
        Dùng khi khởi động lại server.
        """
        if not file_paths:
            return 0
        return self.load_files_into_kb(file_paths)

    def search(
        self,
        query: str,
        top_k: int = 5,
        allowed_filenames: List[str] = None,
    ) -> List[SearchResult]:
        """
        Tim kiem cac chunk lien quan den cau hoi bang fuzzy search.

        Args:
            query: Câu hỏi tìm kiếm.
            top_k: Số kết quả trả về tối đa.
            allowed_filenames: Chỉ tìm trong các file có tên nằm trong danh sách này.
                               None = tìm trong tất cả file.
        """
        rag = self._get_rag()
        if self._kb is None:
            return []

        if allowed_filenames:
            # Tìm kiếm với limit lớn hơn để lọc được đúng top_k sau khi filter
            search_limit = max(top_k * 10, 50)
            results = rag.search(self._kb, query, limit=search_limit, min_score=0.1)
            # Lọc chỉ giữ chunk thuộc các file được phép
            allowed_set = set(allowed_filenames)
            results = [r for r in results if r.chunk.filename in allowed_set]
            return results[:top_k]

        # Không lọc theo file – tìm kiếm toàn bộ KB
        results = rag.search(self._kb, query, limit=top_k, min_score=0.1)
        return results

    def generate_answer(
        self,
        question: str,
        context_chunks: List[SearchResult],
        model: str = None,
        history: List[dict] = None,
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

                # Build history objects
                history_objs = []
                if history:
                    try:
                        from codex_oauth_module.models import ChatMessage # type: ignore
                        for msg in history:
                            history_objs.append(ChatMessage(role=msg["role"], content=msg["content"]))
                    except Exception as e:
                        print(f"Warning: could not parse history: {e}")

                # Gọi CodexOAuth.chat()
                answer = codex.chat(
                    message=full_prompt,
                    model=model,
                    history=history_objs,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    reasoning_effort=CODEX_REASONING_EFFORT,
                )
                return answer
            except Exception as e:
                error_msg = str(e).lower()
                # Nếu lỗi liên quan tới token, thử làm mới và retry
                if "token" in error_msg and "expired" in error_msg and attempt < max_retries - 1:
                    print(f"[WARN] Lan {attempt + 1}: Token het han, thu lam moi...")
                    self._refresh_token_if_needed()
                    continue
                # Nếu không phải token, hoặc đã retry hết lần, ném lỗi
                raise RuntimeError(f"[ERROR] Loi tu AI: {str(e)}")

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
