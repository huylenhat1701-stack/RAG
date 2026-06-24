"""
API Routes - Các endpoints RESTful (Có xác thực user)
POST /documents/upload       - Upload tài liệu
GET  /documents              - Danh sách tài liệu
GET  /documents/{id}/content - Xem nội dung tài liệu
POST /documents/{id}/summarize - Tóm tắt tài liệu bằng AI
DELETE /documents/{id}       - Xóa tài liệu
POST /chat/ask               - Hỏi đáp RAG
GET  /chat/history           - Lịch sử hỏi đáp
DELETE /chat/history         - Xóa lịch sử
GET  /health                 - Kiểm tra trạng thái (public)
"""

import json
import math
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..api.deps import get_current_user
from ..models.domain import User
from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, get_llm_service
from ..services.document_service import (
    save_upload_file,
    process_and_index_document,
    get_document_content,
    get_safe_file_path,
)
from ..services.rag_service import answer_question, summarize_document, generate_exercise, generate_quiz, generate_learning_path
from ..models.schemas import (
    DocumentResponse, DocumentListResponse,
    DocumentContentResponse, DocumentSummaryResponse,
    AskRequest, AskResponse,
    ExerciseRequest, ExerciseResponse,
    QuizRequest, QuizResponse, QuizSubmitRequest, QuizSubmitResponse,
    LearningPathRequest, LearningPathResponse,
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
    current_user: User = Depends(get_current_user),
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
        user_id=current_user.id,
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

    # Return Pydantic schema explicitly to avoid DetachedInstanceError
    # (SQLAlchemy session closes before FastAPI serializes the ORM object)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Danh sách tài liệu",
    tags=["Tài liệu"],
)
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách tất cả tài liệu của user."""
    doc_repo = DocumentRepository(db)
    docs = doc_repo.get_all(user_id=current_user.id)
    return DocumentListResponse(total=len(docs), documents=docs)


@router.get(
    "/documents/{doc_id}/content",
    response_model=DocumentContentResponse,
    summary="Xem nội dung tài liệu",
    description="Đọc và trả về nội dung đầy đủ của tài liệu theo ID.",
    tags=["Tài liệu"],
)
def read_document_content(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đọc nội dung đầy đủ của tài liệu."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
):
    """Tóm tắt tài liệu bằng AI (Local LLM)."""
    # Kiểm tra quyền sở hữu
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

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
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa tài liệu theo ID."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    # Xóa file vật lý
    file_path = get_safe_file_path(doc.file_path)
    if file_path.exists():
        file_path.unlink()
    # Xóa file extracted nếu có
    txt_path = file_path.with_suffix(".extracted.txt")
    if txt_path.exists():
        txt_path.unlink()

    doc_repo.delete(doc_id)
    return MessageResponse(message=f"Đã xóa tài liệu: {doc.file_name}")


@router.get(
    "/documents/{doc_id}/download",
    summary="Tải file tài liệu hoặc file text đã xuất",
    tags=["Tài liệu"],
)
def download_document(
    doc_id: int,
    source: str = Query("extracted", regex="^(original|extracted)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cho phép tải file gốc hoặc file text đã xuất từ tài liệu."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    file_path = get_safe_file_path(doc.file_path)
    if source == "original":
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File gốc không tồn tại")
        return FileResponse(str(file_path), filename=file_path.name)

    extracted_path = file_path.with_suffix(".extracted.txt")
    if not extracted_path.exists():
        content_data = get_document_content(doc_id, doc_repo)
        if not content_data or not content_data.get("content"):
            raise HTTPException(status_code=404, detail="Không thể tạo file text từ tài liệu")
        extracted_path.write_text(content_data["content"], encoding="utf-8")

    return FileResponse(str(extracted_path), filename=extracted_path.name, media_type="text/plain")


@router.post(
    "/documents/{doc_id}/exercise",
    response_model=ExerciseResponse,
    summary="Tạo bài tập từ tài liệu bằng AI",
    tags=["Tài liệu"],
)
def create_exercise(
    doc_id: int,
    request: ExerciseRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
):
    # Kiểm tra quyền
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    try:
        return generate_exercise(
            doc_id=doc_id,
            exercise_type=request.exercise_type,
            count=request.count or 5,
            db=db,
            llm_service=llm_service,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo bài tập: {str(e)}")


@router.post(
    "/documents/{doc_id}/quiz",
    response_model=QuizResponse,
    summary="Tạo bộ câu hỏi thi trắc nghiệm có cấu trúc",
    tags=["Tài liệu"],
)
def create_quiz(
    doc_id: int,
    request: QuizRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
):
    """Tạo bộ câu hỏi thi trắc nghiệm tương tác từ tài liệu."""
    # Thiết lập temperature nếu người dùng truyền vào
    original_temperature = llm_service._temperature
    if request.temperature is not None:
        llm_service._temperature = request.temperature
    try:
        return generate_quiz(
            doc_id=doc_id,
            count=request.count or 10,
            db=db,
            llm_service=llm_service,
            session_id=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo quiz: {str(e)}")
    finally:
        llm_service._temperature = original_temperature


@router.post(
    "/documents/{doc_id}/quiz/submit",
    response_model=QuizSubmitResponse,
    summary="Nộp kết quả câu hỏi trắc nghiệm để cập nhật Adaptive Tutor (BKT)",
    tags=["Tài liệu"],
)
def submit_quiz_result(
    doc_id: int,
    request: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật xác suất hiểu bài của người dùng dựa trên kết quả trả lời."""
    from ..services.adaptive_tutor_service import adaptive_tutor_service
    try:
        new_prob = adaptive_tutor_service.update_knowledge(
            session_id=str(current_user.id),
            doc_id=doc_id,
            chunk_id=request.chunk_id,
            is_correct=1 if request.is_correct else 0,
            db=db
        )
        return QuizSubmitResponse(success=True, new_probability=new_prob)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật BKT: {str(e)}")

@router.post(
    "/documents/{doc_id}/learning-path",
    response_model=LearningPathResponse,
    summary="Tạo lộ trình học tập cá nhân hóa",
    description="Dựa trên câu trả lời sai và dữ liệu BKT, AI tạo lộ trình ôn tập phù hợp.",
    tags=["Tài liệu"],
)
def create_learning_path(
    doc_id: int,
    request: LearningPathRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
):
    """Tạo lộ trình học tập cá nhân hóa sau khi người dùng hoàn thành quiz."""
    # Kiểm tra quyền
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    try:
        return generate_learning_path(
            doc_id=doc_id,
            session_id=str(current_user.id),
            wrong_chunk_ids=request.wrong_chunk_ids,
            db=db,
            llm_service=llm_service,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo lộ trình: {str(e)}")

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
    current_user: User = Depends(get_current_user),
):
    """Hỏi đáp thông minh dựa trên tài liệu đã upload."""
    # Thiết lập temperature nếu người dùng truyền vào
    original_temperature = llm_service._temperature
    if request.temperature is not None:
        llm_service._temperature = request.temperature
    try:
        response = answer_question(
            question=request.question,
            top_k=request.top_k,
            db=db,
            llm_service=llm_service,
            history=[msg.dict() for msg in request.history] if request.history else None,
            doc_ids=request.doc_ids if request.doc_ids else None,
            user_id=current_user.id,
        )
        return response
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Lỗi xử lý câu hỏi: {str(e)}")
    finally:
        # Khôi phục temperature về default để không ảnh hưởng request khác
        llm_service._temperature = original_temperature


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
    current_user: User = Depends(get_current_user),
):
    """Lấy lịch sử các phiên hỏi đáp của user."""
    hist_repo = HistoryRepository(db)
    histories = hist_repo.get_all(limit=limit, skip=skip, user_id=current_user.id)
    total = hist_repo.count(user_id=current_user.id)
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
def clear_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa toàn bộ lịch sử hỏi đáp của user."""
    hist_repo = HistoryRepository(db)
    deleted = hist_repo.clear_all(user_id=current_user.id)
    return MessageResponse(message=f"Đã xóa {deleted} bản ghi lịch sử.")




# ============================================================
# HEALTH CHECK (public — không cần auth)
# ============================================================

@router.get(
    "/health",
    summary="Kiem tra he thong",
    tags=["He thong"],
)
def health_check(llm_service: LLMService = Depends(get_llm_service)):
    """Kiem tra trang thai ket noi Local LLM va RAG."""
    status = llm_service.is_healthy()
    return {
        "status": "ok" if status.get("codex_connected") else "warning",
        **status,
    }


# ============================================================
# EVALUATION ENDPOINTS
# ============================================================

@router.get(
    "/evaluate/bkt",
    summary="Lay chi so danh gia BKT tu database",
    tags=["Danh gia"],
)
def get_bkt_stats(db: Session = Depends(get_db)):
    """
    Lay thong ke BKT tu database:
    - Tong so session, tong so lan tra loi
    - Phan phoi diem BKT (thap/trung/cao)
    - Accuracy du doan cua thuat toan BKT
    - Ty le dung/sai theo tung muc BKT
    """
    from ..models.domain import QuizHistory, UserKnowledge

    BKT_P_SLIP = 0.1
    BKT_P_GUESS = 0.2
    BKT_THRESHOLD = 60

    histories = db.query(QuizHistory).all()
    knowledges = db.query(UserKnowledge).all()

    total_answers = len(histories)
    total_sessions = len(set(h.session_id for h in histories))
    total_chunks_tracked = len(knowledges)

    # Phan phoi BKT score
    low_pct    = sum(1 for k in knowledges if k.probability < 40)
    mid_pct    = sum(1 for k in knowledges if 40 <= k.probability < 70)
    high_pct   = sum(1 for k in knowledges if k.probability >= 70)

    # Accuracy: lay tung record, so sanh du doan vs thuc te
    uk_map = {(k.session_id, k.chunk_id): k.probability for k in knowledges}
    correct_preds = 0
    y_true_all = []
    y_prob_all = []

    for h in histories:
        bkt_prob = uk_map.get((h.session_id, h.chunk_id), 50)
        predicted = 1 if bkt_prob >= BKT_THRESHOLD else 0
        if predicted == h.is_correct:
            correct_preds += 1
        p_know = bkt_prob / 100.0
        p_correct = p_know * (1 - BKT_P_SLIP) + (1 - p_know) * BKT_P_GUESS
        y_true_all.append(h.is_correct)
        y_prob_all.append(p_correct)

    accuracy = round(correct_preds / total_answers, 4) if total_answers > 0 else 0

    # AUC-ROC thu cong
    pos = [p for p, a in zip(y_prob_all, y_true_all) if a == 1]
    neg = [p for p, a in zip(y_prob_all, y_true_all) if a == 0]
    auc = 0.5
    if pos and neg:
        n_correct_pairs = sum(1 for p in pos for n_val in neg if p > n_val)
        n_tie_pairs = sum(1 for p in pos for n_val in neg if p == n_val)
        auc = (n_correct_pairs + 0.5 * n_tie_pairs) / (len(pos) * len(neg))

    # Log-Loss
    eps = 1e-9
    log_loss = 0.0
    if y_prob_all:
        log_loss = -sum(
            a * math.log(max(p, eps)) + (1 - a) * math.log(max(1 - p, eps))
            for p, a in zip(y_prob_all, y_true_all)
        ) / len(y_true_all)

    # Accuracy theo nhom BKT
    group_stats = {"low": {"correct": 0, "total": 0}, "mid": {"correct": 0, "total": 0}, "high": {"correct": 0, "total": 0}}
    for h in histories:
        bkt_prob = uk_map.get((h.session_id, h.chunk_id), 50)
        if bkt_prob < 40:
            g = "low"
        elif bkt_prob < 70:
            g = "mid"
        else:
            g = "high"
        group_stats[g]["total"] += 1
        if h.is_correct:
            group_stats[g]["correct"] += 1

    group_accuracy = {}
    for g, s in group_stats.items():
        group_accuracy[g] = round(s["correct"] / s["total"], 3) if s["total"] > 0 else 0

    return {
        "total_answers":       total_answers,
        "total_sessions":      total_sessions,
        "total_chunks_tracked": total_chunks_tracked,
        "accuracy":            round(accuracy, 3),
        "auc_roc":             round(auc, 3),
        "log_loss":            round(log_loss, 3),
        "distribution": {
            "low_count":   low_pct,
            "mid_count":   mid_pct,
            "high_count":  high_pct,
        },
        "group_accuracy": group_accuracy,
        "correct_total":  sum(h.is_correct for h in histories),
        "wrong_total":    sum(1 - h.is_correct for h in histories),
    }


@router.get(
    "/evaluate/rag-stats",
    summary="Lay thong ke chat luong RAG tu lich su hoi dap",
    tags=["Danh gia"],
)
def get_rag_stats(db: Session = Depends(get_db)):
    """
    Phan tich lich su hoi dap trong ChatHistory de tao thong ke RAG co ban:
    - Tong so cau hoi, phan bo mode (full_context vs rag)
    - Trung binh chieu dai cau tra loi
    """
    from ..models.domain import ChatHistory

    histories = db.query(ChatHistory).all()
    total = len(histories)
    if total == 0:
        return {"total_questions": 0, "message": "Chua co lich su hoi dap nao."}

    avg_answer_len = round(sum(len(h.answer) for h in histories) / total)
    avg_question_len = round(sum(len(h.question) for h in histories) / total)

    # Phan tich nguon (sources)
    multi_source = 0
    for h in histories:
        try:
            srcs = json.loads(h.sources_json) if h.sources_json else []
            if len(srcs) > 1:
                multi_source += 1
        except Exception:
            pass

    return {
        "total_questions":     total,
        "avg_answer_length":   avg_answer_len,
        "avg_question_length": avg_question_len,
        "multi_source_answers": multi_source,
        "multi_source_pct":    round(multi_source / total * 100, 1) if total > 0 else 0,
    }
