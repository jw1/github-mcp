"""
Tests for MCP server tool handlers - ensures tools call the right client methods.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from mcp.types import TextContent

from github_mcp import server


@pytest.fixture
def mock_github_client():
    """Create a mock GitHubClient."""
    mock = Mock()
    # Set up default return values
    mock.username = "testuser"
    mock.get_user_repos.return_value = []
    mock.get_repo_details.return_value = {
        "full_name": "testuser/test-repo",
        "description": "Test repository",
        "stargazers_count": 10,
        "forks_count": 5,
        "watchers_count": 3,
        "open_issues_count": 2,
        "language": "Python",
        "private": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "default_branch": "main",
        "language_breakdown": {"Python": 1000, "JavaScript": 500},
        "topics": ["mcp", "testing"],
        "html_url": "https://github.com/testuser/test-repo",
    }
    mock.search_code.return_value = {"total_count": 0, "items": []}
    mock.get_user_events.return_value = []
    return mock


class TestGetMyRepos:
    """Test the get_my_repos tool handler."""

    @pytest.mark.asyncio
    async def test_calls_client_with_default_limit(self, mock_github_client):
        """Should call get_user_repos with default limit of 30."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_my_repos()

        mock_github_client.get_user_repos.assert_called_once_with(per_page=30)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

    @pytest.mark.asyncio
    async def test_calls_client_with_custom_limit(self, mock_github_client):
        """Should call get_user_repos with specified limit."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_my_repos(limit=50)

        mock_github_client.get_user_repos.assert_called_once_with(per_page=50)

    @pytest.mark.asyncio
    async def test_handles_no_repos(self, mock_github_client):
        """Should return appropriate message when no repos found."""
        mock_github_client.get_user_repos.return_value = []

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_my_repos()

        assert "No repositories found" in result[0].text

    @pytest.mark.asyncio
    async def test_formats_repo_list(self, mock_github_client):
        """Should format repository information."""
        mock_github_client.get_user_repos.return_value = [
            {
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "description": "A test repository",
                "stargazers_count": 5,
                "forks_count": 2,
                "language": "Python",
                "private": False,
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/testuser/test-repo",
            }
        ]

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_my_repos()

        text = result[0].text
        assert "test-repo" in text
        assert "A test repository" in text
        assert "Python" in text


class TestGetRepoDetails:
    """Test the get_repo_details tool handler."""

    @pytest.mark.asyncio
    async def test_calls_client_with_repo_name(self, mock_github_client):
        """Should call get_repo_details with the repo name."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_repo_details("test-repo")

        mock_github_client.get_repo_details.assert_called_once_with("test-repo")
        assert isinstance(result, list)
        assert isinstance(result[0], TextContent)

    @pytest.mark.asyncio
    async def test_formats_repo_details(self, mock_github_client):
        """Should format repository details."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_repo_details("testuser/test-repo")

        text = result[0].text
        assert "test-repo" in text
        assert "Test repository" in text
        assert "10" in text  # stars
        assert "Python" in text

    @pytest.mark.asyncio
    async def test_includes_language_breakdown(self, mock_github_client):
        """Should include language breakdown when available."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_repo_details("test-repo")

        text = result[0].text
        assert "Language Breakdown" in text
        assert "Python" in text
        assert "JavaScript" in text


class TestSearchMyCode:
    """Test the search_my_code tool handler."""

    @pytest.mark.asyncio
    async def test_calls_client_with_query(self, mock_github_client):
        """Should call search_code with the query."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.search_my_code("test query", limit=30)

        mock_github_client.search_code.assert_called_once_with("test query", per_page=30)
        assert isinstance(result, list)
        assert isinstance(result[0], TextContent)

    @pytest.mark.asyncio
    async def test_calls_client_with_custom_limit(self, mock_github_client):
        """Should call search_code with specified limit."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.search_my_code("query", limit=50)

        mock_github_client.search_code.assert_called_once_with("query", per_page=50)

    @pytest.mark.asyncio
    async def test_handles_no_results(self, mock_github_client):
        """Should return appropriate message when no matches found."""
        mock_github_client.search_code.return_value = {"total_count": 0, "items": []}

        with patch.object(server, 'github', mock_github_client):
            result = await server.search_my_code("nonexistent")

        assert "No code matches found" in result[0].text
        assert "nonexistent" in result[0].text

    @pytest.mark.asyncio
    async def test_formats_search_results(self, mock_github_client):
        """Should format code search results."""
        mock_github_client.search_code.return_value = {
            "total_count": 2,
            "items": [
                {
                    "repository": {"full_name": "testuser/repo1"},
                    "path": "src/main.py",
                    "html_url": "https://github.com/testuser/repo1/blob/main/src/main.py",
                }
            ],
        }

        with patch.object(server, 'github', mock_github_client):
            result = await server.search_my_code("test")

        text = result[0].text
        assert "testuser/repo1" in text
        assert "src/main.py" in text


class TestGetRecentActivity:
    """Test the get_recent_activity tool handler."""

    @pytest.mark.asyncio
    async def test_calls_client_with_default_limit(self, mock_github_client):
        """Should call get_user_events with default limit."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        mock_github_client.get_user_events.assert_called_once_with(per_page=30)
        assert isinstance(result, list)
        assert isinstance(result[0], TextContent)

    @pytest.mark.asyncio
    async def test_calls_client_with_custom_limit(self, mock_github_client):
        """Should call get_user_events with specified limit."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity(limit=50)

        mock_github_client.get_user_events.assert_called_once_with(per_page=50)

    @pytest.mark.asyncio
    async def test_handles_no_activity(self, mock_github_client):
        """Should return appropriate message when no activity found."""
        mock_github_client.get_user_events.return_value = []

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        assert "No recent activity found" in result[0].text

    @pytest.mark.asyncio
    async def test_formats_push_event(self, mock_github_client):
        """Should format PushEvent correctly."""
        mock_github_client.get_user_events.return_value = [
            {
                "type": "PushEvent",
                "repo": {"name": "testuser/test-repo"},
                "created_at": "2024-01-01T12:00:00Z",
                "payload": {
                    "ref": "refs/heads/main",
                    "commits": [{"sha": "abc123"}],
                },
            }
        ]

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        text = result[0].text
        assert "Push" in text
        assert "test-repo" in text
        assert "main" in text
        assert "1 commit" in text

    @pytest.mark.asyncio
    async def test_formats_pull_request_event(self, mock_github_client):
        """Should format PullRequestEvent correctly."""
        mock_github_client.get_user_events.return_value = [
            {
                "type": "PullRequestEvent",
                "repo": {"name": "testuser/test-repo"},
                "created_at": "2024-01-01T12:00:00Z",
                "payload": {
                    "action": "opened",
                    "pull_request": {"title": "Add new feature"},
                },
            }
        ]

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        text = result[0].text
        assert "Pull Request" in text
        assert "opened" in text
        assert "Add new feature" in text


class TestCallToolDispatcher:
    """Test the call_tool dispatcher function."""

    @pytest.mark.asyncio
    async def test_dispatches_get_my_repos(self, mock_github_client):
        """Should dispatch to get_my_repos handler."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("get_my_repos", {"limit": 10})

        mock_github_client.get_user_repos.assert_called_once_with(per_page=10)

    @pytest.mark.asyncio
    async def test_dispatches_get_repo_details(self, mock_github_client):
        """Should dispatch to get_repo_details handler."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("get_repo_details", {"repo_name": "test"})

        mock_github_client.get_repo_details.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_dispatches_search_my_code(self, mock_github_client):
        """Should dispatch to search_my_code handler."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("search_my_code", {"query": "test"})

        mock_github_client.search_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatches_get_recent_activity(self, mock_github_client):
        """Should dispatch to get_recent_activity handler."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("get_recent_activity", {})

        mock_github_client.get_user_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_unknown_tool(self, mock_github_client):
        """Should return error for unknown tool."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("unknown_tool", {})

        assert isinstance(result, list)
        assert "Error" in result[0].text
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_handles_client_errors(self, mock_github_client):
        """Should catch and format client errors."""
        mock_github_client.get_user_repos.side_effect = ValueError("API error")

        with patch.object(server, 'github', mock_github_client):
            result = await server.call_tool("get_my_repos", {})

        assert isinstance(result, list)
        assert "Error" in result[0].text
        assert "API error" in result[0].text
