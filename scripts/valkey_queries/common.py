from __future__ import annotations

import json
import os
from typing import Any

import valkey.asyncio as valkey


DEFAULT_VALKEY_URL = "redis://localhost:6379/0"
DEFAULT_PREFIX = "jobmcp"


def valkey_url() -> str:
    return os.getenv("JOBMCP_VALKEY_URL", DEFAULT_VALKEY_URL)


def key_prefix() -> str:
    return os.getenv("JOBMCP_VALKEY_PREFIX", DEFAULT_PREFIX)


def prefixed_key(suffix: str) -> str:
    return f"{key_prefix()}:{suffix}"


async def connect() -> valkey.Valkey:
    client = valkey.from_url(valkey_url(), decode_responses=True)
    await client.ping()
    return client


async def sorted_smembers(client: valkey.Valkey, key: str) -> list[str]:
    return sorted(await client.smembers(key))


async def load_json_records(client: valkey.Valkey, keys: list[str]) -> list[dict[str, Any]]:
    if not keys:
        return []

    payloads = await client.mget(keys)
    records: list[dict[str, Any]] = []
    for payload in payloads:
        if payload:
            records.append(json.loads(payload))
    return records


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
