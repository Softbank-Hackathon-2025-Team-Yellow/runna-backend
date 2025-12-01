from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import functions, jobs
from app.core.redis import RedisClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    RedisClient.close()

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
