from typing import List, Optional

import chromadb

import config


class ChromaVectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: dict,
    ) -> None:
        ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]
        self.collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_document_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        where = None
        if filter_document_ids:
            where = {"document_id": {"$in": filter_document_ids}}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        formatted = []
        for idx, doc in enumerate(documents):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            distance = distances[idx] if idx < len(distances) else 1.0
            formatted.append(
                {
                    "chunk_text": doc,
                    "document_id": meta.get("document_id", ""),
                    "filename": meta.get("filename", ""),
                    "chunk_index": meta.get("chunk_index"),
                    "page_number": meta.get("page_number"),
                    "similarity_score": float(1 - distance),
                }
            )
        return formatted

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def get_collection_stats(self) -> dict:
        return {"total_chunks": self.collection.count()}
