import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_workspace_token(
    workspace_id: uuid.UUID, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Workspace 인증 토큰 생성

    Args:
        workspace_id: 워크스페이스 UUID
        expires_delta: 토큰 만료 시간 (기본값: 24시간)

    Returns:
        JWT 워크스페이스 인증 토큰
    """
    to_encode = {"workspace_id": str(workspace_id), "type": "workspace"}

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            hours=24
        )  # 워크스페이스 토큰은 24시간 유효

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_workspace_token(token: str) -> Optional[dict]:
    """
    Workspace 인증 토큰 검증

    Args:
        token: JWT 토큰

    Returns:
        토큰이 유효한 경우 payload, 무효한 경우 None
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )

        # 워크스페이스 토큰인지 확인
        if payload.get("type") != "workspace":
            return None

        # workspace_id가 존재하는지 확인
        workspace_id = payload.get("workspace_id")
        if not workspace_id:
            return None

        return payload
    except JWTError:
        return None
