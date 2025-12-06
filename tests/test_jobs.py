import json

from fastapi.testclient import TestClient


def test_get_job_by_id(client: TestClient, mock_exec_client, test_workspace):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return {'result': 'success'}",
        "execution_type": "SYNC",
        "workspace_id": str(test_workspace.id),
        "endpoint": "/test-function"
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for this specific test
    mock_exec_client.invoke_sync.return_value = {
        "status": "success",
        "result": {"result": "success"},
    }

    # Invoke function to create a job
    invoke_response = client.post(
        f"/functions/{function_id}/invoke", json={"param1": "test"}
    )
    job_id = invoke_response.json()["data"]["job_id"]

    # Get job by ID
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["job_id"] == job_id
    assert data["data"]["function_id"] == function_id
    assert data["data"]["status"] == "SUCCESS"  # ✅ succeeded → success

    # Result is stored as JSON string, so parse it first
    result = (
        json.loads(data["data"]["result"])
        if isinstance(data["data"]["result"], str)
        else data["data"]["result"]
    )
    assert result["result"] == "success"


def test_get_nonexistent_job(client: TestClient):
    response = client.get("/jobs/999")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "JOB_NOT_FOUND" in data["error"]["code"]


def test_job_creation_with_failed_execution(
    client: TestClient, mock_exec_client, test_workspace
):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
        "workspace_id": str(test_workspace.id),
        "endpoint": "/test-function-failed"
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock to return failure
    mock_exec_client.invoke_sync.return_value = {
        "status": "failed",
        "error": "Execution failed",
    }

    # Invoke function
    invoke_response = client.post(
        f"/functions/{function_id}/invoke", json={"param1": "test"}
    )
    job_id = invoke_response.json()["data"]["job_id"]

    # Get the failed job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "FAILED"
    assert data["data"]["result"] is not None


def test_async_job_creation(client: TestClient, mock_exec_client, test_workspace):
    # Create an async function
    function_data = {
        "name": "test_async_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "ASYNC",
        "workspace_id": str(test_workspace.id),
        "endpoint": "/test-async-function"
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock insert_exec_queue returns True
    mock_exec_client.insert_exec_queue.return_value = True

    # Invoke async function
    invoke_response = client.post(
        f"/functions/{function_id}/invoke", json={"param1": "test"}
    )
    job_id = invoke_response.json()["data"]["job_id"]

    # Get the pending job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "PENDING"
    assert data["data"]["result"] is None


def test_multiple_jobs_for_function(
    client: TestClient, mock_exec_client, test_workspace
):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
        "workspace_id": str(test_workspace.id),
        "endpoint": "/test-multiple-jobs"
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    job_ids = []

    # Configure mock with side_effect for multiple calls
    mock_exec_client.invoke_sync.side_effect = [
        {"status": "success", "result": {"result": "success1"}},
        {"status": "failed", "error": "Failed"},
    ]

    # First successful execution
    invoke1 = client.post(f"/functions/{function_id}/invoke", json={"param1": "test1"})
    job_ids.append(invoke1.json()["data"]["job_id"])

    # Second failed execution
    invoke2 = client.post(f"/functions/{function_id}/invoke", json={"param1": "test2"})
    job_ids.append(invoke2.json()["data"]["job_id"])

    # Get function jobs
    response = client.get(f"/functions/{function_id}/jobs")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["jobs"]) == 2

    # Check that we have both jobs
    jobs = data["data"]["jobs"]
    statuses = [job["status"] for job in jobs]
    assert "SUCCESS" in statuses
    assert "FAILED" in statuses
