from telegram import Update
from telegram.ext import ContextTypes
from bot.command_handlers.utils import _reply


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    help_text = (
        "Commands:\n"
        "/sol_balance [address]\n"
        "/token_info [address]\n"
        "/account_details [address]\n"
        "/transaction [signature]\n"
        "/recent_tx [address] [limit]\n"
        "/token_accounts [address]\n"
        "/validators [limit]\n"
        "/latest_block\n"
        "/network_status\n"
        "/slot\n"
        "/add_wallet [address] [label]\n"
        "/verify_wallet [address] [method] [data]\n"
        "/my_wallets\n"
        "/remove_wallet [address]\n"
        "/my_balance\n"
        "/help"
    )
    await _reply(update, help_text)


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
        ("add_wallet", "Register your wallet"),
        ("verify_wallet", "Verify wallet ownership"),
        ("my_wallets", "List your wallets"),
        ("remove_wallet", "Remove a wallet"),
        ("my_balance", "Check your wallet balance"),
        ("help", "Show help info"),
    ]
