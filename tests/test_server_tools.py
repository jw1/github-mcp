"""
Tests for MCP server tool handlers - ensures tools call the right client methods.
"""

import json
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
        """Should return JSON with empty repositories when no repos found."""
        mock_github_client.get_user_repos.return_value = []

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_my_repos()

        # Parse JSON response
        data = json.loads(result[0].text)
        assert data["summary"]["user"] == "testuser"
        assert data["summary"]["count"] == 0
        assert data["repositories"] == []

    @pytest.mark.asyncio
    async def test_formats_repo_list(self, mock_github_client):
        """Should format repository information as JSON."""
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

        # Parse JSON response
        data = json.loads(result[0].text)

        # Validate summary
        assert data["summary"]["user"] == "testuser"
        assert data["summary"]["count"] == 1
        assert data["summary"]["total_stars"] == 5
        assert data["summary"]["total_forks"] == 2
        assert data["summary"]["sorted_by"] == "recently_updated"

        # Validate repository data
        assert len(data["repositories"]) == 1
        repo = data["repositories"][0]
        assert repo["name"] == "test-repo"
        assert repo["full_name"] == "testuser/test-repo"
        assert repo["description"] == "A test repository"
        assert repo["stars"] == 5
        assert repo["forks"] == 2
        assert repo["language"] == "Python"
        assert repo["visibility"] == "public"
        assert repo["updated_at"] == "2024-01-01T00:00:00Z"
        assert repo["url"] == "https://github.com/testuser/test-repo"

    @pytest.mark.asyncio
    async def test_validates_limit_too_small(self, mock_github_client):
        """Should raise ValueError when limit is less than 1."""
        with patch.object(server, 'github', mock_github_client):
            with pytest.raises(ValueError, match="limit must be between 1 and 100"):
                await server.get_my_repos(limit=0)

    @pytest.mark.asyncio
    async def test_validates_limit_too_large(self, mock_github_client):
        """Should raise ValueError when limit is greater than 100."""
        with patch.object(server, 'github', mock_github_client):
            with pytest.raises(ValueError, match="limit must be between 1 and 100"):
                await server.get_my_repos(limit=101)

    @pytest.mark.asyncio
    async def test_validates_limit_negative(self, mock_github_client):
        """Should raise ValueError when limit is negative."""
        with patch.object(server, 'github', mock_github_client):
            with pytest.raises(ValueError, match="limit must be between 1 and 100"):
                await server.get_my_repos(limit=-5)


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
        """Should format repository details as JSON."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_repo_details("testuser/test-repo")

        # Parse JSON response
        data = json.loads(result[0].text)

        # Validate basic info
        assert data["full_name"] == "testuser/test-repo"
        assert data["description"] == "Test repository"

        # Validate statistics
        assert data["statistics"]["stars"] == 10
        assert data["statistics"]["forks"] == 5
        assert data["statistics"]["watchers"] == 3
        assert data["statistics"]["open_issues"] == 2

        # Validate details
        assert data["details"]["primary_language"] == "Python"
        assert data["details"]["visibility"] == "public"
        assert data["details"]["default_branch"] == "main"
        assert data["details"]["created_at"] == "2024-01-01T00:00:00Z"
        assert data["details"]["updated_at"] == "2024-01-02T00:00:00Z"

    @pytest.mark.asyncio
    async def test_includes_language_breakdown(self, mock_github_client):
        """Should include language breakdown percentages when available."""
        with patch.object(server, 'github', mock_github_client):
            result = await server.get_repo_details("test-repo")

        # Parse JSON response
        data = json.loads(result[0].text)

        # Validate language breakdown (percentages)
        assert "language_breakdown" in data
        assert "Python" in data["language_breakdown"]
        assert "JavaScript" in data["language_breakdown"]
        # 1000 / 1500 = 66.7%
        assert data["language_breakdown"]["Python"] == 66.7
        # 500 / 1500 = 33.3%
        assert data["language_breakdown"]["JavaScript"] == 33.3

        # Validate topics and URLs
        assert data["topics"] == ["mcp", "testing"]
        assert data["urls"]["repository"] == "https://github.com/testuser/test-repo"


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
        """Should return JSON with empty matches when no results found."""
        mock_github_client.search_code.return_value = {"total_count": 0, "items": []}

        with patch.object(server, 'github', mock_github_client):
            result = await server.search_my_code("nonexistent")

        # Parse JSON response
        data = json.loads(result[0].text)
        assert data["query"] == "nonexistent"
        assert data["total_count"] == 0
        assert data["matches"] == []

    @pytest.mark.asyncio
    async def test_formats_search_results(self, mock_github_client):
        """Should format code search results as JSON."""
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

        # Parse JSON response
        data = json.loads(result[0].text)

        assert data["query"] == "test"
        assert data["total_count"] == 2
        assert data["returned_count"] == 1
        assert len(data["matches"]) == 1

        match = data["matches"][0]
        assert match["repository"] == "testuser/repo1"
        assert match["path"] == "src/main.py"
        assert match["url"] == "https://github.com/testuser/repo1/blob/main/src/main.py"

    @pytest.mark.asyncio
    async def test_validates_limit_out_of_range(self, mock_github_client):
        """Should raise ValueError when limit is out of valid range."""
        with patch.object(server, 'github', mock_github_client):
            with pytest.raises(ValueError, match="limit must be between 1 and 100"):
                await server.search_my_code("test", limit=150)


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
        """Should return JSON with empty events when no activity found."""
        mock_github_client.get_user_events.return_value = []

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        # Parse JSON response
        data = json.loads(result[0].text)
        assert data["user"] == "testuser"
        assert data["events"] == []

    @pytest.mark.asyncio
    async def test_formats_push_event(self, mock_github_client):
        """Should format PushEvent as JSON with branch and commit count."""
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

        # Parse JSON response
        data = json.loads(result[0].text)

        assert data["user"] == "testuser"
        assert data["event_count"] == 1
        assert len(data["events"]) == 1

        event = data["events"][0]
        assert event["type"] == "PushEvent"
        assert event["repository"] == "testuser/test-repo"
        assert event["created_at"] == "2024-01-01T12:00:00Z"
        assert event["details"]["branch"] == "main"
        assert event["details"]["commit_count"] == 1

    @pytest.mark.asyncio
    async def test_formats_pull_request_event(self, mock_github_client):
        """Should format PullRequestEvent as JSON with action and title."""
        mock_github_client.get_user_events.return_value = [
            {
                "type": "PullRequestEvent",
                "repo": {"name": "testuser/test-repo"},
                "created_at": "2024-01-01T12:00:00Z",
                "payload": {
                    "action": "opened",
                    "pull_request": {"title": "Add new feature", "number": 42},
                },
            }
        ]

        with patch.object(server, 'github', mock_github_client):
            result = await server.get_recent_activity()

        # Parse JSON response
        data = json.loads(result[0].text)

        event = data["events"][0]
        assert event["type"] == "PullRequestEvent"
        assert event["repository"] == "testuser/test-repo"
        assert event["details"]["action"] == "opened"
        assert event["details"]["title"] == "Add new feature"
        assert event["details"]["number"] == 42

    @pytest.mark.asyncio
    async def test_validates_limit_boundary(self, mock_github_client):
        """Should raise ValueError when limit is at boundary."""
        with patch.object(server, 'github', mock_github_client):
            with pytest.raises(ValueError, match="limit must be between 1 and 100"):
                await server.get_recent_activity(limit=0)


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
