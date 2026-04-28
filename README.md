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
- `app/models.py`: shared company, job, and application models
- `app/repository.py`: Valkey access and query logic
- `app/seed_data.py`: mock jobs and startup seeding helpers
- `Dockerfile`: app container build using `uv`
- `compose.yaml`: app + Valkey stack

## MCP tools

1. `search_jobs`
2. `get_job`
3. `add_job`
4. `update_job`
5. `delete_job`
6. `list_companies`
7. `add_company`
8. `update_company`
9. `get_company`
10. `get_company_jobs`
11. `submit_mock_application`
12. `get_application_status`
13. `update_application_status`
14. `list_mock_applications`
15. `reset_mock_data`

## Mock data model

### Companies

Each company includes:

- id
- name
- description
- website
- industry
- headquarters
- size
- legal name
- street address line 1
- street address line 2
- city
- region/state
- postal code/index
- country
- PO box
- phone
- contact email
- display location
- latitude
- longitude
- founded year
- short history

### Jobs

Each job includes:

- id
- title
- company id
- location
- work mode
- employment type
- seniority
- salary range
- profession tags
- skills tags
- candidate qualities
- summary
- description
- posted date
- application URL
- eligible countries
- office cities
- visa sponsorship availability
- timezone overlap hours with Asia/Almaty
- salary period
- equity offered
- required languages
- nice-to-have languages
- role focus tags
- domain tags
- on-call policy
- relocation requirement
- relocation countries
- deal-breaker tags

The same signals are also written into the mock job descriptions so ranking and extraction algorithms can be tested against prose rather than only clean structured fields.

### Applications

Each mock application includes:

- id
- job id
- company id
- applicant name
- applicant email
- resume URL
- cover note
- status
- submitted timestamp
- decided timestamp

Application statuses are:

- `submitted`
- `positive`
- `rejected`

`submit_mock_application` returns an `application_number`. Use that value with `get_application_status` to check the application later. A submitted application is automatically decided when checked at least one hour after submission: `positive` has a 10% chance, otherwise it becomes `rejected`. `update_application_status` can be used to force a mock status manually.

### Valkey keys

The mock database uses sets as indexes and JSON strings as records:

- `<prefix>:companies`: set of company IDs
- `<prefix>:company:<company_id>`: company JSON string
- `<prefix>:company_jobs:<company_id>`: set of job IDs for one company
- `<prefix>:jobs`: set of job IDs
- `<prefix>:job:<job_id>`: job JSON string
- `<prefix>:applications`: set of application IDs
- `<prefix>:application:<application_id>`: application JSON string
- `<prefix>:job_applications:<job_id>`: set of application IDs for one job

Jobs can only be added for an existing company. Deleting a job is blocked when applications exist unless `force=true`; forced deletion removes the listing but keeps application records for audit-style reads.

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

Manual seed into a running Valkey instance:

```bash
JOBMCP_VALKEY_URL=redis://localhost:6379/0 uv run python scripts/seed_mock_data.py
```

## Example MCP usage

Once a client connects to `http://localhost:8000/mcp`, it can:

- search for remote TypeScript jobs
- fetch a job by id
- create and update companies
- add, update, and delete job listings
- list every job for a company
- search by profession tags or skills tags
- submit a mock application tied to a job

The startup flow seeds fixture data automatically on service startup whenever the jobs set or companies set is missing. You can also seed manually with `scripts/seed_mock_data.py` or reset it through the `reset_mock_data` tool.

## Environment variables

See [.env.example](/Users/chch/Documents/git-projects/jobmcp/.env.example) for the supported settings.

## Version choices

Pinned to current stable releases during setup:

- `FastMCP 3.2.4`
- `valkey-py 6.1.1`
- `valkey/valkey:9.0.3-alpine3.23`
