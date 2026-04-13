"""
Pydantic Schemas - Request/Response Models
Dùng cho FastAPI để validate dữ liệu đầu vào/đầu ra.
"""

import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, computed_field


# ============================================================
# Document Schemas
# ============================================================
class DocumentResponse(BaseModel):
    """Schema trả về thông tin tài liệu."""
    id: int
    file_name: str
    file_size: int
    file_type: Optional[str]
    status: str
    chunk_count: int
    page_count: int = 0
    error_message: Optional[str] = None
    summary: Optional[str] = None
    content_preview: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema trả về danh sách tài liệu."""
    total: int
    documents: List[DocumentResponse]


class DocumentContentResponse(BaseModel):
    """Schema trả về nội dung đầy đủ của tài liệu."""
    id: int
    file_name: str
    file_type: Optional[str]
    content: str
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0


class DocumentSummaryResponse(BaseModel):
    """Schema trả về tóm tắt tài liệu."""
    id: int
    file_name: str
    summary: str
    model_used: str


# ============================================================
# Chat / Q&A Schemas
# ============================================================
class AskRequest(BaseModel):
    """Schema nhận câu hỏi từ người dùng."""
    question: str = Field(..., min_length=3, max_length=2000, description="Câu hỏi của người dùng")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Số lượng chunk tài liệu tìm kiếm")


class SourceInfo(BaseModel):
    """Thông tin nguồn tài liệu tham chiếu."""
    file_name: str
    relevance_score: float


class AskResponse(BaseModel):
    """Schema trả về câu trả lời."""
    question: str
    answer: str
    sources: List[SourceInfo]
    model_used: str
    history_id: int


# ============================================================
# Chat History Schemas
# ============================================================
class ChatHistoryResponse(BaseModel):
    """Schema trả về một mục lịch sử hỏi đáp."""
    id: int
    question: str
    answer: str
    sources: List[str] = []
    model_used: Optional[str]
    created_at: datetime

    @classmethod
    def from_orm_with_sources(cls, obj) -> "ChatHistoryResponse":
        """Tạo từ ORM object, parse sources_json."""
        sources = []
        if obj.sources_json:
            try:
                sources = json.loads(obj.sources_json)
            except Exception:
                sources = []

        return cls(
            id=obj.id,
            question=obj.question,
            answer=obj.answer,
            sources=sources,
            model_used=obj.model_used,
            created_at=obj.created_at,
        )

    class Config:
        from_attributes = True


class ChatHistoryListResponse(BaseModel):
    """Schema trả về danh sách lịch sử."""
    total: int
    histories: List[ChatHistoryResponse]


# ============================================================
# General Response
# ============================================================
class MessageResponse(BaseModel):
    """Schema trả về thông báo chung."""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Schema trả về lỗi."""
    error: str
    detail: Optional[str] = None
