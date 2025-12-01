from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.models.function import Runtime

class Execution(BaseModel):
    job_id: int
    runtime: Runtime
    code: str
    payload: Optional[Dict[str, Any]]
