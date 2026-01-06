"""
GitHub API client with Personal Access Token authentication.

The GitHub API uses simple token-based authentication:
1. Create a Personal Access Token at https://github.com/settings/tokens
2. Use token in Authorization header for all requests
3. No token refresh needed (tokens are long-lived)
"""

import logging
from typing import Any, Optional, Union, cast

import httpx


logger = logging.getLogger("github-mcp")

# Constants
RATE_LIMIT_WARNING_THRESHOLD = 100
DEFAULT_TIMEOUT = 30.0


class GitHubClient:
    """Client for interacting with the GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, username: str):
        """
        Initialize the GitHub client.

        Args:
            token: GitHub Personal Access Token
            username: GitHub username (e.g., 'jw1')
        """
        self.token = token
        self.username = username
        self.client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close HTTP client."""
        self.close()
        return False

    def close(self):
        """Close the HTTP client and release resources."""
        if hasattr(self, 'client'):
            self.client.close()

    def _api_request(self, method: str, endpoint: str, **kwargs) -> Union[dict[str, Any], list[Any]]:
        """
        Make an authenticated API request to GitHub.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/user/repos')
            **kwargs: Additional arguments to pass to httpx

        Returns:
            API response as dictionary or list

        Raises:
            httpx.HTTPStatusError: For HTTP errors
        """
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.client.request(method, url, **kwargs)
            response.raise_for_status()

            # Check rate limiting
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining and int(remaining) < RATE_LIMIT_WARNING_THRESHOLD:
                logger.warning(
                    f"GitHub API rate limit low: {remaining} requests remaining"
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            
            if status_code == 401:
                raise ValueError(
                    "Authentication failed. Check your GITHUB_TOKEN."
                ) from e
            
            elif status_code == 403:
                # Could be rate limit or insufficient permissions
                if "rate limit" in e.response.text.lower():
                    reset_time = e.response.headers.get("X-RateLimit-Reset", "unknown")
                    raise ValueError(
                        f"GitHub API rate limit exceeded. Resets at: {reset_time}"
                    ) from e
                else:
                    raise ValueError(
                        "Access forbidden. Check token permissions (need 'repo' scope)."
                    ) from e
                
            elif status_code == 404:
                raise ValueError("Resource not found or not accessible.") from e
            
            else:
                raise ValueError(f"GitHub API error: {e.response.text}") from e

    def _parse_repo_name(self, repo_name: str) -> tuple[str, str]:
        """
        Parse repository name into owner and repo.

        Args:
            repo_name: Either 'owner/repo' or just 'repo'

        Returns:
            Tuple of (owner, repo)
        """
        if "/" in repo_name:
            parts = repo_name.split("/", 1)
            return parts[0], parts[1]
        else:
            # assume authenticated user's repo
            return self.username, repo_name

    def get_user_repos(
        self, per_page: int = 100, sort: str = "updated"
    ) -> list[dict[str, Any]]:
        """
        Get all repositories for the authenticated user.

        Args:
            per_page: Number of results per page (max 100)
            sort: Sort order ('created', 'updated', 'pushed', 'full_name')

        Returns:
            List of repository dictionaries
        """
        params = {
            "per_page": min(per_page, 100),
            "sort": sort,
            "affiliation": "owner,collaborator,organization_member",
        }

        repos = cast(list[dict[str, Any]], self._api_request("GET", "/user/repos", params=params))
        return repos

    def get_repo_details(self, repo_name: str) -> dict[str, Any]:
        """
        Get detailed information about a specific repository.

        Args:
            repo_name: Repository name as 'owner/repo' or just 'repo'

        Returns:
            Repository details including stats, languages, and topics
        """
        owner, repo = self._parse_repo_name(repo_name)
        endpoint = f"/repos/{owner}/{repo}"

        # Get basic repo info
        repo_data = cast(dict[str, Any], self._api_request("GET", endpoint))

        # Try to get language breakdown (not critical if it fails).
        # The languages endpoint should return a mapping of language -> bytes (ints).
        try:
            languages = self._api_request("GET", f"{endpoint}/languages")

            # Safely handle unexpected types coming from the API or mocks.
            if isinstance(languages, dict):
                coerced: dict[str, int] = {}
                for k, v in languages.items():
                    try:
                        coerced[k] = int(v)
                    except (ValueError, TypeError) as e:
                        # Skip values that cannot be coerced to int
                        logger.debug(
                            "Skipping non-numeric language value for %s: %r - %s",
                            k,
                            v,
                            e,
                        )
                repo_data["language_breakdown"] = coerced
            else:
                logger.debug(
                    "Unexpected languages response type for %s: %s",
                    repo_name,
                    type(languages),
                )
                repo_data["language_breakdown"] = {}
        except (ValueError, httpx.HTTPError) as e:
            logger.debug(f"Could not fetch languages for {repo_name}: {e}")
            repo_data["language_breakdown"] = {}

        return repo_data

    def search_code(self, query: str, per_page: int = 30) -> dict[str, Any]:
        """
        Search for code across the user's repositories.

        Args:
            query: Search query
            per_page: Number of results per page (max 100)

        Returns:
            Search results with code matches

        Note:
            Code search is rate limited to 10 requests per minute.
        """
        # Scope search to user's repositories
        search_query = f"{query} user:{self.username}"

        params = {"q": search_query, "per_page": min(per_page, 100)}

        return cast(dict[str, Any], self._api_request("GET", "/search/code", params=params))

    def get_user_events(self, per_page: int = 30) -> list[dict[str, Any]]:
        """
        Get recent activity/events for the user.

        Args:
            per_page: Number of events to return (max 100)

        Returns:
            List of event dictionaries
        """
        params = {"per_page": min(per_page, 100)}

        endpoint = f"/users/{self.username}/events"
        return cast(list[dict[str, Any]], self._api_request("GET", endpoint, params=params))
