from common_utils import query_database

sql_query = "SELECT COUNT(*) FROM blocks;"

if __name__ == "__main__":
    result = query_database(
        "database/solana_data.db",
        sql_query,
    )
    print(result)
