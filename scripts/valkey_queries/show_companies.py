from __future__ import annotations

import asyncio

from common import connect, load_json_records, prefixed_key, print_json, sorted_smembers


async def main() -> None:
    client = await connect()
    try:
        company_ids = await sorted_smembers(client, prefixed_key("companies"))
        companies = await load_json_records(
            client,
            [prefixed_key(f"company:{company_id}") for company_id in company_ids],
        )
        print_json({"total": len(companies), "companies": companies})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
