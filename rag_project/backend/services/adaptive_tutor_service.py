from sqlalchemy.orm import Session
from ..models.domain import UserKnowledge, QuizHistory
from typing import List

class AdaptiveTutorService:
    def __init__(self):
        # BKT parameters (simplified)
        self.p_slip = 0.1       # Xác suất làm sai dù đã hiểu bài
        self.p_guess = 0.2      # Xác suất đoán mò đúng dù chưa hiểu
        self.p_transit = 0.1    # Xác suất học được kiến thức mới sau khi luyện tập

    def update_knowledge(self, session_id: str, doc_id: int, chunk_id: str, is_correct: int, db: Session):
        """
        Cập nhật mô hình học tập BKT của người dùng
        """
        # 1. Lưu lịch sử làm bài
        history = QuizHistory(
            session_id=session_id,
            doc_id=doc_id,
            chunk_id=chunk_id,
            is_correct=is_correct
        )
        db.add(history)
        
        # 2. Lấy trạng thái kiến thức hiện tại
        knowledge = db.query(UserKnowledge).filter(
            UserKnowledge.session_id == session_id,
            UserKnowledge.doc_id == doc_id,
            UserKnowledge.chunk_id == chunk_id
        ).first()

        if not knowledge:
            knowledge = UserKnowledge(
                session_id=session_id,
                doc_id=doc_id,
                chunk_id=chunk_id,
                probability=50 # Mặc định 50%
            )
            db.add(knowledge)
        
        # 3. Tính toán BKT
        p_L = knowledge.probability / 100.0 # Chuyển từ % sang số thập phân
        
        if is_correct:
            # Xác suất thực sự hiểu bài nếu trả lời đúng
            numerator = p_L * (1 - self.p_slip)
            denominator = numerator + (1 - p_L) * self.p_guess
            p_L_obs = numerator / denominator if denominator > 0 else 0
        else:
            # Xác suất vẫn hiểu bài dù trả lời sai
            numerator = p_L * self.p_slip
            denominator = numerator + (1 - p_L) * (1 - self.p_guess)
            p_L_obs = numerator / denominator if denominator > 0 else 0
            
        # Cập nhật kiến thức mới (sau khi xem xét khả năng vừa học được điều mới)
        p_L_new = p_L_obs + (1 - p_L_obs) * self.p_transit
        
        # Lưu vào database
        knowledge.probability = int(p_L_new * 100)
        db.commit()
        
        return knowledge.probability

    def get_weak_chunks(self, session_id: str, doc_id: int, db: Session) -> List[str]:
        """
        Lấy danh sách các chunk kiến thức bị yếu (dưới 60%)
        """
        weak_knowledges = db.query(UserKnowledge).filter(
            UserKnowledge.session_id == session_id,
            UserKnowledge.doc_id == doc_id,
            UserKnowledge.probability < 60
        ).all()
        
        return [k.chunk_id for k in weak_knowledges]

adaptive_tutor_service = AdaptiveTutorService()
