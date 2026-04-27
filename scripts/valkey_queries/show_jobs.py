from __future__ import annotations

import asyncio

from common import connect, load_json_records, prefixed_key, print_json, sorted_smembers


async def main() -> None:
    client = await connect()
    try:
        job_ids = await sorted_smembers(client, prefixed_key("jobs"))
        jobs = await load_json_records(client, [prefixed_key(f"job:{job_id}") for job_id in job_ids])
        print_json({"total": len(jobs), "jobs": jobs})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
