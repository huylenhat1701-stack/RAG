"""
RAG Service - Điều phối luồng Hỏi & Đáp
Kết hợp search (Retrieval) và generate (Generation).
"""

from typing import Tuple, List
from sqlalchemy.orm import Session

from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, SearchResult
from ..models.schemas import AskResponse, SourceInfo
from ..core.config import CODEX_MODEL


def answer_question(
    question: str,
    top_k: int,
    db: Session,
    llm_service: LLMService,
) -> AskResponse:
    """
    Luồng Q&A hoàn chỉnh:
        1. Kiểm tra có tài liệu đã index chưa
        2. Tìm kiếm Top K chunks liên quan (Retrieval)
        3. Gọi Codex sinh câu trả lời (Generation)
        4. Lưu vào chat_history
        5. Trả về kết quả + sources

    Args:
        question: Câu hỏi của người dùng
        top_k: Số chunk tìm kiếm
        db: SQLAlchemy session
        llm_service: Singleton LLMService

    Returns:
        AskResponse với answer + sources
    """
    doc_repo = DocumentRepository(db)
    hist_repo = HistoryRepository(db)

    # Kiểm tra có tài liệu INDEXED chưa
    indexed_count = doc_repo.count_indexed()
    if indexed_count == 0:
        return AskResponse(
            question=question,
            answer=(
                "⚠️ Chưa có tài liệu nào được tải lên và xử lý.\n"
                "Vui lòng vào tab **Quản lý Tài liệu** để upload tài liệu trước."
            ),
            sources=[],
            model_used=CODEX_MODEL,
            history_id=-1,
        )

    # Bước 1: Retrieval - tìm chunks liên quan
    search_results: List[SearchResult] = llm_service.search(question, top_k=top_k)

    # Bước 2: Generation - gọi Codex sinh câu trả lời
    answer = llm_service.generate_answer(
        question=question,
        context_chunks=search_results,
    )

    # Bước 3: Chuẩn bị danh sách sources
    sources_for_response = []
    sources_for_db = []

    seen_files = set()
    for result in search_results:
        filename = result.chunk.filename
        if filename not in seen_files:
            seen_files.add(filename)
            sources_for_response.append(
                SourceInfo(file_name=filename, relevance_score=round(result.score, 3))
            )
            sources_for_db.append(filename)

    # Bước 4: Lưu vào chat_history
    history = hist_repo.create(
        question=question,
        answer=answer,
        sources=sources_for_db,
        model_used=CODEX_MODEL,
    )

    return AskResponse(
        question=question,
        answer=answer,
        sources=sources_for_response,
        model_used=CODEX_MODEL,
        history_id=history.id,
    )
