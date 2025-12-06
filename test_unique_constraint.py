"""
Function name unique constraint 테스트 스크립트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# 테스트용 인증 토큰 (실제 환경에서는 로그인 후 토큰 사용)
headers = {"Content-Type": "application/json"}

def test_function_name_uniqueness():
    """같은 workspace에서 동일한 function name 생성 시도"""

    print("=" * 80)
    print("Function Name Unique Constraint 테스트")
    print("=" * 80)

    # 1. 사용자 생성
    print("\n[1] 테스트 사용자 생성...")
    import random
    random_suffix = random.randint(100000, 999999)
    user_data = {
        "username": f"testuser{random_suffix}",
        "password": "testpassword123",
        "name": "Test User"
    }

    response = requests.post(f"{BASE_URL}/users/register", json=user_data)
    if response.status_code != 200:
        print(f"   [ERROR] 사용자 생성 실패: {response.text}")
        return

    print(f"   [OK] 사용자 생성 성공")

    # 로그인
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }
    response = requests.post(f"{BASE_URL}/users/login", json=login_data)
    if response.status_code != 200:
        print(f"   [ERROR] 로그인 실패: {response.text}")
        return

    result = response.json()
    token = result["access_token"]
    headers["Authorization"] = f"Bearer {token}"
    print(f"   [OK] 로그인 성공")

    # 2. Workspace 생성
    print("\n[2] Workspace 생성...")
    workspace_data = {
        "name": f"test-ws-{random_suffix}"  # 20자 제한
    }

    response = requests.post(f"{BASE_URL}/workspaces/", json=workspace_data, headers=headers)
    if response.status_code != 200:
        print(f"   [ERROR] Workspace 생성 실패: {response.text}")
        return

    result = response.json()
    print(f"   [DEBUG] Workspace 응답: {result}")  # 디버깅용
    # 응답 구조 확인
    if "data" in result:
        workspace_id = str(result["data"].get("id"))
    else:
        workspace_id = str(result.get("id"))

    print(f"   [OK] Workspace 생성 성공: {workspace_id}")

    # 3. 첫 번째 Function 생성
    print("\n[3] 첫 번째 Function 생성 (name='test-function')...")
    function1_data = {
        "name": "test-function",
        "runtime": "PYTHON",
        "code": "def handler(event, context):\n    return {'statusCode': 200, 'body': 'Hello'}",
        "execution_type": "SYNC",
        "workspace_id": workspace_id,
        "endpoint": "/test1"
    }

    response = requests.post(f"{BASE_URL}/functions/", json=function1_data, headers=headers)
    print(f"   [DEBUG] Function 생성 응답: {response.json()}")  # 디버깅용
    if response.status_code != 200:
        print(f"   [ERROR] Function 생성 실패: {response.text}")
        return

    result = response.json()
    # 응답 구조 확인
    if "data" in result:
        function1_id = str(result["data"].get("function_id") or result["data"].get("id"))
    else:
        function1_id = str(result.get("function_id") or result.get("id"))

    print(f"   [OK] Function 생성 성공: {function1_id}")

    # 4. 같은 이름의 두 번째 Function 생성 시도 (다른 endpoint)
    print("\n[4] 같은 이름으로 두 번째 Function 생성 시도...")
    print("    (name='test-function', endpoint='/test2')")
    function2_data = {
        "name": "test-function",  # 같은 이름!
        "runtime": "PYTHON",
        "code": "def handler(event, context):\n    return {'statusCode': 200, 'body': 'Hello2'}",
        "execution_type": "SYNC",
        "workspace_id": workspace_id,
        "endpoint": "/test2"  # 다른 endpoint
    }

    response = requests.post(f"{BASE_URL}/functions/", json=function2_data, headers=headers)
    if response.status_code == 200:
        print(f"   [FAIL] 중복된 이름으로 생성되어서는 안됩니다!")
        print(f"   응답: {response.json()}")
        return
    else:
        result = response.json()
        error_code = result.get("error", {}).get("code")
        error_message = result.get("error", {}).get("message", "")

        if "already exists" in error_message.lower():
            print(f"   [PASS] 예상대로 생성 실패!")
            print(f"   Error: {error_message}")
        else:
            print(f"   [WARNING] 실패했지만 다른 이유: {error_message}")

    # 5. 다른 이름으로 Function 생성 (정상 케이스)
    print("\n[5] 다른 이름으로 Function 생성 (name='another-function')...")
    function3_data = {
        "name": "another-function",  # 다른 이름
        "runtime": "NODEJS",
        "code": "exports.handler = async (event, context) => { return {statusCode: 200, body: 'Hi'}; }",
        "execution_type": "SYNC",
        "workspace_id": workspace_id,
        "endpoint": "/test3"
    }

    response = requests.post(f"{BASE_URL}/functions/", json=function3_data, headers=headers)
    if response.status_code != 200:
        print(f"   [FAIL] Function 생성 실패: {response.text}")
        return

    result = response.json()
    # 응답 구조 확인
    if "data" in result:
        function3_id = result["data"].get("function_id") or result["data"].get("id")
    else:
        function3_id = result.get("function_id") or result.get("id")

    print(f"   [PASS] Function 생성 성공: {function3_id}")

    # 6. Function 업데이트로 중복 이름 시도
    print("\n[6] Function 업데이트로 중복 이름 시도...")
    print(f"    Function {function3_id}의 name을 'test-function'으로 변경 시도")

    update_data = {
        "name": "test-function"  # 이미 존재하는 이름
    }

    response = requests.put(f"{BASE_URL}/functions/{function3_id}", json=update_data, headers=headers)
    if response.status_code == 200:
        print(f"   [FAIL] 중복된 이름으로 업데이트되어서는 안됩니다!")
        return
    else:
        result = response.json()
        error_message = result.get("error", {}).get("message", "")

        if "already exists" in error_message.lower():
            print(f"   [PASS] 예상대로 업데이트 실패!")
            print(f"   Error: {error_message}")
        else:
            print(f"   [WARNING] 실패했지만 다른 이유: {error_message}")

    # 7. 정리
    print("\n[7] 테스트 데이터 정리...")
    # Functions 삭제
    for func_id in [function1_id, function3_id]:
        requests.delete(f"{BASE_URL}/functions/{func_id}", headers=headers)

    # Workspace 삭제
    requests.delete(f"{BASE_URL}/workspaces/{workspace_id}", headers=headers)

    print("   [OK] 정리 완료")

    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_function_name_uniqueness()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Backend 서버에 연결할 수 없습니다.")
        print("        docker-compose up -d backend")
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
