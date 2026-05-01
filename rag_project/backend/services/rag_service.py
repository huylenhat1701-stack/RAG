"""
RAG Service - Điều phối luồng Hỏi & Đáp và Tóm tắt tài liệu
Full-Context Edition: tự động chọn chế độ đọc toàn bộ hoặc RAG tùy độ dài tài liệu.
"""

from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, SearchResult
from ..services.document_service import get_document_content
from ..models.schemas import AskResponse, SourceInfo, DocumentSummaryResponse, ExerciseResponse
from ..core.config import (
    SUMMARY_SYSTEM_PROMPT,
    LLM_MAX_CONTENT_CHARS,
    FULL_CONTEXT_THRESHOLD_CHARS,
)


def answer_question(
    question: str,
    top_k: int,
    db: Session,
    llm_service: LLMService,
    history: List[dict] = None,
    doc_ids: List[int] = None,
) -> AskResponse:
    """
    Luồng Q&A với Full-Context Mode:

    TRƯỜNG HỢP 1: Người dùng chọn 1 tài liệu cụ thể
        → Đọc toàn bộ nội dung tài liệu đó
        → Nếu vừa context window: Full-Context Mode (chính xác 100%)
        → Nếu quá lớn: RAG Mode với max top_k (vẫn rất tốt)

    TRƯỜNG HỢP 2: Người dùng chọn nhiều tài liệu hoặc tất cả
        → Ghép toàn bộ nội dung các tài liệu đã chọn
        → Nếu vừa: Full-Context Mode ghép nhiều tài liệu
        → Nếu quá lớn: RAG Mode với top_k cao
    """
    doc_repo = DocumentRepository(db)
    hist_repo = HistoryRepository(db)

    indexed_count = doc_repo.count_indexed()
    if indexed_count == 0:
        return AskResponse(
            question=question,
            answer=(
                "Chưa có tài liệu nào được tải lên và xử lý.\n"
                "Vui lòng vào tab Quản Lý Tài Liệu để upload tài liệu trước."
            ),
            sources=[],
            model_used=llm_service._model_name,
            history_id=-1,
            mode="none",
            context_chars=0,
        )

    # ----------------------------------------------------------------
    # Xây dựng danh sách tài liệu được phép truy cập
    # ----------------------------------------------------------------
    allowed_filenames = None
    target_docs = []  # Danh sách doc objects để đọc full content

    if doc_ids:
        allowed_filenames = []
        for did in doc_ids:
            doc = doc_repo.get_by_id(did)
            if doc:
                allowed_filenames.append(Path(doc.file_path).name)
                target_docs.append(doc)
    else:
        # Không chọn cụ thể → lấy tất cả tài liệu đã INDEXED
        target_docs = doc_repo.get_indexed()

    # ----------------------------------------------------------------
    # Thử Full-Context Mode: đọc toàn bộ nội dung tài liệu
    # ----------------------------------------------------------------
    combined_content = ""
    doc_labels = []

    for doc in target_docs:
        content_data = get_document_content(doc.id, doc_repo)
        if content_data and content_data.get("content"):
            content = content_data["content"]
            doc_labels.append(doc.file_name)

            if len(target_docs) == 1:
                # 1 tài liệu: không cần header phân cách
                combined_content = content
            else:
                # Nhiều tài liệu: thêm header phân cách
                combined_content += (
                    f"\n\n{'='*60}\n"
                    f"TÀI LIỆU: {doc.file_name}\n"
                    f"{'='*60}\n"
                    f"{content}"
                )

    # Quyết định chế độ dựa trên tổng độ dài nội dung
    use_full_context = (
        combined_content
        and len(combined_content) <= FULL_CONTEXT_THRESHOLD_CHARS
    )

    # ----------------------------------------------------------------
    # FULL-CONTEXT MODE: Đưa toàn bộ nội dung vào LLM
    # ----------------------------------------------------------------
    if use_full_context:
        mode = "full_context"
        context_chars = len(combined_content)
        filename_label = ", ".join(doc_labels) if doc_labels else ""

        print(f"[Full-Context Mode] {len(doc_labels)} tài liệu, {context_chars:,} ký tự")

        try:
            answer = llm_service.generate_answer_full_context(
                question=question,
                full_text=combined_content,
                filename=filename_label,
                history=history,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Lỗi sinh câu trả lời (Full-Context): {str(e)}")

        # Nguồn trích dẫn = các tài liệu đã đọc
        sources_for_response = [
            SourceInfo(file_name=name, relevance_score=1.0)
            for name in doc_labels
        ]
        sources_for_db = doc_labels

    # ----------------------------------------------------------------
    # RAG MODE: Tài liệu quá lớn → dùng vector search + top_k lớn
    # ----------------------------------------------------------------
    else:
        mode = "rag"
        print(f"[RAG Mode] Nội dung quá lớn ({len(combined_content):,} ký tự), dùng vector search top_k={top_k}")

        try:
            search_results: List[SearchResult] = llm_service.search(
                question, top_k=top_k, allowed_filenames=allowed_filenames
            )
        except Exception as e:
            raise RuntimeError(f"Lỗi tìm kiếm: {str(e)}")

        context_chars = sum(len(r.chunk.text) for r in search_results)

        try:
            answer = llm_service.generate_answer(
                question=question,
                context_chunks=search_results,
                history=history,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Lỗi sinh câu trả lời (RAG): {str(e)}")

        # Build sources
        sources_for_response = []
        sources_for_db = []
        seen = set()
        for r in search_results:
            fn = r.chunk.filename
            if fn not in seen:
                seen.add(fn)
                sources_for_response.append(SourceInfo(file_name=fn, relevance_score=round(r.score, 3)))
                sources_for_db.append(fn)

    # ----------------------------------------------------------------
    # Lưu lịch sử
    # ----------------------------------------------------------------
    hist = hist_repo.create(
        question=question,
        answer=answer,
        sources=sources_for_db,
        model_used=llm_service._model_name,
    )

    return AskResponse(
        question=question,
        answer=answer,
        sources=sources_for_response,
        model_used=llm_service._model_name,
        history_id=hist.id,
        mode=mode,
        context_chars=context_chars,
    )


def summarize_document(
    doc_id: int,
    db: Session,
    llm_service: LLMService,
) -> DocumentSummaryResponse:
    """
    Tóm tắt tài liệu — Full-Context khi có thể, phân đoạn khi tài liệu lớn.
    Không giới hạn độ dài nội dung.
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    # Nếu đã có summary → trả luôn
    if doc.summary:
        return DocumentSummaryResponse(
            id=doc.id,
            file_name=doc.file_name,
            summary=doc.summary,
            model_used=llm_service._model_name,
        )

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    content = content_data["content"]
    max_chars = LLM_MAX_CONTENT_CHARS  # Dùng giới hạn đã tăng rất cao

    # Nếu nội dung vừa → tóm tắt thẳng toàn bộ
    if len(content) <= max_chars:
        prompt = f"TÀI LIỆU: {doc.file_name}\n\nNỘI DUNG:\n{content}"
        summary = llm_service.chat_direct(prompt=prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)
    else:
        # Chia thành các phần và tóm tắt từng phần (tài liệu rất lớn)
        segment_size = max_chars // 2  # Mỗi phần nhỏ hơn để có room cho prompt
        segments = [content[i:i + segment_size] for i in range(0, len(content), segment_size)]

        print(f"[Summarize] Tài liệu dài ({len(content):,} ký tự), chia {len(segments)} đoạn...")

        part_summaries = []
        for idx, part in enumerate(segments, 1):
            part_label = f"[Phần {idx}/{len(segments)}] "
            prompt = f"{part_label}TÀI LIỆU: {doc.file_name}\n\nNỘI DUNG:\n{part}"
            partial = llm_service.chat_direct(prompt=prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)
            part_summaries.append(f"**Phần {idx}:**\n{partial}")

        # Tóm tắt tổng hợp từ các tóm tắt con
        combined = "\n\n".join(part_summaries)
        if len(combined) > max_chars:
            combined = combined[:max_chars]

        final_prompt = (
            f"Dưới đây là tóm tắt từng phần của tài liệu '{doc.file_name}'.\n"
            f"Hãy tổng hợp thành 1 bản tóm tắt hoàn chỉnh, mạch lạc:\n\n{combined}"
        )
        summary = llm_service.chat_direct(
            prompt=final_prompt,
            system_prompt="Tổng hợp và tóm tắt lại bằng tiếng Việt, đầy đủ, có bullet points."
        )

    doc_repo.update_summary(doc_id, summary)

    return DocumentSummaryResponse(
        id=doc.id,
        file_name=doc.file_name,
        summary=summary,
        model_used=llm_service._model_name,
    )


def generate_exercise(
    doc_id: int,
    exercise_type: str,
    count: int,
    db: Session,
    llm_service: LLMService,
) -> ExerciseResponse:
    """Tạo bài tập từ nội dung đầy đủ của tài liệu."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    # Đọc tối đa nội dung có thể (không cắt cứng)
    content = llm_service._safe_truncate(content_data["content"], LLM_MAX_CONTENT_CHARS)

    prompt = (
        f"TẠO {exercise_type.upper()} TỪ TÀI LIỆU: {doc.file_name}\n\n"
        f"YÊU CẦU: Tạo {count} câu {exercise_type} rõ ràng, có đáp án chi tiết.\n"
        f"Câu hỏi phải bám sát nội dung tài liệu.\n\n"
        f"NỘI DUNG TÀI LIỆU:\n{content}"
    )

    exercise_text = llm_service.chat_direct(
        prompt=prompt,
        system_prompt=f"Bạn là trợ lý giáo dục. Tạo {exercise_type} từ tài liệu bằng tiếng Việt, câu hỏi rõ ràng và có đáp án."
    )

    return ExerciseResponse(
        id=doc.id,
        file_name=doc.file_name,
        exercise_text=exercise_text,
        model_used=llm_service._model_name,
    )
