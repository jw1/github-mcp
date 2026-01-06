# Developer Introduction to GitHub MCP Server

Hey! Let me walk you through this codebase. Since you're coming from Java/Spring Boot, I'll point out the similarities and differences as we go. Grab a coffee - this is the 30-minute walkthrough you'd get on a Zoom call.

## What This Thing Does

This is an MCP (Model Context Protocol) server that lets Claude Desktop talk to your GitHub repositories. Think of it like building a REST API, but instead of HTTP endpoints, you're exposing "tools" that Claude can call. It's basically a bridge between an AI and your GitHub data.

Four main capabilities:
- List your repos
- Get detailed info about a specific repo
- Search code across all your repos
- View your recent GitHub activity

## Project Structure

```
github-mcp/
├── src/github_mcp/          # Main package (like src/main/java in Maven)
│   ├── __init__.py          # Package marker (like package-info.java)
│   ├── github_client.py     # GitHub API client
│   └── server.py            # MCP server (the main application)
├── tests/                   # Unit tests (like src/test/java)
│   ├── test_github_client.py
│   └── test_server_tools.py
├── pyproject.toml           # Like pom.xml or build.gradle
├── .env                     # Environment variables (like application.properties)
└── README.md
```

## The Build System: pyproject.toml

**File:** `pyproject.toml`

This is your `pom.xml` or `build.gradle`. Python's moved to this standardized format recently (it used to be `setup.py`, which was... not great).

**Lines 5-10:** Basic project metadata
```toml
[project]
name = "github-mcp"
version = "0.1.0"
```

**Lines 11-15:** Dependencies (like `<dependencies>` in Maven)
```toml
dependencies = [
    "mcp>=1.1.0",           # The MCP SDK - core framework
    "httpx>=0.27.0",        # HTTP client (like RestTemplate or WebClient)
    "python-dotenv>=1.0.0", # Loads .env files
]
```

Note: `httpx` is like Spring's `RestTemplate`, but async-first. If you know Spring WebFlux, this will feel familiar.

**Lines 17-22:** Dev dependencies (like `<scope>test</scope>`)
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",        # Like JUnit
    "pytest-asyncio>=0.21.0",
    "black>=24.0.0",        # Code formatter (like google-java-format)
]
```

**Lines 27-28:** Entry point (like `<mainClass>` in Maven)
```toml
[project.scripts]
github-mcp = "github_mcp.server:run"
```

This creates a command-line script. When you run `github-mcp`, it calls the `run()` function in `server.py`.

## Core Component 1: GitHubClient

**File:** `src/github_mcp/github_client.py`

This is your service layer - handles all GitHub API interactions. If you were building this in Spring, this would be a `@Service` annotated class.

### Class Structure (Lines 19-41)

```python
class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username
        self.client = httpx.Client(...)
```

**Python vs Java note:** No explicit constructor keyword - `__init__` is the constructor. `self` is like `this` in Java, but you have to explicitly declare it as the first parameter.

The `httpx.Client` on line 34 is created with:
- A 30-second timeout
- Authorization headers baked in
- GitHub API version header

This is similar to creating a `RestTemplate` with interceptors in Spring.

**Lines 43-55:** Context manager support for resource cleanup
```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False

def close(self):
    if hasattr(self, 'client'):
        self.client.close()
```

The `GitHubClient` implements Python's context manager protocol (like Java's `AutoCloseable`). This ensures the HTTP client is properly closed when done, preventing resource leaks. You can use it with `with GitHubClient(...) as client:` for automatic cleanup.

### The Core API Method (Lines 57-111)

`_api_request()` is the workhorse method. The underscore prefix is Python's convention for "internal/private" (though not enforced like Java's `private`).

**Lines 60-71:** The happy path
```python
response = self.client.request(method, url, **kwargs)
response.raise_for_status()

# Check rate limiting
remaining = response.headers.get("X-RateLimit-Remaining")
if remaining and int(remaining) < 100:
    logger.warning(f"GitHub API rate limit low: {remaining} requests remaining")

return response.json()
```

**Python note:** `**kwargs` is like varargs in Java, but for keyword arguments. It lets you pass arbitrary parameters through to the underlying `httpx` call.

**Lines 73-97:** Error handling with specific HTTP status codes
```python
except httpx.HTTPStatusError as e:
    status_code = e.response.status_code

    if status_code == 401:
        raise ValueError("Authentication failed. Check your GITHUB_TOKEN.") from e
    elif status_code == 403:
        # Rate limit or permissions...
```

This is like Spring's `@ExceptionHandler`, but inline. The `from e` preserves the original exception stack trace (similar to `throw new CustomException(cause)`).

### Public API Methods (Lines 130-235)

Four methods that correspond to our four MCP tools:

1. **`get_user_repos()`** (Lines 130-150): Lists user's repositories
2. **`get_repo_details()`** (Lines 152-198): Gets detailed repo info
3. **`search_code()`** (Lines 201-219): Searches code across repos
4. **`get_user_events()`** (Lines 222-235): Gets recent activity

**Key pattern to notice:** Lines 162-163 in `get_repo_details()`:
```python
owner, repo = self._parse_repo_name(repo_name)
endpoint = f"/repos/{owner}/{repo}"
```

The `_parse_repo_name()` helper (lines 113-128) handles both "owner/repo" and "repo" formats. This is defensive coding - making the API forgiving for the user.

**Lines 168-197:** Language breakdown with improved error handling
```python
try:
    languages = self._api_request("GET", f"{endpoint}/languages")
    # Safely handle unexpected types...
    for k, v in languages.items():
        try:
            coerced[k] = int(v)
        except (ValueError, TypeError) as e:
            # Skip values that cannot be coerced to int
            logger.debug(...)
except (ValueError, httpx.HTTPError) as e:
    logger.debug(f"Could not fetch languages for {repo_name}: {e}")
    repo_data["language_breakdown"] = {}
```

**Improved exception handling:** Now catches specific exceptions (`ValueError`, `TypeError`, `httpx.HTTPError`) instead of the overly broad `Exception`. This is "fail soft" - if we can't get language stats, we continue with empty data rather than crashing. Best practice for external APIs.

## Core Component 2: MCP Server

**File:** `src/github_mcp/server.py`

This is your controller/application layer. In Spring terms, this is like a `@RestController`, but for MCP instead of HTTP.

### Setup and Initialization (Lines 1-32)

```python
import json
from mcp.server import Server
from mcp.types import Tool, TextContent

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

# Initialize the MCP server
server = Server("github-mcp")

# Global GitHub client (initialized in main)
github: Optional[GitHubClient] = None
```

**Python note:** `github: Optional[GitHubClient] = None` is a type hint. The `: Optional[GitHubClient]` part is like Java's type declarations, but it's optional in Python (pun intended). `Optional[X]` means "X or None" (None is Python's null).

**Line 8:** We import `json` to serialize our tool responses as JSON. Python's `json` module is part of the standard library (like Jackson in Spring, but built-in).

### Tool Definitions (Lines 34-123)

This is the most interesting part! The `@server.list_tools()` decorator registers this function with the MCP framework. In Spring, this is like `@RequestMapping`.

**Lines 45-63:** First tool definition
```python
Tool(
    name="get_my_repos",
    description=(
        "List all repositories for the authenticated user. "
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
```

**Key insight:** The `description` is super important - Claude reads this to decide when to use the tool. Make it detailed and clear.

The `inputSchema` is JSON Schema (standard validation format). In Spring, this is like `@RequestParam` with validation annotations.

### Tool Dispatcher (Lines 126-157)

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "get_my_repos":
            limit = arguments.get("limit", 30)
            return await get_my_repos(limit)
        elif name == "get_repo_details":
            repo_name = arguments["repo_name"]
            return await get_repo_details(repo_name)
        # ... etc
```

**Python note:** `async def` and `await` - this is Python's async/await syntax (like CompletableFuture or reactive programming in Spring). The MCP protocol is async by nature.

`arguments.get("limit", 30)` is like Java's `Optional.orElse(30)` - if "limit" isn't in the dict, use 30.

### Tool Implementations (Lines 160-347)

Each tool has an async function that:
1. Calls the GitHub client
2. Formats the response as JSON
3. Returns `TextContent` with JSON string

**Example: `get_my_repos()` (Lines 160-207)**

Line 162-163: Null check with proper exception handling:
```python
if github is None:
    raise RuntimeError("GitHub client not initialized")
```

Unlike `assert` statements (which can be disabled with Python's `-O` flag), this always raises an exception. It's the professional way to handle required preconditions.

Lines 169-191: Building up a JSON response
```python
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
            # ... more fields ...
        }
        for repo in repos
    ]
}
```

**Python note:** This uses a list comprehension to build the repositories array. It's like Java Streams: `repos.stream().map(r -> new RepoDTO(...)).collect(toList())`.

**Why JSON instead of markdown?** Originally this code returned markdown (with headers, bold text, emojis). We converted it to JSON for efficiency - Claude can parse structured data more reliably, and the payload is smaller. The MCP protocol only supports `TextContent`, so we serialize the JSON to a string.

Line 193: `return [TextContent(type="text", text=json.dumps(result, indent=2))]`

`json.dumps()` serializes the dict to a JSON string. The `indent=2` makes it human-readable (pretty-printed). Like Jackson's `objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result)` in Spring.

**Other Tool Implementations:**

The other three tools follow the same pattern with null checks, input validation, and JSON responses:

- **`get_repo_details()`** (Lines 214-274): Returns detailed repository info with nested objects for statistics, details, language breakdown, topics, and URLs
- **`search_my_code()`** (Lines 261-297): Returns search results with query metadata and an array of matches (repository, path, url). Includes input validation for the `limit` parameter.
- **`get_recent_activity()`** (Lines 300-367): Returns GitHub events with type-specific details (push events include branch/commit count, PRs include action/title, etc.). Also validates `limit` parameter.

All four tools:
- Check if the GitHub client is initialized
- Validate input parameters (limit must be 1-100)
- Return structured JSON that Claude can easily parse

### Application Startup (Lines 379-432)

**`setup_github()` function (Lines 379-405):** Initializes the GitHub client

This function now requires both `GITHUB_TOKEN` and `GITHUB_USERNAME` environment variables. The hardcoded default username was removed to prevent configuration errors.

**`main()` function (Lines 408-427):** The async entry point
```python
async def main():
    logger.info("Starting GitHub MCP server...")

    if not await setup_github():
        logger.error("Failed to initialize GitHub client. Exiting.")
        return

    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, ...)
```

**Lines 440-442:** The MCP server communicates over stdio (standard input/output). Claude Desktop launches this as a subprocess and talks to it via pipes. It's unusual if you're used to HTTP servers, but it's simple and efficient for local processes.

**`run()` function (Lines 451-453):** Synchronous wrapper
```python
def run():
    """Entry point for the command-line script."""
    asyncio.run(main())
```

This is the entry point defined in `pyproject.toml`. `asyncio.run()` is like "start the async runtime" - similar to how Spring Boot's `SpringApplication.run()` starts the server.

## Package Initialization

**File:** `src/github_mcp/__init__.py`

```python
"""GitHub MCP Server - A Model Context Protocol server for GitHub repositories."""

__version__ = "0.1.0"
```

In Python, `__init__.py` marks a directory as a package. It's also executed when you `import github_mcp`, so you can put initialization code here. Right now it just declares the version.

In Java terms, this is a bit like `module-info.java`, but simpler.

## Testing Strategy

Python uses `pytest` - think of it as JUnit but with less boilerplate.

### Test Structure

Both test files follow the same pattern:
- Classes group related tests (like nested test classes in JUnit)
- `@pytest.fixture` creates reusable test objects (like `@Before` methods)
- `@pytest.mark.asyncio` marks async tests

### test_github_client.py

**Lines 12-15:** Fixture definition
```python
@pytest.fixture
def github_client():
    """Create a GitHubClient instance for testing."""
    return GitHubClient(token="test_token", username="testuser")
```

This is injected into every test method that has a `github_client` parameter. Like Spring's `@MockBean`, but more flexible.

**Lines 49-63:** Example test with mocking
```python
def test_401_authentication_failed(self, github_client):
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Bad credentials"

    with patch.object(github_client.client, 'request') as mock_request:
        mock_request.side_effect = httpx.HTTPStatusError(...)

        with pytest.raises(ValueError, match="Authentication failed"):
            github_client._api_request("GET", "/user/repos")
```

`patch.object()` is like Mockito's `@Mock` and `when()`. The `with` blocks are context managers (like try-with-resources in Java).

`pytest.raises()` is like JUnit's `assertThrows()`.

### test_server_tools.py

**Lines 12-37:** Mock fixture with return values
```python
@pytest.fixture
def mock_github_client():
    mock = Mock()
    mock.username = "testuser"
    mock.get_user_repos.return_value = []
    mock.get_repo_details.return_value = {...}
    return mock
```

This creates a fully configured mock. In Mockito, this would be:
```java
@Mock GitHubClient mock;
when(mock.getUsername()).thenReturn("testuser");
```

**Lines 43-52:** Async test example
```python
@pytest.mark.asyncio
async def test_calls_client_with_default_limit(self, mock_github_client):
    with patch.object(server, 'github', mock_github_client):
        result = await server.get_my_repos()

    mock_github_client.get_user_repos.assert_called_once_with(per_page=30)
```

The `@pytest.mark.asyncio` decorator lets pytest handle async functions. `assert_called_once_with()` is like Mockito's `verify()`.

**Testing JSON Responses:**

Since we converted all tool outputs to JSON, the tests now parse and validate JSON structure instead of checking for markdown strings:

```python
@pytest.mark.asyncio
async def test_formats_repo_list(self, mock_github_client):
    # ... setup mock data ...
    result = await server.get_my_repos()

    # Parse JSON response
    data = json.loads(result[0].text)

    # Validate structure
    assert data["summary"]["user"] == "testuser"
    assert data["summary"]["count"] == 1
    assert len(data["repositories"]) == 1
    assert data["repositories"][0]["name"] == "test-repo"
```

This is more robust than string matching - we're validating the actual data structure, not just substring presence.

## Environment Configuration

**File:** `.env.example`

```bash
GITHUB_TOKEN=your_github_token_here
GITHUB_USERNAME=abc
```

Create a `.env` file (already in `.gitignore`) with your actual credentials. The `python-dotenv` library loads these automatically on line 21 of `server.py`: `load_dotenv()`.

In Spring Boot, this is like `application.properties`, but `.env` files are a more general convention across languages.

## Running the Application

### Setup
```bash
# Create virtual environment (like creating a local Maven repo)
python -m venv .venv

# Activate it (you need to do this each terminal session)
source .venv/bin/activate  # On Mac/Linux
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -e ".[dev]"
```

**Python note:** Virtual environments isolate dependencies per-project. Unlike Maven's global `~/.m2/repository`, each venv is completely isolated. It's more like Node's `node_modules`.

The `-e` flag means "editable install" - you can modify the code without reinstalling. The `".[dev]"` means "install this package (`.`) and its dev dependencies".

### Run Tests
```bash
pytest
```

That's it! Pytest auto-discovers test files (anything matching `test_*.py`).

### Run the Server
```bash
github-mcp
```

Or directly:
```bash
python -m github_mcp.server
```

The server runs on stdio, so you won't see much unless Claude Desktop is connected to it.

## Key Python Concepts for Java Developers

### 1. Type Hints (Optional but Recommended)
```python
def get_repo_details(self, repo_name: str) -> dict[str, Any]:
```

The `: str` and `-> dict[str, Any]` are type hints. They're not enforced at runtime (Python is still dynamically typed), but tools like IDEs and `mypy` use them for checking.

### 2. Dictionaries Everywhere
```python
repo = {"name": "test", "stars": 5}
name = repo.get("name", "Unknown")  # With default
stars = repo["stars"]               # Direct access (throws KeyError if missing)
```

Python dictionaries (`dict`) are like Java's `Map`, but more central to the language. JSON deserializes directly to dictionaries.

### 3. List Comprehensions
```python
# Instead of:
result = []
for repo in repos:
    result.append(repo["name"])

# You can write:
result = [repo["name"] for repo in repos]
```

Similar to Java Streams: `repos.stream().map(r -> r.get("name")).collect(toList())`

### 4. async/await
```python
async def get_data():
    result = await some_async_function()
    return result
```

Similar to Java's `CompletableFuture` or Spring WebFlux's `Mono`/`Flux`, but built into the language.

### 5. No Explicit Interfaces or Abstract Classes (Usually)
Python uses "duck typing" - if it walks like a duck and quacks like a duck, it's a duck. You don't need to declare that `GitHubClient implements GitHubService`. Just write the methods and call them.

There are `abc.ABC` (Abstract Base Class) and `Protocol` for formal contracts, but they're less common than in Java.

### 6. Everything is Public by Default
The underscore prefix (`_api_request`) is just a convention, not enforcement. There's no `private` keyword. Trust your fellow developers.

## Common Patterns in This Codebase

### Error Handling Strategy
- External API calls: Catch specific exceptions, raise ValueError with user-friendly messages
- Internal errors: Let them bubble up with full stack traces
- Logging: Use logging module (like SLF4J)

### Data Flow
1. MCP Server (`server.py`) receives tool call from Claude
2. Server routes to appropriate handler function
3. Handler calls `GitHubClient` method
4. Client makes HTTP request to GitHub API
5. Client parses and returns Python dict
6. Handler formats dict as markdown string
7. Server returns TextContent to Claude

### Testing Philosophy
- Unit tests mock external dependencies (GitHub API)
- Tests focus on logic, not integration
- Descriptive test names explain what they verify

## Next Steps

Now that you've seen the big picture, try:

1. Run the tests: `pytest -v`
2. Look at a test failure to understand the error messages
3. Add a print statement in `server.py` line 163 and run the server
4. Try adding a new field to the repo list output (maybe add emoji for visibility?)
5. Read the GitHub API docs to see what other endpoints you could add

The code is straightforward once you map the Python patterns to your Java knowledge. The async stuff might be the most unfamiliar, but think of it as Spring WebFlux - same concepts, different syntax.

Any questions? This is your codebase now!
