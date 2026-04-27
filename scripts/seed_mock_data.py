from __future__ import annotations

import asyncio
import json

from app.config import load_settings
from app.repository import JobRepository
from app.seed_data import MOCK_COMPANIES, MOCK_JOBS


async def main() -> None:
    settings = load_settings()
    repository = JobRepository(settings.valkey_url, settings.valkey_prefix)
    await repository.connect()
    try:
        await repository.save_companies(MOCK_COMPANIES)
        await repository.save_jobs(MOCK_JOBS)
        print(
            json.dumps(
                {
                    "seeded": True,
                    "valkey_url": settings.valkey_url,
                    "prefix": settings.valkey_prefix,
                    "companies": len(MOCK_COMPANIES),
                    "jobs": len(MOCK_JOBS),
                },
                indent=2,
            )
        )
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
