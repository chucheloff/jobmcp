from __future__ import annotations

import json
from collections.abc import Generator

import pytest

from app.repository import JobRepository
from app.seed_data import MOCK_JOBS


class FakePipeline:
    def __init__(self, client: "FakeValkeyClient") -> None:
        self._client = client
        self._operations: list[tuple[str, tuple[object, ...]]] = []

    def delete(self, *keys: str) -> "FakePipeline":
        self._operations.append(("delete", keys))
        return self

    def sadd(self, key: str, value: str) -> "FakePipeline":
        self._operations.append(("sadd", (key, value)))
        return self

    def set(self, key: str, value: str) -> "FakePipeline":
        self._operations.append(("set", (key, value)))
        return self

    async def execute(self) -> list[bool]:
        results: list[bool] = []
        for operation, args in self._operations:
            if operation == "delete":
                for key in args:
                    self._client.values.pop(str(key), None)
                    self._client.sets.pop(str(key), None)
            elif operation == "sadd":
                key, value = args
                self._client.sets.setdefault(str(key), set()).add(str(value))
            elif operation == "set":
                key, value = args
                self._client.values[str(key)] = str(value)
            results.append(True)
        self._operations.clear()
        return results


class FakeValkeyClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self)

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.values.get(key) for key in keys]

    async def exists(self, key: str) -> int:
        return int(key in self.values or key in self.sets)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


@pytest.fixture
def fake_valkey_client() -> FakeValkeyClient:
    return FakeValkeyClient()


@pytest.fixture
async def seeded_repository(fake_valkey_client: FakeValkeyClient) -> JobRepository:
    repository = JobRepository("redis://unused", "test-jobmcp")
    repository._client = fake_valkey_client
    await repository.save_jobs(MOCK_JOBS)
    return repository


@pytest.fixture
def stale_job_payload() -> str:
    return json.dumps(
        {
            "id": "job-stale",
            "title": "Old Listing",
            "company": "Legacy Co",
            "location": "Nowhere",
            "work_mode": "remote",
            "employment_type": "full-time",
            "seniority": "mid",
            "salary_range": {"currency": "USD", "min": 1, "max": 2},
            "keywords": ["legacy"],
            "summary": "Stale data",
            "description": "Stale data",
            "posted_at": "2024-01-01",
            "application_url": "https://example.com/stale",
        }
    )
