import logging
import os

import config

try:
    import database
    from pipeline.chunker import TextChunker
    from pipeline.embedder import TextEmbedder
    from pipeline.extractor import TextExtractor
    from pipeline.vector_store import ChromaVectorStore
except ImportError:
    from backend import database
    from pipeline.chunker import TextChunker
    from pipeline.embedder import TextEmbedder
    from pipeline.extractor import TextExtractor
    from pipeline.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    def __init__(self):
        self.extractor = TextExtractor()
        self.chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
        self.embedder = TextEmbedder()
        self.vector_store = ChromaVectorStore()

    async def ingest(self, document_id: str, file_path: str) -> None:
        try:
            logger.info("Start ingest document_id=%s", document_id)
            database.update_document_status(document_id, "UPLOADED")

            logger.info("Extract text document_id=%s", document_id)
            text = self.extractor.extract(file_path)

            logger.info("Chunk text document_id=%s", document_id)
            chunks = self.chunker.split(text)
            if not chunks:
                raise ValueError("Không trích xuất được chunk nào từ tài liệu.")

            logger.info("Embed chunks document_id=%s chunk_count=%s", document_id, len(chunks))
            embeddings = self.embedder.embed_batch(chunks)

            logger.info("Store vectors document_id=%s", document_id)
            self.vector_store.add_documents(
                document_id=document_id,
                chunks=chunks,
                embeddings=embeddings,
                metadata={"filename": os.path.basename(file_path), "document_id": document_id},
            )

            database.update_document_status(document_id, "INDEXED", chunk_count=len(chunks))
            logger.info("Ingest success document_id=%s", document_id)
        except Exception as exc:
            logger.exception("Ingest failed document_id=%s error=%s", document_id, exc)
            database.update_document_status(document_id, "FAILED")
