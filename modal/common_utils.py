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

        # Add slot field, as it's not included in the RPC response data
        block_data["slot"] = slot
        print(f"Adding slot field to block data: {slot}")

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
    Get the latest block number from Solana mainnet

    Args:
        timeout: RPC request timeout (seconds)

    Returns:
        The latest block number, or None if the request fails
    """
    # Solana mainnet RPC endpoint
    rpc_url = "https://api.mainnet-beta.solana.com"

    # Prepare getSlot RPC request
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSlot",
        "params": [],
    }

    # Send RPC request
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
    # Get slot value
    slot = data["slot"]  # Now we're certain this field exists
    print(f"Inserting block data, slot={slot}, type={type(slot)}")

    block_values = (
        slot,
        data.get("blockHeight", None),
        data.get("blockTime", None),
        data.get("blockhash", ""),
        data.get("parentSlot", None),
        data.get("previousBlockhash", ""),
    )

    # Check if the block already exists
    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    existing_block = cursor.fetchone()

    block_id = None
    if existing_block:
        block_id = existing_block[0]
        print(
            f"Block {slot} already exists, ID={block_id}, will update existing record"
        )

        # Update existing record
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

        # Use direct insert instead of INSERT OR IGNORE to ensure correct rowid
        cursor.execute(
            """
            INSERT INTO blocks 
            (slot, block_height, block_time, blockhash, parent_slot, previous_blockhash)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            block_values,
        )

        # Get last inserted row ID
        block_id = cursor.lastrowid
        print(f"Last inserted row ID (cursor.lastrowid): {block_id}")

        # Verify insertion success
        if block_id is None or block_id == 0:
            cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
            result = cursor.fetchone()
            if result:
                block_id = result[0]
                print(f"Retrieved block ID for slot {slot} via query: {block_id}")
            else:
                # If no record found, it's possible because another transaction inserted the same record
                # Try again to get ID
                cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                result = cursor.fetchone()
                if result:
                    block_id = result[0]
                    print(f"Found block ID {slot} in second attempt: {block_id}")
                else:
                    raise ValueError(f"Failed to insert or find block {slot}")

    # Verify if any rows were modified
    if cursor.rowcount > 0:
        print(f"Block {slot} operation successful, affected rows={cursor.rowcount}")
    else:
        print(f"Block {slot} unchanged, affected rows={cursor.rowcount}")

    # Verify one last time to ensure we have the correct block_id
    if block_id is None:
        cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
        result = cursor.fetchone()
        if result is None:
            raise ValueError(f"Failed to retrieve block ID for slot {slot}")
        block_id = result[0]

    print(f"Final confirmation: Block {slot} ID={block_id}")

    # Additional verification to ensure ID is unique
    cursor.execute("SELECT slot FROM blocks WHERE id = ?", (block_id,))
    result = cursor.fetchone()
    if result and result[0] != slot:
        raise ValueError(
            f"Critical error: Block ID {block_id} already assigned to another block {result[0]}"
        )

    # Verify again to ensure slot-to-ID mapping is correct
    cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
    result = cursor.fetchone()
    if result and result[0] != block_id:
        raise ValueError(
            f"Critical error: Block {slot} ID mismatch, expected {block_id}, actual {result[0]}"
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

    # Insert accounts one by one instead of batch insert
    pubkey_to_id = {}
    for pubkey in pubkeys:
        # Insert account
        cursor.execute(SQL_INSERT_ACCOUNT, (pubkey,))

        # Get account ID
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

    # Process transactions one by one
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

        # Insert transaction data
        tx_data = (
            block_id,
            signature,
            meta.get("fee", 0),
            meta.get("computeUnitsConsumed", 0),
            json.dumps(meta.get("err")) if meta.get("err") else None,
        )
        cursor.execute(SQL_INSERT_TRANSACTION, tx_data)

        # Get transaction ID
        cursor.execute(SQL_SELECT_TRANSACTION_ID, (signature,))
        result = cursor.fetchone()
        if not result:
            continue

        tx_id = result[0]
        tx_key = (block_id, signature)
        tx_id_map[tx_key] = tx_id

        # Process transaction accounts
        account_keys = message.get("accountKeys", [])
        header = message.get("header", {})
        num_required_signatures = header.get("numRequiredSignatures", 0)
        num_readonly_signed = header.get("numReadonlySignedAccounts", 0)
        num_readonly_unsigned = header.get("numReadonlyUnsignedAccounts", 0)

        # Process transaction accounts one by one
        for idx, pubkey in enumerate(account_keys):
            is_signer = idx < num_required_signatures
            is_writable = (is_signer and idx >= num_readonly_signed) or (
                not is_signer and idx < len(account_keys) - num_readonly_unsigned
            )

            # Insert transaction account relationship
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

    # Process transactions one by one
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

        # Process instructions one by one
        for idx, instr in enumerate(message.get("instructions", [])):
            program_idx = instr.get("programIdIndex")
            if program_idx is None or program_idx >= len(account_keys):
                continue

            program_pubkey = account_keys[program_idx]
            if program_pubkey not in pubkey_to_id:
                continue

            program_id = pubkey_to_id[program_pubkey]

            # Convert instruction data to binary format to save space
            instr_data = encode_instruction_data(instr.get("data", ""))

            # Insert instruction data
            cursor.execute(
                SQL_INSERT_INSTRUCTION,
                (
                    tx_id,
                    program_id,
                    program_idx,
                    instr_data,
                ),
            )

            # Get instruction ID
            cursor.execute(SQL_SELECT_INSTRUCTION_ID, (tx_id, program_idx))
            result = cursor.fetchone()
            if not result:
                continue

            instr_id = result[0]

            # Process instruction accounts one by one
            for acct_idx, acct_pos in enumerate(instr.get("accounts", [])):
                if acct_pos >= len(account_keys):
                    continue

                account_pubkey = account_keys[acct_pos]
                if account_pubkey not in pubkey_to_id:
                    continue

                account_id = pubkey_to_id[account_pubkey]

                # Insert instruction account relationship
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
    # Get slot value for logging
    slot = data.get("slot")
    print(f"Starting to save block {slot} to database {db_path}")

    # Ensure database exists
    ensure_database_exists(db_path)

    try:
        # Connect to SQLite database using context manager
        with sqlite3.connect(db_path) as conn:
            # Set stricter transaction isolation level
            conn.execute("PRAGMA isolation_level = IMMEDIATE")

            # Configure SQLite connection
            configure_sqlite_connection(conn)

            # Create cursor (SQLite cursor doesn't support context manager)
            cursor = conn.cursor()

            try:
                # Step 1: Insert block data
                print(f"Step 1: Inserting block {slot} basic data")
                block_id = insert_block_data(cursor, data)
                print(f"Block {slot} ID is {block_id}")

                # Step 2: Collect all pubkeys
                print(f"Step 2: Collecting all pubkeys in block {slot}")
                all_pubkeys = collect_account_pubkeys(data)
                print(f"Found {len(all_pubkeys)} unique pubkeys in block {slot}")

                # Step 3: Process accounts and get pubkey mapping
                print(f"Step 3: Processing block {slot} account data")
                pubkey_to_id = process_accounts(cursor, all_pubkeys)
                print(f"Successfully processed {len(pubkey_to_id)} accounts")

                # Verify account mapping
                if len(all_pubkeys) > 0 and len(pubkey_to_id) == 0:
                    raise ValueError(
                        f"Critical error: Block {slot} account processing failed, no account IDs retrieved"
                    )

                # Step 4: Process transactions and related accounts
                print(f"Step 4: Processing block {slot} transaction data")
                tx_id_map = process_transactions(cursor, data, block_id, pubkey_to_id)
                tx_count = len(data.get("transactions", []))
                print(
                    f"Block {slot} has {tx_count} transactions, successfully processed {len(tx_id_map)}"
                )

                # Verify transaction processing
                if tx_count > 0 and len(tx_id_map) == 0:
                    print(
                        f"Warning: Block {slot} transaction processing may be incomplete"
                    )

                # Step 5: Process instructions and related accounts
                print(f"Step 5: Processing block {slot} instruction data")
                process_instructions(cursor, data, block_id, tx_id_map, pubkey_to_id)
                print(f"Block {slot} instruction processing completed")

                # Final verification
                cursor.execute(
                    "SELECT COUNT(*) FROM transactions WHERE block_id = ?", (block_id,)
                )
                tx_db_count = cursor.fetchone()[0]
                print(
                    f"Transaction count in database for block {slot} (ID={block_id}): {tx_db_count}"
                )

                # Verify block ID consistency
                cursor.execute("SELECT id FROM blocks WHERE slot = ?", (slot,))
                result = cursor.fetchone()
                if not result or result[0] != block_id:
                    raise ValueError(
                        f"Critical error: Block {slot} ID mismatch, expected {block_id}, actual {result[0] if result else 'None'}"
                    )

                # Transaction is automatically committed when the context manager exits
                print(f"Block {slot} data successfully saved to database")

            except Exception as e:
                print(f"Error processing block {slot}: {e}")
                # Here we don't raise an exception, let outer exception handling deal with it
                raise

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        # Provide more detailed error information
        if "FOREIGN KEY constraint failed" in str(e):
            print(
                f"Foreign key constraint error: Possible block ID {block_id} reference issue"
            )
            # Try querying block ID
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
        # Connection and transaction are automatically rolled back when
        # the context manager exits due to an exception
        raise  # Re-raise exception for caller to know about the error


def get_highest_processed_slot(db_path: str) -> int:
    """
    Get the highest block number processed from the database

    Args:
        db_path: Database file path

    Returns:
        The highest block number in the database, or 0 if the database is empty
    """
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
    """
    Execute SQL query and return results

    Args:
        db_path: Database file path
        sql_query: SQL query statement

    Returns:
        Dictionary containing query results
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
