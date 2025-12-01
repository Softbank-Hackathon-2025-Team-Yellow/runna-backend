import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import functions, jobs
from app.core.redis import RedisClient
from app.infra.execution_client import ExecutionClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 백그라운드 리스너 시작
    exec_client = ExecutionClient()
    listener_task = asyncio.create_task(exec_client.start_callback_listener())
    print("[Main] Callback listener started")

    yield

    # Shutdown
    listener_task.cancel()
    RedisClient.close()
    print("[Main] Shutdown complete")


app = FastAPI(
    title="Function Runner API",
    description="API for managing and executing functions",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(functions.router, prefix="/functions", tags=["functions"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/")
def root():
    return {"message": "Function Runner API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
