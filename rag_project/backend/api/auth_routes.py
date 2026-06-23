"""
Auth Routes — Đăng ký, đăng nhập, thông tin user
POST /auth/register  → Tạo tài khoản mới
POST /auth/login     → Đăng nhập, trả JWT token
GET  /auth/me        → Thông tin user hiện tại (cần token)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..repositories.user_repo import UserRepository
from ..core.security import verify_password, get_password_hash, create_access_token
from ..api.deps import get_current_user
from ..models.domain import User
from ..models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    MessageResponse,
)

auth_router = APIRouter()


# ============================================================
# REGISTER
# ============================================================
@auth_router.post(
    "/register",
    response_model=TokenResponse,
    summary="Đăng ký tài khoản",
    description="Tạo tài khoản mới với username và password. Trả về JWT token để sử dụng ngay.",
    tags=["Xác thực"],
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Đăng ký tài khoản mới."""
    user_repo = UserRepository(db)

    # Kiểm tra username đã tồn tại
    existing = user_repo.get_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{request.username}' đã được sử dụng",
        )

    # Tạo user mới
    hashed_pw = get_password_hash(request.password)
    user = user_repo.create(
        username=request.username,
        hashed_password=hashed_pw,
        full_name=request.full_name,
    )

    # Tạo JWT token ngay sau khi đăng ký
    token = create_access_token(user.id, user.username)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ============================================================
# LOGIN
# ============================================================
@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập",
    description="Đăng nhập bằng username/password. Trả về JWT token.",
    tags=["Xác thực"],
)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Đăng nhập và nhận JWT token."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(request.username)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu",
        )

    token = create_access_token(user.id, user.username)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ============================================================
# GET CURRENT USER
# ============================================================
@auth_router.get(
    "/me",
    response_model=UserResponse,
    summary="Thông tin tài khoản",
    description="Lấy thông tin user đang đăng nhập (cần Bearer token).",
    tags=["Xác thực"],
)
def get_me(current_user: User = Depends(get_current_user)):
    """Trả về thông tin user hiện tại."""
    return UserResponse.model_validate(current_user)
