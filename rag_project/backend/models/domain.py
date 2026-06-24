"""
Domain Models - SQLAlchemy ORM
Định nghĩa các bảng: users, documents, chat_history, quiz_history, user_knowledge
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey
from sqlalchemy.sql import func

from ..db.database import Base


class User(Base):
    """
    Bảng người dùng — xác thực và phân quyền dữ liệu.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)                           # Câu hỏi người dùng
    answer = Column(Text, nullable=False)                             # Câu trả lời AI
    sources_json = Column(Text, nullable=True)                        # JSON list tên file nguồn
    model_used = Column(String(50), nullable=True)                    # Model LLM đã dùng
    created_at = Column(DateTime, default=datetime.utcnow)


class QuizHistory(Base):
    """
    Bảng lưu lịch sử từng câu trả lời Quiz của người dùng.
    """
    __tablename__ = "quiz_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)      # Phiên làm việc / User
    doc_id = Column(Integer, nullable=False, index=True)              # File liên quan
    chunk_id = Column(String(100), nullable=False, index=True)        # Chunk kiến thức
    is_correct = Column(Integer, nullable=False)                      # 1 nếu đúng, 0 nếu sai
    timestamp = Column(DateTime, default=datetime.utcnow)
    bloom_level = Column(String(20), nullable=True, default=None)     # Cấp độ Bloom của câu hỏi này


class UserKnowledge(Base):
    """
    Bảng lưu ma trận xác suất hiểu bài (BKT) của người dùng cho từng chunk kiến thức.
    """
    __tablename__ = "user_knowledge"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    doc_id = Column(Integer, nullable=False, index=True)
    chunk_id = Column(String(100), nullable=False, index=True)
    probability = Column(Integer, default=50)                         # % hiểu bài (0 - 100), mặc định 50%
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
