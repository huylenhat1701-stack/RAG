"""
RAG Service - Điều phối luồng Hỏi & Đáp và Tóm tắt tài liệu
Kết hợp search (Retrieval) và generate (Generation).
"""

from typing import Tuple, List
from sqlalchemy.orm import Session

from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, SearchResult
from ..services.document_service import get_document_content
from ..models.schemas import AskResponse, SourceInfo, DocumentSummaryResponse, ExerciseResponse
from ..core.config import CODEX_MODEL, SUMMARY_SYSTEM_PROMPT


def answer_question(
    question: str,
    top_k: int,
    db: Session,
    llm_service: LLMService,
    history: List[dict] = None,
    doc_ids: List[int] = None,
) -> AskResponse:
    """
    Luồng Q&A hoàn chỉnh:
        1. Kiểm tra có tài liệu đã index chưa
        2. Tìm kiếm Top K chunks liên quan (Retrieval) – tuỳ chọn giới hạn theo doc_ids
        3. Gọi Codex sinh câu trả lời (Generation)
        4. Lưu vào chat_history
        5. Trả về kết quả + sources

    Args:
        question: Câu hỏi của người dùng
        top_k: Số chunk tìm kiếm
        db: SQLAlchemy session
        llm_service: Singleton LLMService
        history: Lịch sử trò chuyện
        doc_ids: Danh sách ID tài liệu cần giới hạn tìm kiếm (None = tất cả)

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

    # Xây dựng allowed_filenames nếu người dùng chọn tài liệu cụ thể
    allowed_filenames = None
    if doc_ids:
        from pathlib import Path
        allowed_filenames = []
        for did in doc_ids:
            doc = doc_repo.get_by_id(did)
            if doc:
                p = Path(doc.file_path)
                # Tên file gốc (e.g. "report.pdf")
                allowed_filenames.append(p.name)
                # Tên file .extracted.txt nếu được dùng khi indexing (e.g. "report.extracted.txt")
                allowed_filenames.append(p.with_suffix(".extracted.txt").name)

    # Bước 1: Retrieval - tìm chunks liên quan
    try:
        search_results: List[SearchResult] = llm_service.search(
            question,
            top_k=top_k,
            allowed_filenames=allowed_filenames,
        )
    except Exception as e:
        print(f"⚠️ Lỗi search: {str(e)}")
        raise RuntimeError(f"❌ Lỗi tìm kiếm: {str(e)}")

    # Bước 2: Generation - gọi Codex sinh câu trả lời
    try:
        answer = llm_service.generate_answer(
            question=question,
            context_chunks=search_results,
            history=history,
        )
    except RuntimeError as e:
        # Nếu là lỗi từ llm_service, pass through
        raise
    except Exception as e:
        error_msg = str(e)
        if "token" in error_msg.lower() or "auth" in error_msg.lower():
            raise RuntimeError(f"❌ Lỗi xác thực: {error_msg}")
        raise RuntimeError(f"❌ Lỗi sinh câu trả lời: {error_msg}")

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


def summarize_document(
    doc_id: int,
    db: Session,
    llm_service: LLMService,
) -> DocumentSummaryResponse:
    """
    Tóm tắt tài liệu bằng AI.
    
    Luồng:
        1. Lấy nội dung tài liệu
        2. Gọi CodexOAuth để tóm tắt
        3. Lưu tóm tắt vào DB
        4. Trả về kết quả
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    # Nếu đã có summary, trả luôn
    if doc.summary:
        return DocumentSummaryResponse(
            id=doc.id,
            file_name=doc.file_name,
            summary=doc.summary,
            model_used=CODEX_MODEL,
        )

    # Lấy nội dung tài liệu
    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    # Giới hạn nội dung gửi cho AI (tối đa ~6000 chars để không quá dài)
    content = content_data["content"]
    if len(content) > 6000:
        content = content[:6000] + "\n\n[... nội dung còn lại đã được cắt bớt ...]"

    # Gọi CodexOAuth để tóm tắt
    prompt = (
        f"TÀI LIỆU CẦN TÓM TẮT: {doc.file_name}\n\n"
        f"NỘI DUNG:\n{content}"
    )

    codex = llm_service._get_codex()
    summary = codex.chat(
        message=prompt,
        model=CODEX_MODEL,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        reasoning_effort="medium",
    )

    # Lưu vào DB
    doc_repo.update_summary(doc_id, summary)

    return DocumentSummaryResponse(
        id=doc.id,
        file_name=doc.file_name,
        summary=summary,
        model_used=CODEX_MODEL,
    )


def generate_exercise(
    doc_id: int,
    exercise_type: str,
    count: int,
    db: Session,
    llm_service: LLMService,
) -> ExerciseResponse:
    """Tạo bài tập từ nội dung tài liệu bằng CodexOAuth."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu để tạo bài tập")

    content = content_data["content"]
    if len(content) > 6000:
        content = content[:6000] + "\n\n[... nội dung còn lại đã được cắt bớt ...]"

    prompt = (
        f"TẠO {exercise_type.upper()} TỪ TÀI LIỆU: {doc.file_name}\n\n"
        f"YÊU CẦU: Tạo {count} câu {exercise_type}. \n"
        f"TRẢ VỀ KẾT QUẢ CÓ CÂU HỎI VÀ ĐÁP ÁN RÕ RÀNG.\n\n"
        f"NỘI DUNG:\n{content}"
    )

    codex = llm_service._get_codex()
    exercise_text = codex.chat(
        message=prompt,
        model=CODEX_MODEL,
        system_prompt=(
            f"Bạn là trợ lý giáo dục. Tạo {exercise_type} dựa trên nội dung tài liệu."
        ),
        reasoning_effort="medium",
    )

    return ExerciseResponse(
        id=doc.id,
        file_name=doc.file_name,
        exercise_text=exercise_text,
        model_used=CODEX_MODEL,
    )
