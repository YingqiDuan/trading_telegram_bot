from telegram import Update
from telegram.ext import ContextTypes
from command.utils import _reply

# HTML formatted help text matching the one in solana_bot.py
HELP_TEXT = (
    "🔍 <b>BLOCKCHAIN QUERIES</b>\n"
    "• /sol_balance - Check SOL balance\n"
    "• /token_info - Get token information\n"
    "• /token_accounts - Get token accounts\n"
    "• /account_details - Get account details\n"
    "• /transaction - Get transaction details\n"
    "• /recent_tx - View recent transactions\n\n"
    "🔐 <b>WALLET MANAGEMENT</b>\n"
    "• /add_wallet - Register and verify your Solana wallet\n"
    "• /my_wallets - List your registered wallets\n"
    "• /remove_wallet - Remove a wallet\n"
    "• /my_balance - Check your default wallet balance\n"
    "• /create_wallet - Generate a new Solana wallet\n"
    "• /send_sol - Send SOL from your wallet to another address\n\n"
    "🔐 <b>PRIVY WALLET MANAGEMENT</b>\n"
    "• /create_privy_wallet - Create a new Privy wallet (ETH or SOL)\n"
    "• /create_privy_solana - Create a new Privy Solana wallet\n"
    "• /privy_wallets - List your Privy wallets\n"
    "• /privy_balance - Check your Privy wallet balance\n"
    "• /privy_send - Send sol from your Privy wallet\n"
    "• /privy_tx_history - View transaction history directly from blockchain\n\n"
    "🌐 <b>NETWORK INFORMATION</b>\n"
    "• /latest_block - Get latest block\n"
    "• /network_status - Check network status\n"
    "• /validators - List validators\n"
    "• /slot - Get current slot\n\n"
    "❓ <b>OTHER COMMANDS</b>\n"
    "• /start - Start the bot\n"
    "• /help - Display this help message\n"
    "• /cancel - Cancel current operation"
)


def get_command_list():
    return [
        ("sol_balance", "Get SOL balance"),
        ("token_info", "Get token information"),
        ("account_details", "Get account details"),
        ("transaction", "Get transaction details"),
        ("recent_tx", "Get recent transactions"),
        ("token_accounts", "Get token accounts"),
        ("validators", "Get top validators"),
        ("latest_block", "Get latest block info"),
        ("network_status", "Get network status"),
        ("slot", "Get current slot"),
        ("add_wallet", "Register and verify your wallet"),
        ("create_wallet", "Generate a new Solana wallet"),
        ("my_wallets", "List your wallets"),
        ("remove_wallet", "Remove a wallet"),
        ("my_balance", "Check your wallet balance"),
        ("send_sol", "Send SOL to another address"),
        # Privy wallet commands
        ("create_privy_wallet", "Create a new Privy wallet"),
        ("create_privy_solana", "Create a new Privy Solana wallet"),
        ("privy_wallets", "List your Privy wallets"),
        ("privy_balance", "Check Privy wallet balance"),
        ("privy_send", "Send sol from Privy wallet"),
        ("privy_tx_history", "View transactions directly from blockchain"),
        ("help", "Show help info"),
        ("cancel", "Cancel current operation"),
    ]
