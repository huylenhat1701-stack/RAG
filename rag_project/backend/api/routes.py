"""
API Routes - Các endpoints RESTful
POST /documents/upload       - Upload tài liệu
GET  /documents              - Danh sách tài liệu
GET  /documents/{id}/content - Xem nội dung tài liệu
POST /documents/{id}/summarize - Tóm tắt tài liệu bằng AI
DELETE /documents/{id}       - Xóa tài liệu
POST /chat/ask               - Hỏi đáp RAG
GET  /chat/history           - Lịch sử hỏi đáp
DELETE /chat/history         - Xóa lịch sử
GET  /health                 - Kiểm tra trạng thái
"""

import threading
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, get_llm_service
from ..services.document_service import (
    save_upload_file,
    process_and_index_document,
    get_document_content,
)
from ..services.rag_service import answer_question, summarize_document
from ..models.schemas import (
    DocumentResponse, DocumentListResponse,
    DocumentContentResponse, DocumentSummaryResponse,
    AskRequest, AskResponse,
    ChatHistoryResponse, ChatHistoryListResponse,
    MessageResponse,
)

router = APIRouter()

# Giới hạn định dạng file hỗ trợ
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".md"}
MAX_FILE_SIZE_MB = 50


# ============================================================
# DOCUMENT ENDPOINTS
# ============================================================

@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    summary="Upload tài liệu",
    description="Upload file PDF, TXT hoặc DOCX. File sẽ được xử lý và index vào hệ thống.",
    tags=["Tài liệu"],
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File tài liệu cần upload"),
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Upload và xử lý một tài liệu mới."""
    # Kiểm tra định dạng file
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file_ext}. Chấp nhận: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Lưu file vật lý
    safe_filename = Path(file.filename).name  # Tránh path traversal
    saved_path, file_size = save_upload_file(file.file, safe_filename)

    # Kiểm tra kích thước
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"File quá lớn. Tối đa {MAX_FILE_SIZE_MB}MB."
        )

    # Tạo bản ghi trong DB
    doc_repo = DocumentRepository(db)
    doc = doc_repo.create(
        file_name=safe_filename,
        file_path=str(saved_path),
        file_size=file_size,
        file_type=file_ext.lstrip("."),
    )

    # Xử lý và index trong background
    def _process():
        from ..db.database import SessionLocal
        with SessionLocal() as bg_db:
            bg_repo = DocumentRepository(bg_db)
            try:
                process_and_index_document(
                    doc_id=doc.id,
                    file_path=saved_path,
                    file_type=file_ext.lstrip("."),
                    doc_repo=bg_repo,
                    llm_service=llm_service,
                )
            except Exception as e:
                print(f"Background indexing error: {e}")

    background_tasks.add_task(_process)

    return doc


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Danh sách tài liệu",
    tags=["Tài liệu"],
)
def list_documents(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả tài liệu đã upload."""
    doc_repo = DocumentRepository(db)
    docs = doc_repo.get_all()
    return DocumentListResponse(total=len(docs), documents=docs)


@router.get(
    "/documents/{doc_id}/content",
    response_model=DocumentContentResponse,
    summary="Xem nội dung tài liệu",
    description="Đọc và trả về nội dung đầy đủ của tài liệu theo ID.",
    tags=["Tài liệu"],
)
def read_document_content(doc_id: int, db: Session = Depends(get_db)):
    """Đọc nội dung đầy đủ của tài liệu."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data:
        raise HTTPException(status_code=404, detail="Không thể đọc nội dung tài liệu")

    return DocumentContentResponse(
        id=doc.id,
        file_name=doc.file_name,
        file_type=doc.file_type,
        content=content_data["content"],
        page_count=content_data["page_count"],
        word_count=content_data["word_count"],
        char_count=content_data["char_count"],
    )


@router.post(
    "/documents/{doc_id}/summarize",
    response_model=DocumentSummaryResponse,
    summary="Tóm tắt tài liệu bằng AI",
    description="Sử dụng AI để tóm tắt nội dung tài liệu. Kết quả được cache lại.",
    tags=["Tài liệu"],
)
def summarize_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Tóm tắt tài liệu bằng AI (CodexOAuth)."""
    try:
        return summarize_document(doc_id, db, llm_service)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tóm tắt: {str(e)}")


@router.delete(
    "/documents/{doc_id}",
    response_model=MessageResponse,
    summary="Xóa tài liệu",
    tags=["Tài liệu"],
)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Xóa tài liệu theo ID."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    # Xóa file vật lý
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()
    # Xóa file extracted nếu có
    txt_path = file_path.with_suffix(".extracted.txt")
    if txt_path.exists():
        txt_path.unlink()

    doc_repo.delete(doc_id)
    return MessageResponse(message=f"Đã xóa tài liệu: {doc.file_name}")


# ============================================================
# CHAT / Q&A ENDPOINTS
# ============================================================

@router.post(
    "/chat/ask",
    response_model=AskResponse,
    summary="Đặt câu hỏi",
    description="Đặt câu hỏi để hệ thống RAG truy xuất tài liệu và tạo câu trả lời.",
    tags=["Hỏi & Đáp"],
)
def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Hỏi đáp thông minh dựa trên tài liệu đã upload."""
    try:
        response = answer_question(
            question=request.question,
            top_k=request.top_k,
            db=db,
            llm_service=llm_service,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {str(e)}")


@router.get(
    "/chat/history",
    response_model=ChatHistoryListResponse,
    summary="Lịch sử hỏi đáp",
    tags=["Hỏi & Đáp"],
)
def get_history(
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db),
):
    """Lấy lịch sử các phiên hỏi đáp."""
    hist_repo = HistoryRepository(db)
    histories = hist_repo.get_all(limit=limit, skip=skip)
    total = hist_repo.count()
    return ChatHistoryListResponse(
        total=total,
        histories=[ChatHistoryResponse.from_orm_with_sources(h) for h in histories],
    )


@router.delete(
    "/chat/history",
    response_model=MessageResponse,
    summary="Xóa lịch sử",
    tags=["Hỏi & Đáp"],
)
def clear_history(db: Session = Depends(get_db)):
    """Xóa toàn bộ lịch sử hỏi đáp."""
    hist_repo = HistoryRepository(db)
    deleted = hist_repo.clear_all()
    return MessageResponse(message=f"Đã xóa {deleted} bản ghi lịch sử.")


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get(
    "/health",
    summary="Kiểm tra hệ thống",
    tags=["Hệ thống"],
)
def health_check(llm_service: LLMService = Depends(get_llm_service)):
    """Kiểm tra trạng thái kết nối Codex và RAG."""
    status = llm_service.is_healthy()
    return {
        "status": "ok" if status.get("codex_connected") else "warning",
        **status,
    }
