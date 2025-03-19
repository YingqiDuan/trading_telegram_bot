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
DB_FILENAME = "solana_blocks.db"
DB_PATH = Path(VOLUME_DIR) / DB_FILENAME

# Import functions from our common utils module
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
    # 添加更多调试信息
    container_id = os.environ.get("MODAL_CONTAINER_ID", "unknown")
    start_time = time.time()
    print(
        f"[Container {container_id}] 开始处理区块 {slot}，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}..."
    )

    # 最大重试次数
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Call get_block without fields_to_remove parameter
            rpc_start_time = time.time()
            print(f"[Container {container_id}] 开始 RPC 请求区块 {slot}...")
            block_data = get_block(slot, timeout)
            rpc_end_time = time.time()
            rpc_time = rpc_end_time - rpc_start_time
            print(
                f"[Container {container_id}] RPC 请求区块 {slot} 完成，耗时 {rpc_time:.2f} 秒"
            )

            if not block_data:
                print(f"[Container {container_id}] 区块 {slot} 未找到数据")
                return False

            # 验证区块数据的完整性
            if "blockhash" not in block_data:
                print(
                    f"[Container {container_id}] 区块 {slot} 数据不完整，缺少 blockhash"
                )
                return False

            # Save to SQLite database in the volume
            db_start_time = time.time()
            print(f"[Container {container_id}] 开始保存区块 {slot} 到数据库...")
            try:
                save_to_sqlite(block_data, str(DB_PATH))
                db_end_time = time.time()
                db_time = db_end_time - db_start_time
                print(
                    f"[Container {container_id}] 保存区块 {slot} 到数据库完成，耗时 {db_time:.2f} 秒"
                )
            except sqlite3.Error as e:
                print(f"[Container {container_id}] 数据库错误: {e}")
                # 如果是外键约束错误，可能是由于并发问题导致的
                if (
                    "FOREIGN KEY constraint failed" in str(e)
                    and retry_count < max_retries - 1
                ):
                    retry_count += 1
                    print(
                        f"[Container {container_id}] 尝试重试 ({retry_count}/{max_retries})..."
                    )
                    time.sleep(1)  # 短暂延迟后重试
                    continue
                return False
            except Exception as e:
                print(f"[Container {container_id}] 保存区块 {slot} 时发生错误: {e}")
                return False

            # 验证数据是否成功保存
            try:
                with sqlite3.connect(str(DB_PATH)) as conn:
                    configure_sqlite_connection(conn, enable_transaction=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                    result = cursor.fetchone()
                    if not result:
                        print(
                            f"[Container {container_id}] 验证失败: 区块 {slot} 未成功保存到数据库"
                        )
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            print(
                                f"[Container {container_id}] 尝试重试 ({retry_count}/{max_retries})..."
                            )
                            time.sleep(1)  # 短暂延迟后重试
                            continue
                        return False

                    block_id = result[0]
                    print(
                        f"[Container {container_id}] 验证成功: 区块 {slot} 已保存，ID={block_id}"
                    )

                    # 验证交易数据
                    cursor.execute(
                        "SELECT COUNT(*) FROM transactions WHERE block_id = ?",
                        (block_id,),
                    )
                    tx_count = cursor.fetchone()[0]
                    print(
                        f"[Container {container_id}] 区块 {slot} 的交易数: {tx_count}"
                    )
            except Exception as e:
                print(f"[Container {container_id}] 验证区块 {slot} 时发生错误: {e}")
                # 这里不返回失败，因为数据可能已经成功保存

            # Make sure to commit changes to the volume
            commit_start_time = time.time()
            print(f"[Container {container_id}] 开始提交区块 {slot} 的更改到卷...")
            volume.commit()
            commit_end_time = time.time()
            commit_time = commit_end_time - commit_start_time
            print(
                f"[Container {container_id}] 提交区块 {slot} 的更改到卷完成，耗时 {commit_time:.2f} 秒"
            )
            end_time = time.time()
            processing_time = end_time - start_time
            print(
                f"[Container {container_id}] 成功处理区块 {slot}，总耗时 {processing_time:.2f} 秒"
            )
            return True

        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            print(
                f"[Container {container_id}] 处理区块 {slot} 出错: {str(e)}，耗时 {processing_time:.2f} 秒"
            )

            # 判断是否需要重试
            if retry_count < max_retries - 1:
                retry_count += 1
                print(
                    f"[Container {container_id}] 尝试重试 ({retry_count}/{max_retries})..."
                )
                time.sleep(1)  # 短暂延迟后重试
            else:
                print(
                    f"[Container {container_id}] 已达到最大重试次数，放弃处理区块 {slot}"
                )
                return False

    # 如果执行到这里，说明所有重试都失败了
    return False


@app.function(timeout=60)
def get_latest_slot_wrapper(timeout: int = 30) -> Optional[int]:
    """
    获取Solana主网上的最新区块号的包装函数

    Args:
        timeout: RPC请求超时时间（秒）

    Returns:
        最新的区块号，如果请求失败则返回None
    """
    return get_latest_slot(timeout)


@app.function(volumes={VOLUME_DIR: volume})
def get_highest_processed_slot_wrapper() -> int:
    """
    从数据库中获取已处理的最高区块号的包装函数

    Returns:
        数据库中最高的区块号，如果数据库为空则返回0
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

    # 准备所有需要处理的区块号
    slots = list(range(start_slot, end_slot + 1))
    total_slots = len(slots)

    print(f"准备处理 {total_slots} 个区块，每个区块使用单独的容器...")

    # 并行处理所有区块，每个区块一个容器
    results = list(process_block.map(slots, kwargs={"timeout": timeout}))

    # 统计成功和失败的数量
    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    print(
        f"Processing completed. Successfully processed {success_count} blocks, failed {fail_count} blocks."
    )


@app.function(timeout=3600, volumes={VOLUME_DIR: volume})  # 1 hour maximum runtime
def fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    """
    自动获取最新的区块数据

    Args:
        max_blocks: 最多获取的区块数量
        timeout: RPC请求超时时间（秒）
    """
    # 获取最新区块号和已处理的最高区块号
    latest_slot_call = get_latest_slot_wrapper.spawn(timeout)
    highest_processed_call = get_highest_processed_slot_wrapper.spawn()

    # Wait for both calls to complete
    latest_slot, highest_processed = modal.FunctionCall.gather(
        latest_slot_call, highest_processed_call
    )

    if latest_slot is None:
        print("无法获取最新区块号，退出")
        return

    # 计算需要获取的区块范围
    start_slot = highest_processed + 1
    end_slot = min(latest_slot, start_slot + max_blocks - 1)

    if start_slot > end_slot:
        print(f"数据库已是最新，当前最高区块: {highest_processed}")
        return

    print(
        f"获取区块范围: {start_slot} 到 {end_slot}（共 {end_slot - start_slot + 1} 个区块）"
    )

    # 准备所有需要处理的区块号
    slots = list(range(start_slot, end_slot + 1))
    total_slots = len(slots)

    print(f"准备处理 {total_slots} 个区块，每个区块使用单独的容器...")

    # 确保数据库存在
    ensure_database_exists_call = ensure_database_exists.spawn()
    ensure_database_exists_call.get()  # Wait for database to be ready

    # 并行处理所有区块，每个区块一个容器
    results = list(process_block.map(slots, kwargs={"timeout": timeout}))

    # 统计成功和失败的数量
    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    print(f"处理完成。成功处理 {success_count} 个区块，失败 {fail_count} 个区块。")


@app.function(
    timeout=300,  # 5分钟超时
    volumes={VOLUME_DIR: volume},
    schedule=modal.Period(seconds=20),  # 每20秒运行一次
)
def auto_fetch_latest_blocks(max_blocks: int = 80, timeout: int = 60):
    """
    定时任务：每20秒自动获取最新的区块数据

    此函数由Modal的调度器自动每20秒调用一次，检查是否有新区块，并将它们保存到数据库中。
    使用锁机制确保同一时间只有一个实例在运行。

    Args:
        max_blocks: 每次最多获取的区块数量
        timeout: RPC请求超时时间（秒）
    """
    lock_file = Path(VOLUME_DIR) / "auto_fetch.lock"

    # 检查锁文件是否存在
    if lock_file.exists():
        # 读取锁文件中的时间戳
        try:
            with open(lock_file, "r") as f:
                lock_time_str = f.read().strip()
                lock_time = datetime.fromisoformat(lock_time_str)
                current_time = datetime.now()
                # 如果锁超过10分钟，认为是死锁，可以强制解除
                if (current_time - lock_time).total_seconds() < 600:
                    print(
                        f"上一次任务仍在运行中 [锁创建时间: {lock_time_str}]，跳过本次执行"
                    )
                    return
                else:
                    print(f"发现过期的锁 [锁创建时间: {lock_time_str}]，强制解除")
        except Exception as e:
            print(f"读取锁文件出错: {e}，假设锁已过期")

    # 创建锁文件
    try:
        with open(lock_file, "w") as f:
            current_time = datetime.now()
            f.write(current_time.isoformat())
        volume.commit()  # 确保锁文件被保存到卷中
    except Exception as e:
        print(f"创建锁文件失败: {e}")
        return

    try:
        print(f"开始定时任务 [时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")

        # 确保数据库存在
        ensure_database_exists_call = ensure_database_exists.spawn()
        ensure_database_exists_call.get()  # Wait for database to be ready

        # 获取最新区块号和已处理的最高区块号
        latest_slot_call = get_latest_slot_wrapper.spawn(timeout)
        highest_processed_call = get_highest_processed_slot_wrapper.spawn()

        # Wait for both calls to complete
        latest_slot, highest_processed = modal.FunctionCall.gather(
            latest_slot_call, highest_processed_call
        )

        if latest_slot is None:
            print("无法获取最新区块号，退出")
            return

        # 计算需要获取的区块范围
        start_slot = highest_processed + 1
        end_slot = min(latest_slot, start_slot + max_blocks - 1)

        if start_slot > end_slot:
            print(f"数据库已是最新，当前最高区块: {highest_processed}")
            return

        print(
            f"定时任务获取区块范围: {start_slot} 到 {end_slot}（共 {end_slot - start_slot + 1} 个区块）"
        )

        # 准备所有需要处理的区块号
        slots = list(range(start_slot, end_slot + 1))
        total_slots = len(slots)

        print(f"准备处理 {total_slots} 个区块，每个区块使用单独的容器...")

        # 并行处理所有区块，每个区块一个容器
        results = list(process_block.map(slots, kwargs={"timeout": timeout}))

        # 统计成功和失败的数量
        success_count = sum(1 for r in results if r)
        fail_count = sum(1 for r in results if not r)

        print(
            f"定时任务完成。成功处理 {success_count} 个区块，失败 {fail_count} 个区块。"
        )
        print(f"定时任务结束 [时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")

    finally:
        # 无论任务成功还是失败，都删除锁文件
        try:
            if lock_file.exists():
                os.remove(lock_file)
                volume.commit()  # 确保锁文件删除被保存到卷中
        except Exception as e:
            print(f"删除锁文件失败: {e}")


@app.function(volumes={VOLUME_DIR: volume})
def query_database_wrapper(sql_query: str) -> Dict[str, Any]:
    """
    执行SQL查询并返回结果的包装函数

    Args:
        sql_query: SQL查询语句

    Returns:
        包含查询结果的字典
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
            print("部署定时任务，每20秒自动获取最新区块...")
            # 在这里我们不需要做任何事情，因为函数本身已经有schedule装饰器
            # 只需要确保通过modal deploy部署应用即可
            print("定时任务已配置，请使用 'modal deploy modal_app.py' 部署应用")
        elif args.latest:
            print("获取最新区块...")
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
    本地入口点，可以通过 'modal run modal_app.py' 来执行
    """
    print("Solana区块数据处理应用")
    print("可用命令:")
    print("  获取最新区块: modal run modal_app.py --latest [--max-blocks N]")
    print('  查询数据库: modal run modal_app.py --query "SQL查询语句"')
    print("  获取特定范围: modal run modal_app.py START_SLOT END_SLOT")
    print("  部署定时任务: modal deploy modal_app.py")
    print("")
    print("可选参数:")
    print("  --timeout N: RPC请求超时时间（秒），默认30")
    print("  --max-blocks N: 每次最多获取的区块数量，默认80")
    print("")
    print("部署后，auto_fetch_latest_blocks函数将每20秒自动运行一次")
