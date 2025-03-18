# modal_functions.py
import os
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import modal

from config import VOLUME_DIR, DB_FILENAME, DB_PATH, SOLANA_RPC_URL
from common_utils import (
    get_block,
    save_to_sqlite,
    configure_sqlite_connection,
    get_latest_slot,
    get_highest_processed_slot,
    query_database,
)
from create_database import create_database

# 构建 Modal 镜像和 Volume
image = modal.Image.debian_slim().pip_install("requests")
# 添加本地模块源（确保这些模块文件在项目目录下）
image = image.add_local_python_source("create_database", "common_utils")
app = modal.App("solana_db", image=image)
volume = modal.Volume.from_name("solana-db-volume", create_if_missing=True)


@app.function(timeout=300, volumes={VOLUME_DIR: volume})
def ensure_database_exists():
    import os

    os.makedirs(VOLUME_DIR, exist_ok=True)
    if not Path(DB_PATH).exists():
        print(f"Creating database at {DB_PATH}")
        create_database(DB_PATH)
        volume.commit()
        print("Database created and committed")
    else:
        print(f"Database exists at {DB_PATH}")


@app.function(timeout=180, volumes={VOLUME_DIR: volume}, max_containers=80)
def process_block(slot: int, timeout: int = 60) -> bool:
    container = os.environ.get("MODAL_CONTAINER_ID", "unknown")
    start = time.time()
    print(
        f"[{container}] Process block {slot} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[{container}] Requesting block {slot}...")
            block = get_block(slot, timeout)
            if not block or "blockhash" not in block:
                print(f"[{container}] Block {slot} invalid")
                return False
            print(f"[{container}] Saving block {slot}...")
            save_to_sqlite(block, DB_PATH)
            with sqlite3.connect(DB_PATH) as conn:
                configure_sqlite_connection(conn, enable_transaction=False)
                cur = conn.cursor()
                cur.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                if not cur.fetchone():
                    print(f"[{container}] Block {slot} not saved, retrying...")
                    time.sleep(1)
                    continue
            volume.commit()
            print(f"[{container}] Block {slot} processed in {time.time()-start:.2f}s")
            return True
        except sqlite3.Error as e:
            print(f"[{container}] DB error: {e}, retrying...")
            time.sleep(1)
        except Exception as e:
            print(f"[{container}] Error processing block {slot}: {e}")
            time.sleep(1)
    print(f"[{container}] Failed to process block {slot} after {max_retries} attempts")
    return False


@app.function(timeout=60)
def get_latest_slot_wrapper(timeout: int = 30) -> Optional[int]:
    return get_latest_slot(timeout)


@app.function(volumes={VOLUME_DIR: volume})
def get_highest_processed_slot_wrapper() -> int:
    return get_highest_processed_slot(DB_PATH)


@app.function(timeout=3600, volumes={VOLUME_DIR: volume})
def fetch_blocks_range(start_slot: int, end_slot: int, timeout: int = 60):
    ensure_database_exists.spawn().get()
    slots = list(range(start_slot, end_slot + 1))
    print(f"Processing blocks: {start_slot} - {end_slot}")
    results = list(process_block.map(slots, kwargs={"timeout": timeout}))
    success = sum(1 for r in results if r)
    fail = len(results) - success
    print(f"Success: {success}, Fail: {fail}")


@app.function(timeout=3600, volumes={VOLUME_DIR: volume})
def fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    latest, highest = modal.FunctionCall.gather(
        get_latest_slot_wrapper.spawn(timeout),
        get_highest_processed_slot_wrapper.spawn(),
    )
    if latest is None:
        print("Failed to get latest slot")
        return
    start_slot = highest + 1
    end_slot = min(latest, start_slot + max_blocks - 1)
    if start_slot > end_slot:
        print(f"DB up-to-date, highest slot: {highest}")
        return
    print(f"Fetching blocks: {start_slot} - {end_slot}")
    ensure_database_exists.spawn().get()
    results = list(
        process_block.map(
            list(range(start_slot, end_slot + 1)), kwargs={"timeout": timeout}
        )
    )
    success = sum(1 for r in results if r)
    fail = len(results) - success
    print(f"Success: {success}, Fail: {fail}")


@app.function(
    timeout=3600, volumes={VOLUME_DIR: volume}, schedule=modal.Period(seconds=20)
)
def auto_fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    lock_file = Path(VOLUME_DIR) / "auto_fetch.lock"
    if lock_file.exists():
        try:
            with open(lock_file, "r") as f:
                lock_time = datetime.fromisoformat(f.read().strip())
            if (datetime.now() - lock_time).total_seconds() < 600:
                print(f"Task running since {lock_time}, skipping")
                return
        except Exception:
            print("Error reading lock, assume expired")
    try:
        with open(lock_file, "w") as f:
            f.write(datetime.now().isoformat())
        volume.commit()
    except Exception as e:
        print(f"Lock creation failed: {e}")
        return
    try:
        print(f"Auto-fetch started at {datetime.now().isoformat()}")
        ensure_database_exists.spawn().get()
        latest, highest = modal.FunctionCall.gather(
            get_latest_slot_wrapper.spawn(timeout),
            get_highest_processed_slot_wrapper.spawn(),
        )
        if latest is None:
            print("Failed to get latest slot")
            return
        start_slot = highest + 1
        end_slot = min(latest, start_slot + max_blocks - 1)
        if start_slot > end_slot:
            print(f"DB up-to-date, highest slot: {highest}")
            return
        print(f"Auto-fetching blocks: {start_slot} - {end_slot}")
        results = list(
            process_block.map(
                list(range(start_slot, end_slot + 1)), kwargs={"timeout": timeout}
            )
        )
        success = sum(1 for r in results if r)
        fail = len(results) - success
        print(f"Auto-fetch result: Success {success}, Fail {fail}")
    finally:
        try:
            if lock_file.exists():
                os.remove(lock_file)
                volume.commit()
        except Exception as e:
            print(f"Failed to remove lock: {e}")


@app.function(volumes={VOLUME_DIR: volume})
def query_database_wrapper(sql_query: str) -> Dict[str, Any]:
    return query_database(DB_PATH, sql_query)
