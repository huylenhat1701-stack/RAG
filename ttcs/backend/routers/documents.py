import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

import config

try:
    import database
    from models import DocumentRecord, DocumentStatus, DocumentUploadResponse
    from services.ingestion_service import DocumentIngestionService
except ImportError:
    from backend import database
    from backend.models import DocumentRecord, DocumentStatus, DocumentUploadResponse
    from backend.services.ingestion_service import DocumentIngestionService

from pipeline.vector_store import ChromaVectorStore

router = APIRouter(prefix="/documents", tags=["documents"])
ingestion_service = DocumentIngestionService()
chroma_client = ChromaVectorStore()

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Loại file không hợp lệ. Chỉ hỗ trợ PDF/DOCX/TXT.")

        document_id = str(uuid.uuid4())
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        safe_name = f"{document_id}_{Path(filename).name}"
        file_path = os.path.join(config.UPLOAD_DIR, safe_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        record = DocumentRecord(
            id=document_id,
            filename=filename,
            file_type=ext,
            status=DocumentStatus.UPLOADED,
            created_at=datetime.now(timezone.utc).isoformat(),
            chunk_count=0,
        )
        database.insert_document(record)
        background_tasks.add_task(ingestion_service.ingest, document_id, file_path)

        return DocumentUploadResponse(
            document_id=document_id,
            filename=filename,
            status=DocumentStatus.UPLOADED.value,
            message="Tài liệu đã được tải lên, đang indexing nền.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi upload tài liệu: {exc}") from exc


@router.get("", response_model=List[DocumentRecord])
async def list_documents():
    try:
        docs = database.get_all_documents()
        docs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return [DocumentRecord(**doc) for doc in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách tài liệu: {exc}") from exc


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    try:
        doc = database.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

        chroma_client.delete_document(document_id)

        upload_dir = Path(config.UPLOAD_DIR)
        pattern = f"{document_id}_*"
        for file_path in upload_dir.glob(pattern):
            if file_path.is_file():
                file_path.unlink()

        database.delete_document(document_id)
        return {"message": "Đã xóa thành công"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa tài liệu: {exc}") from exc
