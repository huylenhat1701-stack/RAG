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
class MessageInfo(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    """Schema nhận câu hỏi từ người dùng."""
    question: str = Field(..., min_length=3, max_length=2000, description="Câu hỏi của người dùng")
    top_k: Optional[int] = Field(default=15, ge=1, le=50, description="Số lượng chunk tài liệu tìm kiếm (chỉ dùng khi RAG mode)")
    history: Optional[List[MessageInfo]] = Field(default=[], description="Lịch sử trò chuyện")
    doc_ids: Optional[List[int]] = Field(default=None, description="Giới hạn tìm kiếm trong danh sách ID tài liệu (None = tất cả)")


class ExerciseRequest(BaseModel):
    """Schema nhận yêu cầu tạo bài tập từ tài liệu."""
    exercise_type: str = Field(
        default="trắc nghiệm",
        description="Loại bài tập: trắc nghiệm, tự luận, thảo luận"
    )
    count: Optional[int] = Field(
        default=5,
        ge=1,
        le=30,
        description="Số lượng câu hỏi muốn tạo"
    )


class ExerciseResponse(BaseModel):
    """Schema trả về bài tập do AI tạo."""
    id: int
    file_name: str
    exercise_text: str
    model_used: str


class QuizQuestion(BaseModel):
    """Một câu hỏi trắc nghiệm có cấu trúc."""
    id: int
    question: str
    options: dict          # {"A": "...", "B": "...", "C": "...", "D": "..."}
    answer: str            # "A" | "B" | "C" | "D"
    explanation: str = ""  # Giải thích tại sao đáp án đúng
    step_by_step_explanation: str = "" # CoT Math Tutor
    chunk_id: str = ""     # Để biết câu hỏi sinh từ đoạn kiến thức nào


class QuizResponse(BaseModel):
    """Schema trả về bộ câu hỏi thi trắc nghiệm có cấu trúc."""
    id: int
    file_name: str
    questions: List[QuizQuestion]
    total: int
    model_used: str


class QuizRequest(BaseModel):
    """Schema nhận yêu cầu tạo quiz trắc nghiệm."""
    count: Optional[int] = Field(default=10, ge=3, le=30, description="Số câu hỏi")


class QuizSubmitRequest(BaseModel):
    """Schema nhận kết quả làm bài tập của user."""
    session_id: str = Field(default="default_user", description="ID người dùng")
    chunk_id: str = Field(..., description="ID của chunk kiến thức")
    is_correct: bool = Field(..., description="Người dùng trả lời đúng hay sai")


class QuizSubmitResponse(BaseModel):
    """Schema trả về xác suất hiểu bài sau khi submit."""
    success: bool = True
    new_probability: int


class LearningPathRequest(BaseModel):
    """Schema nhận yêu cầu tạo lộ trình học tập."""
    session_id: str = Field(default="default_user", description="ID phiên người dùng")
    wrong_chunk_ids: List[str] = Field(default=[], description="Danh sách chunk_id của câu trả lời sai")


class LearningPathItem(BaseModel):
    """Một bước trong lộ trình học tập."""
    topic: str                  # Tên chủ đề / tiêu đề ngắn
    content_snippet: str        # Đoạn nội dung trích từ tài liệu cần đọc lại
    advice: str                 # Lời khuyên AI cụ thể
    bkt_probability: int = 0    # Xác suất hiểu bài BKT (0-100)
    chunk_id: str = ""


class LearningPathResponse(BaseModel):
    """Schema trả về lộ trình học tập cá nhân hóa."""
    doc_id: int
    file_name: str
    items: List[LearningPathItem]
    total_weak: int
    overall_message: str        # Nhận xét tổng thể từ AI


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
    mode: str = "rag"           # "full_context" | "rag" | "none"
    context_chars: int = 0      # Số ký tự nội dung đã đưa vào LLM


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


# ============================================================
# Auth Schemas
# ============================================================
class UserRegisterRequest(BaseModel):
    """Schema đăng ký tài khoản."""
    username: str = Field(..., min_length=3, max_length=50, description="Tên đăng nhập")
    password: str = Field(..., min_length=6, max_length=100, description="Mật khẩu")
    full_name: str = Field(default="", max_length=200, description="Họ tên đầy đủ")


class UserLoginRequest(BaseModel):
    """Schema đăng nhập."""
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")


class UserResponse(BaseModel):
    """Schema trả về thông tin user."""
    id: int
    username: str
    full_name: Optional[str] = ""
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema trả về JWT token sau đăng nhập."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

