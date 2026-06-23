"""
User Repository - Thao tác CRUD với bảng users
"""

from typing import Optional
from sqlalchemy.orm import Session

from ..models.domain import User


class UserRepository:
    """Repository Pattern cho bảng users."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, username: str, hashed_password: str, full_name: str = "") -> User:
        """Tạo user mới."""
        user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_username(self, username: str) -> Optional[User]:
        """Tìm user theo username."""
        return self.db.query(User).filter(User.username == username).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Tìm user theo ID."""
        return self.db.query(User).filter(User.id == user_id).first()
