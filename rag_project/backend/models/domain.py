"""
Domain Models - SQLAlchemy ORM
Định nghĩa 2 bảng: documents và chat_history
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger
from sqlalchemy.sql import func

from ..db.database import Base


class Document(Base):
    """
    Bảng quản lý tài liệu đã upload.

    Trạng thái (status):
        UPLOADED  → Đã nhận file, chưa xử lý
        INDEXING  → Đang chunk & embed
        INDEXED   → Đã lưu vào ChromaDB, sẵn sàng tìm kiếm
        ERROR     → Xảy ra lỗi khi xử lý
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)                   # Tên file gốc
    file_path = Column(String(512), nullable=False)                   # Đường dẫn lưu trữ
    file_size = Column(BigInteger, default=0)                          # Kích thước bytes
    file_type = Column(String(20), nullable=True)                     # pdf, txt, docx
    status = Column(String(20), default="UPLOADED")                   # Trạng thái
    chunk_count = Column(Integer, default=0)                          # Số chunk đã tạo
    error_message = Column(Text, nullable=True)                       # Lỗi nếu có
    summary = Column(Text, nullable=True)                             # Tóm tắt tài liệu bởi AI
    content_preview = Column(Text, nullable=True)                     # 500 ký tự đầu tiên
    page_count = Column(Integer, default=0)                           # Số trang (PDF)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class ChatHistory(Base):
    """
    Bảng lưu trữ lịch sử hỏi đáp.
    """
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question = Column(Text, nullable=False)                           # Câu hỏi người dùng
    answer = Column(Text, nullable=False)                             # Câu trả lời AI
    sources_json = Column(Text, nullable=True)                        # JSON list tên file nguồn
    model_used = Column(String(50), nullable=True)                    # Model LLM đã dùng
    created_at = Column(DateTime, default=datetime.utcnow)
