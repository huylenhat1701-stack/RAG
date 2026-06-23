"""
LLM Service - Local LLM qua LM Studio / Ollama (OpenAI API Compatible)
Full-Context Edition — đọc toàn bộ tài liệu, trả lời chính xác nhất.
"""

import uuid
import httpx
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

import chromadb
from sentence_transformers import SentenceTransformer

from ..core.config import (
    LOCAL_LLM_API_BASE,
    LOCAL_LLM_API_KEY,
    LOCAL_LLM_MODEL,
    EMBEDDING_MODEL_NAME,
    CHROMA_PERSIST_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    RAG_SYSTEM_PROMPT,
    LLM_MAX_CONTENT_CHARS,
    LLM_MAX_OUTPUT_TOKENS,
    FULL_CONTEXT_THRESHOLD_CHARS,
)



class ChunkDocument(BaseModel):
    id: str
    text: str
    filename: str


class SearchResult(BaseModel):
    chunk: ChunkDocument
    score: float
    matched_text: str = ""


class LLMService:
    """
    Singleton service: Local LLM (LM Studio/Ollama) + ChromaDB RAG.
    Tự động phát hiện context window của model và giới hạn nội dung phù hợp.
    """

    # Token overhead: hệ thống prompt + câu hỏi + safety buffer
    _PROMPT_OVERHEAD_TOKENS = 400
    # Tiếng Việt: trung bình 2.0 ký tự / token
    _CHARS_PER_TOKEN = 2.0

    def __init__(self):
        self._llm_base_url = LOCAL_LLM_API_BASE
        self._llm_api_key = LOCAL_LLM_API_KEY
        self._model_name = LOCAL_LLM_MODEL

        self._kb_name = "rag_knowledge_base"
        self._indexed_file_paths: list = []

        # HTTP client với connection pool để tăng tốc độ
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=10.0,
                read=600.0,
                write=60.0,
                pool=30.0,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        # Tự động phát hiện context window và tính giới hạn an toàn
        self._context_window_tokens = self._detect_context_window()
        # Cho phép AI xuất tối đa token để không bị cắt ngang câu trả lời
        self._max_output_tokens = LLM_MAX_OUTPUT_TOKENS
        
        # Giả định AI cần tối thiểu 1024 tokens để trả lời khi tính toán không gian cho context
        assumed_output = 1024
        usable_tokens = max(200, self._context_window_tokens - self._PROMPT_OVERHEAD_TOKENS - assumed_output)
        self._max_content_chars = min(
            LLM_MAX_CONTENT_CHARS,
            int(usable_tokens * self._CHARS_PER_TOKEN),
        )
        self._full_context_threshold = self._max_content_chars

        print(
            f"[OK] Context window: {self._context_window_tokens} tokens | "
            f"Max content: {self._max_content_chars:,} ký tự | "
            f"Max output: {self._max_output_tokens} tokens"
        )

        # Init ChromaDB (bền vững, lưu trên đĩa)
        self._chroma_client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        self._collection = self._chroma_client.get_or_create_collection(name=self._kb_name)

        # Init Embedding Model (offline, dùng model local đã tải)
        try:
            print(f"[INFO] Loading embedding model: {EMBEDDING_MODEL_NAME} ...")
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            print("[OK] Embedding model loaded.")
        except Exception as e:
            print(f"[ERROR] Cannot load embedding model: {e}")
            self._embedding_model = None

    def __del__(self):
        """Dóng HTTP client khi service bị hủy."""
        try:
            self._http_client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Auto-detect Context Window
    # ------------------------------------------------------------------

    def _detect_context_window(self) -> int:
        """
        Tự động phát hiện context window (số token tối đa) của model đang chạy.
        - Query LM Studio /v1/models để lấy context_length.
        - Nếu không lấy được → fallback về 4096 (an toàn cho Gemma 4B).
        """
        try:
            res = self._http_client.get(f"{self._llm_base_url}/models", timeout=6.0)
            if res.status_code == 200:
                data = res.json()
                models = data.get("data", [])
                if models:
                    m = models[0]
                    self._model_name = m.get("id", self._model_name)
                    # LM Studio có thể trả về context_length trong nhiều key khác nhau
                    ctx = (
                        m.get("context_length")
                        or m.get("max_context_length")
                        or m.get("n_ctx")
                        or (m.get("meta") or {}).get("context_length")
                        or 0
                    )
                    if ctx and int(ctx) > 0:
                        detected = int(ctx)
                        print(f"[OK] Model '{self._model_name}': context window = {detected} tokens")
                        return detected
        except Exception as e:
            print(f"[WARN] Không thể phát hiện context window: {e}")

        # Fallback: 4096 — an toàn cho Gemma 3 4B và các model nhỏ
        print("[WARN] Không xác định được context window, dùng mặc định: 4096 tokens")
        return 4096

    def refresh_context_limits(self):
        """
        Cập nhật lại giới hạn context sau khi đổi model trong LM Studio.
        Gọi endpoint /health sau khi người dùng đổi model.
        """
        self._context_window_tokens = self._detect_context_window()
        # Cho phép AI xuất tối đa token để không bị cắt ngang câu trả lời
        self._max_output_tokens = LLM_MAX_OUTPUT_TOKENS
        
        # Giả định AI cần tối thiểu 1024 tokens để trả lời khi tính toán không gian cho context
        assumed_output = 1024
        usable_tokens = max(200, self._context_window_tokens - self._PROMPT_OVERHEAD_TOKENS - assumed_output)
        self._max_content_chars = min(
            LLM_MAX_CONTENT_CHARS,
            int(usable_tokens * self._CHARS_PER_TOKEN),
        )
        self._full_context_threshold = self._max_content_chars
        print(
            f"[REFRESH] Context window: {self._context_window_tokens} tokens | "
            f"Max content: {self._max_content_chars:,} ký tự"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_truncate(self, text: str, max_chars: int = None) -> str:
        """Cắt nội dung chỉ khi THỰC SỰ vượt quá giới hạn context window của model."""
        limit = max_chars or self._max_content_chars
        if len(text) <= limit:
            return text
        # Vẫn giữ càng nhiều nội dung càng tốt
        print(f"[WARN] Tài liệu quá lớn ({len(text):,} ký tự), cắt bớt về {limit:,} ký tự.")
        return text[:limit] + "\n\n[...Tài liệu quá dài, phần cuối bị lược bỏ. Vui lòng đặt câu hỏi cụ thể hơn...]"

    def _chunk_text(self, text: str, filename: str) -> List[ChunkDocument]:
        """Chia văn bản thành các đoạn nhỏ theo số từ."""
        chunks = []
        words = text.split()
        step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
        for i in range(0, len(words), step):
            chunk_words = words[i:i + CHUNK_SIZE]
            if not chunk_words:
                break
            chunk_text = " ".join(chunk_words)
            chunk_id = str(uuid.uuid4())
            chunks.append(ChunkDocument(id=chunk_id, text=chunk_text, filename=filename))
        return chunks

    def _call_llm(self, messages: list, timeout: float = 600.0) -> str:
        """Gọi LM Studio/Ollama qua HTTP. Raise RuntimeError nếu thất bại."""
        try:
            response = self._http_client.post(
                f"{self._llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model_name,
                    "messages": messages,
                    "temperature": 0.1,          # Thấp hơn = nhất quán hơn, ít sáng tạo hơn
                    "max_tokens": self._max_output_tokens,
                    "stream": False,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            raise RuntimeError(
                f"LM Studio trả về lỗi {e.response.status_code}.\n"
                f"Chi tiết: {detail}\n"
                f"Gợi ý: Kiểm tra LM Studio đang chạy tại {self._llm_base_url} và model đã được tải."
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Khong the ket noi den LM Studio tai {self._llm_base_url}.\n"
                f"Hay bat Local Server trong LM Studio (tab <->) roi thu lai."
            )
        except httpx.ReadTimeout:
            raise RuntimeError(
                "LM Studio mất quá nhiều thời gian để xử lý.\n"
                "Tài liệu có thể quá lớn. Hãy thử đặt câu hỏi cụ thể hơn hoặc chọn tài liệu ngắn hơn."
            )
        except Exception as e:
            raise RuntimeError(f"Loi goi Local LLM: {str(e)}")

    # ------------------------------------------------------------------
    # Knowledge Base Management
    # ------------------------------------------------------------------

    def load_files_into_kb(self, file_paths: List[str]) -> int:
        """Nạp các file vào ChromaDB (tích lũy, không xóa cũ)."""
        if not self._embedding_model:
            raise RuntimeError("Embedding model chua duoc khoi tao.")

        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                continue

            if fp not in self._indexed_file_paths:
                self._indexed_file_paths.append(fp)

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")

            chunks = self._chunk_text(content, path.name)
            if not chunks:
                continue

            texts = [c.text for c in chunks]
            embeddings = self._embedding_model.encode(texts, batch_size=32, show_progress_bar=False).tolist()

            self._collection.add(
                ids=[c.id for c in chunks],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{"filename": c.filename} for c in chunks],
            )
            print(f"[OK] Indexed {len(chunks)} chunks from {path.name}")

        return self._collection.count()

    def reload_all_files(self, file_paths: List[str]) -> int:
        """Cập nhật danh sách file (ChromaDB persistent nên không cần nạp lại)."""
        self._indexed_file_paths = list(file_paths)
        return self._collection.count()

    # ------------------------------------------------------------------
    # Search (Retrieval)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 15,
        allowed_filenames: List[str] = None,
    ) -> List[SearchResult]:
        """Vector search trong ChromaDB — lấy tối đa chunks liên quan nhất."""
        if not self._embedding_model or self._collection.count() == 0:
            return []

        query_embedding = self._embedding_model.encode([query]).tolist()

        where_filter = None
        if allowed_filenames:
            if len(allowed_filenames) == 1:
                where_filter = {"filename": allowed_filenames[0]}
            else:
                where_filter = {"filename": {"$in": allowed_filenames}}

        # Lấy tối đa nhưng không vượt số chunk có sẵn
        actual_top_k = min(top_k, self._collection.count())
        if actual_top_k == 0:
            return []

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=actual_top_k,
            where=where_filter,
        )

        search_results = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                score = 1.0 / (1.0 + results["distances"][0][i])
                chunk = ChunkDocument(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i],
                    filename=results["metadatas"][0][i].get("filename", "unknown"),
                )
                search_results.append(SearchResult(chunk=chunk, score=score))

        return search_results

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[ChunkDocument]:
        """Lấy danh sách các chunk kiến thức dựa theo ID."""
        if not chunk_ids or self._collection.count() == 0:
            return []
            
        results = self._collection.get(ids=chunk_ids)
        chunks = []
        if results.get("documents"):
            for i in range(len(results["ids"])):
                chunk = ChunkDocument(
                    id=results["ids"][i],
                    text=results["documents"][i],
                    filename=results["metadatas"][i].get("filename", "unknown") if results.get("metadatas") else "unknown",
                )
                chunks.append(chunk)
        return chunks

    def get_random_chunks(self, filename: str, count: int = 5) -> List[ChunkDocument]:
        """Lấy ngẫu nhiên các chunk từ một tài liệu cụ thể."""
        if self._collection.count() == 0:
            return []
            
        results = self._collection.get(where={"filename": filename})
        if not results.get("documents"):
            return []
            
        import random
        # Zip thành list tuples để sample
        items = list(zip(results["ids"], results["documents"], results["metadatas"]))
        if len(items) > count:
            items = random.sample(items, count)
            
        chunks = []
        for id_val, doc_val, meta_val in items:
            chunks.append(ChunkDocument(
                id=id_val,
                text=doc_val,
                filename=meta_val.get("filename", "unknown") if meta_val else "unknown"
            ))
        return chunks

    def get_random_chunks_by_stem(self, stem: str, count: int = 5) -> List[ChunkDocument]:
        """Lấy ngẫu nhiên các chunk từ tài liệu bằng cách tìm tên file chứa stem.
        
        Dùng khi PDF được lưu dưới dạng .extracted.txt nên tên file không khớp chính xác.
        Ví dụ: stem='BT Giai tich 2' sẽ khớp 'BT Giai tich 2.extracted.txt'
        """
        if self._collection.count() == 0:
            return []

        # Lấy tất cả các chunk và lọc theo stem
        try:
            all_results = self._collection.get(limit=self._collection.count())
        except Exception:
            return []

        if not all_results.get("documents") or not all_results.get("metadatas"):
            return []

        # Lọc chunk có filename chứa stem (không phân biệt hoa/thường)
        stem_lower = stem.lower()
        matching_items = []
        for i in range(len(all_results["ids"])):
            meta = all_results["metadatas"][i] if all_results.get("metadatas") else {}
            fn = meta.get("filename", "") if meta else ""
            if stem_lower in fn.lower():
                matching_items.append((
                    all_results["ids"][i],
                    all_results["documents"][i],
                    meta,
                ))

        if not matching_items:
            return []

        import random
        if len(matching_items) > count:
            matching_items = random.sample(matching_items, count)

        chunks = []
        for id_val, doc_val, meta_val in matching_items:
            chunks.append(ChunkDocument(
                id=id_val,
                text=doc_val,
                filename=meta_val.get("filename", "unknown") if meta_val else "unknown",
            ))
        return chunks

    # ------------------------------------------------------------------
    # Generation — Full-Context Mode (ưu tiên) & RAG Mode (fallback)
    # ------------------------------------------------------------------

    def generate_answer_full_context(
        self,
        question: str,
        full_text: str,
        filename: str = "",
        history: List[dict] = None,
    ) -> str:
        """
        Full-Context Mode: Đưa TOÀN BỘ nội dung tài liệu vào prompt.
        AI đọc 100% tài liệu → trả lời chính xác nhất có thể.
        Dùng khi tài liệu đủ nhỏ để fit vào context window của model.
        """
        # Chỉ cắt nếu thực sự vượt giới hạn tối đa
        content = self._safe_truncate(full_text, self._max_content_chars)

        doc_label = f'"{filename}"' if filename else "được cung cấp"
        full_prompt = (
            f"{RAG_SYSTEM_PROMPT}\n\n"
            f"=== TÀI LIỆU {doc_label} (ĐỌC TOÀN BỘ) ===\n"
            f"{content}\n"
            f"=== HẾT TÀI LIỆU ===\n\n"
            f"CÂU HỎI: {question}\n\n"
            f"TRẢ LỜI (đầy đủ, chi tiết, dựa hoàn toàn vào tài liệu trên):"
        )

        messages = []
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": full_prompt})

        char_count = len(content)
        print(f"[Full-Context] Gửi {char_count:,} ký tự tới LLM...")
        return self._call_llm(messages, timeout=600.0)

    def generate_answer(
        self,
        question: str,
        context_chunks: List[SearchResult],
        history: List[dict] = None,
    ) -> str:
        """
        RAG Mode: Sinh câu trả lời từ các chunks được tìm thấy.
        Dùng khi tài liệu quá lớn cho Full-Context Mode.
        """
        if not context_chunks:
            context = "Không tìm thấy thông tin liên quan trong tài liệu."
        else:
            parts = []
            for i, r in enumerate(context_chunks, 1):
                parts.append(f"[Nguồn {i} — {r.chunk.filename}]\n{r.chunk.text}")
            context = "\n\n---\n\n".join(parts)

        # Cắt context nếu vượt giới hạn
        context = self._safe_truncate(context, self._max_content_chars)

        full_prompt = (
            f"{RAG_SYSTEM_PROMPT}\n\n"
            f"=== NGỮ CẢNH TỪ TÀI LIỆU ({len(context_chunks)} đoạn liên quan nhất) ===\n"
            f"{context}\n"
            f"=== HẾT NGỮ CẢNH ===\n\n"
            f"CÂU HỎI: {question}\n\n"
            f"TRẢ LỜI (đầy đủ, chi tiết, dựa hoàn toàn vào nội dung trên):"
        )

        messages = []
        # Giữ lịch sử hội thoại gần nhất (4 lượt = 8 messages)
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": full_prompt})

        print(f"[RAG Mode] {len(context_chunks)} chunks, {len(context):,} ký tự context...")
        return self._call_llm(messages, timeout=600.0)

    def chat_direct(self, prompt: str, system_prompt: str = "") -> str:
        """Chat trực tiếp với LLM (dùng cho Tóm Tắt, Tạo Bài Tập)."""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Không cắt content — để model xử lý tối đa có thể
        full_prompt = self._safe_truncate(full_prompt, self._max_content_chars)

        messages = [{"role": "user", "content": full_prompt}]
        return self._call_llm(messages, timeout=600.0)

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def is_healthy(self) -> dict:
        """Kiểm tra kết nối LM Studio và trạng thái RAG."""
        status = {
            "llm_connected": False,
            "rag_ready": False,
            "kb_loaded": False,
            "kb_chunk_count": 0,
            "model_name": self._model_name,
            "api_base": self._llm_base_url,
            "context_window_tokens": self._context_window_tokens,
            "max_content_chars": self._max_content_chars,
            "max_output_tokens": self._max_output_tokens,
        }

        try:
            res = self._http_client.get(f"{self._llm_base_url}/models", timeout=5.0)
            if res.status_code == 200:
                status["llm_connected"] = True
                status["codex_connected"] = True  # compat
                models_data = res.json()
                if models_data.get("data"):
                    current_model = models_data["data"][0].get("id", self._model_name)
                    # Nếu model đã thay đổi → cập nhật lại giới hạn
                    if current_model != self._model_name:
                        print(f"[INFO] Model đổi: {self._model_name} → {current_model}, cập nhật giới hạn...")
                        self.refresh_context_limits()
                    status["model_name"] = self._model_name
                    status["context_window_tokens"] = self._context_window_tokens
                    status["max_content_chars"] = self._max_content_chars
        except Exception:
            status["codex_connected"] = False

        status["rag_ready"] = self._embedding_model is not None

        try:
            count = self._collection.count()

            status["kb_loaded"] = count > 0
            status["kb_chunk_count"] = count
        except Exception:
            pass

        return status


# ============================================================
# Singleton
# ============================================================
_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
