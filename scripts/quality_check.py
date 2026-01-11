import argparse
import asyncio
import json
import os
import sys

from aseprite_mcp.tools import quality

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Aseprite scene consistency.")
    parser.add_argument("filename", help="Path to .aseprite file")
    parser.add_argument(
        "--layers",
        required=True,
        help="Comma-separated list of required layer names",
    )
    parser.add_argument("--start", type=int, default=1, help="Start frame (1-based)")
    parser.add_argument("--end", type=int, default=None, help="End frame (1-based)")
    return parser.parse_args()

async def run() -> int:
    args = parse_args()
    if not os.path.exists(args.filename):
        print(f"File not found: {args.filename}")
        return 2
    layers = [l.strip() for l in args.layers.split(",") if l.strip()]
    if not layers:
        print("No layers provided")
        return 2
    result = await quality.validate_scene(
        args.filename, layers, args.start, args.end
    )
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        print(result)
        return 1
    print(json.dumps(data, indent=2))
    missing = data.get("missing_layers", []) or data.get("missing_cels", [])
    return 1 if missing else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
