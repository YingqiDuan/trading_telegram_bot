import requests
import json
import os
import sqlite3
import base64
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# SQL constants
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

SQL_INSERT_ACCOUNT = "INSERT OR IGNORE INTO accounts (pubkey) VALUES (?)"

SQL_INSERT_TRANSACTION = """
INSERT OR IGNORE INTO transactions 
(block_id, signature, fee, compute_units_consumed, error_message)
VALUES (?, ?, ?, ?, ?)
"""

SQL_SELECT_TRANSACTION_ID = "SELECT id FROM transactions WHERE signature = ?"

SQL_INSERT_TX_ACCOUNT = """
INSERT OR IGNORE INTO transaction_accounts 
(transaction_id, account_id, position, is_signer, is_writable)
VALUES (?, ?, ?, ?, ?)
"""

SQL_INSERT_INSTRUCTION = """
INSERT OR IGNORE INTO instructions 
(transaction_id, program_id_account_id, program_index, data)
VALUES (?, ?, ?, ?)
"""

SQL_SELECT_INSTRUCTION_ID = """
SELECT id FROM instructions 
WHERE transaction_id = ? AND program_index = ? AND program_id_account_id = ? AND data = ?
"""

SQL_INSERT_INSTRUCTION_ACCOUNT = """
INSERT OR IGNORE INTO instruction_accounts 
(instruction_id, account_id, position)
VALUES (?, ?, ?)
"""


def get_block(slot: int, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Fetch block data from Solana network and process it to reduce size
    """
    rpc_url = "https://solana-mainnet.g.alchemy.com/v2/D7uf6FR6CE3ZJsl8cjux1wofeTUpy4O_"

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

    print(f"Fetching block {slot} from {rpc_url}...")

    try:
        response = requests.post(
            rpc_url, headers=headers, json=payload, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"Error fetching block: {result['error']['message']}")
            return None

        if "result" not in result:
            print(f"No result data in response for block {slot}")
            return None

        block_data = result["result"]
        if not block_data:
            print(f"Empty block data for slot {slot}")
            return None

        if not isinstance(block_data, dict):
            print(f"Block data is not a dictionary for slot {slot}")
            return None

        # Add slot field
        block_data["slot"] = slot
        print(f"Adding slot field to block data: {slot}")

        if "rewards" in block_data:
            del block_data["rewards"]

        if "blockHeight" in block_data and block_data["blockHeight"] == "null":
            block_data["blockHeight"] = None

        if "blockTime" in block_data and block_data["blockTime"] == "null":
            block_data["blockTime"] = None

        # Filter redundant data in transactions
        if "transactions" in block_data and block_data["transactions"]:
            for tx in block_data["transactions"]:
                meta = tx.get("meta")
                transaction = tx.get("transaction", {})
                message = transaction.get("message", {})

                new_meta = {}
                if meta == "null":
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

                tx["meta"] = new_meta

                if "version" in transaction:
                    del transaction["version"]

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
    rpc_url = "https://api.mainnet-beta.solana.com"
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSlot",
        "params": [],
    }
    try:
        response = requests.post(
            rpc_url, headers=headers, json=payload, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            print(f"Error getting latest block number: {result['error']['message']}")
            return None
        return result["result"]
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error processing response: {e}")
        return None


def ensure_database_exists(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
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
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")
    if enable_transaction:
        conn.execute("BEGIN TRANSACTION")


def encode_instruction_data(data: str) -> bytes:
    if not data:
        return b""
    try:
        return base64.b64decode(data)
    except ValueError:
        try:
            return data.encode("utf-8")
        except UnicodeEncodeError:
            return data.encode("latin-1")
    except Exception as e:
        print(f"Unexpected error encoding instruction data: {e}")
        return b"ERROR_ENCODING_DATA"


def insert_block_data(cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
    slot = data["slot"]
    print(f"Inserting block data, slot={slot}, type={type(slot)}")

    block_values = (
        slot,
        data.get("blockHeight", None),
        data.get("blockTime", None),
        data.get("blockhash", ""),
        data.get("parentSlot", None),
        data.get("previousBlockhash", ""),
    )

    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    existing_block = cursor.fetchone()

    block_id = None
    if existing_block:
        block_id = existing_block[0]
        print(
            f"Block {slot} already exists, ID={block_id}, will update existing record"
        )
        update_values = (
            data.get("blockHeight", None),
            data.get("blockTime", None),
            data.get("blockhash", ""),
            data.get("parentSlot", None),
            data.get("previousBlockhash", ""),
            slot,
        )
        print(f"Executing SQL update, values={update_values}")
        cursor.execute(SQL_UPDATE_BLOCK, update_values)
    else:
        print(f"Block {slot} does not exist, will insert new record")
        print(f"Executing SQL insert, values={block_values}")
        cursor.execute(
            "INSERT INTO blocks (slot, block_height, block_time, blockhash, parent_slot, previous_blockhash) VALUES (?, ?, ?, ?, ?, ?)",
            block_values,
        )
        block_id = cursor.lastrowid
        print(f"Last inserted row ID (cursor.lastrowid): {block_id}")

        if block_id is None or block_id == 0:
            cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
            result = cursor.fetchone()
            if result:
                block_id = result[0]
                print(f"Retrieved block ID for slot {slot} via query: {block_id}")
            else:
                raise ValueError(f"Failed to insert or find block {slot}")

    if cursor.rowcount > 0:
        print(f"Block {slot} operation successful, affected rows={cursor.rowcount}")
    else:
        print(f"Block {slot} unchanged, affected rows={cursor.rowcount}")

    cursor.execute("SELECT slot FROM blocks WHERE id = ?", (block_id,))
    result = cursor.fetchone()
    if result and result[0] != slot:
        raise ValueError(
            f"Critical error: Block ID {block_id} already assigned to another block {result[0]}"
        )

    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    result = cursor.fetchone()
    if result and result[0] != block_id:
        raise ValueError(
            f"Critical error: Block {slot} ID mismatch, expected {block_id}, actual {result[0]}"
        )

    return block_id


def collect_account_pubkeys(data: Dict[str, Any]) -> set:
    all_pubkeys = set()
    if "transactions" not in data or not data["transactions"]:
        return all_pubkeys

    for tx in data["transactions"]:
        transaction = tx.get("transaction", {})
        message = transaction.get("message", {})
        account_keys = message.get("accountKeys", [])
        if account_keys:
            all_pubkeys.update(account_keys)

        instructions = message.get("instructions", [])
        if not instructions:
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
    if not pubkeys:
        return {}

    pubkey_to_id = {}
    for pubkey in pubkeys:
        cursor.execute(SQL_INSERT_ACCOUNT, (pubkey,))
        cursor.execute("SELECT id FROM accounts WHERE pubkey = ?", (pubkey,))
        result = cursor.fetchone()
        if result:
            pubkey_to_id[pubkey] = result[0]
    return pubkey_to_id


def process_transactions(
    cursor: sqlite3.Cursor, data: Dict[str, Any], block_id: int, pubkey_to_id: dict
) -> dict:
    if "transactions" not in data or not data["transactions"]:
        return {}

    tx_id_map = {}
    for tx in data["transactions"]:
        meta = tx.get("meta", {})
        transaction = tx.get("transaction", {})
        if not transaction:
            continue

        message = transaction.get("message", {})
        signatures = transaction.get("signatures", [])
        signature = signatures[0] if signatures else ""
        if not signature:
            continue

        tx_data = (
            block_id,
            signature,
            meta.get("fee", 0),
            meta.get("computeUnitsConsumed", 0),
            json.dumps(meta.get("err")) if meta.get("err") else None,
        )
        cursor.execute(SQL_INSERT_TRANSACTION, tx_data)
        cursor.execute(SQL_SELECT_TRANSACTION_ID, (signature,))
        result = cursor.fetchone()
        if not result:
            continue

        tx_id = result[0]
        tx_key = (block_id, signature)
        tx_id_map[tx_key] = tx_id

        account_keys = message.get("accountKeys", [])
        header = message.get("header", {})
        num_required_signatures = header.get("numRequiredSignatures", 0)
        num_readonly_signed = header.get("numReadonlySignedAccounts", 0)
        num_readonly_unsigned = header.get("numReadonlyUnsignedAccounts", 0)

        for idx, pubkey in enumerate(account_keys):
            is_signer = idx < num_required_signatures
            is_writable = (is_signer and idx >= num_readonly_signed) or (
                not is_signer and idx < len(account_keys) - num_readonly_unsigned
            )
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
    if "transactions" not in data or not data["transactions"]:
        return

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
        for idx, instr in enumerate(message.get("instructions", [])):
            program_idx = instr.get("programIdIndex")
            if program_idx is None or program_idx >= len(account_keys):
                continue

            program_pubkey = account_keys[program_idx]
            if program_pubkey not in pubkey_to_id:
                continue

            program_id = pubkey_to_id[program_pubkey]
            instr_data = encode_instruction_data(instr.get("data", ""))
            cursor.execute(SQL_INSERT_INSTRUCTION, (tx_id, program_id, idx, instr_data))
            instr_id = cursor.lastrowid
            # If insertion was not successful, try to get ID through a query
            if not instr_id:
                cursor.execute(
                    SQL_SELECT_INSTRUCTION_ID, (tx_id, idx, program_id, instr_data)
                )
                result = cursor.fetchone()
                if result:
                    instr_id = result[0]
                else:
                    continue

            for acct_idx, acct_pos in enumerate(instr.get("accounts", [])):
                if acct_pos >= len(account_keys):
                    continue
                account_pubkey = account_keys[acct_pos]
                if account_pubkey not in pubkey_to_id:
                    continue
                account_id = pubkey_to_id[account_pubkey]
                cursor.execute(
                    SQL_INSERT_INSTRUCTION_ACCOUNT, (instr_id, account_id, acct_idx)
                )


def save_to_sqlite(data: Dict[str, Any], db_path: str) -> None:
    slot = data.get("slot")
    print(f"Starting to save block {slot} to database {db_path}")

    ensure_database_exists(db_path)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA isolation_level = IMMEDIATE")
            configure_sqlite_connection(conn)
            cursor = conn.cursor()

            try:
                print(f"Step 1: Inserting block {slot} basic data")
                block_id = insert_block_data(cursor, data)
                print(f"Block {slot} ID is {block_id}")

                print(f"Step 2: Collecting all pubkeys in block {slot}")
                all_pubkeys = collect_account_pubkeys(data)
                print(f"Found {len(all_pubkeys)} unique pubkeys in block {slot}")

                print(f"Step 3: Processing block {slot} account data")
                pubkey_to_id = process_accounts(cursor, all_pubkeys)
                print(f"Successfully processed {len(pubkey_to_id)} accounts")
                if len(all_pubkeys) > 0 and len(pubkey_to_id) == 0:
                    raise ValueError(
                        f"Critical error: Block {slot} account processing failed, no account IDs retrieved"
                    )

                print(f"Step 4: Processing block {slot} transaction data")
                tx_id_map = process_transactions(cursor, data, block_id, pubkey_to_id)
                tx_count = len(data.get("transactions", []))
                print(
                    f"Block {slot} has {tx_count} transactions, successfully processed {len(tx_id_map)}"
                )
                if tx_count > 0 and len(tx_id_map) == 0:
                    print(
                        f"Warning: Block {slot} transaction processing may be incomplete"
                    )

                print(f"Step 5: Processing block {slot} instruction data")
                process_instructions(cursor, data, block_id, tx_id_map, pubkey_to_id)
                print(f"Block {slot} instruction processing completed")

                cursor.execute(
                    "SELECT COUNT(*) FROM transactions WHERE block_id = ?", (block_id,)
                )
                tx_db_count = cursor.fetchone()[0]
                print(
                    f"Transaction count in database for block {slot} (ID={block_id}): {tx_db_count}"
                )

                cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                result = cursor.fetchone()
                if not result or result[0] != block_id:
                    raise ValueError(
                        f"Critical error: Block {slot} ID mismatch, expected {block_id}, actual {result[0] if result else 'None'}"
                    )

                print(f"Block {slot} data successfully saved to database")

            except Exception as e:
                print(f"Error processing block {slot}: {e}")
                raise

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if "FOREIGN KEY constraint failed" in str(e):
            print(
                f"Foreign key constraint error: Possible block ID {block_id} reference issue"
            )
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                    result = cursor.fetchone()
                    if result:
                        print(f"Block {slot} ID in database: {result[0]}")
                    else:
                        print(f"Block {slot} not found in database")
            except Exception as ex:
                print(f"Error querying block ID: {ex}")
        elif "UNIQUE constraint failed" in str(e):
            print(f"Unique constraint error: Possible duplicate data insertion attempt")
        raise


def get_highest_processed_slot(db_path: str) -> int:
    if not os.path.exists(db_path):
        print("Database does not exist, returning starting block number 0")
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
        print(f"Database error: {str(e)}")
        return 0


def query_database(db_path: str, sql_query: str) -> Dict[str, Any]:
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
