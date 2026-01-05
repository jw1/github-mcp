## Project Summary (from README)

**GitHub MCP Server** - An MCP server that enables Claude Desktop to interact with GitHub repositories through natural language.

### Core Functionality
Four main tools:
1. **get_my_repos** - List repositories with stats
2. **get_repo_details** - Detailed repo information
3. **search_my_code** - Search code across all repos
4. **get_recent_activity** - View recent GitHub activity

### Key Features
- Simple Personal Access Token authentication (no OAuth)
- Access to public and private repos
- Code search across all accessible repositories
- Rate limit handling and error management

### Tech Stack
- Python 3.10+
- MCP SDK (Model Context Protocol)
- httpx (GitHub API client)
- Async/await architecture

### Authentication
Uses GitHub Personal Access Token with scopes:
- `repo` - Full repository access
- `read:user` - User profile data

### Rate Limits
- Standard API: 5,000 requests/hour
- Code Search: 10 requests/minute
