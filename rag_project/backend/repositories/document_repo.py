"""
Document Repository - Thao tác CRUD với bảng documents
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from ..models.domain import Document


class DocumentRepository:
    """Repository Pattern cho bảng documents."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, file_name: str, file_path: str, file_size: int, file_type: str) -> Document:
        """Tạo bản ghi tài liệu mới với trạng thái UPLOADED."""
        doc = Document(
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            status="UPLOADED",
            chunk_count=0,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, doc_id: int) -> Optional[Document]:
        """Lấy tài liệu theo ID."""
        return self.db.query(Document).filter(Document.id == doc_id).first()

    def get_all(self) -> List[Document]:
        """Lấy tất cả tài liệu, mới nhất trước."""
        return self.db.query(Document).order_by(Document.uploaded_at.desc()).all()

    def get_indexed(self) -> List[Document]:
        """Lấy tất cả tài liệu đã được index."""
        return self.db.query(Document).filter(Document.status == "INDEXED").all()

    def update_status(self, doc_id: int, status: str, chunk_count: int = None, error: str = None) -> Optional[Document]:
        """Cập nhật trạng thái xử lý tài liệu."""
        doc = self.get_by_id(doc_id)
        if doc:
            doc.status = status
            if chunk_count is not None:
                doc.chunk_count = chunk_count
            if error:
                doc.error_message = error
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def delete(self, doc_id: int) -> bool:
        """Xóa tài liệu theo ID."""
        doc = self.get_by_id(doc_id)
        if doc:
            self.db.delete(doc)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """Đếm tổng số tài liệu."""
        return self.db.query(Document).count()

    def count_indexed(self) -> int:
        """Đếm tài liệu đã index."""
        return self.db.query(Document).filter(Document.status == "INDEXED").count()
