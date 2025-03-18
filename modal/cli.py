# cli.py
import argparse
from modal_functions import (
    ensure_database_exists,
    fetch_latest_blocks,
    fetch_blocks_range,
    query_database_wrapper,
)
import modal


def main():
    parser = argparse.ArgumentParser(
        description="Modal functions for Solana block data"
    )
    parser.add_argument("--query", type=str, help="SQL query to run")
    parser.add_argument("start_slot", type=int, nargs="?", help="Start slot")
    parser.add_argument("end_slot", type=int, nargs="?", help="End slot")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout (sec)")
    parser.add_argument("--latest", action="store_true", help="Fetch latest blocks")
    parser.add_argument(
        "--max-blocks", type=int, default=80, help="Max blocks to fetch with --latest"
    )
    parser.add_argument(
        "--schedule", action="store_true", help="Deploy scheduled function"
    )
    args = parser.parse_args()

    with modal.App("solana_db").run():
        if args.schedule:
            print("Deploy scheduled task: auto_fetch_latest_blocks")
        elif args.latest:
            fetch_latest_blocks.spawn(args.max_blocks, args.timeout).get()
        elif args.query:
            result = query_database_wrapper.spawn(args.query).get()
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"{result['row_count']} rows")
                print("\t".join(result["columns"]))
                for row in result["rows"][:20]:
                    print("\t".join(map(str, row)))
        elif args.start_slot is not None and args.end_slot is not None:
            fetch_blocks_range.spawn(args.start_slot, args.end_slot, args.timeout).get()
        else:
            ensure_database_exists.spawn().get()
            print("Database is ready.")


if __name__ == "__main__":
    main()
