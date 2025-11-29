from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime

from app.models.execution import ExecutionStatus


class InvokeFunctionRequest(BaseModel):
    param1: Optional[str] = None
    param2: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.param1 is not None:
            result["param1"] = self.param1
        if self.param2 is not None:
            result["param2"] = self.param2
        return result