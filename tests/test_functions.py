from fastapi.testclient import TestClient


def test_create_function(client: TestClient, test_workspace):
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return {'result': 'success'}",
        "execution_type": "SYNC",
    }

    response = client.post("/functions/", json=function_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "function_id" in data["data"]


def test_get_functions_empty(client: TestClient):
    response = client.get("/functions/")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["functions"] == []


def test_get_functions_with_data(client: TestClient, test_workspace):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
    }

    create_response = client.post("/functions/", json=function_data)
    assert create_response.status_code == 200

    # Get functions
    response = client.get("/functions/")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["functions"]) == 1
    assert data["data"]["functions"][0]["name"] == "test_function"


def test_get_function_by_id(client: TestClient, test_workspace):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Get function by ID
    response = client.get(f"/functions/{function_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "test_function"
    assert data["data"]["id"] == function_id


def test_get_nonexistent_function(client: TestClient):
    response = client.get("/functions/999")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    # Function이 없거나 접근 권한이 없는 경우 ACCESS_DENIED가 반환될 수 있음
    assert "ACCESS_DENIED" in data["error"]["code"] or "FUNCTION_NOT_FOUND" in data["error"]["code"]


def test_update_function(client: TestClient, test_workspace):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Update function
    update_data = {
        "name": "updated_function",
        "code": "def handler(event): return {'updated': True}",
    }

    response = client.put(f"/functions/{function_id}", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["function_id"] == function_id


def test_delete_function(client: TestClient, test_workspace):
    # Create a function first
    function_data = {
        "name": "test_function",
        "runtime": "PYTHON",
        "code": "def handler(event): return event",
        "execution_type": "SYNC",
    }

    create_response = client.post("/functions/", json=function_data)
    function_id = create_response.json()["data"]["function_id"]

    # Delete function
    response = client.delete(f"/functions/{function_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True

    # Verify function is deleted
    get_response = client.get(f"/functions/{function_id}")
    assert get_response.json()["success"] is False


def test_create_function_with_invalid_code(client: TestClient, test_workspace):
    function_data = {
        "name": "malicious_function",
        "runtime": "PYTHON",
        "code": "import os; os.system('rm -rf /')",
        "execution_type": "SYNC",
    }

    response = client.post("/functions/", json=function_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "VALIDATION_ERROR" in data["error"]["code"]


def test_create_nodejs_function_with_syntax_error(client: TestClient, test_workspace):
    """Test that JavaScript syntax errors are caught"""
    function_data = {
        "name": "broken_js_function",
        "runtime": "NODEJS",
        "code": "function handler(event { return { message: 'Hello' }; }",  # Missing )
        "execution_type": "SYNC",
    }

    response = client.post("/functions/", json=function_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "VALIDATION_ERROR" in data["error"]["code"]
    assert "Syntax error" in data["error"]["message"]


def test_create_nodejs_function_with_dangerous_module(client: TestClient, test_workspace):
    """Test that dangerous Node.js modules are blocked"""
    function_data = {
        "name": "malicious_nodejs_function",
        "runtime": "NODEJS",
        "code": "const fs = require('fs'); function handler(e) { return fs.readFileSync('/etc/passwd'); }",
        "execution_type": "SYNC",
    }

    response = client.post("/functions/", json=function_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "VALIDATION_ERROR" in data["error"]["code"]
    assert "fs" in data["error"]["message"]


def test_create_valid_nodejs_function(client: TestClient, test_workspace):
    """Test that valid JavaScript code is accepted"""
    function_data = {
        "name": "valid_nodejs_function",
        "runtime": "NODEJS",
        "code": "function handler(event) { return { message: 'Hello World', data: event }; }",
        "execution_type": "SYNC",
    }

    response = client.post("/functions/", json=function_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "function_id" in data["data"]
