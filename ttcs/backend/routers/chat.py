import json
from typing import List

from fastapi import APIRouter, HTTPException, Query

try:
    import database
    from models import ChatHistoryItem, ChatRequest, ChatResponse, SourceChunk
    from services.llm_service import ServiceUnavailableException
    from services.rag_service import RAGService
except ImportError:
    from backend import database
    from backend.models import ChatHistoryItem, ChatRequest, ChatResponse, SourceChunk
    from backend.services.llm_service import ServiceUnavailableException
    from backend.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])
rag_service = RAGService()


@router.post("/ask", response_model=ChatResponse)
async def ask_question(payload: ChatRequest):
    try:
        docs = database.get_all_documents()
        indexed_docs = [d for d in docs if d.get("status") == "INDEXED"]
        if not indexed_docs:
            raise HTTPException(
                status_code=400,
                detail="Chưa có tài liệu INDEXED. Vui lòng tải lên và đợi indexing hoàn tất.",
            )

        response = await rag_service.answer(
            question=payload.question,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        )

        sources_json = json.dumps([item.model_dump() for item in response.sources], ensure_ascii=False)
        database.insert_chat_history(payload.question, response.answer, sources_json)
        return response
    except HTTPException:
        raise
    except ServiceUnavailableException as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {exc}") from exc


@router.get("/history", response_model=List[ChatHistoryItem])
async def get_history(limit: int = Query(default=50, ge=1, le=200)):
    try:
        rows = database.get_chat_history(limit=limit)
        items: List[ChatHistoryItem] = []
        for row in rows:
            sources_raw = row.get("sources", "[]")
            sources_data = json.loads(sources_raw) if isinstance(sources_raw, str) else sources_raw
            sources = [SourceChunk(**source) for source in sources_data]
            items.append(
                ChatHistoryItem(
                    id=row["id"],
                    question=row["question"],
                    answer=row["answer"],
                    sources=sources,
                    timestamp=row["timestamp"],
                )
            )
        return items
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy lịch sử hội thoại: {exc}") from exc
