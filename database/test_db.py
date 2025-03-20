import time

DB_PATH = "database/solana_data.db"

from common_utils import (
    get_latest_slot,
    get_highest_processed_slot,
    get_block,
    save_to_sqlite,
)


def main():
    while True:
        # Get the latest block number every 5 seconds
        latest_slot = get_latest_slot()
        if latest_slot is None:
            print("Failed to get latest slot, retrying in 5 seconds...")
            time.sleep(5)
            continue

        # Get the highest processed slot in the database
        highest_slot = get_highest_processed_slot(DB_PATH)
        print(f"Highest slot in database: {highest_slot}, Latest slot: {latest_slot}")

        # If there are new blocks, process them one by one
        if latest_slot > highest_slot:
            for slot in range(highest_slot + 1, latest_slot + 1):
                print(f"Processing slot {slot}")
                block_data = get_block(slot)
                if block_data:
                    try:
                        save_to_sqlite(block_data, DB_PATH)
                        print(f"Slot {slot} has been successfully saved to database")
                    except Exception as e:
                        print(f"Error saving slot {slot}: {e}")
                else:
                    print(f"Unable to get block data for slot {slot}")
                # Wait 0.1 seconds after processing each block
        else:
            print("No new blocks")

        # Check for latest slot every 5 seconds
        time.sleep(2)


if __name__ == "__main__":
    main()
