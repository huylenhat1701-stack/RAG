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
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Cần thiết cho SQLite
    echo=False,
)

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
    from ..models.domain import Document, ChatHistory  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("✅ Database đã được khởi tạo.")
