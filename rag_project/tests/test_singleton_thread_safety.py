"""
test_singleton_thread_safety.py

Chứng minh race condition trong get_llm_service() và verify fix.

Chạy: pytest tests/test_singleton_thread_safety.py -v
"""
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers để reset module-level state giữa các test
# ---------------------------------------------------------------------------

def _reset_singleton():
    """Reset _llm_service_instance và _llm_service_lock về trạng thái ban đầu."""
    import backend.services.llm_service as llm_mod
    llm_mod._llm_service_instance = None
    # Nếu module đã có lock (sau khi fix), không reset lock —
    # chỉ reset instance để test có thể tạo mới.


def _get_service():
    """Wrapper gọi get_llm_service() và trả về instance."""
    from backend.services.llm_service import get_llm_service
    return get_llm_service()


# ---------------------------------------------------------------------------
# Fixture: Mock LLMService.__init__ để không cần LM Studio thật
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_llm_init(monkeypatch):
    """
    Mock LLMService.__init__ để test không cần LM Studio, ChromaDB, hay
    SentenceTransformer thật. Trả về MagicMock instance.
    """
    import backend.services.llm_service as llm_mod

    original_init = llm_mod.LLMService.__init__

    def fake_init(self):
        # Gán các attribute tối thiểu để tránh AttributeError trong code
        self._model_name = "mock-model"
        self._llm_base_url = "http://localhost:1234/v1"
        self._llm_api_key = "mock-key"
        self._indexed_file_paths = []
        self._http_client = MagicMock()
        self._context_window_tokens = 4096
        self._max_output_tokens = 1024
        self._max_content_chars = 50000
        self._full_context_threshold = 50000
        self._chroma_client = MagicMock()
        self._collection = MagicMock()
        self._embedding_model = MagicMock()

    monkeypatch.setattr(llm_mod.LLMService, "__init__", fake_init)
    _reset_singleton()
    yield
    _reset_singleton()


# ---------------------------------------------------------------------------
# TEST 1: 20 threads đồng thời — chỉ tạo 1 instance duy nhất
# ---------------------------------------------------------------------------

class TestSingletonThreadSafety:

    def test_single_thread_returns_same_instance(self):
        """Baseline: single-threaded call luôn trả cùng 1 instance."""
        from backend.services.llm_service import get_llm_service
        s1 = get_llm_service()
        s2 = get_llm_service()
        assert id(s1) == id(s2), "Singleton vi phạm: 2 lần gọi trả về instance khác nhau"

    def test_20_concurrent_threads_produce_single_instance(self):
        """
        20 threads gọi get_llm_service() đồng thời.
        Tất cả phải nhận cùng 1 instance (id() giống nhau).
        """
        from backend.services.llm_service import get_llm_service

        results = []
        errors = []

        def worker():
            try:
                svc = get_llm_service()
                results.append(id(svc))
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker) for _ in range(20)]
            for f in as_completed(futures):
                pass  # exceptions đã được catch trong worker

        assert not errors, f"Worker gặp lỗi: {errors}"
        assert len(results) == 20, f"Chỉ {len(results)}/20 worker hoàn thành"

        unique_ids = set(results)
        assert len(unique_ids) == 1, (
            f"Race condition: {len(unique_ids)} instance khác nhau được tạo! "
            f"Unique IDs: {unique_ids}"
        )

    def test_instance_id_consistent_after_init(self):
        """
        Sau khi singleton được tạo, mọi lần gọi tiếp theo trả về cùng object.
        """
        from backend.services.llm_service import get_llm_service
        first = get_llm_service()
        subsequent = [get_llm_service() for _ in range(10)]
        assert all(id(s) == id(first) for s in subsequent)


# ---------------------------------------------------------------------------
# TEST 2: Exception trong __init__ → không bị stuck, retry được
# ---------------------------------------------------------------------------

class TestSingletonExceptionRetry:

    def test_exception_in_init_allows_retry(self, monkeypatch):
        """
        Nếu LLMService.__init__() raise lần 1, lần gọi sau phải retry
        được (không bị stuck ở state lỗi).
        """
        import backend.services.llm_service as llm_mod

        call_count = [0]

        def flaky_init(self):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated init failure (lần 1)")
            # Lần 2 thành công
            self._model_name = "mock-model"
            self._llm_base_url = "http://localhost:1234/v1"
            self._llm_api_key = "mock-key"
            self._indexed_file_paths = []
            self._http_client = MagicMock()
            self._context_window_tokens = 4096
            self._max_output_tokens = 1024
            self._max_content_chars = 50000
            self._full_context_threshold = 50000
            self._chroma_client = MagicMock()
            self._collection = MagicMock()
            self._embedding_model = MagicMock()

        monkeypatch.setattr(llm_mod.LLMService, "__init__", flaky_init)
        _reset_singleton()

        # Lần 1: phải raise
        with pytest.raises(RuntimeError, match="Simulated init failure"):
            llm_mod.get_llm_service()

        # Sau khi lỗi, instance không được set
        assert llm_mod._llm_service_instance is None, (
            "Bug: instance được set dù __init__ raise exception — "
            "lần gọi sau sẽ nhận một object lỗi không dùng được"
        )

        # Lần 2: phải thành công (retry)
        svc = llm_mod.get_llm_service()
        assert svc is not None
        assert call_count[0] == 2, f"__init__ chỉ nên gọi 2 lần, thực tế: {call_count[0]}"

    def test_exception_does_not_block_other_threads(self, monkeypatch):
        """
        Nếu 1 thread gặp lỗi khi init, các thread khác vẫn có thể tạo instance.
        """
        import backend.services.llm_service as llm_mod

        call_count = [0]
        lock = threading.Lock()

        def sometimes_flaky_init(self):
            with lock:
                call_count[0] += 1
                count = call_count[0]
            if count == 1:
                raise RuntimeError("First init fails")
            self._model_name = "mock-model"
            self._llm_base_url = "http://localhost:1234/v1"
            self._llm_api_key = "mock-key"
            self._indexed_file_paths = []
            self._http_client = MagicMock()
            self._context_window_tokens = 4096
            self._max_output_tokens = 1024
            self._max_content_chars = 50000
            self._full_context_threshold = 50000
            self._chroma_client = MagicMock()
            self._collection = MagicMock()
            self._embedding_model = MagicMock()

        monkeypatch.setattr(llm_mod.LLMService, "__init__", sometimes_flaky_init)
        _reset_singleton()

        # Gọi lần đầu → fail
        try:
            llm_mod.get_llm_service()
        except RuntimeError:
            pass

        # Gọi lần 2 → phải thành công (không bị stuck)
        svc = llm_mod.get_llm_service()
        assert svc is not None
