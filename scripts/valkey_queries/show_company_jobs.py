from __future__ import annotations

import argparse
import asyncio

from common import connect, load_json_records, prefixed_key, print_json, sorted_smembers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show all jobs for one company.")
    parser.add_argument("company_id", help="Company id, for example company-alphabet")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = await connect()
    try:
        company_payload = await client.get(prefixed_key(f"company:{args.company_id}"))
        job_ids = await sorted_smembers(client, prefixed_key(f"company_jobs:{args.company_id}"))
        jobs = await load_json_records(client, [prefixed_key(f"job:{job_id}") for job_id in job_ids])
        print_json(
            {
                "company_id": args.company_id,
                "company_found": company_payload is not None,
                "total": len(jobs),
                "jobs": jobs,
            }
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
