import modal
import os
import sqlite3
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import time

# Create base image with dependencies
image = modal.Image.debian_slim().pip_install("requests")

# Add local module sources
image = image.add_local_python_source("create_database", "common_utils")

# Create Modal app and volume with create_if_missing
app = modal.App("solana_db", image=image)
volume = modal.Volume.from_name("solana-db-volume", create_if_missing=True)

# Constants
VOLUME_DIR = "/data"
DB_FILENAME = "solana_data.db"
DB_PATH = Path(VOLUME_DIR) / DB_FILENAME

from common_utils import (
    get_block,
    save_to_sqlite,
    configure_sqlite_connection,
    get_latest_slot,
    get_highest_processed_slot,
    query_database,
)
from create_database import create_database


@app.function(timeout=300, volumes={VOLUME_DIR: volume})  # 5 minutes
def ensure_database_exists():
    """Create the SQLite database in the Modal volume if it doesn't exist"""
    os.makedirs(VOLUME_DIR, exist_ok=True)

    if not DB_PATH.exists():
        print(f"Creating database at {DB_PATH}")
        create_database(str(DB_PATH))
        volume.commit()
        print("Database creation completed and committed to volume")
    else:
        print(f"Database already exists at {DB_PATH}")


@app.function(timeout=180, volumes={VOLUME_DIR: volume}, max_containers=80)
def process_block(slot: int, timeout: int = 60) -> bool:
    """
    Process a single block and save it to the database

    Args:
        slot: The slot number to process
        timeout: Request timeout in seconds

    Returns:
        True if block was successfully processed, False otherwise
    """
    # Add more debug information
    container_id = os.environ.get("MODAL_CONTAINER_ID", "unknown")
    start_time = time.time()
    print(
        f"[Container {container_id}] Starting to process block {slot}, time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}..."
    )

    # Maximum retry count
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Call get_block without fields_to_remove parameter
            rpc_start_time = time.time()
            print(
                f"[Container {container_id}] Starting RPC request for block {slot}..."
            )
            block_data = get_block(slot, timeout)
            rpc_end_time = time.time()
            rpc_time = rpc_end_time - rpc_start_time
            print(
                f"[Container {container_id}] RPC request for block {slot} completed, time: {rpc_time:.2f} seconds"
            )

            if not block_data:
                print(f"[Container {container_id}] No data found for block {slot}")
                return False

            # Verify the integrity of block data
            if "blockhash" not in block_data:
                print(
                    f"[Container {container_id}] Block {slot} data is incomplete, missing blockhash"
                )
                return False

            # Save to SQLite database in the volume
            db_start_time = time.time()
            print(
                f"[Container {container_id}] Starting to save block {slot} to database..."
            )
            try:
                save_to_sqlite(block_data, str(DB_PATH))
                db_end_time = time.time()
                db_time = db_end_time - db_start_time
                print(
                    f"[Container {container_id}] Saving block {slot} to database completed, time: {db_time:.2f} seconds"
                )
            except sqlite3.Error as e:
                print(f"[Container {container_id}] Database error: {e}")
                # If it's a foreign key constraint error, it might be due to concurrency issues
                if (
                    "FOREIGN KEY constraint failed" in str(e)
                    and retry_count < max_retries - 1
                ):
                    retry_count += 1
                    print(
                        f"[Container {container_id}] Trying to retry ({retry_count}/{max_retries})..."
                    )
                    time.sleep(1)  # Wait for a short time before retrying
                    continue
                return False
            except Exception as e:
                print(f"[Container {container_id}] Error saving block {slot}: {e}")
                return False

            # Verify data was successfully saved
            try:
                with sqlite3.connect(str(DB_PATH)) as conn:
                    configure_sqlite_connection(conn, enable_transaction=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                    result = cursor.fetchone()
                    if not result:
                        print(
                            f"[Container {container_id}] Verification failed: block {slot} not saved to database"
                        )
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            print(
                                f"[Container {container_id}] Trying to retry ({retry_count}/{max_retries})..."
                            )
                            time.sleep(1)  # Wait for a short time before retrying
                            continue
                        return False

                    block_id = result[0]
                    print(
                        f"[Container {container_id}] Verification successful: block {slot} saved, ID={block_id}"
                    )

                    # Verify transaction data
                    cursor.execute(
                        "SELECT COUNT(*) FROM transactions WHERE block_id = ?",
                        (block_id,),
                    )
                    tx_count = cursor.fetchone()[0]
                    print(
                        f"[Container {container_id}] Block {slot} transaction count: {tx_count}"
                    )
            except Exception as e:
                print(
                    f"[Container {container_id}] Verification error for block {slot}: {e}"
                )
                # Here we don't return False because data might have been successfully saved

            # Make sure to commit changes to the volume
            commit_start_time = time.time()
            print(f"[Container {container_id}] Starting to commit changes to volume...")
            volume.commit()
            commit_end_time = time.time()
            commit_time = commit_end_time - commit_start_time
            print(
                f"[Container {container_id}] Commit changes to volume completed, time: {commit_time:.2f} seconds"
            )
            end_time = time.time()
            processing_time = end_time - start_time
            print(
                f"[Container {container_id}] Successfully processed block {slot}, total time: {processing_time:.2f} seconds"
            )
            return True

        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            print(
                f"[Container {container_id}] Error processing block {slot}: {str(e)}, time: {processing_time:.2f} seconds"
            )

            # Check if we need to retry
            if retry_count < max_retries - 1:
                retry_count += 1
                print(
                    f"[Container {container_id}] Trying to retry ({retry_count}/{max_retries})..."
                )
                time.sleep(1)  # Wait for a short time before retrying
            else:
                print(
                    f"[Container {container_id}] Reached maximum retry count, giving up on block {slot}"
                )
                return False

    # If we reach here, all retries have failed
    return False


@app.function(timeout=60)
def get_latest_slot_wrapper(timeout: int = 30) -> Optional[int]:
    """
    Wrapper function to get the latest block number from Solana mainnet

    Args:
        timeout: RPC request timeout (seconds)

    Returns:
        The latest block number, or None if the request fails
    """
    return get_latest_slot(timeout)


@app.function(volumes={VOLUME_DIR: volume})
def get_highest_processed_slot_wrapper() -> int:
    """
    Wrapper function to get the highest processed block number from the database

    Returns:
        The highest block number in the database, or 0 if the database is empty
    """
    return get_highest_processed_slot(str(DB_PATH))


@app.function(timeout=3600, volumes={VOLUME_DIR: volume})  # 1 hour maximum runtime
def fetch_blocks_range(start_slot: int, end_slot: int, timeout: int = 60):
    """
    Fetch and process a range of blocks

    Args:
        start_slot: Starting slot number
        end_slot: Ending slot number (inclusive)
        timeout: RPC request timeout (seconds)
    """
    # Ensure database exists in volume
    ensure_database_exists_call = ensure_database_exists.spawn()
    ensure_database_exists_call.get()  # Wait for database to be ready

    # Prepare all slots to be processed
    slots = list(range(start_slot, end_slot + 1))
    total_slots = len(slots)

    print(
        f"Preparing to process {total_slots} blocks, each using a separate container..."
    )

    # Process all blocks in parallel, each block one container
    results = list(process_block.map(slots, kwargs={"timeout": timeout}))

    # Count successful and failed blocks
    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    print(
        f"Processing completed. Successfully processed {success_count} blocks, failed {fail_count} blocks."
    )


@app.function(timeout=3600, volumes={VOLUME_DIR: volume})  # 1 hour maximum runtime
def fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    """
    Automatically fetch the latest block data

    Args:
        max_blocks: Maximum number of blocks to fetch
        timeout: RPC request timeout (seconds)
    """
    # Get latest block number and highest processed block number
    latest_slot_call = get_latest_slot_wrapper.spawn(timeout)
    highest_processed_call = get_highest_processed_slot_wrapper.spawn()

    # Wait for both calls to complete
    latest_slot, highest_processed = modal.FunctionCall.gather(
        latest_slot_call, highest_processed_call
    )

    if latest_slot is None:
        print("Unable to get latest block number, exiting")
        return

    # Calculate block range to fetch
    start_slot = highest_processed + 1
    end_slot = min(latest_slot, start_slot + max_blocks - 1)

    if start_slot > end_slot:
        print(f"Database is latest, current highest block: {highest_processed}")
        return

    print(
        f"Fetching block range: {start_slot} to {end_slot} (total {end_slot - start_slot + 1} blocks)"
    )

    # Prepare all slots to be processed
    slots = list(range(start_slot, end_slot + 1))
    total_slots = len(slots)

    print(
        f"Preparing to process {total_slots} blocks, each using a separate container..."
    )

    # Ensure database exists
    ensure_database_exists_call = ensure_database_exists.spawn()
    ensure_database_exists_call.get()  # Wait for database to be ready

    # Process all blocks in parallel, each block one container
    results = list(process_block.map(slots, kwargs={"timeout": timeout}))

    # Count successful and failed blocks
    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    print(
        f"Processing completed. Successfully processed {success_count} blocks, failed {fail_count} blocks."
    )


@app.function(
    timeout=300,  # 5 minutes timeout
    volumes={VOLUME_DIR: volume},
    schedule=modal.Period(seconds=20),  # Run every 20 seconds
)
def auto_fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    """
    Timer task: Automatically fetch the latest block data every 20 seconds

    This function is automatically called every 20 seconds by the Modal scheduler to check for new blocks and save them to the database.
    Using lock mechanism to ensure only one instance is running at the same time.

    Args:
        max_blocks: Maximum number of blocks to fetch each time
        timeout: RPC request timeout (seconds)
    """
    lock_file = Path(VOLUME_DIR) / "auto_fetch.lock"

    # Check if lock file exists
    if lock_file.exists():
        # Read lock file timestamp
        try:
            with open(lock_file, "r") as f:
                lock_time_str = f.read().strip()
                lock_time = datetime.fromisoformat(lock_time_str)
                current_time = datetime.now()
                # If lock is older than 10 minutes, consider it deadlocked, can force unlock
                if (current_time - lock_time).total_seconds() < 600:
                    print(
                        f"Previous task still running [lock creation time: {lock_time_str}]，skip this execution"
                    )
                    return
                else:
                    print(
                        f"Found expired lock [lock creation time: {lock_time_str}]，force unlock"
                    )
        except Exception as e:
            print(f"Error reading lock file: {e}，assume lock expired")

    # Create lock file
    try:
        with open(lock_file, "w") as f:
            current_time = datetime.now()
            f.write(current_time.isoformat())
        volume.commit()  # Ensure lock file is saved to volume
    except Exception as e:
        print(f"Error creating lock file: {e}")
        return

    try:
        print(
            f"Starting scheduled task [time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
        )

        # Ensure database exists
        ensure_database_exists_call = ensure_database_exists.spawn()
        ensure_database_exists_call.get()  # Wait for database to be ready

        # Get latest block number and highest processed block number
        latest_slot_call = get_latest_slot_wrapper.spawn(timeout)
        highest_processed_call = get_highest_processed_slot_wrapper.spawn()

        # Wait for both calls to complete
        latest_slot, highest_processed = modal.FunctionCall.gather(
            latest_slot_call, highest_processed_call
        )

        if latest_slot is None:
            print("Unable to get latest block number, exiting")
            return

        # Calculate block range to fetch
        start_slot = highest_processed + 1
        end_slot = min(latest_slot, start_slot + max_blocks - 1)

        if start_slot > end_slot:
            print(f"Database is latest, current highest block: {highest_processed}")
            return

        print(
            f"Scheduled task fetching block range: {start_slot} to {end_slot} (total {end_slot - start_slot + 1} blocks)"
        )

        # Prepare all slots to be processed
        slots = list(range(start_slot, end_slot + 1))
        total_slots = len(slots)

        print(
            f"Preparing to process {total_slots} blocks, each using a separate container..."
        )

        # Process all blocks in parallel, each block one container
        results = list(process_block.map(slots, kwargs={"timeout": timeout}))

        # Count successful and failed blocks
        success_count = sum(1 for r in results if r)
        fail_count = sum(1 for r in results if not r)

        print(
            f"Scheduled task completed. Successfully processed {success_count} blocks, failed {fail_count} blocks."
        )
        print(
            f"Scheduled task ended [time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
        )

    finally:
        # Regardless of task success or failure, delete lock file
        try:
            if lock_file.exists():
                os.remove(lock_file)
                volume.commit()  # Ensure lock file deletion is saved to volume
        except Exception as e:
            print(f"Error deleting lock file: {e}")


@app.function(volumes={VOLUME_DIR: volume})
def query_database_wrapper(sql_query: str) -> Dict[str, Any]:
    """
    Wrapper function to execute SQL query and return results

    Args:
        sql_query: SQL query statement

    Returns:
        Dictionary containing query results
    """
    return query_database(str(DB_PATH), sql_query)


# Modify the entrypoint to handle command line arguments
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Modal functions for Solana block data"
    )
    parser.add_argument(
        "--query", type=str, help="SQL query to run against the database"
    )
    parser.add_argument(
        "start_slot", type=int, nargs="?", help="Start slot number for fetch"
    )
    parser.add_argument(
        "end_slot", type=int, nargs="?", help="End slot number for fetch"
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Request timeout (seconds)"
    )
    parser.add_argument("--latest", action="store_true", help="Fetch latest blocks")
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=80,
        help="Maximum number of blocks to fetch when using --latest",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Deploy the scheduled function to run every 20 seconds",
    )

    args = parser.parse_args()

    with app.run():
        if args.schedule:
            print("Deploy scheduled task, auto fetch latest blocks every 20 seconds")
            # We don't need to do anything here because the function itself already has schedule decorator
            # Just ensure to pass through modal deploy to deploy the application
            print(
                "Scheduled task configured, use 'modal deploy modal_app.py' to deploy application"
            )
        elif args.latest:
            print("Fetching latest block...")
            fetch_latest_blocks_call = fetch_latest_blocks.spawn(
                args.max_blocks, args.timeout
            )
            fetch_latest_blocks_call.get()  # Wait for completion
        elif args.query:
            result_call = query_database_wrapper.spawn(args.query)
            result = result_call.get()  # Wait for the result
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Found {result['row_count']} rows")
                print("\t".join(result["columns"]))
                print("-" * 80)
                for row in result["rows"][:20]:
                    print("\t".join(str(item) for item in row))

                if result["row_count"] > 20:
                    print(f"... and {result['row_count'] - 20} more rows")

        elif args.start_slot is not None and args.end_slot is not None:
            fetch_blocks_range_call = fetch_blocks_range.spawn(
                args.start_slot,
                args.end_slot,
                args.timeout,
            )
            fetch_blocks_range_call.get()  # Wait for completion

        else:
            ensure_database_exists_call = ensure_database_exists.spawn()
            ensure_database_exists_call.get()  # Wait for completion
            print("Database is ready in Modal volume.")


@app.local_entrypoint()
def main():
    """
    Local entry point, can be executed by 'modal run modal_app.py'
    """
    print("Solana block data processing application")
    print("Available commands:")
    print("  Get latest blocks: modal run modal_app.py --latest [--max-blocks N]")
    print('  Query database: modal run modal_app.py --query "SQL query statement"')
    print("  Get specific range: modal run modal_app.py START_SLOT END_SLOT")
    print("  Deploy scheduled task: modal deploy modal_app.py")
    print("")
    print("Optional parameters:")
    print("  --timeout N: RPC request timeout (seconds), default 30")
    print("  --max-blocks N: Maximum number of blocks to fetch, default 80")
    print("")
    print(
        "After deployment, auto_fetch_latest_blocks function will run automatically every 20 seconds"
    )
