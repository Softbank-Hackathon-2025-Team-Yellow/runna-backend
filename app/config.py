import os
import secrets
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/runna_db"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

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

    # Worker/Redis Stream 설정
    exec_stream_name: str = "exec_stream"
    callback_channel_name: str = "callback_channel"
    consumer_group_name: str = "exec_consumers"

    # Worker 처리 설정
    worker_max_messages: int = 1
    worker_block_time_ms: int = 1000
    worker_timeout_seconds: int = 30

    # Kubernetes 설정
    kubernetes_in_cluster: bool = False  # Pod 내부 실행 여부 (기본값: Mock 사용)
    kubernetes_config_path: Optional[str] = None  # 로컬 개발용

    # Namespace 리소스 제한
    namespace_cpu_limit: str = "2000m"  # 2 core
    namespace_memory_limit: str = "4Gi"  # 4GB
    namespace_pod_limit: int = 10  # 최대 Pod 수

    @field_validator("secret_key", mode="before")
    @classmethod
    def generate_secret_key(cls, v):
        if v is None or v == "":
            # 프로덕션에서는 반드시 환경변수로 설정해야 함
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("SECRET_KEY must be set in production environment")
            # 개발환경에서는 자동 생성
            return secrets.token_urlsafe(32)
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        if v.startswith("postgresql://user:password@"):
            print(
                "[WARNING] Using default database settings. Please configure .env file."
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """설정 인스턴스를 반환하는 팩토리 함수"""
    return Settings()


settings = get_settings()
