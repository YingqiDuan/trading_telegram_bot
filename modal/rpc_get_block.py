import requests
import json
import os
import sqlite3
from typing import Dict, Any, Optional, List, Tuple
import base64

# 导入所有共用函数
from common_utils import (
    get_block,
    save_to_sqlite,
)

# 如果有其他特定于此模块的函数，可以在这里定义

if __name__ == "__main__":
    # Specify a slot number to fetch
    slot_number = 327704426  # Example slot number, adjust as needed

    # SQLite database file path
    db_path = "modal/solana_data.db"

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
