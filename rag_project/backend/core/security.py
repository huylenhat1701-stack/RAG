"""
Security Module — Password Hashing (bcrypt) & JWT Token (python-jose)
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# ============================================================
# Config
# ============================================================
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "rag-smart-reader-secret-key-change-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# ============================================================
# Password Hashing
# ============================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu plain-text có khớp với hash không."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash mật khẩu bằng bcrypt."""
    return pwd_context.hash(password)


# ============================================================
# JWT Token
# ============================================================
def create_access_token(user_id: int, username: str) -> str:
    """Tạo JWT access token chứa user_id và username."""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode JWT token. Trả về payload dict hoặc None nếu invalid/expired.
    Payload chứa: sub (user_id), username, exp
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
