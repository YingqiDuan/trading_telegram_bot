import logging
from typing import Optional, Coroutine, Any, Union
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.solana_service import SolanaService
from services.user_service import UserService

logger = logging.getLogger(__name__)
solana_service = SolanaService()
user_service = UserService()

# Callback data patterns for wallet verification methods
VERIFY_SIGNATURE_CB = "verify_signature_{}"
VERIFY_TRANSFER_CB = "verify_transfer_{}"
VERIFY_PRIVATE_KEY_CB = "verify_private_key_{}"


async def _reply(update: Update, text: str) -> Optional[Any]:
    """Send a reply message if update.message exists, otherwise return None."""
    if update.message:
        return await update.message.reply_text(text)
    return None


async def cmd_sol_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /sol_balance [wallet address]")
    address = context.args[0]
    result = await solana_service.get_sol_balance(address)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {address}."
    )
    await _reply(update, text)


async def cmd_token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /token_info [token address]")
    address = context.args[0]
    result = await solana_service.get_token_info(address)
    if result:
        text = f"Token Information:\nAddress: {result['address']}\nSupply: {result['supply']}\nDecimals: {result['decimals']}"
    else:
        text = f"Unable to retrieve token info for {address}."
    await _reply(update, text)


async def cmd_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /account_details [account address]")
    address = context.args[0]
    result = await solana_service.get_account_details(address)
    if result:
        text = (
            f"Account Details:\nAddress: {result['address']}\nLamports: {result['lamports']}\n"
            f"Owner: {result['owner']}\nExecutable: {result['executable']}\nRent Epoch: {result['rent_epoch']}"
        )
    else:
        text = f"Unable to retrieve account details for {address}."
    await _reply(update, text)


async def cmd_latest_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    result = await solana_service.get_latest_block()
    text = (
        f"Latest Block:\nBlockhash: {result['blockhash']}\nLast Valid Block Height: {result['last_valid_block_height']}"
        if result
        else "Unable to retrieve latest block information."
    )
    await _reply(update, text)


async def cmd_network_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    result = await solana_service.get_network_status()
    text = (
        f"Network Status:\nSolana Core: {result['solana_core']}\nFeature Set: {result['feature_set']}"
        if result
        else "Unable to retrieve network status."
    )
    await _reply(update, text)


async def cmd_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /transaction [signature]")
    signature = context.args[0]
    result = await solana_service.get_transaction_details(signature)
    if result:
        status = "✅ Successful" if result.get("success", False) else "❌ Failed"
        text = (
            f"Transaction Details:\nSignature: {result['signature']}\nStatus: {status}\n"
            f"Slot: {result.get('slot', 'Unknown')}\nBlock Time: {result.get('block_time', 'Unknown')}"
        )
    else:
        text = f"Unable to retrieve transaction details for {signature}."
    await _reply(update, text)


async def cmd_recent_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /recent_tx [wallet address] [limit]")
    address = context.args[0]
    limit = 5
    if len(context.args) > 1:
        try:
            limit = max(1, min(int(context.args[1]), 10))
        except ValueError:
            pass
    transactions = await solana_service.get_recent_transactions(address, limit)
    if transactions:
        text = f"Recent Transactions for {address}:\n\n"
        for i, tx in enumerate(transactions, 1):
            status = "✅" if tx.get("success", False) else "❌"
            text += f"{i}. {status} {tx.get('signature', 'Unknown')[:12]}...\n   Slot: {tx.get('slot', 'Unknown')}\n"
    else:
        text = f"No recent transactions found for {address}."
    await _reply(update, text)


async def cmd_validators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    limit = 5
    if context.args:
        try:
            limit = max(1, min(int(context.args[0]), 10))
        except ValueError:
            pass
    validators = await solana_service.get_validators(limit)
    if validators:
        text = f"Top {len(validators)} Active Validators:\n\n"
        for i, v in enumerate(validators, 1):
            text += (
                f"{i}. Node: {v.get('node_pubkey', 'Unknown')[:8]}...\n"
                f"   Vote: {v.get('vote_pubkey', 'Unknown')[:8]}...\n"
                f"   Stake: {v.get('activated_stake', 'Unknown')} SOL\n"
                f"   Commission: {v.get('commission', 'Unknown')}%\n\n"
            )
    else:
        text = "Unable to retrieve validator information."
    await _reply(update, text)


async def cmd_token_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /token_accounts [wallet address]")
    address = context.args[0]
    accounts = await solana_service.get_token_accounts(address)
    if accounts:
        text = f"Token Accounts for {address}:\n\n" + "\n".join(
            f"{i+1}. {acc.get('pubkey', 'Unknown')[:10]}...{' - ' + acc.get('data') if acc.get('data') else ''}"
            for i, acc in enumerate(accounts)
        )
    else:
        text = f"No token accounts found for {address}."
    await _reply(update, text)


async def cmd_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    slot = await solana_service.get_slot()
    text = (
        f"Current Solana Slot: {slot}"
        if slot > 0
        else "Unable to retrieve current slot."
    )
    await _reply(update, text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    help_text = (
        "Commands:\n"
        "/sol_balance [address]\n/token_info [address]\n/account_details [address]\n"
        "/transaction [signature]\n/recent_tx [address] [limit]\n/token_accounts [address]\n"
        "/validators [limit]\n/latest_block\n/network_status\n/slot\n"
        "/add_wallet [address] [label]\n/verify_wallet [address] [method] [data]\n"
        "/my_wallets\n/remove_wallet [address]\n/my_balance\n/help"
    )
    await _reply(update, help_text)


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(update, "Usage: /add_wallet [address] [optional label]")
    user_id = str(update.effective_user.id)
    address = context.args[0]
    label = " ".join(context.args[1:]) if len(context.args) > 1 else None
    if len(address) not in (43, 44):
        return await _reply(update, "Invalid wallet address format.")
    success, message = user_service.add_wallet(user_id, address, label)
    if success:
        guide = (
            f"Wallet {address} added.\nTo verify, use /verify_wallet {address}\n"
            "Verification methods:\n1. Signature (Recommended)\n2. Micro Transfer\n3. Private key (Not recommended)"
        )
        await _reply(update, guide)
    else:
        await _reply(update, message)


async def cmd_verify_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(
            update,
            "Usage: /verify_wallet [address] [method] [data]\nMethods: signature, transfer, private_key",
        )
    user_id = str(update.effective_user.id)
    address = context.args[0]
    if len(context.args) == 1:
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Signature (Recommended)",
                    callback_data=VERIFY_SIGNATURE_CB.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "💸 Micro Transfer",
                    callback_data=VERIFY_TRANSFER_CB.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔑 Private Key (Not Recommended)",
                    callback_data=VERIFY_PRIVATE_KEY_CB.format(address),
                )
            ],
        ]
        return await update.message.reply_text(
            f"Choose verification method for {address}:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    method = (
        context.args[1].lower()
        if context.args[1].lower() in ["signature", "transfer", "private_key"]
        else "signature"
    )
    data = context.args[2] if len(context.args) > 2 else None
    success, message = user_service.verify_wallet(user_id, address, method, data)
    await _reply(update, message)


async def handle_verification_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    method = None

    if not data:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Invalid callback data."
            )
        return

    if data.startswith("verify_signature_"):
        method = "signature"
        address = data[len("verify_signature_") :]
    elif data.startswith("verify_transfer_"):
        method = "transfer"
        address = data[len("verify_transfer_") :]
    elif data.startswith("verify_private_key_"):
        method = "private_key"
        address = data[len("verify_private_key_") :]
    else:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Invalid selection."
            )
        return

    success, message = user_service.verify_wallet(user_id, address, method)
    try:
        await query.edit_message_text(f"Selected {method} verification for {address}.")
    except Exception as e:
        logger.error(f"Edit message error: {e}")

    if update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def cmd_list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = str(update.effective_user.id)
    wallets = user_service.get_user_wallets(user_id)
    if not wallets:
        return await _reply(
            update, "No registered wallets. Use /add_wallet to add one."
        )
    text = "Your wallets:\n\n" + "\n".join(
        f"{i+1}. {wallet.get('label','My Wallet')}\n   Address: {wallet['address']}\n   Status: {'✅ Verified' if wallet.get('verified') else '❌ Not verified'}"
        for i, wallet in enumerate(wallets)
    )
    text += "\nUse /remove_wallet [address] to remove a wallet."
    await _reply(update, text)


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(update, "Usage: /remove_wallet [address]")
    user_id = str(update.effective_user.id)
    address = context.args[0]
    success, message = user_service.remove_wallet(user_id, address)
    await _reply(update, message)


async def cmd_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = str(update.effective_user.id)
    default_wallet = user_service.get_default_wallet(user_id)
    if not default_wallet:
        return await _reply(
            update, "No registered wallets. Use /add_wallet to add one."
        )
    result = await solana_service.get_sol_balance(default_wallet)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {default_wallet}."
    )
    await _reply(update, text)


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
