"""
test_relevance_threshold.py

Chứng minh thiếu relevance threshold và fallback "I don't know".
Test các trường hợp:
1. Query out-of-scope → phải trả fallback message, KHÔNG gọi LLM
2. Query có chunk liên quan thấp → lọc bớt trước khi vào LLM

Chạy: pytest tests/test_relevance_threshold.py -v
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_result(score: float, text: str = "sample chunk", filename: str = "doc.txt"):
    """Tạo SearchResult mock với score cho sẵn."""
    from backend.services.llm_service import SearchResult, ChunkDocument
    chunk = ChunkDocument(id="chunk-1", text=text, filename=filename)
    return SearchResult(chunk=chunk, score=score)


def _make_mock_llm_service(search_results):
    """Tạo LLMService mock với search() trả về search_results cố định."""
    svc = MagicMock()
    svc.search.return_value = search_results
    svc._model_name = "mock-model"
    svc.generate_answer.return_value = "LLM generated answer"
    svc.generate_answer_full_context.return_value = "LLM full context answer"
    return svc


# ---------------------------------------------------------------------------
# TEST 1: Out-of-scope query (max score < NO_CONTEXT_THRESHOLD)
#         → phải trả fallback, KHÔNG gọi generate_answer
# ---------------------------------------------------------------------------

class TestNoContextFallback:

    def test_out_of_scope_returns_fallback_not_llm(self):
        """
        Câu hỏi không liên quan tài liệu → max score rất thấp.
        Phải trả fallback message mà KHÔNG gọi llm_service.generate_answer().
        """
        from backend.services import rag_service
        from backend.core.config import NO_CONTEXT_THRESHOLD

        # Tạo search results với score cực thấp (< 0.4)
        low_score_results = [
            _make_search_result(score=0.1),
            _make_search_result(score=0.15),
            _make_search_result(score=0.05),
        ]
        mock_svc = _make_mock_llm_service(low_score_results)

        # Mock db và repositories
        mock_db = MagicMock()
        mock_doc_repo = MagicMock()
        mock_hist_repo = MagicMock()
        mock_hist_repo.create.return_value = MagicMock(id=1)

        # Mock doc_repo.count_indexed và get_indexed
        mock_doc = MagicMock()
        mock_doc.file_name = "test.pdf"
        mock_doc.file_path = "/uploads/test.pdf"
        mock_doc.id = 1

        with patch("backend.services.rag_service.DocumentRepository") as MockDocRepo, \
             patch("backend.services.rag_service.HistoryRepository") as MockHistRepo, \
             patch("backend.services.rag_service.get_document_content") as mock_get_content:

            MockDocRepo.return_value = mock_doc_repo
            MockHistRepo.return_value = mock_hist_repo
            mock_doc_repo.count_indexed.return_value = 1
            mock_doc_repo.get_indexed.return_value = [mock_doc]
            mock_get_content.return_value = {
                "content": "A" * 500000,  # Nội dung lớn → force RAG mode
                "page_count": 1,
                "word_count": 1000,
                "char_count": 500000,
            }

            response = rag_service.answer_question(
                question="Thời tiết hôm nay thế nào?",  # Out-of-scope
                top_k=15,
                db=mock_db,
                llm_service=mock_svc,
                history=None,
                doc_ids=None,
                user_id=1,
            )

        # ASSERTION CHÍNH: generate_answer KHÔNG được gọi
        mock_svc.generate_answer.assert_not_called(), (
            "Bug: generate_answer được gọi dù max score < NO_CONTEXT_THRESHOLD"
        )

        # Response phải là fallback message
        assert "không tìm thấy" in response.answer.lower() or \
               "không có thông tin" in response.answer.lower(), (
            f"Fallback message không đúng format. Nhận được: '{response.answer}'"
        )

    def test_max_score_above_no_context_threshold_calls_llm(self):
        """
        Câu hỏi có ít nhất 1 chunk đủ liên quan → PHẢI gọi generate_answer.
        """
        from backend.services import rag_service

        # Score = 0.6 > RELEVANCE_THRESHOLD (0.5)
        high_score_results = [
            _make_search_result(score=0.6),
            _make_search_result(score=0.45),
        ]
        mock_svc = _make_mock_llm_service(high_score_results)

        mock_db = MagicMock()
        mock_doc_repo = MagicMock()
        mock_hist_repo = MagicMock()
        mock_hist_repo.create.return_value = MagicMock(id=1)

        mock_doc = MagicMock()
        mock_doc.file_name = "test.pdf"
        mock_doc.file_path = "/uploads/test.pdf"
        mock_doc.id = 1

        with patch("backend.services.rag_service.DocumentRepository") as MockDocRepo, \
             patch("backend.services.rag_service.HistoryRepository") as MockHistRepo, \
             patch("backend.services.rag_service.get_document_content") as mock_get_content:

            MockDocRepo.return_value = mock_doc_repo
            MockHistRepo.return_value = mock_hist_repo
            mock_doc_repo.count_indexed.return_value = 1
            mock_doc_repo.get_indexed.return_value = [mock_doc]
            mock_get_content.return_value = {
                "content": "A" * 500000,  # Force RAG mode
                "page_count": 1,
                "word_count": 1000,
                "char_count": 500000,
            }

            response = rag_service.answer_question(
                question="Giải thích khái niệm chính trong tài liệu?",
                top_k=15,
                db=mock_db,
                llm_service=mock_svc,
                history=None,
                doc_ids=None,
                user_id=1,
            )

        mock_svc.generate_answer.assert_called_once()


# ---------------------------------------------------------------------------
# TEST 2: RELEVANCE_THRESHOLD — lọc chunk thấp trước khi vào LLM
# ---------------------------------------------------------------------------

class TestRelevanceThresholdFilter:

    def test_low_score_chunks_filtered_from_context(self):
        """
        Nếu max score vượt NO_CONTEXT_THRESHOLD nhưng một số chunk
        thấp hơn RELEVANCE_THRESHOLD → các chunk đó bị lọc trước khi
        gọi generate_answer.
        """
        from backend.services import rag_service
        from backend.core.config import RELEVANCE_THRESHOLD
        
        # Score = 0.8 > RELEVANCE_THRESHOLD (0.76)
        mixed_results = [
            _make_search_result(score=0.7, text="Chunk rất liên quan", filename="doc.txt"),
            _make_search_result(score=0.3, text="Chunk ít liên quan", filename="doc.txt"),
            _make_search_result(score=0.1, text="Chunk không liên quan", filename="doc.txt"),
        ]
        mock_svc = _make_mock_llm_service(mixed_results)

        mock_db = MagicMock()
        mock_doc_repo = MagicMock()
        mock_hist_repo = MagicMock()
        mock_hist_repo.create.return_value = MagicMock(id=1)

        mock_doc = MagicMock()
        mock_doc.file_name = "test.pdf"
        mock_doc.file_path = "/uploads/test.pdf"
        mock_doc.id = 1

        with patch("backend.services.rag_service.DocumentRepository") as MockDocRepo, \
             patch("backend.services.rag_service.HistoryRepository") as MockHistRepo, \
             patch("backend.services.rag_service.get_document_content") as mock_get_content:

            MockDocRepo.return_value = mock_doc_repo
            MockHistRepo.return_value = mock_hist_repo
            mock_doc_repo.count_indexed.return_value = 1
            mock_doc_repo.get_indexed.return_value = [mock_doc]
            mock_get_content.return_value = {
                "content": "A" * 500000,
                "page_count": 1,
                "word_count": 1000,
                "char_count": 500000,
            }

            rag_service.answer_question(
                question="Nội dung chính của tài liệu?",
                top_k=15,
                db=mock_db,
                llm_service=mock_svc,
                history=None,
                doc_ids=None,
                user_id=1,
            )

        # Kiểm tra generate_answer được gọi với các chunk đã lọc
        assert mock_svc.generate_answer.called, "generate_answer phải được gọi"
        call_args = mock_svc.generate_answer.call_args

        # Lấy context_chunks từ positional hoặc keyword args
        if call_args.args:
            _, context_chunks = call_args.args[0], call_args.args[1]
        else:
            context_chunks = call_args.kwargs.get("context_chunks", [])

        # Không có chunk nào với score < RELEVANCE_THRESHOLD trong call
        low_chunks = [r for r in context_chunks if r.score < RELEVANCE_THRESHOLD]
        assert len(low_chunks) == 0, (
            f"Chunk thấp hơn threshold {RELEVANCE_THRESHOLD} vẫn được đưa vào LLM: "
            f"{[(r.chunk.text, r.score) for r in low_chunks]}"
        )

    def test_all_chunks_below_relevance_threshold_uses_best_chunks(self):
        """
        Nếu TẤT CẢ chunk đều thấp hơn RELEVANCE_THRESHOLD nhưng
        max score vượt NO_CONTEXT_THRESHOLD → fallback dùng toàn bộ
        search_results (không lọc hết rồi call LLM với list rỗng).
        """
        from backend.services import rag_service

        # Tất cả scores nằm giữa NO_CONTEXT_THRESHOLD (0.4) và RELEVANCE_THRESHOLD (0.5)
        borderline_results = [
            _make_search_result(score=0.45, text="Chunk hơi liên quan", filename="doc.txt"),
            _make_search_result(score=0.42, text="Chunk hơi liên quan 2", filename="doc.txt"),
        ]
        mock_svc = _make_mock_llm_service(borderline_results)

        mock_db = MagicMock()
        mock_doc_repo = MagicMock()
        mock_hist_repo = MagicMock()
        mock_hist_repo.create.return_value = MagicMock(id=1)

        mock_doc = MagicMock()
        mock_doc.file_name = "test.pdf"
        mock_doc.file_path = "/uploads/test.pdf"
        mock_doc.id = 1

        with patch("backend.services.rag_service.DocumentRepository") as MockDocRepo, \
             patch("backend.services.rag_service.HistoryRepository") as MockHistRepo, \
             patch("backend.services.rag_service.get_document_content") as mock_get_content:

            MockDocRepo.return_value = mock_doc_repo
            MockHistRepo.return_value = mock_hist_repo
            mock_doc_repo.count_indexed.return_value = 1
            mock_doc_repo.get_indexed.return_value = [mock_doc]
            mock_get_content.return_value = {
                "content": "A" * 500000,
                "page_count": 1,
                "word_count": 1000,
                "char_count": 500000,
            }

            rag_service.answer_question(
                question="Nội dung chính?",
                top_k=15,
                db=mock_db,
                llm_service=mock_svc,
                history=None,
                doc_ids=None,
                user_id=1,
            )

        # generate_answer phải được gọi (không bị chặn sai)
        assert mock_svc.generate_answer.called, (
            "generate_answer bị chặn sai khi max score > NO_CONTEXT_THRESHOLD"
        )
