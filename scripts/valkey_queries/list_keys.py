from __future__ import annotations

import asyncio

from common import connect, key_prefix, print_json


async def main() -> None:
    client = await connect()
    try:
        keys = sorted(await client.keys(f"{key_prefix()}:*"))
        print_json({"total": len(keys), "keys": keys})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
