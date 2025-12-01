from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models.job import JobStatus


def test_invoke_sync_function_success(client: TestClient):
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

    # Mock ExecutionClient.invoke_sync (instance method)
    with patch(
        "app.infra.execution_client.ExecutionClient.invoke_sync"
    ) as mock_invoke:
        mock_invoke.return_value = {"status": "succeeded", "result": "test_value"}

        # Invoke function
        invoke_data = {"input": {"param1": "test_value"}}

        response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "succeeded"
        assert data["data"]["result"]["result"] == "test_value"
        assert "job_id" in data["data"]
        assert data["data"]["function_id"] == function_id


def test_invoke_sync_function_failure(client: TestClient):
    # Create a function first
    function_data = {
        "name": "test_sync_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock KNative client to return failure
    with patch(
        "app.core.knative_client.knative_client.execute_function_sync"
    ) as mock_execute:
        mock_execute.return_value = {"success": False, "error": "Execution failed"}

        # Invoke function
        invoke_data = {"param1": "test_value"}

        response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "failed"
        assert data["data"]["result"] is None


def test_invoke_async_function(client: TestClient):
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

    # Mock ExecutionClient.insert_exec_queue (instance method)
    with patch(
        "app.infra.execution_client.ExecutionClient.insert_exec_queue"
    ) as mock_enqueue:
        mock_enqueue.return_value = None

        # Invoke async function
        invoke_data = {"input": {"param1": "test_value"}}

        response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
        assert response.status_code == 202

        data = response.json()
        assert data["status"] == "pending"
        assert data["result"] is None
        assert "job_id" in data


def test_get_function_jobs(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_function_jobs",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock successful execution to create a job
    with patch(
        "app.infra.execution_client.ExecutionClient.invoke_sync"
    ) as mock_invoke:
        mock_invoke.return_value = {"result": "success"}

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
    assert data["data"]["jobs"][0]["status"] == "success"


def test_get_job(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_get_job",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock successful execution
    with patch(
        "app.infra.execution_client.ExecutionClient.invoke_sync"
    ) as mock_invoke:
        mock_invoke.return_value = {"result": "success"}

        # Invoke function
        invoke_data = {"input": {"param1": "test"}}
        invoke_res = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
        job_id = invoke_res.json()["job_id"]

    # Get job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "succeeded"

