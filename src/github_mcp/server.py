"""
MCP server for GitHub repositories.

This server provides tools for Claude Desktop to interact with GitHub repositories.
"""

import asyncio
import json
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
                "List all repos for authenticated user. "
                "Returns repo name, description, stars, forks, primary language, "
                "visibility, last updated date. "
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
                "Get detailed info about specific repository. "
                "Includes description, stats (stars, forks, watchers, open issues), "
                "primary language, language breakdown, topics, recent activity. "
                "Provide repo name as 'owner/repo' or 'repo' for current user."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name (e.g., 'owner/my-project' or 'my-project')",
                    }
                },
                "required": ["repo_name"],
            },
        ),
        Tool(
            name="search_my_code",
            description=(
                "Search for code across all repo accessible by current user. "
                "Returns matching snippets w/ file paths and repos. "
                "Note: search_my_code rate limited to 10 requests per minute."
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
                        "description": "Max number of results to return (default: 30, max: 100)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_recent_activity",
            description=(
                "Get recent activity for current including commits, pull requests, "
                "issues, and repository creation. Shows the most recent events across "
                "all repositories."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Max number of events to return (default: 30, max: 100)",
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
        limit = arguments.get("limit", 30)

        if name == "get_my_repos":
            return await get_my_repos(limit)
        elif name == "get_repo_details":
            repo_name = arguments["repo_name"]
            return await get_repo_details(repo_name)
        elif name == "search_my_code":
            query = arguments["query"]
            return await search_my_code(query, limit)
        elif name == "get_recent_activity":
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

    # Build structured response
    result = {
        "summary": {
            "user": github.username,
            "count": len(repos),
            "total_stars": sum(repo.get("stargazers_count", 0) for repo in repos),
            "total_forks": sum(repo.get("forks_count", 0) for repo in repos),
            "sorted_by": "recently_updated"
        },
        "repositories": [
            {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language"),
                "visibility": "private" if repo.get("private", False) else "public",
                "updated_at": repo.get("updated_at"),
                "url": repo.get("html_url"),
            }
            for repo in repos
        ]
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def get_repo_details(repo_name: str) -> list[TextContent]:
    """Get detailed information about a specific repository."""
    assert github is not None, "GitHub client not initialized"
    repo = github.get_repo_details(repo_name)

    # Calculate language breakdown percentages
    language_breakdown: dict[str, int] = repo.get("language_breakdown", {})
    language_percentages = {}
    if language_breakdown:
        total_bytes = sum(language_breakdown.values())
        if total_bytes > 0:
            language_percentages = {
                lang: round((bytes_count / total_bytes * 100), 1)
                for lang, bytes_count in language_breakdown.items()
            }

    # Build structured response
    license_info: dict[str, Any] | None = repo.get("license")
    result = {
        "full_name": repo.get("full_name", repo_name),
        "description": repo.get("description"),
        "statistics": {
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "watchers": repo.get("watchers_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
        },
        "details": {
            "primary_language": repo.get("language"),
            "visibility": "private" if repo.get("private", False) else "public",
            "default_branch": repo.get("default_branch", "main"),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
        },
        "language_breakdown": language_percentages,
        "topics": repo.get("topics", []),
        "urls": {
            "repository": repo.get("html_url"),
            "homepage": repo.get("homepage"),
        },
        "license": license_info.get("name") if license_info else None,
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
                text=json.dumps({"query": query, "total_count": 0, "matches": []}),
            )
        ]

    # Build structured response
    result = {
        "query": query,
        "total_count": total_count,
        "returned_count": len(items),
        "matches": [
            {
                "repository": item.get("repository", {}).get("full_name"),
                "path": item.get("path"),
                "url": item.get("html_url"),
            }
            for item in items
        ],
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def get_recent_activity(limit: int = 30) -> list[TextContent]:
    """Get recent activity/events for the user."""
    assert github is not None, "GitHub client not initialized"
    events = github.get_user_events(per_page=limit)

    if not events:
        return [TextContent(type="text", text=json.dumps({"user": github.username, "events": []}))]

    # Build structured events list
    structured_events = []
    for event in events:
        event_type = event.get("type", "Unknown")
        repo_info: dict[str, Any] = event.get("repo", {})
        repo_name = repo_info.get("name")
        created_at = event.get("created_at")

        # Parse event details based on type
        event_data: dict[str, Any] = {
            "type": event_type,
            "repository": repo_name,
            "created_at": created_at,
        }

        payload: dict[str, Any] = event.get("payload", {})

        if event_type == "PushEvent":
            commits: list[Any] = payload.get("commits", [])
            ref = payload.get("ref", "")
            branch = ref.split("/")[-1] if "/" in ref else ref
            event_data["details"] = {
                "branch": branch,
                "commit_count": len(commits),
            }

        elif event_type == "PullRequestEvent":
            pr: dict[str, Any] = payload.get("pull_request", {})
            event_data["details"] = {
                "action": payload.get("action"),
                "title": pr.get("title"),
                "number": pr.get("number"),
            }

        elif event_type == "IssuesEvent":
            issue: dict[str, Any] = payload.get("issue", {})
            event_data["details"] = {
                "action": payload.get("action"),
                "title": issue.get("title"),
                "number": issue.get("number"),
            }

        elif event_type == "CreateEvent":
            event_data["details"] = {
                "ref_type": payload.get("ref_type"),
                "ref": payload.get("ref"),
            }

        elif event_type == "WatchEvent":
            event_data["details"] = {"action": "starred"}

        elif event_type == "ForkEvent":
            forkee: dict[str, Any] = payload.get("forkee", {})
            event_data["details"] = {"forkee": forkee.get("full_name")}

        structured_events.append(event_data)

    result = {
        "user": github.username,
        "event_count": len(structured_events),
        "events": structured_events,
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
