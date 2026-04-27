from __future__ import annotations

import argparse
import asyncio
import json

from common import connect, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show one raw Valkey key.")
    parser.add_argument("key", help="Full key name, for example jobmcp:jobs")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = await connect()
    try:
        key_type = await client.type(args.key)
        if key_type == "set":
            value = sorted(await client.smembers(args.key))
        elif key_type == "string":
            raw_value = await client.get(args.key)
            try:
                value = json.loads(raw_value) if raw_value is not None else None
            except json.JSONDecodeError:
                value = raw_value
        elif key_type == "none":
            value = None
        else:
            value = f"Unsupported key type: {key_type}"

        print_json({"key": args.key, "type": key_type, "value": value})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
