import httpx
import asyncio
from typing import Dict, Any, Optional
import json
import uuid

from app.config import settings


class KNativeClient:
    def __init__(self):
        self.base_url = settings.knative_url
        self.timeout = settings.knative_timeout

    async def execute_function(
        self, 
        function_name: str, 
        function_code: str, 
        language: str, 
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "function_name": function_name,
                "code": function_code,
                "language": language,
                "input": input_data or {}
            }
            
            try:
                response = await client.post(
                    f"{self.base_url}/execute",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": f"HTTP error: {str(e)}",
                    "output": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}",
                    "output": None
                }

    def execute_function_sync(
        self, 
        function_name: str, 
        function_code: str, 
        language: str, 
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.execute_function(function_name, function_code, language, input_data)
        )

    async def create_function_deployment(
        self, 
        function_name: str, 
        function_code: str, 
        language: str
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "name": function_name,
                "code": function_code,
                "language": language
            }
            
            try:
                response = await client.post(
                    f"{self.base_url}/deploy",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": f"Deployment failed: {str(e)}"
                }

    async def delete_function_deployment(self, function_name: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.delete(f"{self.base_url}/functions/{function_name}")
                response.raise_for_status()
                return {"success": True}
                
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": f"Deletion failed: {str(e)}"
                }

    def generate_job_id(self) -> str:
        return f"job_{uuid.uuid4().hex[:8]}"


knative_client = KNativeClient()