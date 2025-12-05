import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.dependencies import get_current_user, get_execution_client, get_workspace_auth
from app.infra.execution_client import ExecutionClient
from app.schemas.user import UserCreate
from app.schemas.workspace import WorkspaceCreate
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Empty lifespan for testing (prevents actual ExecutionClient creation in main.py)
@asynccontextmanager
async def empty_lifespan(app):
    yield


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_exec_client():
    """
    Mock ExecutionClient for testing.

    Returns a mock object with AsyncMock methods for:
    - invoke_sync: Returns successful execution result
    - insert_exec_queue: Returns True (success)
    """
    client = Mock(spec=ExecutionClient)
    client.invoke_sync = AsyncMock(return_value={"status": "success", "result": {}})
    client.insert_exec_queue = AsyncMock(return_value=True)
    return client


@pytest.fixture
def test_user(db_session):
    """
    테스트용 사용자 생성
    """
    user_service = UserService(db_session)
    unique_id = str(uuid.uuid4())[:8]
    user_data = UserCreate(
        username=f"test_user_{unique_id}", name="Test User", password="test_password"
    )
    user = user_service.create_user(user_data)
    return user


@pytest.fixture
def test_workspace(db_session, test_user):
    """
    테스트용 워크스페이스 생성
    """
    workspace_service = WorkspaceService(db_session)
    unique_id = str(uuid.uuid4())[:8]
    workspace_data = WorkspaceCreate(
        name=f"test-{unique_id}"
    )  # 20자 제한: "test-" (5자) + uuid (8자) = 13자
    workspace = workspace_service.create_workspace(workspace_data, test_user.id)
    return workspace


@pytest.fixture
def client(db_session, mock_exec_client, test_user, test_workspace):
    """
    FastAPI TestClient with dependency overrides.

    Overrides:
    - get_db: Use test database session
    - get_execution_client: Use mock ExecutionClient
    """
    # Import app here to avoid circular imports
    from app.main import app

    # Override lifespan to prevent actual ExecutionClient creation
    app.router.lifespan_context = empty_lifespan

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override dependencies with test instances
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_execution_client] = lambda: mock_exec_client
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_auth] = lambda: test_workspace

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()
