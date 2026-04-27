from __future__ import annotations

import argparse
import asyncio

from common import connect, load_json_records, prefixed_key, print_json, sorted_smembers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show submitted applications.")
    parser.add_argument("--job-id", help="Optional job id filter")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = await connect()
    try:
        if args.job_id:
            application_ids = await sorted_smembers(client, prefixed_key(f"job_applications:{args.job_id}"))
        else:
            application_ids = await sorted_smembers(client, prefixed_key("applications"))

        applications = await load_json_records(
            client,
            [prefixed_key(f"application:{application_id}") for application_id in application_ids],
        )
        print_json({"total": len(applications), "applications": applications})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
