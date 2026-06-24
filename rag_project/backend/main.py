"""
FastAPI Main Application
Khởi tạo ứng dụng, đăng ký routes và lifecycle events.
"""

import sys
if sys.platform == "win32":
    import platform
    from collections import namedtuple
    _uname_result = namedtuple('uname_result', ['system', 'node', 'release', 'version', 'machine'])
    platform.uname = lambda: _uname_result(system='Windows', node='UNKNOWN', release='10', version='10.0.22631', machine='AMD64')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db.database import init_db, SessionLocal
from .api.routes import router
from .api.auth_routes import auth_router
from .repositories.document_repo import DocumentRepository
from .services.llm_service import get_llm_service
from .services.document_service import reload_indexed_documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: khởi tạo DB và reload documents khi start."""
    # === STARTUP ===
    print("[START] Dang khoi dong Smart Document Reader Backend...")

    # 1. Khởi tạo SQLite tables
    init_db()

    # 2. Reload tài liệu đã index từ lần chạy trước
    try:
        llm_service = get_llm_service()
        with SessionLocal() as db:
            doc_repo = DocumentRepository(db)
            reload_indexed_documents(doc_repo, llm_service)
    except Exception as e:
        print(f"[WARN] Khong reload duoc tai lieu: {e}")

    print("[OK] Smart Document Reader Backend san sang!")
    yield

    # === SHUTDOWN ===
    print("[STOP] Smart Document Reader Backend dang tat...")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="Smart Document Reader API",
    description=(
        "**Hệ thống Đọc Tài Liệu Thông Minh** sử dụng kiến trúc RAG "
        "(Retrieval-Augmented Generation)\n\n"
        "### Tính năng chính:\n"
        "- 📁 **Upload & Quản lý** tài liệu (PDF, DOCX, TXT, MD)\n"
        "- 📖 **Đọc nội dung** tài liệu trực tuyến\n"
        "- 🤖 **Tóm tắt tự động** bằng AI\n"
        "- 💬 **Hỏi đáp thông minh** dựa trên tài liệu\n"
        "- 📚 **Lịch sử** các phiên hỏi đáp\n\n"
        "**Sinh viên:** Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090\n\n"
        "**Công nghệ:** FastAPI + ChromaDB + CodexOAuth (GPT-5)"
    ),
    version="2.0.0",
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log toàn bộ traceback khi có unhandled exception."""
    tb = traceback.format_exc()
    print(f"[UNHANDLED ERROR] {request.method} {request.url}")
    print(tb)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": tb[-1000:]},
    )

# Đăng ký tất cả routes
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth")


@app.get("/", tags=["Gốc"])
def root():
    """Thông tin ứng dụng."""
    return {
        "app": "Smart Document Reader",
        "version": "2.0.0",
        "description": "Hệ thống Đọc Tài Liệu Thông Minh",
        "features": [
            "Upload & quan ly tai lieu",
            "Doc noi dung truc tuyen",
            "Tom tat tai lieu bang AI",
            "Hoi dap thong minh (RAG)",
        ],
        "docs": "/docs",
        "health": "/api/v1/health",
    }
