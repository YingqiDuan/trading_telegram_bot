import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.solana_service import SolanaService

logger = logging.getLogger(__name__)
solana_service = SolanaService()


async def cmd_sol_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sol_balance command"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /sol_balance [address]"
        )
        return

    address = context.args[0]
    result = await solana_service.get_sol_balance(address)
    if result:
        text = f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
    else:
        text = f"Unable to retrieve SOL balance for address {address}."

    await update.message.reply_text(text)


async def cmd_token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /token_info command"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a token address: /token_info [address]"
        )
        return

    address = context.args[0]
    result = await solana_service.get_token_info(address)
    if result:
        text = (
            f"Token Information:\n"
            f"Address: {result['address']}\n"
            f"Supply: {result['supply']}\n"
            f"Decimals: {result['decimals']}"
        )
    else:
        text = f"Unable to retrieve token information for {address}."

    await update.message.reply_text(text)


async def cmd_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /account_details command"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide an account address: /account_details [address]"
        )
        return

    address = context.args[0]
    result = await solana_service.get_account_details(address)
    if result:
        text = (
            f"Account Details:\n"
            f"Address: {result['address']}\n"
            f"Lamports: {result['lamports']}\n"
            f"Owner: {result['owner']}\n"
            f"Executable: {result['executable']}\n"
            f"Rent Epoch: {result['rent_epoch']}"
        )
    else:
        text = f"Unable to retrieve account details for {address}."

    await update.message.reply_text(text)


async def cmd_latest_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /latest_block command"""
    if not update.message:
        return

    result = await solana_service.get_latest_block()
    if result:
        text = (
            f"Latest Block:\n"
            f"Blockhash: {result['blockhash']}\n"
            f"Last Valid Block Height: {result['last_valid_block_height']}"
        )
    else:
        text = "Unable to retrieve latest block information."

    await update.message.reply_text(text)


async def cmd_network_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /network_status command"""
    if not update.message:
        return

    result = await solana_service.get_network_status()
    if result:
        text = (
            f"Solana Network Status:\n"
            f"Solana Core: {result['solana_core']}\n"
            f"Feature Set: {result['feature_set']}"
        )
    else:
        text = "Unable to retrieve Solana network status."

    await update.message.reply_text(text)


async def cmd_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /transaction command to get details of a transaction by signature"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a transaction signature: /transaction [signature]"
        )
        return

    signature = context.args[0]
    result = await solana_service.get_transaction_details(signature)
    if result:
        status = "✅ Successful" if result.get("success", False) else "❌ Failed"
        text = (
            f"Transaction Details:\n"
            f"Signature: {result['signature']}\n"
            f"Status: {status}\n"
            f"Slot: {result.get('slot', 'Unknown')}\n"
            f"Block Time: {result.get('block_time', 'Unknown')}"
        )
    else:
        text = f"Unable to retrieve transaction details for signature {signature}."

    await update.message.reply_text(text)


async def cmd_recent_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recent_tx command to get recent transactions for a wallet"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /recent_tx [address] [limit]"
        )
        return

    address = context.args[0]
    limit = 5  # default
    if len(context.args) > 1:
        try:
            limit = int(context.args[1])
            if limit < 1:
                limit = 1
            elif limit > 10:
                limit = 10  # Cap at 10 to prevent large responses
        except ValueError:
            pass

    transactions = await solana_service.get_recent_transactions(address, limit)
    if transactions:
        text = f"Recent Transactions for {address}:\n\n"
        for i, tx in enumerate(transactions, 1):
            status = "✅" if tx.get("success", False) else "❌"
            text += (
                f"{i}. {status} {tx.get('signature', 'Unknown')[:12]}...\n"
                f"   Slot: {tx.get('slot', 'Unknown')}\n"
            )
    else:
        text = f"No recent transactions found for {address}."

    await update.message.reply_text(text)


async def cmd_validators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /validators command to get active validators"""
    if not update.message:
        return

    limit = 5  # default
    if context.args and len(context.args) > 0:
        try:
            limit = int(context.args[0])
            if limit < 1:
                limit = 1
            elif limit > 10:
                limit = 10  # Cap at 10 to prevent large responses
        except ValueError:
            pass

    validators = await solana_service.get_validators(limit)
    if validators:
        text = f"Top {len(validators)} Active Validators:\n\n"
        for i, validator in enumerate(validators, 1):
            text += (
                f"{i}. Node: {validator.get('node_pubkey', 'Unknown')[:8]}...\n"
                f"   Vote Account: {validator.get('vote_pubkey', 'Unknown')[:8]}...\n"
                f"   Stake: {validator.get('activated_stake', 'Unknown')} SOL\n"
                f"   Commission: {validator.get('commission', 'Unknown')}%\n\n"
            )
    else:
        text = "Unable to retrieve validator information."

    await update.message.reply_text(text)


async def cmd_token_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /token_accounts command to get token accounts for a wallet"""
    if not update.message:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /token_accounts [address]"
        )
        return

    address = context.args[0]
    accounts = await solana_service.get_token_accounts(address)
    if accounts:
        text = f"Token Accounts for {address}:\n\n"
        for i, account in enumerate(accounts, 1):
            text += f"{i}. Account: {account.get('pubkey', 'Unknown')[:10]}...\n"
            # Add more details if available
            if "data" in account:
                text += f"   Data: {account['data']}\n"
    else:
        text = f"No token accounts found for {address}."

    await update.message.reply_text(text)


async def cmd_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /slot command to get current slot"""
    if not update.message:
        return

    slot = await solana_service.get_slot()
    if slot > 0:
        text = f"Current Solana Slot: {slot}"
    else:
        text = "Unable to retrieve current slot information."

    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    if not update.message:
        return

    await update.message.reply_text(
        "You can interact with me in two ways:\n\n"
        "1️⃣ Use natural language, for example:\n"
        "• 'What's the balance of wallet address 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV?'\n"
        "• 'Tell me about the latest Solana block'\n"
        "• 'Show me information about token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'\n\n"
        "2️⃣ Use direct commands:\n"
        "• /sol_balance [wallet address] - Get SOL balance\n"
        "• /token_info [token address] - Get token information\n"
        "• /account_details [account address] - Get account details\n"
        "• /transaction [signature] - Get transaction details\n"
        "• /recent_tx [address] [limit] - Get recent transactions\n"
        "• /token_accounts [address] - Get token accounts\n"
        "• /validators [limit] - Get top validators\n"
        "• /latest_block - Get latest block information\n"
        "• /network_status - Get Solana network status\n"
        "• /slot - Get current slot number\n"
        "• /help - Show this help message"
    )


def get_command_list():
    """Return command list and descriptions for Telegram command menu"""
    return [
        ("sol_balance", "Get SOL balance"),
        ("token_info", "Get token information"),
        ("account_details", "Get account details"),
        ("transaction", "Get transaction details"),
        ("recent_tx", "Get recent transactions"),
        ("token_accounts", "Get token accounts"),
        ("validators", "Get top validators"),
        ("latest_block", "Get latest block information"),
        ("network_status", "Get Solana network status"),
        ("slot", "Get current slot number"),
        ("help", "Show help information"),
    ]
