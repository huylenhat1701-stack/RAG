from datetime import datetime, timezone
from typing import List, Optional

try:
    from models import ChatResponse, SourceChunk
    from services.llm_service import LLMService
except ImportError:
    from backend.models import ChatResponse, SourceChunk
    from backend.services.llm_service import LLMService

from pipeline.embedder import TextEmbedder
from pipeline.vector_store import ChromaVectorStore

try:
    from prompt import build_rag_prompt
except ImportError:
    # Fallback for running from the repository root (same pattern used elsewhere in this package)
    from ttcs.prompt import build_rag_prompt


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RAGService:
    def __init__(self):
        self.embedder = TextEmbedder()
        self.vector_store = ChromaVectorStore()
        self.llm_service = LLMService()

    async def answer(
        self,
        question: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> ChatResponse:
        query_embedding = self.embedder.embed_single(question)
        results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_document_ids=document_ids,
        )

        context = "\n\n---\n\n".join([r["chunk_text"] for r in results]) if results else ""
        prompt = build_rag_prompt(context=context, question=question)
        answer_text = await self.llm_service.generate(prompt)
        sources = [SourceChunk(**r) for r in results]
        return ChatResponse(
            answer=answer_text,
            sources=sources,
            question=question,
            timestamp=now_iso(),
        )
