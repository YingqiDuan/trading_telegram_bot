import requests
import json
import os
import sqlite3
from typing import Dict, Any, Optional, List, Tuple
import base64
import time

from common_utils import (
    get_block,
    save_to_sqlite,
)

if __name__ == "__main__":
    slot_numbers = [327872837]

    # SQLite database file path
    db_path = "database/solana_data.db"
    for slot_number in slot_numbers:
        time.sleep(0.5)
        try:
            # Get block data
            block_data = get_block(slot_number)

            if block_data:
                # Check if block_data has the expected structure
                if "transactions" in block_data:
                    print(
                        f"Retrieved block data with {len(block_data.get('transactions', []))} transactions"
                    )
                else:
                    print("Warning: Block data doesn't contain transaction information")

                # Save to SQLite database
                save_to_sqlite(block_data, db_path)
            else:
                print("Failed to get block data. API returned None.")
        except Exception as e:
            print(f"Error processing block data: {e}")
            import traceback

            traceback.print_exc()
