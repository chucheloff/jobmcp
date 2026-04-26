# jobmcp

Standalone mock MCP job-search server for agent prototyping.

This version is intentionally:

- Python-based with `FastMCP`
- fully containerized with Docker Compose
- backed by `Valkey`
- exposed over stateless Streamable HTTP MCP for multi-instance scaling later

## Why stateless HTTP

The server does not rely on MCP transport session memory between requests. Durable state lives in Valkey instead. That gives us:

- easier horizontal scaling
- cleaner load balancer behavior
- no reliance on sticky sessions
- simpler rollout to multiple remote servers later

FastMCP recommends stateless HTTP for horizontally scaled deployments, while its stateful mode keeps session data in process memory. Sources: [FastMCP HTTP deployment](https://gofastmcp.com/deployment/http), [FastMCP server runtime](https://fastmcp.wiki/en/python-sdk/fastmcp-server-server).

## Current architecture

- `app/main.py`: FastMCP bootstrap, tool registration, HTTP runtime, health route
- `app/config.py`: environment-driven settings
- `app/models.py`: shared job and application models
- `app/repository.py`: Valkey access and query logic
- `app/seed_data.py`: mock jobs and startup seeding helpers
- `Dockerfile`: app container build using `uv`
- `compose.yaml`: app + Valkey stack

## MCP tools

1. `search_jobs`
2. `get_job`
3. `list_companies`
4. `submit_mock_application`
5. `list_mock_applications`
6. `reset_mock_data`

## Mock data model

### Jobs

Each job includes:

- id
- title
- company
- location
- work mode
- employment type
- seniority
- salary range
- keywords
- summary
- description
- posted date
- application URL

### Applications

Each mock application includes:

- id
- job id
- applicant name
- applicant email
- resume URL
- cover note
- status
- submitted timestamp

## Running the stack

```bash
docker compose up --build
```

That starts:

- Valkey on `localhost:6379`
- the MCP server on `http://localhost:8000/mcp`

Health check:

```bash
curl http://localhost:8000/health
```

Smoke test from inside the running app container:

```bash
docker compose exec jobmcp uv run python scripts/smoke_test.py --url http://127.0.0.1:8000/mcp
```

## Example MCP usage

Once a client connects to `http://localhost:8000/mcp`, it can:

- search for remote TypeScript jobs
- fetch a job by id
- submit a mock application tied to a job

The startup flow seeds fixture data automatically when the database is empty. You can also reset it through the `reset_mock_data` tool.

## Environment variables

See [.env.example](/Users/chch/Documents/git-projects/jobmcp/.env.example) for the supported settings.

## Version choices

Pinned to current stable releases during setup:

- `FastMCP 3.2.4`
- `valkey-py 6.1.1`
- `valkey/valkey:9.0.3-alpine3.23`
