"""
Document Repository - Thao tác CRUD với bảng documents
Tất cả truy vấn đều lọc theo user_id để đảm bảo data isolation.
"""

from typing import List, Optional
from sqlalchemy.orm import Session  # type: ignore

from ..models.domain import Document


class DocumentRepository:
    """Repository Pattern cho bảng documents."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, file_name: str, file_path: str, file_size: int, file_type: str, user_id: int = None) -> Document:
        """Tạo bản ghi tài liệu mới với trạng thái UPLOADED."""
        doc = Document(
            user_id=user_id,
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

    def get_by_id(self, doc_id: int, user_id: int = None) -> Optional[Document]:
        """Lấy tài liệu theo ID. Nếu có user_id thì kiểm tra quyền sở hữu."""
        query = self.db.query(Document).filter(Document.id == doc_id)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.first()

    def get_all(self, user_id: int = None) -> List[Document]:
        """Lấy tất cả tài liệu của user, mới nhất trước."""
        query = self.db.query(Document)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.order_by(Document.uploaded_at.desc()).all()

    def get_indexed(self, user_id: int = None) -> List[Document]:
        """Lấy tất cả tài liệu đã được index (của user)."""
        query = self.db.query(Document).filter(Document.status == "INDEXED")
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.all()

    def update_status(self, doc_id: int, status: str, chunk_count: int = None, error: str = None) -> Optional[Document]:
        """Cập nhật trạng thái xử lý tài liệu."""
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = status
            if chunk_count is not None:
                doc.chunk_count = chunk_count
            if error:
                doc.error_message = error
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def update_summary(self, doc_id: int, summary: str) -> Optional[Document]:
        """Cập nhật tóm tắt tài liệu."""
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.summary = summary
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def update_content_preview(self, doc_id: int, preview: str, page_count: int = 0) -> Optional[Document]:
        """Cập nhật preview nội dung và số trang."""
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.content_preview = preview
            doc.page_count = page_count
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def delete(self, doc_id: int) -> bool:
        """Xóa tài liệu theo ID."""
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            self.db.delete(doc)
            self.db.commit()
            return True
        return False

    def count(self, user_id: int = None) -> int:
        """Đếm tổng số tài liệu (của user)."""
        query = self.db.query(Document)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.count()

    def count_indexed(self, user_id: int = None) -> int:
        """Đếm tài liệu đã index (của user)."""
        query = self.db.query(Document).filter(Document.status == "INDEXED")
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.count()
