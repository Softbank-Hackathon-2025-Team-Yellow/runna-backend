import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ExecutionResult(BaseModel):
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class FunctionExecutor(ABC):
    """함수 실행 추상화 인터페이스"""
    
    @abstractmethod
    async def execute(self, function_id: int, payload: Dict[str, Any]) -> ExecutionResult:
        """함수를 실행하고 결과를 반환합니다."""
        pass


class DummyExecutor(FunctionExecutor):
    """테스트용 더미 실행기"""
    
    async def execute(self, function_id: int, payload: Dict[str, Any]) -> ExecutionResult:
        start_time = datetime.now()
        
        try:
            # 테스트를 위한 파라미터 처리
            sleep_time = payload.get("test_time", 1) if payload else 1
            should_error = payload.get("test_error", False) if payload else False
            
            await asyncio.sleep(sleep_time)
            
            if should_error:
                raise Exception(f"Test error for function {function_id}")
            
            result = {
                "message": f"Function {function_id} executed successfully",
                "input": payload,
                "timestamp": datetime.now().isoformat(),
            }
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ExecutionResult(
                success=True,
                result=result,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return ExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )