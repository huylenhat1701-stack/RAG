from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class DocumentRecord(BaseModel):
    id: str
    filename: str
    file_type: str
    status: DocumentStatus
    created_at: str
    chunk_count: int = 0


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: Optional[List[str]] = None


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_text: str
    page_number: Optional[int] = None
    similarity_score: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    question: str
    timestamp: str


class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    sources: List[SourceChunk]
    timestamp: str
