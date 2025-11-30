from unittest.mock import patch

from fastapi.testclient import TestClient


def test_invoke_sync_function_success(client: TestClient):
    # Create a function first
    function_data = {
        "name": "test_sync_function",
        "runtime": "python",
        "code": "def handler(event): return {'result': event.get('param1', 'default')}",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock KNative client to return success
    with patch(
        "app.core.knative_client.knative_client.execute_function_sync"
    ) as mock_execute:
        mock_execute.return_value = {
            "success": True,
            "output": {"result": "test_value"},
        }

        # Invoke function
        invoke_data = {"param1": "test_value", "param2": "another_value"}

        response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "succeeded"
        assert data["data"]["result"]["result"] == "test_value"
        assert "id" in data["data"]
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
    function_id = create_response.json()["data"]["function_id"]

    # Invoke async function
    invoke_data = {"param1": "test_value"}

    response = client.post(f"/functions/{function_id}/invoke", json=invoke_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "pending"
    assert data["data"]["result"] is None
    assert "id" in data["data"]


def test_invoke_nonexistent_function(client: TestClient):
    invoke_data = {"param1": "test_value"}

    response = client.post("/functions/999/invoke", json=invoke_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "FUNCTION_NOT_FOUND" in data["error"]["code"]


def test_get_function_jobs(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Mock successful execution
    with patch(
        "app.core.knative_client.knative_client.execute_function_sync"
    ) as mock_execute:
        mock_execute.return_value = {"success": True, "output": {"result": "success"}}

        # Invoke function to create a job
        invoke_data = {"param1": "test"}
        client.post(f"/functions/{function_id}/invoke", json=invoke_data)

    # Get function jobs
    response = client.get(f"/functions/{function_id}/jobs")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["jobs"]) == 1
    assert data["data"]["jobs"][0]["function_id"] == function_id
    assert data["data"]["jobs"][0]["status"] == "succeeded"


def test_get_function_metrics(client: TestClient):
    # Create a function
    function_data = {
        "name": "test_function",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Get metrics (should be empty initially)
    response = client.get(f"/functions/{function_id}/metrics")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["invocations"]["total"] == 0
    assert data["data"]["success_rate"] == 0
