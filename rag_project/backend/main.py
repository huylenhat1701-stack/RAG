"""
FastAPI Main Application
Khởi tạo ứng dụng, đăng ký routes và lifecycle events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db.database import init_db, SessionLocal
from .api.routes import router
from .repositories.document_repo import DocumentRepository
from .services.llm_service import get_llm_service
from .services.document_service import reload_indexed_documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: khởi tạo DB và reload documents khi start."""
    # === STARTUP ===
    print("🚀 Đang khởi động RAG Backend...")

    # 1. Khởi tạo SQLite tables
    init_db()

    # 2. Reload tài liệu đã index từ lần chạy trước
    try:
        llm_service = get_llm_service()
        with SessionLocal() as db:
            doc_repo = DocumentRepository(db)
            reload_indexed_documents(doc_repo, llm_service)
    except Exception as e:
        print(f"⚠️ Không reload được tài liệu: {e}")

    print("✅ RAG Backend sẵn sàng!")
    yield

    # === SHUTDOWN ===
    print("👋 RAG Backend đang tắt...")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="🤖 RAG Q&A API",
    description=(
        "Hệ thống Hỏi Đáp Thông Minh sử dụng kiến trúc RAG "
        "(Retrieval-Augmented Generation)\n\n"
        "**Sinh viên:** Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090\n\n"
        "**Công nghệ:** FastAPI + ChromaDB + CodexOAuth (GPT-5)"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",    # Swagger UI
    redoc_url="/redoc",  # ReDoc
)

# CORS - Cho phép Streamlit frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production: chỉ định rõ origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký tất cả routes
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Gốc"])
def root():
    """Thông tin ứng dụng."""
    return {
        "app": "RAG Q&A System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
