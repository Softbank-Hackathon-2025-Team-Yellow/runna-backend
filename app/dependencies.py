from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.database import get_db
from app.infra.execution_client import ExecutionClient
from app.models.user import User
from app.services.user_service import UserService

security = HTTPBearer()


def get_execution_client() -> ExecutionClient:
    """
    Get singleton ExecutionClient instance.

    ExecutionClient uses __new__ method to ensure singleton behavior,
    so direct constructor call always returns the same instance.
    """
    return ExecutionClient()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    현재 사용자를 JWT 토큰을 통해 인증하고 반환

    Args:
        credentials: HTTP Authorization Bearer 토큰
        db: 데이터베이스 세션

    Returns:
        인증된 User 객체

    Raises:
        HTTPException: 토큰이 유효하지 않거나 사용자를 찾을 수 없는 경우
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_service = UserService(db)
    user = user_service.get_user_by_username(username)
    if user is None:
        raise credentials_exception

    return user


def get_admin_user():
    pass
