# GitHub MCP Server

A Model Context Protocol (MCP) server that enables Claude Desktop to interact with your GitHub repositories through natural language.

## Overview

This MCP server provides Claude with four powerful tools to explore and analyze your GitHub repositories:

1. **get_my_repos** - List all your repositories with stats
2. **get_repo_details** - Get detailed information about a specific repository
3. **search_my_code** - Search for code across all your repositories
4. **get_recent_activity** - View your recent GitHub activity (commits, PRs, issues, etc.)

## Features

- Simple Personal Access Token authentication (no complex OAuth flow)
- Access to both public and private repositories
- Language breakdown and repository statistics
- Code search across all accessible repositories
- Activity tracking for commits, pull requests, and issues
- Rate limit handling and error management

## Prerequisites

- Python 3.10 or higher
- A GitHub account
- Claude Desktop (or any MCP-compatible client)

## Installation

### 1. Clone or Download This Repository

```bash
cd ~/github-mcp
```

### 2. Install Dependencies

```bash
pip install -e .
```

This installs the package in editable mode along with all required dependencies:

- `mcp` - Model Context Protocol SDK
- `httpx` - HTTP client for GitHub API
- `python-dotenv` - Environment variable management

### 3. Create a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens/new
2. Give your token a descriptive name (e.g., "Claude Desktop MCP")
3. Select the following scopes:
   - `repo` - Full control of private repositories (includes public repos)
   - `read:user` - Read user profile data
4. Click "Generate token"
5. **Copy the token immediately** (you won't be able to see it again!)

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your token:

```bash
GITHUB_TOKEN=ghp_your_actual_token_here
GITHUB_USERNAME=your_github_username
```

**Important:** Never commit the `.env` file to version control. It's already in `.gitignore`.

## Configuration for Claude Desktop

Add this to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "github-mcp",
      "env": {
        "GITHUB_TOKEN": "ghp_your_actual_token_here",
        "GITHUB_USERNAME": "your_github_username"
      }
    }
  }
}
```

**Note:** You can either:

- Put the token directly in the config (as shown above), OR
- Reference the `.env` file by running the server from the project directory
- You might need to use the absolute path instead of just "github-mcp" for command

## Usage

### Running the Server Standalone

You can test the server directly:

```bash
github-mcp
```

You should see:

```
INFO:github-mcp:Starting GitHub MCP server...
INFO:github-mcp:GitHub client initialized for user: your_username
INFO:github-mcp:MCP server running on stdio
```

### Using with Claude Desktop

Once configured, restart Claude Desktop. You can now ask Claude questions like:

- "Show me all my GitHub repositories"
- "What are the details of my repository [repo-name]?"
- "Search my code for 'authentication'"
- "What have I been working on recently?"

Claude will automatically use the appropriate tools to answer your questions.

## Available Tools

### 1. get_my_repos

Lists all repositories accessible to the authenticated user.

**Parameters:**

- `limit` (optional): Maximum number of repositories to return (default: 30, max: 100)

**Example:** "List my GitHub repositories"

### 2. get_repo_details

Get detailed information about a specific repository.

**Parameters:**

- `repo_name` (required): Repository name as "owner/repo" or just "repo" for your own repos

**Example:** "Show me details about my github-mcp repository"

### 3. search_my_code

Search for code across all accessible repositories.

**Parameters:**

- `query` (required): Search query
- `limit` (optional): Maximum results (default: 30, max: 100)

**Note:** Code search is rate limited to 10 requests per minute by GitHub.

**Example:** "Search my code for 'class UserController'"

### 4. get_recent_activity

View recent GitHub activity including commits, PRs, and issues.

**Parameters:**

- `limit` (optional): Maximum events to return (default: 30, max: 100)

**Example:** "What have I been working on recently?"

## Project Structure

```
github-mcp/
├── src/
│   └── github_mcp/
│       ├── __init__.py          # Package metadata
│       ├── github_client.py     # GitHub API client
│       └── server.py            # MCP server implementation
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore rules
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

## Architecture

### GitHub API Client (`github_client.py`)

- Simple token-based authentication
- No token refresh needed (Personal Access Tokens are long-lived)
- Rate limit monitoring and warnings
- User-friendly error messages

### MCP Server (`server.py`)

- Implements 4 tools for GitHub interaction
- Async/await for efficient operations
- JSON formatted responses for structured data
- Input validation (limit parameters must be 1-100)
- Comprehensive error handling with specific exceptions
- Resource cleanup with context managers

## Rate Limits

GitHub API has the following rate limits:

- **Standard API:** 5,000 requests per hour (authenticated)
- **Code Search:** 10 requests per minute

The server monitors rate limits and will warn you when approaching limits.

## Troubleshooting

### "GITHUB_TOKEN not found in environment variables"

Make sure you've either:

1. Created a `.env` file with your token, OR
2. Added the token to your Claude Desktop config

### "GITHUB_USERNAME not found in environment variables"

The server requires your GitHub username to be set. Add it to:

1. Your `.env` file: `GITHUB_USERNAME=your_username`, OR
2. Your Claude Desktop config (see example above)

### "Authentication failed. Check your GITHUB_TOKEN"

Your token may be invalid or expired. Generate a new token at:
https://github.com/settings/tokens/new

### "Access forbidden. Check token permissions"

Your token doesn't have the required scopes. Make sure you selected:

- `repo` scope for repository access
- `read:user` scope for user data

### Rate Limit Errors

If you see rate limit errors:

- **Standard API:** Wait an hour for the limit to reset
- **Code Search:** Wait a minute before searching again

## Development

### Running in Development Mode

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Format code with Black
black src/

# Run tests (when available)
pytest
```

## VS Code Quick Start

Follow these steps to get the project running in VS Code quickly.

1. Create and activate a virtual environment (macOS / Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install the project in editable mode:

```bash
pip install -e .
```

3. Select the VS Code Python interpreter: open Command Palette (Shift+Command+P) → `Python: Select Interpreter` → choose the interpreter at `.venv/bin/python`.

4. Run the test suite:

```bash
pytest -q
```

5. Use the VS Code tasks (Command Palette → `Tasks: Run Task`):

- `Create venv` — create `.venv`
- `Install dependencies` — run `pip install -e .`
- `Run tests` — run `pytest -q`

Notes:

- The workspace includes recommended extensions and settings in `.vscode/` to enable `pytest`, `black` formatting, and a suggested interpreter path.
- `.env.example` shows the environment variables to set; create a `.env` with your `GITHUB_TOKEN` and `GITHUB_USERNAME`.

### Project Goals

This project demonstrates:

- MCP server implementation with Python
- GitHub API integration patterns
- Clean separation of concerns (API client vs. MCP server)
- Enterprise-grade error handling and logging
- Modern Python practices (type hints, async/await)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Built by James Warlick as a learning project to understand MCP fundamentals and demonstrate API integration skills.

## Acknowledgments

- Built with the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- Uses the [GitHub REST API](https://docs.github.com/en/rest)
- Inspired by the MCP ecosystem of integrations
