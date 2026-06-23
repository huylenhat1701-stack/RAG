"""
Database Setup - SQLite với SQLAlchemy
Tạo 2 bảng: documents và chat_history
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..core.config import DATABASE_URL


# ============================================================
# SQLAlchemy Engine & Session
# ============================================================
# NOTE: Giới hạn concurrency của SQLite trong production:
# - SQLite WAL mode: hỗ trợ nhiều reader đồng thời, chỉ 1 writer tại một thời điểm
# - Phù hợp với prototype/đồ án dưới 10 concurrent users
# - Nếu tịnh trạng > 10 user đồng thời hoặc write-heavy → cân nhắc migrate sang PostgreSQL
# - Để migrate: đổi DATABASE_URL • chạy alembic migrate • xóa check_same_thread arg
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Cần thiết cho SQLite multi-thread
    echo=False,
)

# Bật WAL mode cho SQLite: cải thiện hiệu suất đồng thời (nhiều reader + 1 writer)
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")  # Cân bằng tốc độ và độ an toàn
        cursor.execute("PRAGMA busy_timeout=5000")   # 5s timeout trước khi bỏ qua
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ============================================================
# Dependency Injection cho FastAPI
# ============================================================
def get_db():
    """FastAPI dependency - trả về DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Khởi tạo database - tạo tất cả bảng."""
    # Import các model để SQLAlchemy nhận diện
    from ..models.domain import User, Document, ChatHistory, QuizHistory, UserKnowledge  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("[OK] Database da duoc khoi tao.")
