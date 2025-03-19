import sqlite3
import os
import sys
import importlib.util
from pathlib import Path

# Import common functions
from common_utils import configure_sqlite_connection


def create_database(db_path: str) -> None:
    """
    Create SQLite database schema if it doesn't exist

    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Connect to database with context manager
    with sqlite3.connect(db_path) as conn:
        # Configure connection
        configure_sqlite_connection(conn, enable_transaction=True)

        cursor = conn.cursor()

        try:
            # Create blocks table - stores block metadata
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                slot INTEGER NOT NULL UNIQUE,
                block_height INTEGER,
                block_time INTEGER,
                blockhash TEXT NOT NULL UNIQUE,
                parent_slot INTEGER,
                previous_blockhash TEXT
            )
            """
            )

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_slot ON blocks(slot)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_blocks_block_time ON blocks(block_time)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_blocks_blockhash ON blocks(blockhash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_blocks_parent_slot ON blocks(parent_slot)"
            )

            # Create accounts table - stores all pubkeys to avoid duplication
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                pubkey TEXT NOT NULL UNIQUE
            )
            """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounts_pubkey ON accounts(pubkey)"
            )

            # Create transactions table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                block_id INTEGER NOT NULL,
                signature TEXT NOT NULL UNIQUE,
                fee INTEGER,
                compute_units_consumed INTEGER DEFAULT 0,
                error_message TEXT,
                FOREIGN KEY (block_id) REFERENCES blocks(id) ON DELETE CASCADE
            )
            """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_block_id ON transactions(block_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_signature ON transactions(signature)"
            )

            # Create transaction_accounts table - stores account involvement in transactions
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS transaction_accounts (
                transaction_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                is_signer INTEGER DEFAULT 0,
                is_writable INTEGER DEFAULT 0,
                PRIMARY KEY (transaction_id, account_id, position),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tx_accounts_account_id ON transaction_accounts(account_id)"
            )

            # Create instructions table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS instructions (
                id INTEGER PRIMARY KEY,
                transaction_id INTEGER NOT NULL,
                program_id_account_id INTEGER NOT NULL,
                program_index INTEGER,
                data BLOB,  
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (program_id_account_id) REFERENCES accounts(id)
            )
            """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_instructions_transaction_id ON instructions(transaction_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_instructions_program_id ON instructions(program_id_account_id)"
            )

            # Create instruction_accounts table - stores account involvement in instructions
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS instruction_accounts (
                instruction_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (instruction_id, account_id, position),
                FOREIGN KEY (instruction_id) REFERENCES instructions(id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_instr_accounts_account_id ON instruction_accounts(account_id)"
            )

            # Commit all changes
            conn.commit()
            print(f"Database schema created at {db_path}")

        except sqlite3.Error as e:
            # Roll back in case of error
            conn.rollback()
            print(f"Error creating database schema: {e}")


if __name__ == "__main__":
    db_path = "modal/solana_data.db"
    print(f"Creating database at {db_path}")
    create_database(db_path)
    print("Database creation completed")
