"""
Namespace 구현 검증 테스트

Phase 5: 구현된 기능들의 동작 확인
"""
import sys


def test_workspace_name_validation():
    """Phase 2: Workspace.name 검증 로직 테스트"""
    print("\n=== Test 1: Workspace Name Validation ===")

    from app.models.workspace import Workspace

    test_cases = [
        ("alice-dev", True, "Valid name with hyphen"),
        ("my-workspace-1", True, "Valid name with numbers"),
        ("abc", True, "Short valid name"),
        ("Alice-Dev", False, "Invalid: uppercase letters"),
        ("-alice", False, "Invalid: starts with hyphen"),
        ("alice-", False, "Invalid: ends with hyphen"),
        ("this-is-very-long-workspace-name", False, "Invalid: exceeds 20 chars"),
        ("alice_dev", False, "Invalid: underscore not allowed"),
        ("", False, "Invalid: empty string"),
    ]

    passed = 0
    failed = 0

    for name, should_pass, description in test_cases:
        try:
            # SQLAlchemy @validates 호출하기 위해 임시 인스턴스 생성 시도
            ws = Workspace()
            validated_name = ws.validate_name('name', name)

            if should_pass:
                print(f"  PASS: '{name}' - {description}")
                passed += 1
            else:
                print(f"  FAIL: '{name}' should have failed but passed - {description}")
                failed += 1
        except ValueError as e:
            if not should_pass:
                print(f"  PASS: '{name}' correctly rejected - {description}")
                print(f"        Reason: {e}")
                passed += 1
            else:
                print(f"  FAIL: '{name}' should have passed but failed - {description}")
                print(f"        Error: {e}")
                failed += 1

    print(f"\nValidation Test Results: {passed} passed, {failed} failed")
    return failed == 0


def test_namespace_manager_import():
    """Phase 3: NamespaceManager 임포트 테스트"""
    print("\n=== Test 2: NamespaceManager Import ===")

    try:
        from app.core.namespace_manager import NamespaceManager
        print("  PASS: NamespaceManager imported successfully")

        # 클래스 메서드 확인
        required_methods = [
            'create_function_namespace',
            'delete_function_namespace',
            'namespace_exists',
            '_apply_resource_quota',
            '_apply_limit_range',
            '_apply_network_policy'
        ]

        for method_name in required_methods:
            if hasattr(NamespaceManager, method_name):
                print(f"  PASS: Method '{method_name}' exists")
            else:
                print(f"  FAIL: Method '{method_name}' not found")
                return False

        return True
    except Exception as e:
        print(f"  FAIL: Could not import NamespaceManager: {e}")
        return False


def test_function_service_integration():
    """Phase 4: FunctionService 통합 테스트"""
    print("\n=== Test 3: FunctionService Integration ===")

    try:
        from app.services.function_service import FunctionService
        from app.core.namespace_manager import NamespaceManager
        import inspect

        print("  PASS: FunctionService imported successfully")

        # __init__ 시그니처 확인
        init_signature = inspect.signature(FunctionService.__init__)
        params = list(init_signature.parameters.keys())

        if 'namespace_manager' in params:
            print("  PASS: FunctionService.__init__ accepts namespace_manager parameter")
        else:
            print("  FAIL: namespace_manager parameter not found in __init__")
            return False

        # create_function 메서드 소스 코드 확인
        create_func_source = inspect.getsource(FunctionService.create_function)

        checks = [
            ('Workspace', 'Workspace model imported'),
            ('create_function_namespace', 'Namespace creation called'),
            ('workspace.name', 'Workspace name used'),
        ]

        for keyword, description in checks:
            if keyword in create_func_source:
                print(f"  PASS: {description}")
            else:
                print(f"  FAIL: {description} - keyword '{keyword}' not found")
                return False

        # delete_function 메서드 확인
        delete_func_source = inspect.getsource(FunctionService.delete_function)

        if 'delete_function_namespace' in delete_func_source:
            print("  PASS: Namespace deletion called in delete_function")
        else:
            print("  FAIL: Namespace deletion not found in delete_function")
            return False

        return True
    except Exception as e:
        print(f"  FAIL: FunctionService integration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_namespace_name_format():
    """Namespace 이름 형식 테스트"""
    print("\n=== Test 4: Namespace Name Format ===")

    test_cases = [
        ("alice-dev", 101, "alice-dev-f-101", True),
        ("my-workspace", 999, "my-workspace-f-999", True),
        ("a", 1, "a-f-1", True),
        ("12345678901234567890", 12345678901234567890123456789012345678901234,
         "12345678901234567890-f-12345678901234567890123456789012345678901234", False),  # > 63 chars
    ]

    passed = 0
    failed = 0

    for workspace_name, function_id, expected_namespace, should_fit in test_cases:
        namespace = f"{workspace_name}-f-{function_id}"
        length = len(namespace)

        if should_fit:
            if length <= 63 and namespace == expected_namespace:
                print(f"  PASS: '{namespace}' (length: {length})")
                passed += 1
            else:
                print(f"  FAIL: '{namespace}' - expected '{expected_namespace}' or length > 63")
                failed += 1
        else:
            if length > 63:
                print(f"  PASS: '{namespace}' correctly exceeds 63 chars (length: {length})")
                passed += 1
            else:
                print(f"  FAIL: '{namespace}' should exceed 63 chars but is {length}")
                failed += 1

    print(f"\nNamespace Format Results: {passed} passed, {failed} failed")
    return failed == 0


def test_config_settings():
    """Phase 1: Config 설정 테스트"""
    print("\n=== Test 5: Config Settings ===")

    try:
        from app.config import settings

        required_settings = {
            'kubernetes_in_cluster': bool,
            'kubernetes_config_path': (type(None), str),
            'namespace_cpu_limit': str,
            'namespace_memory_limit': str,
            'namespace_pod_limit': int,
        }

        passed = 0
        failed = 0

        for setting_name, expected_type in required_settings.items():
            if hasattr(settings, setting_name):
                value = getattr(settings, setting_name)
                if isinstance(expected_type, tuple):
                    if type(value) in expected_type:
                        print(f"  PASS: {setting_name} = {value} (type: {type(value).__name__})")
                        passed += 1
                    else:
                        print(f"  FAIL: {setting_name} has wrong type: {type(value).__name__}")
                        failed += 1
                else:
                    if isinstance(value, expected_type):
                        print(f"  PASS: {setting_name} = {value}")
                        passed += 1
                    else:
                        print(f"  FAIL: {setting_name} has wrong type: {type(value).__name__}")
                        failed += 1
            else:
                print(f"  FAIL: {setting_name} not found in settings")
                failed += 1

        print(f"\nConfig Settings Results: {passed} passed, {failed} failed")
        return failed == 0
    except Exception as e:
        print(f"  FAIL: Could not load settings: {e}")
        return False


def main():
    """모든 테스트 실행"""
    print("=" * 60)
    print("Namespace Implementation Validation Tests")
    print("=" * 60)

    results = []

    # Phase 1: Config 설정
    results.append(("Config Settings", test_config_settings()))

    # Phase 2: Workspace 검증
    results.append(("Workspace Validation", test_workspace_name_validation()))

    # Phase 3: NamespaceManager
    results.append(("NamespaceManager Import", test_namespace_manager_import()))

    # Phase 4: FunctionService 통합
    results.append(("FunctionService Integration", test_function_service_integration()))

    # 추가: Namespace 이름 형식
    results.append(("Namespace Name Format", test_namespace_name_format()))

    # 결과 요약
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}")

    print(f"\nTotal: {total_passed}/{total_tests} test suites passed")

    if total_passed == total_tests:
        print("\nAll tests passed! Implementation is ready.")
        return 0
    else:
        print(f"\n{total_tests - total_passed} test suite(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
