"""
History Repository - Thao tác CRUD với bảng chat_history
Tất cả truy vấn đều lọc theo user_id để đảm bảo data isolation.
"""

import json
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models.domain import ChatHistory


class HistoryRepository:
    """Repository Pattern cho bảng chat_history."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        question: str,
        answer: str,
        sources: List[str],
        model_used: str,
        user_id: int = None,
    ) -> ChatHistory:
        """Lưu một phiên hỏi đáp vào lịch sử."""
        history = ChatHistory(
            user_id=user_id,
            question=question,
            answer=answer,
            sources_json=json.dumps(sources, ensure_ascii=False),
            model_used=model_used,
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_by_id(self, history_id: int) -> Optional[ChatHistory]:
        """Lấy lịch sử theo ID."""
        return self.db.query(ChatHistory).filter(ChatHistory.id == history_id).first()

    def get_all(self, limit: int = 100, skip: int = 0, user_id: int = None) -> List[ChatHistory]:
        """Lấy lịch sử hỏi đáp của user, mới nhất trước."""
        query = self.db.query(ChatHistory)
        if user_id is not None:
            query = query.filter(ChatHistory.user_id == user_id)
        return (
            query
            .order_by(ChatHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, user_id: int = None) -> int:
        """Đếm tổng số phiên hỏi đáp (của user)."""
        query = self.db.query(ChatHistory)
        if user_id is not None:
            query = query.filter(ChatHistory.user_id == user_id)
        return query.count()

    def delete(self, history_id: int) -> bool:
        """Xóa một mục lịch sử."""
        history = self.get_by_id(history_id)
        if history:
            self.db.delete(history)
            self.db.commit()
            return True
        return False

    def clear_all(self, user_id: int = None) -> int:
        """Xóa toàn bộ lịch sử (của user). Trả về số bản ghi đã xóa."""
        query = self.db.query(ChatHistory)
        if user_id is not None:
            query = query.filter(ChatHistory.user_id == user_id)
        count = query.count()
        query.delete()
        self.db.commit()
        return count
