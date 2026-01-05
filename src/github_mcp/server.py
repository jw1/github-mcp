"""
MCP server for GitHub repositories.

This server provides tools for Claude Desktop to interact with GitHub repositories.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import Tool, TextContent

from .github_client import GitHubClient

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("github-mcp")

# Initialize the MCP server
server = Server("github-mcp")

# Global GitHub client (initialized in main)
github: Optional[GitHubClient] = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Define the tools available to Claude.

    Each tool has:
    - name: Unique identifier
    - description: What the tool does (Claude uses this to decide when to call it)
    - inputSchema: JSON Schema defining the parameters
    """
    return [
        Tool(
            name="get_my_repos",
            description=(
                "List all repositories for the authenticated user (jw1). "
                "Returns repository name, description, stars, forks, primary language, "
                "visibility (public/private), and last updated date. "
                "Sorted by most recently updated first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of repositories to return (default: 30, max: 100)",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="get_repo_details",
            description=(
                "Get detailed information about a specific repository. "
                "Includes description, statistics (stars, forks, watchers, open issues), "
                "primary language, language breakdown, topics, and recent activity. "
                "Provide repository name as 'owner/repo' or just 'repo' for user jw1."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name (e.g., 'jw1/my-project' or 'my-project')",
                    }
                },
                "required": ["repo_name"],
            },
        ),
        Tool(
            name="search_my_code",
            description=(
                "Search for code across all repositories accessible by user jw1. "
                "Returns matching code snippets with file paths and repositories. "
                "Note: Code search is rate limited to 10 requests per minute."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'function authenticate', 'class UserController')",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 30, max: 100)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_recent_activity",
            description=(
                "Get recent activity for user jw1 including commits, pull requests, "
                "issues, and repository creation. Shows the most recent events across "
                "all repositories."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of events to return (default: 30, max: 100)",
                    }
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool calls from Claude.

    Args:
        name: The tool name
        arguments: Dictionary of arguments matching the inputSchema

    Returns:
        List of TextContent with the results
    """
    try:
        if name == "get_my_repos":
            limit = arguments.get("limit", 30)
            return await get_my_repos(limit)
        elif name == "get_repo_details":
            repo_name = arguments["repo_name"]
            return await get_repo_details(repo_name)
        elif name == "search_my_code":
            query = arguments["query"]
            limit = arguments.get("limit", 30)
            return await search_my_code(query, limit)
        elif name == "get_recent_activity":
            limit = arguments.get("limit", 30)
            return await get_recent_activity(limit)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_my_repos(limit: int = 30) -> list[TextContent]:
    """Get list of user's repositories."""
    assert github is not None, "GitHub client not initialized"
    repos = github.get_user_repos(per_page=limit)

    if not repos:
        return [TextContent(type="text", text="No repositories found.")]

    result_lines = [f"# Repositories for {github.username}\n"]
    result_lines.append(f"Found {len(repos)} repositories (sorted by recently updated)\n")

    for repo in repos:
        name = repo.get("name", "Unknown")
        full_name = repo.get("full_name", name)
        description = repo.get("description") or "No description"
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        language = repo.get("language") or "Not specified"
        visibility = "Private" if repo.get("private", False) else "Public"
        updated_at = repo.get("updated_at", "")

        # Format the updated date
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                updated_str = dt.strftime("%Y-%m-%d")
            except Exception:
                updated_str = updated_at
        else:
            updated_str = "Unknown"

        result_lines.append(f"\n## {full_name}")
        result_lines.append(f"**Description:** {description}")
        result_lines.append(
            f"**Stats:** ⭐ {stars} stars | 🍴 {forks} forks | 📅 Updated {updated_str}"
        )
        result_lines.append(f"**Language:** {language} | **Visibility:** {visibility}")

        # Add URL
        html_url = repo.get("html_url", "")
        if html_url:
            result_lines.append(f"**URL:** {html_url}")

    # Add summary at the end
    total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    result_lines.append(f"\n**Total stars across all repositories:** {total_stars}")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def get_repo_details(repo_name: str) -> list[TextContent]:
    """Get detailed information about a specific repository."""
    assert github is not None, "GitHub client not initialized"
    repo = github.get_repo_details(repo_name)

    full_name = repo.get("full_name", repo_name)
    description = repo.get("description") or "No description provided"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    watchers = repo.get("watchers_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    language = repo.get("language") or "Not specified"
    visibility = "Private" if repo.get("private", False) else "Public"
    created_at = repo.get("created_at", "")
    updated_at = repo.get("updated_at", "")
    default_branch = repo.get("default_branch", "main")

    # Format dates
    try:
        created_str = (
            datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            if created_at
            else "Unknown"
        )
        updated_str = (
            datetime.fromisoformat(updated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            if updated_at
            else "Unknown"
        )
    except Exception:
        created_str = created_at or "Unknown"
        updated_str = updated_at or "Unknown"

    result_lines = [f"# {full_name}\n"]
    result_lines.append(f"**Description:** {description}\n")

    # Stats section
    result_lines.append("## Statistics")
    result_lines.append(f"- ⭐ Stars: {stars}")
    result_lines.append(f"- 🍴 Forks: {forks}")
    result_lines.append(f"- 👀 Watchers: {watchers}")
    result_lines.append(f"- 🐛 Open Issues: {open_issues}")

    # Details section
    result_lines.append("\n## Details")
    result_lines.append(f"- **Primary Language:** {language}")
    result_lines.append(f"- **Visibility:** {visibility}")
    result_lines.append(f"- **Default Branch:** {default_branch}")
    result_lines.append(f"- **Created:** {created_str}")
    result_lines.append(f"- **Last Updated:** {updated_str}")

    # Language breakdown
    language_breakdown: dict[str, int] = repo.get("language_breakdown", {})
    if language_breakdown:
        result_lines.append("\n## Language Breakdown")
        # Sort by bytes of code
        sorted_langs = sorted(
            language_breakdown.items(), key=lambda x: x[1], reverse=True
        )
        total_bytes = sum(language_breakdown.values())
        for lang, bytes_count in sorted_langs[:5]:  # Top 5 languages
            percentage = (bytes_count / total_bytes * 100) if total_bytes > 0 else 0
            result_lines.append(f"- {lang}: {percentage:.1f}%")
        if len(sorted_langs) > 5:
            result_lines.append(f"- ...and {len(sorted_langs) - 5} more")

    # Topics
    topics: list[str] = repo.get("topics", [])
    if topics:
        result_lines.append("\n## Topics")
        result_lines.append(f"{', '.join(topics)}")

    # URLs
    html_url = repo.get("html_url", "")
    homepage = repo.get("homepage")
    result_lines.append("\n## Links")
    if html_url:
        result_lines.append(f"- **Repository:** {html_url}")
    if homepage:
        result_lines.append(f"- **Homepage:** {homepage}")

    # License
    license_info: dict[str, Any] | None = repo.get("license")
    if license_info:
        license_name = license_info.get("name", "Unknown")
        result_lines.append(f"\n**License:** {license_name}")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def search_my_code(query: str, limit: int = 30) -> list[TextContent]:
    """Search for code across user's repositories."""
    assert github is not None, "GitHub client not initialized"
    results = github.search_code(query, per_page=limit)

    total_count: int = results.get("total_count", 0)
    items: list[dict[str, Any]] = results.get("items", [])

    if total_count == 0:
        return [
            TextContent(
                type="text",
                text=f"No code matches found for query: '{query}'",
            )
        ]

    result_lines = [f"# Code Search Results for '{query}'\n"]
    result_lines.append(f"Found {total_count} matches (showing first {len(items)})\n")

    for item in items:
        repository: dict[str, Any] = item.get("repository", {})
        repo_name = repository.get("full_name", "Unknown")
        file_path = item.get("path", "Unknown")
        html_url = item.get("html_url", "")

        result_lines.append(f"\n## {repo_name}: {file_path}")
        if html_url:
            result_lines.append(f"**URL:** {html_url}")

        # Add a snippet of the match if available
        # Note: The search API doesn't return code snippets in the main response
        # You'd need to make additional API calls to get the actual content

    return [TextContent(type="text", text="\n".join(result_lines))]


async def get_recent_activity(limit: int = 30) -> list[TextContent]:
    """Get recent activity/events for the user."""
    assert github is not None, "GitHub client not initialized"
    events = github.get_user_events(per_page=limit)

    if not events:
        return [TextContent(type="text", text="No recent activity found.")]

    result_lines = [f"# Recent Activity for {github.username}\n"]
    result_lines.append(f"Showing last {len(events)} events\n")

    for event in events:
        event_type = event.get("type", "Unknown")
        repo_info: dict[str, Any] = event.get("repo", {})
        repo_name = repo_info.get("name", "Unknown")
        created_at = event.get("created_at", "")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            time_str = created_at

        # Parse event details based on type
        if event_type == "PushEvent":
            payload: dict[str, Any] = event.get("payload", {})
            commits: list[Any] = payload.get("commits", [])
            commits_count = len(commits)
            ref = payload.get("ref", "unknown branch")
            branch = ref.split("/")[-1] if "/" in ref else ref
            result_lines.append(
                f"\n📝 **Push** to {repo_name} ({branch}) - {commits_count} commit(s)"
            )

        elif event_type == "PullRequestEvent":
            payload: dict[str, Any] = event.get("payload", {})
            action = payload.get("action", "unknown")
            pr: dict[str, Any] = payload.get("pull_request", {})
            pr_title = pr.get("title", "Unknown PR")
            result_lines.append(f"\n🔀 **Pull Request** {action} in {repo_name}")
            result_lines.append(f"   {pr_title}")

        elif event_type == "IssuesEvent":
            payload: dict[str, Any] = event.get("payload", {})
            action = payload.get("action", "unknown")
            issue: dict[str, Any] = payload.get("issue", {})
            issue_title = issue.get("title", "Unknown Issue")
            result_lines.append(f"\n🐛 **Issue** {action} in {repo_name}")
            result_lines.append(f"   {issue_title}")

        elif event_type == "CreateEvent":
            payload: dict[str, Any] = event.get("payload", {})
            ref_type = payload.get("ref_type", "unknown")
            result_lines.append(f"\n✨ **Created** {ref_type} in {repo_name}")

        elif event_type == "WatchEvent":
            result_lines.append(f"\n⭐ **Starred** {repo_name}")

        elif event_type == "ForkEvent":
            result_lines.append(f"\n🍴 **Forked** {repo_name}")

        else:
            # Generic event
            result_lines.append(f"\n📌 **{event_type}** in {repo_name}")

        result_lines.append(f"   *{time_str}*")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def setup_github() -> bool:
    """
    Set up GitHub authentication.

    Returns True if authenticated, False otherwise.
    """
    global github

    token = os.getenv("GITHUB_TOKEN")
    username = os.getenv("GITHUB_USERNAME", "jw1")

    if not token:
        logger.error("GITHUB_TOKEN not found in environment variables")
        logger.error("Please create a Personal Access Token at:")
        logger.error("https://github.com/settings/tokens/new")
        logger.error("Required scopes: repo, read:user")
        return False

    github = GitHubClient(token, username)
    logger.info(f"GitHub client initialized for user: {username}")
    return True


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting GitHub MCP server...")

    # Set up GitHub authentication
    if not await setup_github():
        logger.error("Failed to initialize GitHub client. Exiting.")
        return

    # Run the MCP server
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP server running on stdio")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run():
    """Entry point for the command-line script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
