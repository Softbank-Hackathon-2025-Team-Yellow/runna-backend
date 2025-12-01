from fastapi.testclient import TestClient


def test_invoke_sync_function_success(client: TestClient, mock_exec_client):
    # Create a function first
    function_data = {
        "name": "test_sync_function",
        "runtime": "python",
        "code": "def handler(event): return {'result': event.get('param1', 'default')}",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    assert create_response.status_code == 200
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for success
    mock_exec_client.invoke_sync.return_value = {
        "status": "succeeded",
        "result": {"result": "test_value"},
    }

    # Invoke function
    invoke_data = {"input": {"param1": "test_value"}}

    response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "success"  # JobStatus.SUCCESS
    assert "job_id" in data["data"]
    assert data["data"]["function_id"] == function_id


def test_invoke_sync_function_failure(client: TestClient, mock_exec_client):
    # Create a function first
    function_data = {
        "name": "test_sync_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for failure
    mock_exec_client.invoke_sync.return_value = {
        "status": "failed",
        "error": "Execution failed",
    }

    # Invoke function
    invoke_data = {"param1": "test_value"}

    response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "failed"
    assert data["data"]["result"] is not None  # Error message stored


def test_invoke_async_function(client: TestClient, mock_exec_client):
    # Create an async function
    function_data = {
        "name": "test_async_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "async",
    }

    create_response = client.post("/functions/", json=function_data)
    assert create_response.status_code == 200
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for async
    mock_exec_client.insert_exec_queue.return_value = True

    # Invoke async function
    invoke_data = {"input": {"param1": "test_value"}}

    response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
    assert response.status_code == 200  # ✅ Changed from 202 to match standard response

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "pending"
    assert data["data"]["result"] is None
    assert "job_id" in data["data"]


def test_get_function_jobs(client: TestClient, mock_exec_client):
    # Create a function
    function_data = {
        "name": "test_function_jobs",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for success
    mock_exec_client.invoke_sync.return_value = {
        "status": "succeeded",
        "result": {"result": "success"},
    }

    # Invoke function to create a job
    invoke_data = {"input": {"param1": "test"}}
    client.post(f"/functions/{function_id}/invoke", json=invoke_data)

    # Get function jobs
    response = client.get(f"/functions/{function_id}/jobs")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["jobs"]) == 1
    assert data["data"]["jobs"][0]["function_id"] == function_id
    assert data["data"]["jobs"][0]["status"] == "success"  # JobStatus.SUCCESS


def test_get_job(client: TestClient, mock_exec_client):
    # Create a function
    function_data = {
        "name": "test_get_job",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Configure mock for success
    mock_exec_client.invoke_sync.return_value = {
        "status": "succeeded",
        "result": {"result": "success"},
    }

    # Invoke function
    invoke_data = {"input": {"param1": "test"}}
    invoke_res = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
    job_id = invoke_res.json()["data"]["job_id"]  # ✅ Changed from direct "job_id"

    # Get job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True  # ✅ Standard response format
    assert data["data"]["job_id"] == job_id
    assert data["data"]["status"] == "success"  # ✅ JobStatus.SUCCESS
