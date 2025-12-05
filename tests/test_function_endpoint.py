"""
Tests for Function endpoint functionality.

Tests endpoint auto-generation, validation, and uniqueness.
"""

from unittest.mock import MagicMock

import pytest

from app.core.sanitize import (
    SanitizationError,
    sanitize_function_endpoint,
    validate_custom_endpoint,
)


class TestFunctionEndpointSanitization:
    """Test function endpoint sanitization and generation"""

    def test_basic_endpoint_generation(self):
        """Basic endpoint should start with / and be lowercase"""
        assert sanitize_function_endpoint("MyFunction") == "/myfunction"
        assert sanitize_function_endpoint("my-function") == "/my-function"
        assert sanitize_function_endpoint("function123") == "/function123"

    def test_special_characters_converted_to_hyphen(self):
        """Special characters should be converted to hyphens"""
        assert sanitize_function_endpoint("my function") == "/my-function"
        assert sanitize_function_endpoint("my@function") == "/my-function"
        assert sanitize_function_endpoint("my_function") == "/my-function"
        assert sanitize_function_endpoint("my.function") == "/my-function"

    def test_consecutive_hyphens_removed(self):
        """Consecutive hyphens should be collapsed to single hyphen"""
        assert sanitize_function_endpoint("my--function") == "/my-function"
        assert sanitize_function_endpoint("my___function") == "/my-function"
        assert sanitize_function_endpoint("my   function") == "/my-function"

    def test_leading_trailing_special_chars_removed(self):
        """Leading and trailing special characters should be removed"""
        assert sanitize_function_endpoint("-function") == "/function"
        assert sanitize_function_endpoint("function-") == "/function"
        assert sanitize_function_endpoint("/function/") == "/function"

    def test_length_limit_enforced(self):
        """Endpoint should be truncated to 100 characters (including /)"""
        long_name = "a" * 150
        endpoint = sanitize_function_endpoint(long_name)
        assert len(endpoint) == 100  # / + 99 characters
        assert endpoint.startswith("/")

    def test_empty_name_raises_error(self):
        """Empty names should raise error"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            sanitize_function_endpoint("")

    def test_only_special_characters_raises_error(self):
        """Names with only special characters should raise error"""
        with pytest.raises(SanitizationError, match="비어있습니다"):
            sanitize_function_endpoint("@@@")

    def test_duplicate_handling_without_db(self):
        """Without db, should return base endpoint"""
        endpoint = sanitize_function_endpoint("myfunction", db=None)
        assert endpoint == "/myfunction"

    def test_duplicate_handling_with_db(self):
        """With db, should handle duplicates by adding suffix"""
        mock_db = MagicMock()

        # Mock existing function with endpoint "/myfunction"
        mock_existing = MagicMock()
        mock_existing.endpoint = "/myfunction"

        # First query returns existing, second returns None
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing,  # First attempt: duplicate found
            None,  # Second attempt: no duplicate
        ]

        endpoint = sanitize_function_endpoint("myfunction", db=mock_db)
        assert endpoint == "/myfunction-2"

    def test_multiple_duplicates_handling(self):
        """Should keep incrementing suffix until unique endpoint found"""
        mock_db = MagicMock()

        mock_existing1 = MagicMock()
        mock_existing2 = MagicMock()
        mock_existing3 = MagicMock()

        # Simulate: /myfunction, /myfunction-2, /myfunction-3 exist
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing1,  # /myfunction exists
            mock_existing2,  # /myfunction-2 exists
            mock_existing3,  # /myfunction-3 exists
            None,  # /myfunction-4 is free
        ]

        endpoint = sanitize_function_endpoint("myfunction", db=mock_db, max_attempts=10)
        assert endpoint == "/myfunction-4"

    def test_max_attempts_exceeded(self):
        """Should raise error if max attempts exceeded"""
        mock_db = MagicMock()

        # Always return existing function
        mock_existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_existing
        )

        with pytest.raises(
            SanitizationError, match="unique한 endpoint를 생성할 수 없습니다"
        ):
            sanitize_function_endpoint("myfunction", db=mock_db, max_attempts=3)

    def test_slashes_in_name_handled(self):
        """Slashes in function name should be preserved (for nested paths)"""
        assert sanitize_function_endpoint("api/v1/handler") == "/api/v1/handler"
        assert sanitize_function_endpoint("user//profile") == "/user/profile"

    def test_real_world_function_names(self):
        """Test real-world function name scenarios"""
        test_cases = [
            ("Process Payment", "/process-payment"),
            ("getUserProfile", "/getuserprofile"),
            ("calculate_tax_2024", "/calculate-tax-2024"),
            ("API Handler v2", "/api-handler-v2"),
            ("send-email-notification", "/send-email-notification"),
        ]

        for input_name, expected_endpoint in test_cases:
            endpoint = sanitize_function_endpoint(input_name)
            assert endpoint == expected_endpoint


class TestCustomEndpointValidation:
    """Test custom endpoint validation"""

    def test_valid_custom_endpoints(self):
        """Valid custom endpoints should pass"""
        valid_endpoints = [
            "/myfunction",
            "/my-function",
            "/api/v1/handler",
            "/user-profile",
            "/a",
        ]
        for endpoint in valid_endpoints:
            result = validate_custom_endpoint(endpoint)
            assert result == endpoint

    def test_must_start_with_slash(self):
        """Endpoint must start with /"""
        with pytest.raises(SanitizationError, match="/로 시작해야 합니다"):
            validate_custom_endpoint("myfunction")

        with pytest.raises(SanitizationError, match="/로 시작해야 합니다"):
            validate_custom_endpoint("api/v1/handler")

    def test_empty_endpoint_rejected(self):
        """Empty endpoint should be rejected"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            validate_custom_endpoint("")

    def test_length_limit_enforced(self):
        """Endpoint longer than 100 characters should be rejected"""
        long_endpoint = "/" + "a" * 100
        with pytest.raises(SanitizationError, match="100자 이하여야 합니다"):
            validate_custom_endpoint(long_endpoint)

    def test_invalid_characters_rejected(self):
        """Invalid characters should be rejected"""
        invalid_endpoints = [
            "/my function",  # space
            "/my@function",  # @
            "/my_function",  # underscore
            "/my.function",  # period
            "/my$function",  # dollar
            "/MY-FUNCTION",  # uppercase
        ]
        for endpoint in invalid_endpoints:
            with pytest.raises(
                SanitizationError, match="소문자, 숫자, 하이픈, 슬래시만"
            ):
                validate_custom_endpoint(endpoint)

    def test_consecutive_hyphens_rejected(self):
        """Consecutive hyphens should be rejected"""
        with pytest.raises(SanitizationError, match="연속된 하이픈"):
            validate_custom_endpoint("/my--function")

    def test_consecutive_slashes_rejected(self):
        """Consecutive slashes should be rejected"""
        with pytest.raises(SanitizationError, match="연속된 슬래시"):
            validate_custom_endpoint("/my//function")

    def test_trailing_hyphen_rejected(self):
        """Endpoint ending with hyphen should be rejected"""
        with pytest.raises(SanitizationError, match="하이픈으로 끝날 수 없습니다"):
            validate_custom_endpoint("/my-function-")

    def test_only_slash_rejected(self):
        """Endpoint with only / should be rejected"""
        with pytest.raises(SanitizationError, match="소문자, 숫자, 하이픈, 슬래시만"):
            validate_custom_endpoint("/")

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed"""
        assert validate_custom_endpoint("  /myfunction  ") == "/myfunction"
        assert validate_custom_endpoint("\t/myfunction\n") == "/myfunction"

    def test_nested_paths_allowed(self):
        """Nested paths with multiple slashes should be allowed"""
        assert validate_custom_endpoint("/api/v1/users") == "/api/v1/users"
        assert validate_custom_endpoint("/a/b/c/d") == "/a/b/c/d"


class TestFunctionEndpointIntegration:
    """Integration tests for function endpoint"""

    def test_endpoint_length_with_suffix(self):
        """Endpoint with suffix should not exceed 100 characters"""
        # 99-character base name
        long_name = "a" * 99
        mock_db = MagicMock()
        mock_existing = MagicMock()

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing,  # exists
            None,  # truncated version with suffix is free
        ]

        endpoint = sanitize_function_endpoint(long_name, db=mock_db)

        # Should be truncated to make room for "-2" suffix
        assert len(endpoint) <= 100
        assert endpoint.endswith("-2")

    def test_complex_endpoint_scenarios(self):
        """Test complex real-world scenarios"""
        # Scenario 1: API versioning
        assert (
            sanitize_function_endpoint("API v1 User Handler") == "/api-v1-user-handler"
        )

        # Scenario 2: Event handlers
        assert (
            sanitize_function_endpoint("on_user_created_event")
            == "/on-user-created-event"
        )

        # Scenario 3: Microservice style
        assert sanitize_function_endpoint("auth.service.login") == "/auth-service-login"

    def test_security_injection_attempts(self):
        """Test that injection attempts are safely handled"""
        # SQL injection attempts should be sanitized
        assert sanitize_function_endpoint("'; DROP TABLE--") == "/drop-table"

        # Path traversal should be sanitized (.. becomes -)
        assert sanitize_function_endpoint("../../../etc/passwd") == "/-/-/etc/passwd"

        # Command injection should be sanitized (trailing / becomes -)
        assert sanitize_function_endpoint("func; rm -rf /") == "/func-rm-rf-"


class TestEmptyEndpointHandling:
    """Test handling of empty endpoint values"""

    def test_empty_string_endpoint_raises_error(self):
        """Empty string endpoint should raise error"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            sanitize_function_endpoint("")

    def test_whitespace_only_endpoint_raises_error(self):
        """Whitespace-only endpoint should raise error"""
        with pytest.raises(SanitizationError, match="비어있습니다"):
            sanitize_function_endpoint("   ")

    def test_empty_custom_endpoint_validation(self):
        """Empty custom endpoint should be rejected"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            validate_custom_endpoint("")

    def test_whitespace_custom_endpoint_validation(self):
        """Whitespace-only custom endpoint should be rejected"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            validate_custom_endpoint("   ")
