"""
Tests for GitHubClient - focusing on error handling and parsing logic.
"""

import pytest
import httpx
from unittest.mock import Mock, patch

from github_mcp.github_client import GitHubClient


@pytest.fixture
def github_client():
    """Create a GitHubClient instance for testing."""
    return GitHubClient(token="test_token", username="testuser")


class TestRepoNameParsing:
    """Test the _parse_repo_name method."""

    def test_parse_repo_name_with_owner(self, github_client):
        """Should split 'owner/repo' format."""
        owner, repo = github_client._parse_repo_name("octocat/hello-world")
        assert owner == "octocat"
        assert repo == "hello-world"

    def test_parse_repo_name_without_owner(self, github_client):
        """Should prepend username when no owner specified."""
        owner, repo = github_client._parse_repo_name("my-repo")
        assert owner == "testuser"
        assert repo == "my-repo"

    def test_parse_repo_name_with_multiple_slashes(self, github_client):
        """Should only split on first slash."""
        owner, repo = github_client._parse_repo_name("owner/repo/extra")
        assert owner == "owner"
        assert repo == "repo/extra"

    def test_parse_repo_name_empty_string(self, github_client):
        """Should handle empty string."""
        owner, repo = github_client._parse_repo_name("")
        assert owner == "testuser"
        assert repo == ""


class TestErrorHandling:
    """Test API error handling and user-friendly messages."""

    def test_401_authentication_failed(self, github_client):
        """Should raise ValueError with auth message on 401."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Bad credentials"

        with patch.object(github_client.client, 'request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=Mock(),
                response=mock_response
            )

            with pytest.raises(ValueError, match="Authentication failed. Check your GITHUB_TOKEN"):
                github_client._api_request("GET", "/user/repos")

    def test_403_rate_limit(self, github_client):
        """Should raise ValueError with rate limit message on 403."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"
        mock_response.headers = {"X-RateLimit-Reset": "1234567890"}

        with patch.object(github_client.client, 'request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "403 Forbidden",
                request=Mock(),
                response=mock_response
            )

            with pytest.raises(ValueError, match="GitHub API rate limit exceeded"):
                github_client._api_request("GET", "/user/repos")

    def test_403_permissions(self, github_client):
        """Should raise ValueError with permission message on 403 (not rate limit)."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Resource not accessible by integration"
        mock_response.headers = {}

        with patch.object(github_client.client, 'request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "403 Forbidden",
                request=Mock(),
                response=mock_response
            )

            with pytest.raises(ValueError, match="Access forbidden.*token permissions"):
                github_client._api_request("GET", "/user/repos")

    def test_404_not_found(self, github_client):
        """Should raise ValueError with not found message on 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(github_client.client, 'request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=mock_response
            )

            with pytest.raises(ValueError, match="Resource not found or not accessible"):
                github_client._api_request("GET", "/repos/owner/nonexistent")


class TestRateLimitWarning:
    """Test rate limit warning when limits are low."""

    def test_rate_limit_warning_when_low(self, github_client, caplog):
        """Should log warning when remaining requests < 100."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "50"}
        mock_response.json.return_value = {"data": "test"}

        with patch.object(github_client.client, 'request', return_value=mock_response):
            import logging
            with caplog.at_level(logging.WARNING):
                github_client._api_request("GET", "/user/repos")

            assert "rate limit low: 50 requests remaining" in caplog.text

    def test_no_warning_when_rate_limit_ok(self, github_client, caplog):
        """Should not log warning when remaining requests >= 100."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = {"data": "test"}

        with patch.object(github_client.client, 'request', return_value=mock_response):
            import logging
            with caplog.at_level(logging.WARNING):
                github_client._api_request("GET", "/user/repos")

            assert "rate limit" not in caplog.text


class TestSuccessfulRequests:
    """Test successful API requests."""

    def test_successful_api_request(self, github_client):
        """Should return JSON response on successful request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = {"name": "test-repo"}

        with patch.object(github_client.client, 'request', return_value=mock_response):
            result = github_client._api_request("GET", "/repos/owner/repo")

        assert result == {"name": "test-repo"}

    def test_get_user_repos_constructs_correct_url(self, github_client):
        """Should call /user/repos with correct parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = []

        with patch.object(github_client.client, 'request', return_value=mock_response) as mock_request:
            github_client.get_user_repos(per_page=50, sort="updated")

            # Verify the request was made correctly
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert args[0] == "GET"
            assert "https://api.github.com/user/repos" in args[1]
            assert kwargs["params"]["per_page"] == 50
            assert kwargs["params"]["sort"] == "updated"

    def test_get_repo_details_with_owner(self, github_client):
        """Should call correct endpoint when owner specified."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = {"name": "test-repo"}

        with patch.object(github_client.client, 'request', return_value=mock_response) as mock_request:
            github_client.get_repo_details("octocat/hello-world")

            # Verify correct endpoint was called
            args = mock_request.call_args_list[0][0]
            assert "/repos/octocat/hello-world" in args[1]

    def test_get_repo_details_without_owner(self, github_client):
        """Should prepend username when owner not specified."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = {"name": "test-repo"}

        with patch.object(github_client.client, 'request', return_value=mock_response) as mock_request:
            github_client.get_repo_details("my-repo")

            # Verify username was prepended
            args = mock_request.call_args_list[0][0]
            assert "/repos/testuser/my-repo" in args[1]

    def test_search_code_constructs_query(self, github_client):
        """Should add 'user:{username}' to search query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = {"total_count": 0, "items": []}

        with patch.object(github_client.client, 'request', return_value=mock_response) as mock_request:
            github_client.search_code("test query")

            # Verify query includes user filter
            kwargs = mock_request.call_args[1]
            assert kwargs["params"]["q"] == "test query user:testuser"
