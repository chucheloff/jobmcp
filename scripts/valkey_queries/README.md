# Valkey manual queries

Small scripts for inspecting the mock Valkey database by hand.

Defaults:

- URL: `redis://localhost:6379/0`
- Prefix: `jobmcp`

Both can be overridden with environment variables:

```bash
JOBMCP_VALKEY_URL=redis://localhost:6379/0 JOBMCP_VALKEY_PREFIX=jobmcp \
  uv run python scripts/valkey_queries/show_companies.py
```

Common commands:

```bash
uv run python scripts/valkey_queries/list_keys.py
uv run python scripts/valkey_queries/show_companies.py
uv run python scripts/valkey_queries/show_jobs.py
uv run python scripts/valkey_queries/show_company_jobs.py company-alphabet
uv run python scripts/valkey_queries/show_applications.py
uv run python scripts/valkey_queries/get_raw_key.py jobmcp:jobs
```

If you run scripts from inside the `jobmcp` Docker service, set:

```bash
JOBMCP_VALKEY_URL=redis://valkey:6379/0
```
