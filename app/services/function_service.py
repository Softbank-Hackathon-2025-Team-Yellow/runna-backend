from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from sqlalchemy import func

from app.models.function import Function
from app.models.execution import Execution
from app.models.job import Job, JobStatus
from app.schemas.function import FunctionCreate, FunctionUpdate
from app.core.static_analysis import analyzer


class FunctionService:
    def __init__(self, db: Session):
        self.db = db

    def create_function(self, function_data: FunctionCreate) -> Function:
        analysis_result = self._analyze_code(function_data.code, function_data.runtime.value)
        
        if not analysis_result["is_safe"]:
            raise ValueError(f"Code analysis failed: {', '.join(analysis_result['violations'])}")

        db_function = Function(**function_data.dict())
        self.db.add(db_function)
        self.db.commit()
        self.db.refresh(db_function)
        return db_function

    def get_function(self, function_id: int) -> Optional[Function]:
        return self.db.query(Function).filter(Function.id == function_id).first()

    def get_function_by_name(self, name: str) -> Optional[Function]:
        return self.db.query(Function).filter(Function.name == name).first()

    def list_functions(self, skip: int = 0, limit: int = 100) -> List[Function]:
        return self.db.query(Function).filter(Function.is_active == True).offset(skip).limit(limit).all()

    def update_function(self, function_id: int, function_update: FunctionUpdate) -> Optional[Function]:
        db_function = self.get_function(function_id)
        if not db_function:
            return None

        update_data = function_update.dict(exclude_unset=True)
        
        if "code" in update_data:
            runtime = update_data.get("runtime", db_function.runtime)
            analysis_result = self._analyze_code(update_data["code"], runtime.value if hasattr(runtime, 'value') else runtime)
            
            if not analysis_result["is_safe"]:
                raise ValueError(f"Code analysis failed: {', '.join(analysis_result['violations'])}")

        for field, value in update_data.items():
            setattr(db_function, field, value)

        self.db.commit()
        self.db.refresh(db_function)
        return db_function

    def delete_function(self, function_id: int) -> bool:
        db_function = self.get_function(function_id)
        if not db_function:
            return False

        db_function.is_active = False
        self.db.commit()
        return True

    def get_function_metrics(self, function_id: int) -> Optional[Dict[str, Any]]:
        function = self.get_function(function_id)
        if not function:
            return None

        total_executions = self.db.query(Execution).filter(
            Execution.function_id == function_id
        ).count()

        successful_executions = self.db.query(Job).join(Execution).filter(
            Execution.function_id == function_id,
            Job.status == JobStatus.SUCCEEDED
        ).count()

        failed_executions = self.db.query(Job).join(Execution).filter(
            Execution.function_id == function_id,
            Job.status == JobStatus.FAILED
        ).count()

        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0

        return {
            "invocations": {
                "total": total_executions,
                "successful": successful_executions,
                "failed": failed_executions
            },
            "success_rate": round(success_rate, 2),
            "avg_execution_time": "120ms",
            "cpu_usage": "70%",
            "memory_usage": "256MB"
        }

    def _analyze_code(self, code: str, runtime: str) -> dict:
        if runtime == "python":
            return analyzer.analyze_python_code(code)
        elif runtime == "nodejs":
            return analyzer.analyze_nodejs_code(code)
        else:
            return {"is_safe": False, "violations": ["Unsupported runtime"]}