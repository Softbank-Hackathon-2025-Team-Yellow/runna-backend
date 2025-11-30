from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import functions, jobs
from app.database import engine
from app.models import function, job

app = FastAPI(
    title="Function Runner API",
    description="API for managing and executing functions",
    version="1.0.0"
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