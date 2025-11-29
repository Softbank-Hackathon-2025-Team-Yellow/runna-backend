import os
import secrets
from pydantic import BaseSettings, validator
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/runna_db"
    
    # KNative
    knative_url: str = "http://localhost:8080"
    knative_timeout: int = 30
    
    # Security
    secret_key: Optional[str] = None
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    @validator('secret_key', pre=True)
    def generate_secret_key(cls, v):
        if v is None or v == "":
            # 프로덕션에서는 반드시 환경변수로 설정해야 함
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                raise ValueError("SECRET_KEY must be set in production environment")
            # 개발환경에서는 자동 생성
            return secrets.token_urlsafe(32)
        return v
    
    @validator('database_url')
    def validate_database_url(cls, v):
        if v.startswith('postgresql://user:password@'):
            print("⚠️  경고: 기본 데이터베이스 설정을 사용 중입니다. .env 파일을 설정하세요.")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """설정 인스턴스를 반환하는 팩토리 함수"""
    return Settings()


settings = get_settings()