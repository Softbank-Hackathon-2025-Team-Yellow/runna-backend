"""
Tests for Workspace alias functionality.

Tests alias auto-generation, uniqueness, and immutability.
"""
import pytest
from unittest.mock import MagicMock
from app.core.sanitize import sanitize_workspace_alias, SanitizationError


class TestWorkspaceAliasSanitization:
    """Test workspace alias sanitization and generation"""

    def test_basic_alias_generation(self):
        """Basic alias should be lowercase and clean"""
        assert sanitize_workspace_alias("MyWorkspace") == "myworkspace"
        assert sanitize_workspace_alias("My-Workspace") == "my-workspace"
        assert sanitize_workspace_alias("workspace123") == "workspace123"

    def test_special_characters_converted_to_hyphen(self):
        """Special characters should be converted to hyphens"""
        assert sanitize_workspace_alias("my workspace") == "my-workspace"
        assert sanitize_workspace_alias("my@workspace") == "my-workspace"
        assert sanitize_workspace_alias("my_workspace") == "my-workspace"
        assert sanitize_workspace_alias("my.workspace") == "my-workspace"

    def test_consecutive_hyphens_removed(self):
        """Consecutive hyphens should be collapsed to single hyphen"""
        assert sanitize_workspace_alias("my--workspace") == "my-workspace"
        assert sanitize_workspace_alias("my___workspace") == "my-workspace"
        assert sanitize_workspace_alias("my   workspace") == "my-workspace"

    def test_leading_trailing_hyphens_removed(self):
        """Leading and trailing hyphens should be removed"""
        assert sanitize_workspace_alias("-workspace") == "workspace"
        assert sanitize_workspace_alias("workspace-") == "workspace"
        assert sanitize_workspace_alias("-workspace-") == "workspace"

    def test_length_limit_enforced(self):
        """Alias should be truncated to 20 characters"""
        long_name = "a" * 30
        alias = sanitize_workspace_alias(long_name)
        assert len(alias) == 20
        assert alias == "a" * 20

    def test_length_limit_with_trailing_hyphen(self):
        """Truncation should not leave trailing hyphen"""
        # 21 characters with hyphen at position 20
        name = "a" * 19 + "-b"
        alias = sanitize_workspace_alias(name)
        assert len(alias) == 19
        assert not alias.endswith("-")

    def test_empty_name_raises_error(self):
        """Empty names should raise error"""
        with pytest.raises(SanitizationError, match="비어있을 수 없습니다"):
            sanitize_workspace_alias("")

    def test_only_special_characters_raises_error(self):
        """Names with only special characters should raise error"""
        with pytest.raises(SanitizationError, match="비어있습니다"):
            sanitize_workspace_alias("@@@")

        with pytest.raises(SanitizationError, match="비어있습니다"):
            sanitize_workspace_alias("___")

    def test_reserved_names_get_suffix(self):
        """Reserved Kubernetes names should get -ws suffix"""
        assert sanitize_workspace_alias("default") == "default-ws"
        assert sanitize_workspace_alias("kube-system") == "kube-system-ws"
        assert sanitize_workspace_alias("kube-public") == "kube-public-ws"
        assert sanitize_workspace_alias("kube-node-lease") == "kube-node-lease-ws"

    def test_duplicate_handling_without_db(self):
        """Without db, should return base alias"""
        alias = sanitize_workspace_alias("myworkspace", db=None)
        assert alias == "myworkspace"

    def test_duplicate_handling_with_db(self):
        """With db, should handle duplicates by adding suffix"""
        # Mock database session
        mock_db = MagicMock()

        # Mock existing workspace with alias "myworkspace"
        mock_existing = MagicMock()
        mock_existing.alias = "myworkspace"

        # First query returns existing, second returns None
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing,  # First attempt: duplicate found
            None            # Second attempt: no duplicate
        ]

        alias = sanitize_workspace_alias("myworkspace", db=mock_db)
        assert alias == "myworkspace-2"

    def test_multiple_duplicates_handling(self):
        """Should keep incrementing suffix until unique alias found"""
        mock_db = MagicMock()

        # Mock 3 existing workspaces
        mock_existing1 = MagicMock()
        mock_existing2 = MagicMock()
        mock_existing3 = MagicMock()

        # Simulate: myworkspace, myworkspace-2, myworkspace-3 exist
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing1,  # myworkspace exists
            mock_existing2,  # myworkspace-2 exists
            mock_existing3,  # myworkspace-3 exists
            None             # myworkspace-4 is free
        ]

        alias = sanitize_workspace_alias("myworkspace", db=mock_db, max_attempts=10)
        assert alias == "myworkspace-4"

    def test_max_attempts_exceeded(self):
        """Should raise error if max attempts exceeded"""
        mock_db = MagicMock()

        # Always return existing workspace
        mock_existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        with pytest.raises(SanitizationError, match="unique한 alias를 생성할 수 없습니다"):
            sanitize_workspace_alias("myworkspace", db=mock_db, max_attempts=3)

    def test_unicode_and_emoji_removed(self):
        """Unicode and emoji should be removed/converted"""
        assert sanitize_workspace_alias("my😀workspace") == "my-workspace"
        assert sanitize_workspace_alias("my한글workspace") == "my-workspace"
        assert sanitize_workspace_alias("ñoño") == "o-o"


class TestWorkspaceAliasIntegration:
    """Integration tests for workspace alias with database models"""

    def test_alias_length_stays_under_limit_with_suffix(self):
        """Alias with suffix should not exceed 20 characters"""
        # 20-character base name
        long_name = "a" * 20
        mock_db = MagicMock()
        mock_existing = MagicMock()

        # First attempt returns duplicate
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_existing,  # myworkspace exists
            None            # truncated version with suffix is free
        ]

        alias = sanitize_workspace_alias(long_name, db=mock_db)

        # Should be truncated to make room for "-2" suffix
        assert len(alias) <= 20
        assert alias.endswith("-2")

    def test_real_world_workspace_names(self):
        """Test real-world workspace name scenarios"""
        test_cases = [
            ("Alice's Dev Workspace", "alice-s-dev-workspac"),  # Truncated to 20 chars
            ("Bob & Co. Production", "bob-co-production"),
            ("Team #1 Staging", "team-1-staging"),
            ("TEST_ENV_2024", "test-env-2024"),
            ("my.awesome.project", "my-awesome-project"),
        ]

        for input_name, expected_alias in test_cases:
            alias = sanitize_workspace_alias(input_name)
            assert alias == expected_alias
            assert len(alias) <= 20  # Always under limit
