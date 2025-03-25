TELEGRAM_BOT_TOKEN = "8087619840:AAGxmxJqn00vnt0uw_2JJFWtsiSKqq_I-no"
SOLANA_RPC_URL = "https://solana-mainnet.g.alchemy.com/v2/D7uf6FR6CE3ZJsl8cjux1wofeTUpy4O_"  # Solana mainnet RPC URL
SOLANA_BACKUP_RPC_URL = (
    "https://api.mainnet-beta.solana.com"  # Public RPC endpoint as backup
)
OPEN_AI_API_KEY = "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"

# Rate limiting configuration
RATE_LIMIT_ENABLED = True
RATE_LIMIT_MAX_CALLS = 30  # Maximum number of commands per time window
RATE_LIMIT_WINDOW_SECONDS = 60  # Time window in seconds
RATE_LIMIT_SPECIAL_COMMANDS = {
    "sol_balance": 15,  # Max 15 calls per minute
    "token_info": 15,
    "account_details": 15,
    "transaction": 15,
    "recent_tx": 10,  # More resource-intensive, so lower limit
    "validators": 5,  # More resource-intensive
}

# User wallet management configuration
USER_WALLET_DB_PATH = "user_wallets.db"  # SQLite database for user wallet data
WALLET_VERIFICATION_EXPIRY_SECONDS = (
    15 * 60  # How long a verification request is valid (15 min)
)
SOLANA_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Constants for message formatting
MAX_VALIDATORS_DISPLAY = 10  # Maximum number of validators to display
MAX_TRANSACTIONS_DISPLAY = 10  # Maximum number of transactions to display
DEFAULT_TRANSACTIONS_DISPLAY = 5  # Default number of transactions to display

# modal
VOLUME_DIR = "/data"
DB_FILENAME = "solana_data.db"
DB_PATH = f"{VOLUME_DIR}/{DB_FILENAME}"
