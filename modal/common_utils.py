import requests
import json
import os
import sqlite3
import base64
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# SQL Statements as constants
SQL_INSERT_BLOCK = """
INSERT OR IGNORE INTO blocks 
(slot, block_height, block_time, blockhash, parent_slot, previous_blockhash)
VALUES (?, ?, ?, ?, ?, ?)
"""

SQL_UPDATE_BLOCK = """
UPDATE blocks SET
block_height = ?,
block_time = ?,
blockhash = ?,
parent_slot = ?,
previous_blockhash = ?
WHERE slot = ?
"""

SQL_SELECT_BLOCK_ID = "SELECT id FROM blocks WHERE slot = ?"

SQL_INSERT_ACCOUNT = "INSERT OR REPLACE INTO accounts (pubkey) VALUES (?)"

SQL_INSERT_TRANSACTION = """
INSERT OR REPLACE INTO transactions 
(block_id, signature, fee, compute_units_consumed, error_message)
VALUES (?, ?, ?, ?, ?)
"""

SQL_SELECT_TRANSACTION_ID = "SELECT id FROM transactions WHERE signature = ?"

SQL_INSERT_TX_ACCOUNT = """
INSERT OR REPLACE INTO transaction_accounts 
(transaction_id, account_id, position, is_signer, is_writable)
VALUES (?, ?, ?, ?, ?)
"""

SQL_INSERT_INSTRUCTION = """
INSERT OR REPLACE INTO instructions 
(transaction_id, program_id_account_id, program_index, data)
VALUES (?, ?, ?, ?)
"""

SQL_SELECT_INSTRUCTION_ID = """
SELECT id FROM instructions 
WHERE transaction_id = ? AND program_index = ?
"""

SQL_INSERT_INSTRUCTION_ACCOUNT = """
INSERT OR REPLACE INTO instruction_accounts 
(instruction_id, account_id, position)
VALUES (?, ?, ?)
"""


def get_block(slot: int, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Fetch block data from Solana network and process it to reduce size

    Args:
        slot: The slot number to fetch
        timeout: Request timeout in seconds

    Returns:
        Processed block data or None if there was an error
    """
    rpc_url = "https://solana-mainnet.g.alchemy.com/v2/D7uf6FR6CE3ZJsl8cjux1wofeTUpy4O_"

    # Prepare the getBlock RPC request
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBlock",
        "params": [
            slot,
            {
                "encoding": "json",
                "transactionDetails": "full",
                "rewards": False,
                "maxSupportedTransactionVersion": 0,
            },
        ],
    }

    # For debugging
    print(f"Fetching block {slot} from {rpc_url}...")

    # Make the RPC request
    try:
        response = requests.post(
            rpc_url, headers=headers, json=payload, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"Error fetching block: {result['error']['message']}")
            return None

        # Check if result contains actual data
        if "result" not in result:
            print(f"No result data in response for block {slot}")
            return None

        block_data = result["result"]

        # Check if block data is None or empty
        if not block_data:
            print(f"Empty block data for slot {slot}")
            return None

        # Ensure block_data is a dictionary with at least the basic fields
        if not isinstance(block_data, dict):
            print(f"Block data is not a dictionary for slot {slot}")
            return None

        # 添加slot字段，因为RPC返回的数据中不包含此字段
        block_data["slot"] = slot
        print(f"添加slot字段到区块数据: {slot}")

        # Remove rewards if present (save space)
        if "rewards" in block_data:
            del block_data["rewards"]

        # Ensure blockHeight and blockTime are present (can be None)
        if "blockHeight" in block_data and block_data["blockHeight"] == "null":
            block_data["blockHeight"] = None

        if "blockTime" in block_data and block_data["blockTime"] == "null":
            block_data["blockTime"] = None

        # Remove specified fields from transaction data
        if "transactions" in block_data and block_data["transactions"]:
            for tx in block_data["transactions"]:
                # Handle case where meta might be None
                meta = tx.get("meta")

                transaction = tx.get("transaction", {})
                message = transaction.get("message", {})

                # Create a new meta dict with only the fields we want to keep
                new_meta = {}
                if meta == "null":
                    # empty meta if it's missing
                    tx["meta"] = {}
                else:
                    if meta is not None:
                        if "fee" in meta:
                            new_meta["fee"] = meta["fee"]
                        if "computeUnitsConsumed" in meta:
                            new_meta["computeUnitsConsumed"] = meta[
                                "computeUnitsConsumed"
                            ]
                        if "err" in meta:
                            new_meta["err"] = meta["err"]

                # Replace the original meta with our filtered version
                tx["meta"] = new_meta

                # Remove version from transaction
                if "version" in transaction:
                    del transaction["version"]

                # Remove recentBlockhash from transaction message
                if "recentBlockhash" in message:
                    del message["recentBlockhash"]

        return block_data

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error processing response: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_block: {e}")
        return None


def get_latest_slot(timeout: int = 30) -> Optional[int]:
    """
    获取Solana主网上的最新区块号

    Args:
        timeout: RPC请求超时时间（秒）

    Returns:
        最新的区块号，如果请求失败则返回None
    """
    # Solana主网RPC端点
    rpc_url = "https://api.mainnet-beta.solana.com"

    # 准备getSlot RPC请求
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSlot",
        "params": [],
    }

    # 发送RPC请求
    try:
        response = requests.post(
            rpc_url, headers=headers, json=payload, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"获取最新区块号错误: {result['error']['message']}")
            return None

        return result["result"]

    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"处理响应错误: {e}")
        return None


def ensure_database_exists(db_path: str) -> None:
    """
    Check if database exists and create it if it doesn't

    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Check if database file exists
    if not os.path.exists(db_path):
        try:
            from create_database import create_database

            create_database(db_path)
        except sqlite3.Error as e:
            print(f"Warning: Could not create database: {e}")
            print("Please make sure the database is properly initialized.")


def configure_sqlite_connection(
    conn: sqlite3.Connection, enable_transaction: bool = True
) -> None:
    """
    Configure SQLite connection with optimized settings

    Args:
        conn: SQLite connection object
        enable_transaction: Whether to begin a transaction
    """
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Optimize SQLite performance
    conn.execute(
        "PRAGMA journal_mode = WAL"
    )  # Write-Ahead Logging for better concurrency
    conn.execute("PRAGMA synchronous = NORMAL")  # Balanced durability and speed
    conn.execute("PRAGMA cache_size = -64000")  # Use more memory for caching (64MB)
    conn.execute("PRAGMA temp_store = MEMORY")  # Store temporary tables in memory

    # Begin transaction if requested
    if enable_transaction:
        conn.execute("BEGIN TRANSACTION")


def encode_instruction_data(data: str) -> bytes:
    """
    Convert instruction data string to binary format to save space

    Args:
        data: Instruction data string (usually base58 or base64)

    Returns:
        Binary data as bytes
    """
    if not data:
        return b""

    try:
        # Try to decode as base64 first (most common format)
        return base64.b64decode(data)
    except ValueError:
        # If not base64, store as UTF-8 bytes
        try:
            return data.encode("utf-8")
        except UnicodeEncodeError:
            # As a last resort, use latin-1 which can encode any string
            return data.encode("latin-1")
    except Exception as e:
        # Log the error and return a safe fallback
        print(f"Unexpected error encoding instruction data: {e}")
        return b"ERROR_ENCODING_DATA"


def insert_block_data(cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
    """
    Insert block data into the database

    Args:
        cursor: SQLite cursor
        data: Block data

    Returns:
        The block_id of the inserted record
    """
    # 获取slot值
    slot = data["slot"]  # 现在我们确信这个字段存在
    print(f"插入区块数据，slot={slot}, 类型={type(slot)}")

    block_values = (
        slot,
        data.get("blockHeight", None),
        data.get("blockTime", None),
        data.get("blockhash", ""),
        data.get("parentSlot", None),
        data.get("previousBlockhash", ""),
    )

    # 检查区块是否已存在
    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    existing_block = cursor.fetchone()

    block_id = None
    if existing_block:
        block_id = existing_block[0]
        print(f"区块 {slot} 已存在，ID={block_id}，将更新现有记录")

        # 更新现有记录
        update_values = (
            data.get("blockHeight", None),
            data.get("blockTime", None),
            data.get("blockhash", ""),
            data.get("parentSlot", None),
            data.get("previousBlockhash", ""),
            slot,
        )
        print(f"执行SQL更新，values={update_values}")
        cursor.execute(SQL_UPDATE_BLOCK, update_values)
    else:
        print(f"区块 {slot} 不存在，将插入新记录")
        print(f"执行SQL插入，values={block_values}")

        # 使用直接插入而不是INSERT OR IGNORE，以确保获得正确的rowid
        cursor.execute(
            """
            INSERT INTO blocks 
            (slot, block_height, block_time, blockhash, parent_slot, previous_blockhash)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            block_values,
        )

        # 获取最后插入的行ID
        block_id = cursor.lastrowid
        print(f"最后插入的行ID (cursor.lastrowid): {block_id}")

        # 验证插入是否成功
        if block_id is None or block_id == 0:
            cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
            result = cursor.fetchone()
            if result:
                block_id = result[0]
                print(f"通过查询获取区块 {slot} 的ID={block_id}")
            else:
                # 如果没有找到记录，可能是因为另一个事务已经插入了相同的记录
                # 再次尝试获取ID
                cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                result = cursor.fetchone()
                if result:
                    block_id = result[0]
                    print(f"在第二次尝试中找到区块 {slot}，ID={block_id}")
                else:
                    raise ValueError(f"无法插入或找到区块 {slot}")

    # 检查是否有行被修改
    if cursor.rowcount > 0:
        print(f"区块 {slot} 操作成功，影响行数={cursor.rowcount}")
    else:
        print(f"区块 {slot} 没有变化，影响行数={cursor.rowcount}")

    # 最后验证一次，确保我们有正确的block_id
    if block_id is None:
        cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
        result = cursor.fetchone()
        if result is None:
            raise ValueError(f"Failed to retrieve block ID for slot {slot}")
        block_id = result[0]

    print(f"最终确认: 区块 {slot} 的ID={block_id}")

    # 添加额外的验证，确保ID是唯一的
    cursor.execute("SELECT slot FROM blocks WHERE id = ?", (block_id,))
    result = cursor.fetchone()
    if result and result[0] != slot:
        raise ValueError(
            f"严重错误: 区块ID {block_id} 已经被分配给了另一个区块 {result[0]}"
        )

    # 再次验证，确保slot对应的ID是正确的
    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    result = cursor.fetchone()
    if result and result[0] != block_id:
        raise ValueError(
            f"严重错误: 区块 {slot} 的ID不一致，期望 {block_id}，实际 {result[0]}"
        )

    return block_id


def collect_account_pubkeys(data: Dict[str, Any]) -> set:
    """
    Collect all pubkeys from transactions

    Args:
        data: Block data

    Returns:
        Set of all pubkeys in the block
    """
    all_pubkeys = set()

    # Skip if no transactions
    if "transactions" not in data or not data["transactions"]:
        return all_pubkeys

    # Process transactions - collect all pubkeys
    for tx in data["transactions"]:
        transaction = tx.get("transaction", {})
        message = transaction.get("message", {})

        # Collect account pubkeys
        account_keys = message.get("accountKeys", [])
        if account_keys:  # Only update if account_keys is not empty
            all_pubkeys.update(account_keys)

        # Collect program ids from instructions
        instructions = message.get("instructions", [])
        if not instructions:  # Skip if instructions is empty
            continue

        for instr in instructions:
            program_idx = instr.get("programIdIndex")
            if (
                program_idx is not None
                and account_keys
                and program_idx < len(account_keys)
            ):
                all_pubkeys.add(account_keys[program_idx])

    return all_pubkeys


def process_accounts(cursor: sqlite3.Cursor, pubkeys: set) -> dict:
    """
    Process account data, insert into database and return mapping

    Args:
        cursor: SQLite cursor
        pubkeys: Set of pubkeys

    Returns:
        Dictionary mapping pubkeys to account IDs
    """
    # Skip if no pubkeys
    if not pubkeys:
        return {}

    # 逐个插入账户，而不是批量插入
    pubkey_to_id = {}
    for pubkey in pubkeys:
        # 插入账户
        cursor.execute(SQL_INSERT_ACCOUNT, (pubkey,))

        # 获取账户ID
        cursor.execute("SELECT id FROM accounts WHERE pubkey = ?", (pubkey,))
        result = cursor.fetchone()
        if result:
            pubkey_to_id[pubkey] = result[0]

    return pubkey_to_id


def process_transactions(
    cursor: sqlite3.Cursor, data: Dict[str, Any], block_id: int, pubkey_to_id: dict
) -> dict:
    """
    Process transaction data and insert into database

    Args:
        cursor: SQLite cursor
        data: Block data
        block_id: Block ID
        pubkey_to_id: Dictionary mapping pubkeys to account IDs

    Returns:
        Dictionary mapping transaction keys to transaction IDs
    """
    # Skip if no transactions
    if "transactions" not in data or not data["transactions"]:
        return {}

    tx_id_map = {}

    # 逐个处理交易
    for tx in data["transactions"]:
        meta = tx.get("meta", {})
        transaction = tx.get("transaction", {})

        # Skip if transaction data is missing
        if not transaction:
            continue

        message = transaction.get("message", {})
        signatures = transaction.get("signatures", [])
        signature = signatures[0] if signatures else ""

        if not signature:
            continue

        # 插入交易数据
        tx_data = (
            block_id,
            signature,
            meta.get("fee", 0),
            meta.get("computeUnitsConsumed", 0),
            json.dumps(meta.get("err")) if meta.get("err") else None,
        )
        cursor.execute(SQL_INSERT_TRANSACTION, tx_data)

        # 获取交易ID
        cursor.execute(SQL_SELECT_TRANSACTION_ID, (signature,))
        result = cursor.fetchone()
        if not result:
            continue

        tx_id = result[0]
        tx_key = (block_id, signature)
        tx_id_map[tx_key] = tx_id

        # 处理交易中的账户
        account_keys = message.get("accountKeys", [])
        header = message.get("header", {})
        num_required_signatures = header.get("numRequiredSignatures", 0)
        num_readonly_signed = header.get("numReadonlySignedAccounts", 0)
        num_readonly_unsigned = header.get("numReadonlyUnsignedAccounts", 0)

        # 逐个处理交易中的账户
        for idx, pubkey in enumerate(account_keys):
            is_signer = idx < num_required_signatures
            is_writable = (is_signer and idx >= num_readonly_signed) or (
                not is_signer and idx < len(account_keys) - num_readonly_unsigned
            )

            # 插入交易账户关系
            if pubkey in pubkey_to_id:
                cursor.execute(
                    SQL_INSERT_TX_ACCOUNT,
                    (
                        tx_id,
                        pubkey_to_id[pubkey],
                        idx,
                        1 if is_signer else 0,
                        1 if is_writable else 0,
                    ),
                )

    return tx_id_map


def process_instructions(
    cursor: sqlite3.Cursor,
    data: Dict[str, Any],
    block_id: int,
    tx_id_map: dict,
    pubkey_to_id: dict,
) -> None:
    """
    Process instruction data and insert into database

    Args:
        cursor: SQLite cursor
        data: Block data
        block_id: Block ID
        tx_id_map: Dictionary mapping transaction keys to transaction IDs
        pubkey_to_id: Dictionary mapping pubkeys to account IDs
    """
    # Skip if no transactions
    if "transactions" not in data or not data["transactions"]:
        return

    # 逐个处理交易中的指令
    for tx in data["transactions"]:
        transaction = tx.get("transaction", {})
        message = transaction.get("message", {})
        signatures = transaction.get("signatures", [])
        signature = signatures[0] if signatures else ""
        tx_key = (block_id, signature)

        if tx_key not in tx_id_map:
            continue

        tx_id = tx_id_map[tx_key]
        account_keys = message.get("accountKeys", [])

        # 逐个处理指令
        for idx, instr in enumerate(message.get("instructions", [])):
            program_idx = instr.get("programIdIndex")
            if program_idx is None or program_idx >= len(account_keys):
                continue

            program_pubkey = account_keys[program_idx]
            if program_pubkey not in pubkey_to_id:
                continue

            program_id = pubkey_to_id[program_pubkey]

            # 转换指令数据为二进制格式以节省空间
            instr_data = encode_instruction_data(instr.get("data", ""))

            # 插入指令数据
            cursor.execute(
                SQL_INSERT_INSTRUCTION,
                (
                    tx_id,
                    program_id,
                    program_idx,
                    instr_data,
                ),
            )

            # 获取指令ID
            cursor.execute(SQL_SELECT_INSTRUCTION_ID, (tx_id, program_idx))
            result = cursor.fetchone()
            if not result:
                continue

            instr_id = result[0]

            # 逐个处理指令中的账户
            for acct_idx, acct_pos in enumerate(instr.get("accounts", [])):
                if acct_pos >= len(account_keys):
                    continue

                account_pubkey = account_keys[acct_pos]
                if account_pubkey not in pubkey_to_id:
                    continue

                account_id = pubkey_to_id[account_pubkey]

                # 插入指令账户关系
                cursor.execute(
                    SQL_INSERT_INSTRUCTION_ACCOUNT,
                    (
                        instr_id,
                        account_id,
                        acct_idx,
                    ),
                )


def save_to_sqlite(data: Dict[str, Any], db_path: str) -> None:
    """
    Save block data to SQLite database

    Args:
        data: The block data to save
        db_path: Path to the SQLite database file
    """
    # 获取slot值用于日志记录
    slot = data.get("slot")
    print(f"开始保存区块 {slot} 到数据库 {db_path}")

    # Ensure database exists
    ensure_database_exists(db_path)

    try:
        # Connect to SQLite database using context manager
        with sqlite3.connect(db_path) as conn:
            # 设置更严格的事务隔离级别
            conn.execute("PRAGMA isolation_level = IMMEDIATE")

            # Configure SQLite connection
            configure_sqlite_connection(conn)

            # Create cursor (SQLite cursor doesn't support context manager)
            cursor = conn.cursor()

            try:
                # Step 1: Insert block data
                print(f"步骤1: 插入区块 {slot} 的基本数据")
                block_id = insert_block_data(cursor, data)
                print(f"区块 {slot} 的ID为 {block_id}")

                # Step 2: Collect all pubkeys
                print(f"步骤2: 收集区块 {slot} 中的所有公钥")
                all_pubkeys = collect_account_pubkeys(data)
                print(f"区块 {slot} 中找到 {len(all_pubkeys)} 个唯一公钥")

                # Step 3: Process accounts and get pubkey mapping
                print(f"步骤3: 处理区块 {slot} 的账户数据")
                pubkey_to_id = process_accounts(cursor, all_pubkeys)
                print(f"成功处理 {len(pubkey_to_id)} 个账户")

                # 验证账户映射
                if len(all_pubkeys) > 0 and len(pubkey_to_id) == 0:
                    raise ValueError(
                        f"严重错误: 区块 {slot} 的账户处理失败，没有获取到任何账户ID"
                    )

                # Step 4: Process transactions and related accounts
                print(f"步骤4: 处理区块 {slot} 的交易数据")
                tx_id_map = process_transactions(cursor, data, block_id, pubkey_to_id)
                tx_count = len(data.get("transactions", []))
                print(
                    f"区块 {slot} 中有 {tx_count} 个交易，成功处理 {len(tx_id_map)} 个"
                )

                # 验证交易处理
                if tx_count > 0 and len(tx_id_map) == 0:
                    print(f"警告: 区块 {slot} 的交易处理可能不完整")

                # Step 5: Process instructions and related accounts
                print(f"步骤5: 处理区块 {slot} 的指令数据")
                process_instructions(cursor, data, block_id, tx_id_map, pubkey_to_id)
                print(f"区块 {slot} 的指令处理完成")

                # 最终验证
                cursor.execute(
                    "SELECT COUNT(*) FROM transactions WHERE block_id = ?", (block_id,)
                )
                tx_db_count = cursor.fetchone()[0]
                print(f"数据库中区块 {slot} (ID={block_id}) 的交易数: {tx_db_count}")

                # 验证区块ID是否正确
                cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                result = cursor.fetchone()
                if not result or result[0] != block_id:
                    raise ValueError(
                        f"严重错误: 区块 {slot} 的ID不一致，期望 {block_id}，实际 {result[0] if result else 'None'}"
                    )

                # Transaction is automatically committed when the context manager exits
                print(f"区块 {slot} 的数据已成功保存到数据库")

            except Exception as e:
                print(f"处理区块 {slot} 时发生错误: {e}")
                # 在这里不抛出异常，让外层的异常处理来处理
                raise

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        # 提供更详细的错误信息
        if "FOREIGN KEY constraint failed" in str(e):
            print(f"外键约束错误: 可能是区块ID {block_id} 的引用问题")
            # 尝试查询区块ID
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                    result = cursor.fetchone()
                    if result:
                        print(f"数据库中区块 {slot} 的ID为 {result[0]}")
                    else:
                        print(f"数据库中找不到区块 {slot}")
            except Exception as ex:
                print(f"尝试查询区块ID时出错: {ex}")
        elif "UNIQUE constraint failed" in str(e):
            print(f"唯一约束错误: 可能是尝试插入重复数据")
        # Connection and transaction are automatically rolled back when
        # the context manager exits due to an exception
        raise  # 重新抛出异常，让调用者知道发生了错误


def get_highest_processed_slot(db_path: str) -> int:
    """
    从数据库中获取已处理的最高区块号

    Args:
        db_path: 数据库文件路径

    Returns:
        数据库中最高的区块号，如果数据库为空则返回0
    """
    if not os.path.exists(db_path):
        print("数据库不存在，返回起始区块号0")
        return 0

    try:
        with sqlite3.connect(db_path) as conn:
            configure_sqlite_connection(conn, enable_transaction=False)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(slot) FROM blocks")
            result = cursor.fetchone()

            if result and result[0] is not None:
                return result[0]
            else:
                return 0

    except sqlite3.Error as e:
        print(f"数据库错误: {str(e)}")
        return 0


def query_database(db_path: str, sql_query: str) -> Dict[str, Any]:
    """
    执行SQL查询并返回结果

    Args:
        db_path: 数据库文件路径
        sql_query: SQL查询语句

    Returns:
        包含查询结果的字典
    """
    if not os.path.exists(db_path):
        return {"error": "Database does not exist"}

    try:
        with sqlite3.connect(db_path) as conn:
            configure_sqlite_connection(conn, enable_transaction=False)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except sqlite3.Error as e:
        return {"error": f"Database error: {str(e)}"}
