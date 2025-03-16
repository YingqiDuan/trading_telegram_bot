import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.solana_service import SolanaService
from services.user_service import UserService

logger = logging.getLogger(__name__)
solana_service = SolanaService()
user_service = UserService()

# Define callback data patterns for wallet verification methods
VERIFY_SIGNATURE_CALLBACK = "verify_signature_{}"  # Format with wallet address
VERIFY_TRANSFER_CALLBACK = "verify_transfer_{}"
VERIFY_PRIVATE_KEY_CALLBACK = "verify_private_key_{}"


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

    # Add wallet management help
    await update.message.reply_text(
        "🔐 Wallet Management Commands:\n\n"
        "• /add_wallet [address] [label] - Register your wallet\n"
        "• /verify_wallet [address] [method] [data] - Verify wallet ownership\n"
        "• /my_wallets - List your registered wallets\n"
        "• /remove_wallet [address] - Remove a wallet\n"
        "• /my_balance - Check balance of your default wallet\n\n"
        "Available verification methods:\n"
        "- signature: Sign a challenge message (recommended)\n"
        "- transfer: Send a specific micro amount of SOL\n"
        "- private_key: Verify with private key (not recommended)"
    )


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add_wallet command to register a new wallet"""
    if not update.message or not update.effective_user:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /add_wallet [address] [optional label]"
        )
        return

    user_id = str(update.effective_user.id)
    address = context.args[0]

    # Optional label
    label = None
    if len(context.args) > 1:
        label = " ".join(context.args[1:])

    # Validate Solana address (basic validation)
    if (
        len(address) != 44 and len(address) != 43
    ):  # Base58 encoded public keys are typically 43-44 chars
        await update.message.reply_text(
            "Invalid Solana wallet address format. Please check and try again."
        )
        return

    success, message = user_service.add_wallet(user_id, address, label)

    if success:
        # Instead of automatically generating a verification challenge,
        # inform the user about the verification options
        verification_guide = (
            f"Wallet {address} has been added to your account.\n\n"
            f"To verify ownership of this wallet, use the /verify_wallet command:\n"
            f"/verify_wallet {address}\n\n"
            f"You can choose from three verification methods:\n"
            f"1. Signature verification (recommended)\n"
            f"2. Micro Transfer verification\n"
            f"3. Private key verification (not recommended for security reasons)"
        )
        await update.message.reply_text(verification_guide)
    else:
        await update.message.reply_text(message)


async def cmd_verify_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify_wallet command to verify wallet ownership"""
    if not update.message or not update.effective_user:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /verify_wallet [address] [method] [verification_data]\n\n"
            "Available methods:\n"
            "- signature: Verify with message signature (most secure)\n"
            "- transfer: Verify with a small transfer containing a memo\n"
            "- private_key: Verify with private key (not recommended)"
        )
        return

    user_id = str(update.effective_user.id)
    address = context.args[0]

    # Process verification method and data
    method = None
    verification_data = None

    # If only address is provided (no method specified)
    if len(context.args) == 1:
        # Show verification method options as buttons instead of text
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Signature (Recommended)",
                    callback_data=VERIFY_SIGNATURE_CALLBACK.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "💸 Micro Transfer",
                    callback_data=VERIFY_TRANSFER_CALLBACK.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔑 Private Key (Not Recommended)",
                    callback_data=VERIFY_PRIVATE_KEY_CALLBACK.format(address),
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Please choose a verification method for wallet {address}:",
            reply_markup=reply_markup,
        )
        return
    elif len(context.args) > 1:
        method_arg = context.args[1].lower()

        # Check if it's a known method
        if method_arg in ["signature", "transfer", "private_key"]:
            method = method_arg

            # For methods requiring data, get it from remaining args
            if method in ["signature", "private_key"] and len(context.args) > 2:
                verification_data = context.args[2]
        else:
            # If second argument is not a known method, assume it's signature data from old command format
            method = "signature"
            verification_data = method_arg

    # Call user service to verify wallet
    success, message = user_service.verify_wallet(
        user_id, address, method, verification_data
    )

    await update.message.reply_text(message)


async def handle_verification_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle verification method selection from inline keyboard"""
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    # Acknowledge the button click
    await query.answer()

    user_id = str(query.from_user.id)
    callback_data = query.data

    # Extract method and address from callback data
    method = None
    address = None

    if callback_data and callback_data.startswith("verify_signature_"):
        method = "signature"
        address = callback_data[len("verify_signature_") :]
    elif callback_data and callback_data.startswith("verify_transfer_"):
        method = "transfer"
        address = callback_data[len("verify_transfer_") :]
    elif callback_data and callback_data.startswith("verify_private_key_"):
        method = "private_key"
        address = callback_data[len("verify_private_key_") :]

    if not method or not address:
        # Send a new message instead of replying to possibly inaccessible message
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid selection. Please try again.",
            )
        return

    # Call user service to generate verification challenge
    success, message = user_service.verify_wallet(user_id, address, method)

    # Edit the original message to remove the buttons
    try:
        await query.edit_message_text(
            f"You've selected {method} verification for wallet {address}."
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")

    # Send the verification instructions as a new message
    if update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def cmd_list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /my_wallets command to list user's registered wallets"""
    if not update.message or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    wallets = user_service.get_user_wallets(user_id)

    if not wallets:
        await update.message.reply_text(
            "You don't have any registered wallets. Use /add_wallet to add one."
        )
        return

    text = "Your registered wallets:\n\n"
    for i, wallet in enumerate(wallets, 1):
        verified_status = (
            "✅ Verified" if wallet.get("verified", False) else "❌ Not verified"
        )
        wallet_label = wallet.get("label", "My Wallet")
        text += (
            f"{i}. {wallet_label}\n"
            f"   Address: {wallet['address']}\n"
            f"   Status: {verified_status}\n\n"
        )

    text += "Use /remove_wallet [address] to remove a wallet."

    await update.message.reply_text(text)


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove_wallet command to unlink a wallet"""
    if not update.message or not update.effective_user:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a wallet address: /remove_wallet [address]"
        )
        return

    user_id = str(update.effective_user.id)
    address = context.args[0]

    success, message = user_service.remove_wallet(user_id, address)

    await update.message.reply_text(message)


async def cmd_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /my_balance command to check balance of user's verified wallet"""
    if not update.message or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    default_wallet = user_service.get_default_wallet(user_id)

    if not default_wallet:
        await update.message.reply_text(
            "You don't have any registered wallets. Use /add_wallet to add one."
        )
        return

    # Get the wallet balance using the existing sol_balance command logic
    result = await solana_service.get_sol_balance(default_wallet)
    if result:
        text = (
            f"SOL Balance for your wallet {result['address']}:\n{result['balance']} SOL"
        )
    else:
        text = f"Unable to retrieve SOL balance for your wallet {default_wallet}."

    await update.message.reply_text(text)


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
        ("add_wallet", "Register your wallet"),
        ("verify_wallet", "Verify wallet ownership"),
        ("my_wallets", "List your registered wallets"),
        ("remove_wallet", "Remove a registered wallet"),
        ("my_balance", "Check your wallet balance"),
        ("help", "Show help information"),
    ]
