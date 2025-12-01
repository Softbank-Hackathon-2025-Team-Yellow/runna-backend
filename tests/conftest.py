from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.dependencies import get_execution_client
from app.infra.execution_client import ExecutionClient
# Import models to register them with SQLAlchemy metadata
from app.models.function import Function
from app.models.job import Job

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
    client.invoke_sync = AsyncMock(return_value={"status": "succeeded", "result": {}})
    client.insert_exec_queue = AsyncMock(return_value=True)
    return client


@pytest.fixture
def client(db_session, mock_exec_client):
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

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()
