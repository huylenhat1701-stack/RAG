"""
test_llm_retry.py

Test retry logic cho LLM calls với tenacity.

Acceptance: mock LLM endpoint lỗi 2 lần đầu, thành công lần 3
→ request phải vẫn thành công

Chạy: pytest tests/test_llm_retry.py -v
"""
import pytest
from unittest.mock import MagicMock, patch, call
import httpx


# ---------------------------------------------------------------------------
# Fixture: LLMService mock (không cần real server)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_service():
    """Tạo LLMService với HTTP client được mock."""
    with patch("backend.services.llm_service.chromadb"), \
         patch("backend.services.llm_service.SentenceTransformer"), \
         patch.object(
             __import__("backend.services.llm_service", fromlist=["LLMService"]).LLMService,
             "_detect_context_window",
             return_value=4096
         ):
        from backend.services.llm_service import LLMService
        svc = MagicMock(spec=LLMService)
        svc._llm_base_url = "http://localhost:1234/v1"
        svc._llm_api_key = "test"
        svc._model_name = "mock-model"
        svc._max_output_tokens = 1024
        # Bind _call_llm thật để test retry logic
        svc._call_llm = LLMService._call_llm.__get__(svc, LLMService)
        return svc


# ---------------------------------------------------------------------------
# TEST 1: 2 lần ConnectError, lần 3 thành công
# ---------------------------------------------------------------------------

class TestLLMRetry:

    def test_retry_on_connect_error_succeeds_on_third_attempt(self):
        """
        Mock endpoint lỗi ConnectError 2 lần đầu, thành công lần 3.
        _call_llm phải trả về kết quả thành công.
        """
        from backend.services.llm_service import LLMService

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise httpx.ConnectError("Connection refused")
            # Lần 3: thành công
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Câu trả lời thành công"}}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        mock_http = MagicMock()
        mock_http.post.side_effect = mock_post

        with patch("backend.services.llm_service.chromadb"), \
             patch("backend.services.llm_service.SentenceTransformer"):
            from backend.services.llm_service import LLMService

            # Tạo instance thủ công không qua __init__ để tránh deps
            svc = object.__new__(LLMService)
            svc._llm_base_url = "http://localhost:1234/v1"
            svc._llm_api_key = "test-key"
            svc._model_name = "mock-model"
            svc._max_output_tokens = 1024
            svc._http_client = mock_http

            messages = [{"role": "user", "content": "Test question"}]
            result = svc._call_llm(messages)

        assert result == "Câu trả lời thành công"
        assert call_count[0] == 3, f"Phải gọi 3 lần, thực tế: {call_count[0]}"

    def test_retry_on_read_timeout_succeeds(self):
        """ReadTimeout → retry và thành công."""
        from backend.services.llm_service import LLMService

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise httpx.ReadTimeout("Timeout")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Thành công sau timeout"}}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        mock_http = MagicMock()
        mock_http.post.side_effect = mock_post

        with patch("backend.services.llm_service.chromadb"), \
             patch("backend.services.llm_service.SentenceTransformer"):
            svc = object.__new__(LLMService)
            svc._llm_base_url = "http://localhost:1234/v1"
            svc._llm_api_key = "test-key"
            svc._model_name = "mock-model"
            svc._max_output_tokens = 1024
            svc._http_client = mock_http

            result = svc._call_llm([{"role": "user", "content": "Test"}])

        assert result == "Thành công sau timeout"
        assert call_count[0] == 3

    def test_no_retry_on_4xx_client_error(self):
        """
        4xx (lỗi client/parse) → KHÔNG retry, raise ngay.
        """
        from backend.services.llm_service import LLMService

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            error = httpx.HTTPStatusError(
                "400 Bad Request",
                request=MagicMock(),
                response=mock_response
            )
            mock_response.raise_for_status.side_effect = error
            return mock_response

        mock_http = MagicMock()
        mock_http.post.side_effect = mock_post

        with patch("backend.services.llm_service.chromadb"), \
             patch("backend.services.llm_service.SentenceTransformer"):
            svc = object.__new__(LLMService)
            svc._llm_base_url = "http://localhost:1234/v1"
            svc._llm_api_key = "test-key"
            svc._model_name = "mock-model"
            svc._max_output_tokens = 1024
            svc._http_client = mock_http

            with pytest.raises(RuntimeError):
                svc._call_llm([{"role": "user", "content": "Test"}])

        # 4xx không retry → chỉ gọi 1 lần
        assert call_count[0] == 1, (
            f"4xx không được retry, nhưng endpoint được gọi {call_count[0]} lần"
        )

    def test_exhausted_retries_raises_runtime_error(self):
        """
        Sau 3 lần retry đều thất bại → raise RuntimeError.
        """
        from backend.services.llm_service import LLMService

        call_count = [0]

        def always_fail(*args, **kwargs):
            call_count[0] += 1
            raise httpx.ConnectError("Always fails")

        mock_http = MagicMock()
        mock_http.post.side_effect = always_fail

        with patch("backend.services.llm_service.chromadb"), \
             patch("backend.services.llm_service.SentenceTransformer"):
            svc = object.__new__(LLMService)
            svc._llm_base_url = "http://localhost:1234/v1"
            svc._llm_api_key = "test-key"
            svc._model_name = "mock-model"
            svc._max_output_tokens = 1024
            svc._http_client = mock_http

            with pytest.raises(RuntimeError):
                svc._call_llm([{"role": "user", "content": "Test"}])

        # Phải thử đúng MAX_RETRIES lần (3 attempts total)
        assert call_count[0] == 3, (
            f"Phải retry 3 lần trước khi give up, thực tế: {call_count[0]}"
        )
