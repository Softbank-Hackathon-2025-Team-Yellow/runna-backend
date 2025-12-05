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
    kubernetes_in_cluster: bool = False  # Pod 내부 실행 여부
    kubernetes_config_path: Optional[str] = None  # 로컬 개발용

    # K8s 설정
    k8s_namespace_prefix: str = "runna"
    base_domain: str = "runna.haifu.cloud"

    # Runtime별 Docker 이미지
    k8s_python_image: str = "docker.io/runna/python-runtime:latest"
    k8s_nodejs_image: str = "docker.io/runna/nodejs-runtime:latest"

    # 기존 Ingress 설정 (하위 호환성)
    k8s_ingress_class: str = "nginx"
    k8s_ingress_domain: str = "runna.dev"

    # K8s 리소스 제한
    k8s_cpu_request: str = "100m"
    k8s_memory_request: str = "128Mi"
    k8s_cpu_limit: str = "500m"
    k8s_memory_limit: str = "256Mi"

    # Namespace 리소스 한도
    namespace_cpu_limit: str = "2000m"
    namespace_memory_limit: str = "4Gi"
    namespace_pod_limit: int = 10

    # 외부 Namespace Manager API
    namespace_manager_url: Optional[str] = None

    # KNative 오토스케일링
    knative_min_scale: str = "1"
    knative_max_scale: str = "10"

    # Gateway API 설정
    gateway_name: str = "runna-gateway"
    gateway_namespace: str = "istio-system"

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
