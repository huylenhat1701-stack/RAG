from pathlib import Path
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.domain import Document, UserKnowledge, QuizHistory
from ..repositories.document_repo import DocumentRepository
from ..services.llm_service import LLMService

class GraphService:
    @staticmethod
    def build_graph(doc_id: int, user_id: int, db: Session, llm_service: LLMService) -> dict:
        """
        Xây dựng bản đồ tri thức:
        1. Lấy toàn bộ chunks kèm vector embeddings từ ChromaDB.
        2. Lấy xác suất hiểu bài BKT từ UserKnowledge (default 50).
        3. Lấy số lần trả lời câu hỏi luyện tập của từng chunk từ QuizHistory.
        4. Giới hạn tối đa 50 chunks (ưu tiên chunks có điểm hiểu bài thấp nhất).
        5. Tính pairwise cosine similarity bằng numpy.
        6. Tạo liên kết (edge) nếu similarity > 0.60.
        """
        doc_repo = DocumentRepository(db)
        doc = doc_repo.get_by_id(doc_id)
        if not doc:
            raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

        # 1. Lấy chunks & embeddings từ ChromaDB
        stem = Path(doc.file_name).stem
        raw_results = llm_service._get_embeddings_for_doc(doc.file_name, stem)
        total_chunks = len(raw_results.get("ids", []))
        if total_chunks == 0:
            return {
                "nodes": [],
                "edges": [],
                "total_nodes": 0,
                "avg_probability": 0.0
            }

        # 2. Lấy UserKnowledge
        knowledges = db.query(UserKnowledge).filter(
            UserKnowledge.doc_id == doc_id,
            UserKnowledge.session_id == str(user_id)
        ).all()
        knowledge_map = {k.chunk_id: k.probability for k in knowledges}

        # 3. Lấy QuizHistory attempts
        attempts = db.query(
            QuizHistory.chunk_id,
            func.count(QuizHistory.id).label("attempts")
        ).filter(
            QuizHistory.doc_id == doc_id,
            QuizHistory.session_id == str(user_id)
        ).group_by(QuizHistory.chunk_id).all()
        attempts_map = {a.chunk_id: a.attempts for a in attempts}

        # 4. Tổ hợp danh sách chunks
        all_chunks = []
        for i in range(total_chunks):
            cid = raw_results["ids"][i]
            txt = raw_results["documents"][i]
            embedding = raw_results["embeddings"][i] if raw_results.get("embeddings") is not None else None
            prob = knowledge_map.get(cid, 50)
            att = attempts_map.get(cid, 0)
            
            all_chunks.append({
                "id": cid,
                "text": txt,
                "embedding": embedding,
                "probability": prob,
                "quiz_attempts": att
            })

        # 5. Sắp xếp tăng dần theo probability và lấy top 50
        all_chunks.sort(key=lambda x: x["probability"])
        target_chunks = all_chunks[:50]

        # 6. Build nodes list
        nodes = []
        for chunk in target_chunks:
            text_clean = " ".join(chunk["text"].split())
            label = text_clean[:40] + "..." if len(text_clean) > 40 else text_clean
            preview = text_clean[:150] + "..." if len(text_clean) > 150 else text_clean
            
            nodes.append({
                "id": chunk["id"],
                "label": label,
                "preview": preview,
                "probability": chunk["probability"],
                "quiz_attempts": chunk["quiz_attempts"]
            })

        # 7. Tính pairwise cosine similarity bằng numpy và build edges list
        edges = []
        n = len(target_chunks)
        
        # Hàm tính cosine similarity
        def cosine_similarity(v1, v2):
            if v1 is None or v2 is None:
                return 0.0
            v1_arr = np.array(v1)
            v2_arr = np.array(v2)
            dot_product = np.dot(v1_arr, v2_arr)
            norm_v1 = np.linalg.norm(v1_arr)
            norm_v2 = np.linalg.norm(v2_arr)
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            return float(dot_product / (norm_v1 * norm_v2))

        for i in range(n):
            for j in range(i + 1, n):
                emb1 = target_chunks[i]["embedding"]
                emb2 = target_chunks[j]["embedding"]
                if emb1 is not None and emb2 is not None:
                    sim = cosine_similarity(emb1, emb2)
                    if sim > 0.60:
                        edges.append({
                            "source": target_chunks[i]["id"],
                            "target": target_chunks[j]["id"],
                            "weight": round(sim, 3)
                        })

        # Tính toán thông số tổng quan
        avg_prob = round(sum(c["probability"] for c in target_chunks) / n, 1) if n > 0 else 0.0

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": n,
            "avg_probability": avg_prob
        }
