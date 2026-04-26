from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8000
    mcp_path: str = "/mcp"
    stateless_http: bool = True
    valkey_url: str = "redis://valkey:6379/0"
    valkey_prefix: str = "jobmcp"
    seed_on_startup: bool = True


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("JOBMCP_HOST", "0.0.0.0"),
        port=int(os.getenv("JOBMCP_PORT", "8000")),
        mcp_path=os.getenv("JOBMCP_MCP_PATH", "/mcp"),
        stateless_http=_get_bool("JOBMCP_STATELESS_HTTP", True),
        valkey_url=os.getenv("JOBMCP_VALKEY_URL", "redis://valkey:6379/0"),
        valkey_prefix=os.getenv("JOBMCP_VALKEY_PREFIX", "jobmcp"),
        seed_on_startup=_get_bool("JOBMCP_SEED_ON_STARTUP", True),
    )
