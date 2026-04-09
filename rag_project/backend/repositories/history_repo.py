"""
History Repository - Thao tác CRUD với bảng chat_history
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
    ) -> ChatHistory:
        """Lưu một phiên hỏi đáp vào lịch sử."""
        history = ChatHistory(
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

    def get_all(self, limit: int = 100, skip: int = 0) -> List[ChatHistory]:
        """Lấy lịch sử hỏi đáp, mới nhất trước."""
        return (
            self.db.query(ChatHistory)
            .order_by(ChatHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        """Đếm tổng số phiên hỏi đáp."""
        return self.db.query(ChatHistory).count()

    def delete(self, history_id: int) -> bool:
        """Xóa một mục lịch sử."""
        history = self.get_by_id(history_id)
        if history:
            self.db.delete(history)
            self.db.commit()
            return True
        return False

    def clear_all(self) -> int:
        """Xóa toàn bộ lịch sử. Trả về số bản ghi đã xóa."""
        count = self.db.query(ChatHistory).count()
        self.db.query(ChatHistory).delete()
        self.db.commit()
        return count
