from __future__ import annotations

import json
import os
from typing import cast

import valkey.asyncio as valkey

from app.models import JsonValue, RecordPayload


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


async def load_json_records(client: valkey.Valkey, keys: list[str]) -> list[RecordPayload]:
    if not keys:
        return []

    payloads = await client.mget(keys)
    records: list[RecordPayload] = []
    for raw_payload in payloads:
        if raw_payload:
            payload: object = json.loads(raw_payload)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object payload, got {type(payload).__name__}.")
            records.append(cast(RecordPayload, payload))
    return records


def print_json(payload: JsonValue) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
