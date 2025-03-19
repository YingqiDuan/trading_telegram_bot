import time

# 数据库文件路径，根据需要修改
DB_PATH = "solana_data.db"

from common_utils import (
    get_latest_slot,
    get_highest_processed_slot,
    get_block,
    save_to_sqlite,
)


def main():
    while True:
        # 每5秒获取一次最新区块号
        latest_slot = get_latest_slot()
        if latest_slot is None:
            print("获取最新区块号失败，等待5秒后重试...")
            time.sleep(5)
            continue

        # 获取数据库中已处理的最高 slot
        highest_slot = get_highest_processed_slot(DB_PATH)
        print(f"数据库中最高slot: {highest_slot}，最新slot: {latest_slot}")

        # 如果有新区块，逐个处理
        if latest_slot > highest_slot:
            for slot in range(highest_slot + 1, latest_slot + 1):
                print(f"开始处理slot {slot}")
                block_data = get_block(slot)
                if block_data:
                    try:
                        save_to_sqlite(block_data, DB_PATH)
                        print(f"slot {slot} 已成功保存到数据库")
                    except Exception as e:
                        print(f"保存slot {slot}时发生错误: {e}")
                else:
                    print(f"无法获取slot {slot} 的区块数据")
                # 每处理一个区块等待0.2秒
                time.sleep(0.2)
        else:
            print("暂无新区块")

        # 每5秒执行一次最新slot检查
        time.sleep(5)


if __name__ == "__main__":
    main()
