"""
LLM Service - Local LLM qua LM Studio / Ollama (OpenAI API Compatible)
Full-Context Edition — đọc toàn bộ tài liệu, trả lời chính xác nhất.
"""

import uuid
import threading
import hashlib
import time
from functools import lru_cache
import httpx
from pathlib import Path
from typing import Optional, List, Tuple
from pydantic import BaseModel
from transformers import pipeline

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

import chromadb
from sentence_transformers import SentenceTransformer

from ..core.config import (
    LOCAL_LLM_API_BASE,
    LOCAL_LLM_API_KEY,
    LOCAL_LLM_MODEL,
    EMBEDDING_MODEL_NAME,
    NLI_MODEL_NAME,
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
    file_stem: str = ""  # Stem của tên file (không có extension) — dùng để filter ChromaDB


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
    # Tiếng Việt: an toàn với LLM local (khoảng 0.6 ký tự / token cho một số model)
    _CHARS_PER_TOKEN = 0.6

    def __init__(self):
        self._llm_base_url = LOCAL_LLM_API_BASE
        self._llm_api_key = LOCAL_LLM_API_KEY
        self._model_name = LOCAL_LLM_MODEL
        self._temperature: float = 0.1  # Default: thấp = nhất quán, ít sáng tạo

        self._kb_name = "rag_knowledge_base"
        self._indexed_file_paths: list = []

        # Search cache: key → (results, timestamp)
        # Invalidate khi có document mới được index
        self._search_cache: dict = {}       # {cache_key: (results, timestamp)}
        self._search_cache_lock = threading.Lock()
        self._CACHE_TTL_SECONDS = 3600      # 1 giờ
        self._CACHE_MAX_SIZE = 256          # Tối đa 256 query khác nhau


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

        # Init NLI Model
        try:
            print(f"[INFO] Loading NLI model: {NLI_MODEL_NAME} ...")
            self._nli_model = pipeline("text-classification", model=NLI_MODEL_NAME, top_k=None)
            print("[OK] NLI model loaded.")
        except Exception as e:
            print(f"[ERROR] Cannot load NLI model: {e}")
            self._nli_model = None

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
        """
        Gọi LM Studio/Ollama qua HTTP.

        Retry logic (tenacity):
        - 3 lần thử, exponential backoff: 1s → 2s → 4s
        - Chỉ retry khi gặp lỗi network/timeout (ConnectError, ReadTimeout)
        - KHÔNG retry với lỗi 4xx (parse/validation) — vô ích và chậm
        - Sau 3 lần thất bại → raise RuntimeError với thông điệp rõ ràng
        """
        _RETRY_EXCEPTIONS = (httpx.ConnectError, httpx.ReadTimeout)
        MAX_ATTEMPTS = 3

        @retry(
            retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            reraise=False,  # Chúng ta tự xử lý exception phía dưới
        )
        def _attempt():
            response = self._http_client.post(
                f"{self._llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model_name,
                    "messages": messages,
                    "temperature": getattr(self, "_temperature", 0.1),
                    "max_tokens": self._max_output_tokens,
                    "stream": False,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        try:
            return _attempt()
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
        except RetryError as e:
            # tenacity đã hết lượt retry — lấy lỗi cuối để xác định loại
            last = e.last_attempt.exception()
            if isinstance(last, httpx.ConnectError):
                raise RuntimeError(
                    f"Khong the ket noi den LM Studio tai {self._llm_base_url} sau {MAX_ATTEMPTS} lần thu.\n"
                    f"Hay bat Local Server trong LM Studio (tab <->) roi thu lai."
                ) from last
            raise RuntimeError(
                f"LM Studio không phản hồi sau {MAX_ATTEMPTS} lần thử (timeout).\n"
                f"Tài liệu có thể quá lớn. Hãy thử đặt câu hỏi cụ thể hơn."
            ) from last
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
            
            # Thêm prefix "passage: " cho e5 model
            passage_texts = [f"passage: {t}" for t in texts]
            
            # Log 1 ví dụ ra màn hình (chỉ chạy 1 lần để xác nhận)
            if not hasattr(self, "_logged_passage_example") and len(passage_texts) > 0:
                print(f"\n[DEBUG - PREFIX PASSAGE EXAMPLE]:\n{passage_texts[0][:200]}...\n")
                self._logged_passage_example = True

            embeddings = self._embedding_model.encode(passage_texts, batch_size=32, show_progress_bar=False).tolist()

            # Thêm cả filename và file_stem vào metadata — file_stem dùng cho
            # ChromaDB filter chính xác mà không cần load toàn bộ collection
            stem = path.stem  # Ví dụ: 'BT Giai tich 2' từ 'BT Giai tich 2.extracted.txt'
            self._collection.add(
                ids=[c.id for c in chunks],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "filename": c.filename,
                    "file_stem": stem,
                } for c in chunks],
            )
            print(f"[OK] Indexed {len(chunks)} chunks from {path.name} (stem={stem!r})")

        # Invalidate search cache — document mới ảnh hưởng đến kết quả vector search
        self.invalidate_search_cache()
        return self._collection.count()

    def reload_all_files(self, file_paths: List[str]) -> int:
        """Cập nhật danh sách file (ChromaDB persistent nên không cần nạp lại)."""
        self._indexed_file_paths = list(file_paths)
        return self._collection.count()

    # ------------------------------------------------------------------
    # Search cache helpers
    # ------------------------------------------------------------------

    def _make_cache_key(self, query: str, top_k: int, allowed_filenames: Optional[List[str]]) -> str:
        """Tạo cache key từ query + top_k + allowed_filenames."""
        raw = f"{query}|{top_k}|{sorted(allowed_filenames) if allowed_filenames else None}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[List["SearchResult"]]:
        """Lấy kết quả từ cache nếu còn hiệu lực (chưa hết TTL)."""
        with self._search_cache_lock:
            entry = self._search_cache.get(key)
            if entry is None:
                return None
            results, ts = entry
            if time.time() - ts > self._CACHE_TTL_SECONDS:
                del self._search_cache[key]  # Expired
                return None
            return results

    def _put_to_cache(self, key: str, results: List["SearchResult"]) -> None:
        """Lưu kết quả vào cache, giời hạn tối đa CACHE_MAX_SIZE entry."""
        with self._search_cache_lock:
            if len(self._search_cache) >= self._CACHE_MAX_SIZE:
                # Xóa entry cũ nhất (FIFO approximation)
                oldest_key = next(iter(self._search_cache))
                del self._search_cache[oldest_key]
            self._search_cache[key] = (results, time.time())

    def invalidate_search_cache(self) -> None:
        """Xóa toàn bộ search cache. Gọi khi có document mới được index."""
        with self._search_cache_lock:
            count = len(self._search_cache)
            self._search_cache.clear()
            if count > 0:
                print(f"[Cache] Invalidated {count} search cache entries do có document mới.")


    # ------------------------------------------------------------------
    # Search (Retrieval)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 15,
        allowed_filenames: List[str] = None,
    ) -> List[SearchResult]:
        """Vector search trong ChromaDB với LRU cache (TTL 1 giờ).
        
        Cache key = hash(query + top_k + allowed_filenames).
        Cache bị xóa hoàn toàn khi có document mới được index.
        """
        if not self._embedding_model or self._collection.count() == 0:
            return []

        cache_key = self._make_cache_key(query, top_k, allowed_filenames)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            print(f"[Cache] HIT — query={query[:40]!r}, top_k={top_k}")
            return cached

        # Thêm prefix "query: " cho e5 model
        query_text = f"query: {query}"
        query_embedding = self._embedding_model.encode([query_text]).tolist()

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
                    file_stem=results["metadatas"][0][i].get("file_stem", ""),
                )
                search_results.append(SearchResult(chunk=chunk, score=score))

        self._put_to_cache(cache_key, search_results)
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

        Ưu tiên dùng ChromaDB filter trên field 'file_stem' (chậm nhỏ, không load toàn bộ RAM).
        Fallback về Python filter nếu DB cũ chưa có metadata 'file_stem'.

        Ví dụ: stem='BT Giai tich 2' khớp 'BT Giai tich 2.extracted.txt'
        """
        if self._collection.count() == 0:
            return []

        import random
        stem_lower = stem.lower()

        # -----------------------------------------------------------
        # Ưu tiên: ChromaDB filter theo file_stem (chính xác, hiệu quả bộ nhớ)
        # -----------------------------------------------------------
        try:
            results = self._collection.get(
                where={"file_stem": stem},  # Exact match trên field file_stem
            )
            if results.get("documents"):
                items = list(zip(results["ids"], results["documents"], results["metadatas"]))
                if items:
                    if len(items) > count:
                        items = random.sample(items, count)
                    chunks = []
                    for id_val, doc_val, meta_val in items:
                        chunks.append(ChunkDocument(
                            id=id_val,
                            text=doc_val,
                            filename=meta_val.get("filename", "unknown") if meta_val else "unknown",
                            file_stem=meta_val.get("file_stem", "") if meta_val else "",
                        ))
                    print(f"[OK] get_random_chunks_by_stem: ChromaDB filter match {len(chunks)} chunks (stem={stem!r})")
                    return chunks
        except Exception as e:
            print(f"[WARN] ChromaDB filter failed ({e}), falling back to Python filter")

        # -----------------------------------------------------------
        # Fallback: DB cũ không có file_stem — thử filter theo filename exact match
        # -----------------------------------------------------------
        try:
            results = self._collection.get(where={"filename": {"$in": [
                stem,                         # exact filename
                f"{stem}.txt",               # plain text
                f"{stem}.extracted.txt",     # PDF/DOCX extracted
            ]}})
            if results.get("documents"):
                items = list(zip(results["ids"], results["documents"], results["metadatas"]))
                if items:
                    if len(items) > count:
                        items = random.sample(items, count)
                    chunks = []
                    for id_val, doc_val, meta_val in items:
                        chunks.append(ChunkDocument(
                            id=id_val,
                            text=doc_val,
                            filename=meta_val.get("filename", "unknown") if meta_val else "unknown",
                        ))
                    print(f"[OK] get_random_chunks_by_stem: filename filter match {len(chunks)} chunks")
                    return chunks
        except Exception as e:
            print(f"[WARN] Filename filter failed ({e}), falling back to full-scan")

        # -----------------------------------------------------------
        # Last resort fallback: load toàn bộ và filter bằng Python
        # (chỉ có thể xảy ra với DB rất cũ không có metadata nào)
        # -----------------------------------------------------------
        print(
            f"[WARN] get_random_chunks_by_stem: fallback full-scan — DB cũ thiếu metadata. "
            f"Hãy re-index để cải thiện hiệu suất."
        )
        try:
            all_results = self._collection.get(limit=self._collection.count())
        except Exception:
            return []

        if not all_results.get("documents") or not all_results.get("metadatas"):
            return []

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
    # NLI Verification
    # ------------------------------------------------------------------

    def verify_claims(self, context: str, claims: List[str]) -> List[List[dict]]:
        """Verify list of claims against context using NLI model."""
        if not self._nli_model or not claims:
            return []
        
        results = []
        # Tối ưu: truncate context nếu quá dài so với giới hạn NLI (thường là 512 tokens)
        # NLI pipeline tự động xử lý truncate, nhưng an toàn thì ta để nguyên pipeline xử lý.
        for claim in claims:
            try:
                # text = premise (context), text_pair = hypothesis (claim)
                result = self._nli_model({"text": context, "text_pair": claim}, truncation=True)
                results.append(result)
            except Exception as e:
                print(f"[WARN] Lỗi khi verify claim: {e}")
                results.append([])
                
        return results

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
# Singleton — Thread-safe (double-checked locking)
# ============================================================
_llm_service_instance: Optional[LLMService] = None
_llm_service_lock = threading.Lock()


def get_llm_service() -> LLMService:
    """
    Trả về singleton LLMService.

    Thread-safe bằng double-checked locking:
    - Kiểm tra lần 1 ngoài lock: tránh overhead acquire lock sau khi đã init.
    - Kiểm tra lần 2 trong lock: đảm bảo chỉ 1 thread tạo instance.
    - Instance chỉ được gán SAU KHI constructor thành công:
      nếu LLMService.__init__() raise exception, _llm_service_instance
      vẫn là None và lần gọi tiếp theo sẽ retry được.
    """
    global _llm_service_instance
    # Lần kiểm tra 1 (ngoài lock): fast path khi đã khởi tạo
    if _llm_service_instance is None:
        with _llm_service_lock:
            # Lần kiểm tra 2 (trong lock): tránh race condition
            if _llm_service_instance is None:
                # Tạo trên biến cục bộ trước — chỉ assign vào global
                # sau khi constructor thành công, tránh stuck ở state lỗi
                instance = LLMService()
                _llm_service_instance = instance
    return _llm_service_instance
