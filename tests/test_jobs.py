import pytest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_get_job_by_id(client: TestClient):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "python",
        "code": "def handler(event): return {'result': 'success'}",
        "execution_type": "sync"
    }
    
    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]
    
    # Mock successful execution to create a job
    with patch('app.core.knative_client.knative_client.execute_function_sync') as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "output": {"result": "success"}
        }
        
        # Invoke function to create a job
        invoke_response = client.post(f"/functions/{function_id}/invoke", json={"param1": "test"})
        job_id = invoke_response.json()["data"]["id"]
    
    # Get job by ID
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == job_id
    assert data["data"]["function_id"] == function_id
    assert data["data"]["status"] == "succeeded"
    # Result is stored as JSON string, so parse it first
    result = json.loads(data["data"]["result"]) if isinstance(data["data"]["result"], str) else data["data"]["result"]
    assert result["result"] == "success"


def test_get_nonexistent_job(client: TestClient):
    response = client.get("/jobs/999")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is False
    assert "JOB_NOT_FOUND" in data["error"]["code"]


def test_job_creation_with_failed_execution(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "python", 
        "code": "def handler(event): return event",
        "execution_type": "sync"
    }
    
    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]
    
    # Mock failed execution
    with patch('app.core.knative_client.knative_client.execute_function_sync') as mock_execute:
        mock_execute.return_value = {
            "success": False,
            "error": "Execution failed"
        }
        
        # Invoke function
        invoke_response = client.post(f"/functions/{function_id}/invoke", json={"param1": "test"})
        job_id = invoke_response.json()["data"]["id"]
    
    # Get the failed job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "failed"
    assert data["data"]["result"] is None


def test_async_job_creation(client: TestClient):
    # Create an async function
    function_data = {
        "name": "test_async_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "async"
    }
    
    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]
    
    # Invoke async function
    invoke_response = client.post(f"/functions/{function_id}/invoke", json={"param1": "test"})
    job_id = invoke_response.json()["data"]["id"]
    
    # Get the pending job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "pending"
    assert data["data"]["result"] is None


def test_multiple_jobs_for_function(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync"
    }
    
    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]
    
    job_ids = []
    
    # Create multiple jobs with different outcomes
    with patch('app.core.knative_client.knative_client.execute_function_sync') as mock_execute:
        # First successful execution
        mock_execute.return_value = {"success": True, "output": {"result": "success1"}}
        invoke1 = client.post(f"/functions/{function_id}/invoke", json={"param1": "test1"})
        job_ids.append(invoke1.json()["data"]["id"])
        
        # Second failed execution
        mock_execute.return_value = {"success": False, "error": "Failed"}
        invoke2 = client.post(f"/functions/{function_id}/invoke", json={"param1": "test2"})
        job_ids.append(invoke2.json()["data"]["id"])
    
    # Get function jobs
    response = client.get(f"/functions/{function_id}/jobs")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["jobs"]) == 2
    
    # Check that we have both jobs
    jobs = data["data"]["jobs"]
    statuses = [job["status"] for job in jobs]
    assert "succeeded" in statuses
    assert "failed" in statuses