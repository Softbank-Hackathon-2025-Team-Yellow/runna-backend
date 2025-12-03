from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import Token, User as UserSchema, UserCreate, UserLogin
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=UserSchema)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    새 사용자 등록

    Args:
        user: 사용자 등록 정보
        db: 데이터베이스 세션

    Returns:
        생성된 사용자 정보

    Raises:
        HTTPException: 사용자명이 이미 존재하는 경우
    """
    user_service = UserService(db)

    # Check if username already exists
    if user_service.get_user_by_username(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    return user_service.create_user(user)


@router.post("/login", response_model=Token)
def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """
    사용자 로그인

    Args:
        user_credentials: 로그인 자격증명
        db: 데이터베이스 세션

    Returns:
        JWT 액세스 토큰

    Raises:
        HTTPException: 인증 실패 시
    """
    user_service = UserService(db)

    user = user_service.authenticate_user(
        user_credentials.username, user_credentials.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = user_service.create_access_token_for_user(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    현재 사용자 정보 조회

    Args:
        current_user: 인증된 현재 사용자

    Returns:
        현재 사용자 정보
    """
    return current_user