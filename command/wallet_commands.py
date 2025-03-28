import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.user_service import UserService
from services.solana_rpc_service import SolanaService
from services.user_service_sqlite import _verify_private_key
from command.utils import _reply
from nacl.signing import SigningKey
import base58
from telegram.ext import ConversationHandler

logger = logging.getLogger(__name__)
user_service = UserService()
solana_service = SolanaService()

# Conversation states for send_sol command
SEND_SELECT_SOURCE = 1
SEND_INPUT_DESTINATION = 2
SEND_INPUT_AMOUNT = 3
SEND_CONFIRM = 4
SEND_INPUT_PRIVATE_KEY = 5

# Callback data prefixes
SEND_WALLET_PREFIX = "send_wallet_"
SEND_CONFIRM_YES = "send_confirm_yes"
SEND_CONFIRM_NO = "send_confirm_no"


async def cmd_create_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    # Generate new keypair
    try:
        # Create new random keypair
        signing_key = SigningKey.generate()
        private_key = base58.b58encode(bytes(signing_key)).decode("utf-8")
        public_key = base58.b58encode(bytes(signing_key.verify_key)).decode("utf-8")

        # Create label (default or from args)
        label = None
        if context.args:
            label = context.args[0]

        # Add wallet to user's account and verify it
        success, message = user_service.add_wallet(user_id, public_key, label)
        if not success:
            return await _reply(
                update, f"❌ Failed to add wallet: {message}", context=context
            )

        # Verify the wallet
        verify_success, _ = user_service.verify_wallet(
            user_id, public_key, "private_key", private_key
        )

        # Store the private key
        user_service.set_wallet_private_key(user_id, public_key, private_key)

        await _reply(
            update,
            f"✅ New wallet created!\n\n📋 Address: `{public_key}`\n\n🔑 Private Key: `{private_key}`\n\n⚠️ **SAVE YOUR PRIVATE KEY** - This is the only time it will be shown to you.",
            parse_mode="Markdown",
            context=context,
        )
    except Exception as e:
        logger.error(f"Error creating wallet: {e}")
        await _reply(update, f"❌ Failed to create wallet: {str(e)}", context=context)


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    if not context.args:
        return await _reply(
            update,
            "Usage: /add_wallet [address] [optional label] [private_key]]",
            context=context,
        )

    user_id = str(effective_user.id)
    address = context.args[0]

    # Verify wallet address format
    if len(address) not in (43, 44):
        return await _reply(update, "Invalid wallet address format.", context=context)

    # Check parameter count to determine if label and private key are provided
    if len(context.args) == 1:  # Address only
        label = None
        private_key = None
    elif (
        len(context.args) == 2
    ):  # Address and second parameter (possibly label or private key)
        # Determine if the second parameter is a label or private key
        if len(context.args[1]) >= 32:  # If length ≥32, likely private key
            label = None
            private_key = context.args[1]
        else:  # Otherwise treat as label
            label = context.args[1]
            private_key = None
    else:  # Address, label and private key all provided
        label = context.args[1]
        private_key = context.args[2]

    # If no private key, save current state and request user to input private key
    if not private_key:
        if context.user_data is not None:
            context.user_data["pending"] = "add_wallet"
            context.user_data["add_wallet_address"] = address
            context.user_data["add_wallet_label"] = label

            await _reply(
                update,
                f"Please enter your private key to verify ownership of wallet {address}:",
                context=context,
            )
            return
        return await _reply(
            update,
            "Unable to save session state, please use the complete command: /add_wallet [address] [label] [private_key]",
            context=context,
        )

    # 先检查钱包是否已经存在
    # First check if the wallet already exists
    wallets = user_service.get_user_wallets(user_id)
    wallet_exists = any(w["address"].lower() == address.lower() for w in wallets)

    if wallet_exists:
        return await _reply(
            update,
            f"Wallet {address} already exists. To re-verify, please first remove the wallet using /remove_wallet {address}.",
            context=context,
        )

    # 验证私钥
    # Verify private key
    try:
        # 直接使用_verify_private_key函数验证
        # Directly use _verify_private_key function to verify
        success, verify_message = _verify_private_key(address, private_key)

        if not success:
            return await _reply(
                update,
                f"❌ Private key verification failed: {verify_message}\nPlease check your private key and try again.",
                context=context,
            )

        # Verification successful, add wallet
        add_success, add_message = user_service.add_wallet(user_id, address, label)
        if not add_success:
            return await _reply(
                update, f"❌ Failed to add wallet: {add_message}", context=context
            )

        # 直接使用verify_wallet方法设置验证状态
        # Directly use verify_wallet method to set verification status
        verify_success, _ = user_service.verify_wallet(
            user_id, address, "private_key", private_key
        )
        if not verify_success:
            await _reply(
                update,
                f"⚠️ Warning: Wallet has been added, but marking it as verified failed. You can verify it again later.",
                context=context,
            )
        else:
            # Store the private key
            user_service.set_wallet_private_key(user_id, address, private_key)

        await _reply(
            update,
            f"✅ Private key verification successful, wallet {address} has been added and verified!",
            context=context,
        )
    except Exception as e:
        logger.error(f"Error verifying or adding wallet: {e}")
        await _reply(
            update,
            f"❌ Error occurred during processing: {str(e)}\nPlease try again later.",
            context=context,
        )


async def cmd_list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Make sure we can get the user ID regardless of whether this is a message or callback
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)
    wallets = user_service.get_user_wallets(user_id)
    if not wallets:
        return await _reply(
            update,
            "No registered wallets. Use /add_wallet to add one.",
            context=context,
        )

    text = "Your wallets:\n\n" + "\n".join(
        f"{i+1}. {wallet.get('label', 'My Wallet')}\n   Address: {wallet['address']}\n   Status: {'✅ Verified' if wallet.get('verified') else '❌ Not verified'}"
        for i, wallet in enumerate(wallets)
    )
    text += "\nUse /remove_wallet [address] to remove a wallet."
    await _reply(update, text, context=context)


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    if not context.args:
        return await _reply(update, "Usage: /remove_wallet [address]", context=context)

    user_id = str(effective_user.id)
    address = context.args[0]
    success, message = user_service.remove_wallet(user_id, address)
    await _reply(update, message, context=context)


async def cmd_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)
    default_wallet = user_service.get_default_wallet(user_id)
    if not default_wallet:
        return await _reply(
            update,
            "No registered wallets. Use /add_wallet to add one.",
            context=context,
        )
    result = await solana_service.get_sol_balance(default_wallet)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {default_wallet}."
    )
    await _reply(update, text, context=context)


async def cmd_send_sol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send SOL from one of user's wallets to another address"""
    try:
        effective_user = update.effective_user
        if not effective_user:
            logger.error("No effective user in cmd_send_sol")
            return await _reply(
                update,
                "Error: Could not identify user.",
                context=context,
            )

        user_id = str(effective_user.id)
        logger.info(f"Starting cmd_send_sol for user {user_id}")
        wallets = user_service.get_user_wallets(user_id)

        if not wallets:
            logger.info(f"User {user_id} has no registered wallets")
            return await _reply(
                update,
                "You don't have any registered wallets. Use /add_wallet to add one first.",
                context=context,
            )

        # Check if we're in the middle of a send operation
        if context.user_data and "send_sol_state" in context.user_data:
            state = context.user_data.get("send_sol_state")
            logger.info(f"Continuing send operation in state {state}")

            if state == SEND_INPUT_DESTINATION:
                return await _handle_send_destination(update, context)
            elif state == SEND_INPUT_AMOUNT:
                return await _handle_send_amount(update, context)

        # Start new send operation
        keyboard = []
        wallets_with_keys = []

        # Create buttons for each wallet
        for wallet in wallets:
            address = wallet["address"]
            logger.info(f"Checking wallet {address} for private key")

            # Check if this wallet has a private key stored
            private_key = user_service.get_wallet_private_key(user_id, address)
            if not private_key:
                logger.info(f"No private key found for wallet {address}")
                continue

            wallets_with_keys.append(wallet)
            logger.info(f"Added wallet {address} to selection list")

            label = wallet.get("label", "My Wallet")
            # Get balance for each wallet
            balance_info = await solana_service.get_sol_balance(address)
            balance = balance_info.get("balance", 0)

            display_text = f"{label}: {address[:6]}...{address[-4:]} ({balance} SOL)"
            callback_data = f"{SEND_WALLET_PREFIX}{address}"

            # Truncate callback_data if it's too long
            if len(callback_data) > 64:
                callback_data = f"{SEND_WALLET_PREFIX}{address[:30]}...{address[-30:]}"
                logger.info(f"Truncated callback data to {len(callback_data)} chars")

            logger.info(f"Creating wallet button with callback_data: {callback_data}")
            keyboard.append(
                [InlineKeyboardButton(display_text, callback_data=callback_data)]
            )

        if not wallets_with_keys:
            logger.info(f"User {user_id} has no wallets with private keys")
            return await _reply(
                update,
                "You don't have any wallets with stored private keys. Please use /add_wallet with a private key first.",
                context=context,
            )

        logger.info(f"Found {len(wallets_with_keys)} wallets with private keys")
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="send_cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Clear any previous message if this is from a callback query
        if update.callback_query and update.callback_query.message:
            try:
                await update.callback_query.edit_message_text(
                    "Select a wallet to send SOL from:"
                )
                await update.callback_query.edit_message_reply_markup(
                    reply_markup=reply_markup
                )
                logger.info("Updated existing message with wallet selection")
            except Exception as e:
                logger.error(f"Error updating message: {e}")
                # If we can't edit, send a new message
                if update.callback_query.message.chat:
                    await update.callback_query.message.reply_text(
                        "Select a wallet to send SOL from:",
                        reply_markup=reply_markup,
                    )
                    logger.info("Sent new message with wallet selection")
        else:
            # Normal message flow
            await _reply(
                update,
                "Select a wallet to send SOL from:",
                context=context,
                reply_markup=reply_markup,
            )
            logger.info("Sent wallet selection message")

        # Set state in user_data
        if context.user_data is not None:
            context.user_data["send_sol_state"] = SEND_SELECT_SOURCE
            # Set a flag to mark that we're in a send_sol flow
            context.user_data["in_send_sol_flow"] = True
            logger.info(f"Set state to SEND_SELECT_SOURCE")

        return SEND_SELECT_SOURCE
    except Exception as e:
        logger.error(f"Error in cmd_send_sol: {e}")
        await _reply(
            update,
            f"An error occurred while starting the send operation: {str(e)}",
            context=context,
        )
        return ConversationHandler.END


async def _handle_send_wallet_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle wallet selection callback"""
    query = update.callback_query
    if not query:
        logger.error("No callback query in _handle_send_wallet_selection")
        return

    try:
        logger.info(f"Processing wallet selection. Callback data: {query.data}")
        await query.answer()

        if query.data == "send_cancel":
            logger.info("User cancelled wallet selection")
            # Clean up user data
            if context.user_data:
                if "send_sol_state" in context.user_data:
                    del context.user_data["send_sol_state"]
                if "send_sol_source" in context.user_data:
                    del context.user_data["send_sol_source"]
                if "in_send_sol_flow" in context.user_data:
                    del context.user_data["in_send_sol_flow"]

            await query.edit_message_text("Transaction cancelled.")

            # Try to return to the main menu if possible
            try:
                from telegram_bot.solana_bot import SELECT_OPTION

                if hasattr(
                    context.bot_data.get("bot_instance", None), "send_main_menu"
                ):
                    await context.bot_data["bot_instance"].send_main_menu(
                        update, context
                    )
                    return SELECT_OPTION
            except Exception as e:
                logger.error(f"Error returning to main menu: {e}")

            # Just return to end the conversation if we can't go to main menu
            return ConversationHandler.END

        logger.info(f"Wallet selection callback data: {query.data}")
        if not query.data.startswith(SEND_WALLET_PREFIX):
            logger.error(f"Invalid callback data: {query.data}")
            return

        # Extract wallet address from callback data
        address = query.data[len(SEND_WALLET_PREFIX) :]
        logger.info(f"Extracted address: {address}")

        # Handle truncated addresses
        if "..." in address:
            logger.info("Handling truncated address")
            # Get the full list of user wallets
            user_id = str(update.effective_user.id) if update.effective_user else None
            if not user_id:
                await query.edit_message_text("Error: Could not identify user.")
                return

            wallets = user_service.get_user_wallets(user_id)
            found = False

            # Find the matching wallet by checking if the truncated parts match
            prefix, suffix = address.split("...")
            for wallet in wallets:
                full_address = wallet["address"]
                if full_address.startswith(prefix) and full_address.endswith(suffix):
                    address = full_address
                    found = True
                    logger.info(f"Found matching wallet: {address}")
                    break

            if not found:
                await query.edit_message_text("Error: Could not find selected wallet.")
                return

        # Verify the wallet has a private key
        user_id = str(update.effective_user.id) if update.effective_user else None
        if not user_id:
            await query.edit_message_text("Error: Could not identify user.")
            return

        private_key = user_service.get_wallet_private_key(user_id, address)
        if not private_key:
            await query.edit_message_text(
                "Error: No private key found for this wallet. Please add a private key first."
            )
            return ConversationHandler.END

        # Store selected wallet in user data
        if context.user_data is not None:
            context.user_data["send_sol_source"] = address
            context.user_data["send_sol_state"] = SEND_INPUT_DESTINATION

        # Get balance for display
        balance_info = await solana_service.get_sol_balance(address)
        balance = balance_info.get("balance", 0)

        await query.edit_message_text(
            f"Selected wallet: {address[:8]}...{address[-6:]} (Balance: {balance} SOL)\n\n"
            f"Please enter the destination wallet address:"
        )

        return SEND_INPUT_DESTINATION
    except Exception as e:
        logger.error(f"Error in _handle_send_wallet_selection: {e}")
        try:
            await query.edit_message_text(f"An error occurred: {str(e)}")
        except:
            pass
        return ConversationHandler.END


async def _handle_send_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination address input"""
    try:
        logger.info("Processing destination address input")
        if not update.message or not update.message.text:
            logger.error("No message text in _handle_send_destination")
            return SEND_INPUT_DESTINATION

        destination = update.message.text.strip()
        logger.info(f"Received destination address: {destination}")

        # Validate destination address format
        if len(destination) not in (43, 44):
            logger.warning(f"Invalid address format: {len(destination)} characters")
            await update.message.reply_text(
                "Invalid wallet address format. Please enter a valid Solana address."
            )
            return SEND_INPUT_DESTINATION

        # Store destination in user data
        if context.user_data is not None:
            context.user_data["send_sol_destination"] = destination
            context.user_data["send_sol_state"] = SEND_INPUT_AMOUNT
            logger.info(
                f"Updated state to SEND_INPUT_AMOUNT with destination {destination}"
            )

        # Display source and destination for confirmation
        source = (
            context.user_data.get("send_sol_source", "Unknown")
            if context.user_data
            else "Unknown"
        )
        logger.info(f"Confirming source {source} and destination {destination}")

        await update.message.reply_text(
            f"From: {source[:8]}...{source[-6:]}\n"
            f"To: {destination[:8]}...{destination[-6:]}\n\n"
            f"Please enter the amount of SOL to send:"
        )

        return SEND_INPUT_AMOUNT
    except Exception as e:
        logger.error(f"Error in _handle_send_destination: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")
        return SEND_INPUT_DESTINATION


async def _handle_send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle amount input"""
    try:
        logger.info("Processing amount input")
        if not update.message or not update.message.text:
            logger.error("No message text in _handle_send_amount")
            return SEND_INPUT_AMOUNT

        amount_text = update.message.text.strip()
        logger.info(f"Received amount: {amount_text}")

        # Validate amount
        try:
            amount = float(amount_text)
            if amount <= 0:
                logger.warning(f"Invalid amount: {amount} (must be > 0)")
                await update.message.reply_text("Amount must be greater than 0.")
                return SEND_INPUT_AMOUNT
        except ValueError:
            logger.warning(f"Could not parse amount: {amount_text}")
            await update.message.reply_text("Please enter a valid number.")
            return SEND_INPUT_AMOUNT

        # Check if user has enough balance
        source = (
            context.user_data.get("send_sol_source", "") if context.user_data else ""
        )
        if source:
            logger.info(f"Checking balance for source wallet: {source}")
            balance_info = await solana_service.get_sol_balance(source)
            balance = balance_info.get("balance", 0)
            logger.info(f"Source wallet balance: {balance} SOL")

            if amount > balance:
                logger.warning(
                    f"Insufficient balance: {balance} SOL, tried to send {amount} SOL"
                )
                await update.message.reply_text(
                    f"Insufficient balance. You have {balance} SOL available."
                )
                return SEND_INPUT_AMOUNT

        # Store amount in user data
        if context.user_data is not None:
            context.user_data["send_sol_amount"] = amount
            context.user_data["send_sol_state"] = SEND_CONFIRM
            logger.info(f"Updated state to SEND_CONFIRM with amount {amount}")

        # Display transaction summary for confirmation
        source = (
            context.user_data.get("send_sol_source", "Unknown")
            if context.user_data
            else "Unknown"
        )
        destination = (
            context.user_data.get("send_sol_destination", "Unknown")
            if context.user_data
            else "Unknown"
        )
        logger.info(
            f"Preparing confirmation for transfer {amount} SOL from {source} to {destination}"
        )

        keyboard = [
            [
                InlineKeyboardButton("Confirm", callback_data=SEND_CONFIRM_YES),
                InlineKeyboardButton("Cancel", callback_data=SEND_CONFIRM_NO),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Transaction Summary:\n\n"
            f"From: {source[:8]}...{source[-6:]}\n"
            f"To: {destination[:8]}...{destination[-6:]}\n"
            f"Amount: {amount} SOL\n\n"
            f"Please confirm this transaction:",
            reply_markup=reply_markup,
        )

        return SEND_CONFIRM
    except Exception as e:
        logger.error(f"Error in _handle_send_amount: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")
        return SEND_INPUT_AMOUNT


async def _handle_send_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle transaction confirmation"""
    try:
        logger.info("Processing transaction confirmation")
        query = update.callback_query
        if not query:
            logger.error("No callback query in _handle_send_confirmation")
            return ConversationHandler.END

        await query.answer()
        logger.info(f"Confirmation response: {query.data}")

        if query.data == SEND_CONFIRM_NO:
            logger.info("User cancelled the transaction")
            # Clean up user data
            if context.user_data:
                if "send_sol_state" in context.user_data:
                    del context.user_data["send_sol_state"]
                if "send_sol_source" in context.user_data:
                    del context.user_data["send_sol_source"]
                if "send_sol_destination" in context.user_data:
                    del context.user_data["send_sol_destination"]
                if "send_sol_amount" in context.user_data:
                    del context.user_data["send_sol_amount"]
                if "in_send_sol_flow" in context.user_data:
                    del context.user_data["in_send_sol_flow"]

            await query.edit_message_text("Transaction cancelled.")

            # Try to return to the main menu if possible
            try:
                from telegram_bot.solana_bot import SELECT_OPTION

                if hasattr(
                    context.bot_data.get("bot_instance", None), "send_main_menu"
                ):
                    await context.bot_data["bot_instance"].send_main_menu(
                        update, context
                    )
                    return SELECT_OPTION
            except Exception as e:
                logger.error(f"Error returning to main menu: {e}")

            # Just return to end the conversation if we can't go to main menu
            return ConversationHandler.END

        if query.data == SEND_CONFIRM_YES and context.user_data:
            logger.info("User confirmed the transaction")
            # Get transaction parameters
            source = context.user_data.get("send_sol_source", "")
            destination = context.user_data.get("send_sol_destination", "")
            amount = context.user_data.get("send_sol_amount", 0)

            logger.info(
                f"Preparing to send {amount} SOL from {source} to {destination}"
            )

            # Get the user ID
            user_id = str(update.effective_user.id) if update.effective_user else None
            if not user_id:
                logger.error("Could not identify user ID")
                await query.edit_message_text("Error: Could not identify user.")
                return ConversationHandler.END

            # Retrieve private key from database
            private_key = user_service.get_wallet_private_key(user_id, source)
            logger.info(
                f"Retrieved private key for wallet {source}: {'Found' if private_key else 'Not found'}"
            )

            if not private_key:
                logger.error(f"No private key found for wallet {source}")
                await query.edit_message_text(
                    "❌ Could not find the private key for this wallet. "
                    "Please use /add_wallet to re-verify this wallet with its private key."
                )

                # Clean up user data
                if "send_sol_state" in context.user_data:
                    del context.user_data["send_sol_state"]
                if "send_sol_source" in context.user_data:
                    del context.user_data["send_sol_source"]
                if "send_sol_destination" in context.user_data:
                    del context.user_data["send_sol_destination"]
                if "send_sol_amount" in context.user_data:
                    del context.user_data["send_sol_amount"]
                if "in_send_sol_flow" in context.user_data:
                    del context.user_data["in_send_sol_flow"]

                return ConversationHandler.END

            # Show processing message
            await query.edit_message_text("Processing transaction...")

            # Execute the transaction
            logger.info(
                f"Executing transaction: {amount} SOL from {source} to {destination}"
            )
            result = await solana_service.send_sol(
                source, destination, amount, private_key
            )
            logger.info(f"Transaction result: {result}")

            # Clean up user data
            if "send_sol_state" in context.user_data:
                del context.user_data["send_sol_state"]
            if "send_sol_source" in context.user_data:
                del context.user_data["send_sol_source"]
            if "send_sol_destination" in context.user_data:
                del context.user_data["send_sol_destination"]
            if "send_sol_amount" in context.user_data:
                del context.user_data["send_sol_amount"]
            if "in_send_sol_flow" in context.user_data:
                del context.user_data["in_send_sol_flow"]

            # Display result
            if result.get("success", False):
                logger.info(
                    f"Transaction successful: {result.get('signature', 'Unknown')}"
                )
                success_text = (
                    f"✅ Transaction successful!\n\n"
                    f"Amount: {amount} SOL\n"
                    f"From: {source[:8]}...{source[-6:]}\n"
                    f"To: {destination[:8]}...{destination[-6:]}\n"
                    f"Transaction signature: {result.get('signature', 'Unknown')}"
                )
                await query.edit_message_text(success_text)
            else:
                error_msg = result.get("error", "Unknown error")
                details = result.get("details", "")
                logger.error(f"Transaction failed: {error_msg} - Details: {details}")

                # Fix empty or incomplete error messages
                if not error_msg or error_msg == "Send failed: ":
                    if "429" in details or "Too Many Requests" in details:
                        error_msg = "Rate limit exceeded (HTTP 429)"
                    elif details:
                        error_msg = details
                    else:
                        error_msg = "Transaction rejected by the network"
                    logger.info(f"Fixed empty error message to: {error_msg}")

                # Create a user-friendly error message based on the error type
                if (
                    "rate limit" in error_msg.lower()
                    or "429" in error_msg
                    or "Too Many Requests" in error_msg
                ):
                    # 检查是否尝试了两个节点
                    if (
                        "after trying both RPC nodes" in error_msg
                        or "both RPC nodes" in details
                    ):
                        error_text = (
                            f"❌ Transaction failed: Rate limit exceeded\n\n"
                            f"The Solana RPC nodes are currently experiencing heavy traffic. "
                            f"System tried both primary and backup nodes but both are rate limited.\n\n"
                            f"Please wait a minute and try again later."
                        )
                    else:
                        error_text = (
                            f"❌ Transaction failed: Rate limit exceeded\n\n"
                            f"The Solana network is busy. Please wait a few seconds and try again.\n"
                            f"The system will automatically try using alternative RPC nodes on your next attempt."
                        )
                elif (
                    "insufficient funds" in error_msg.lower()
                    or "insufficient funds" in details.lower()
                    or "insufficient funds for rent" in error_msg.lower()
                    or "insufficient funds for rent" in details.lower()
                ):
                    error_text = (
                        f"❌ Transaction failed: Insufficient funds\n\n"
                        f"Your wallet does not have enough SOL to complete this transaction.\n"
                        f"Remember to account for transaction fees and required minimum balance (rent)."
                    )
                elif (
                    "signature verification" in error_msg.lower()
                    or "signature verification" in details.lower()
                ):
                    error_text = (
                        f"❌ Transaction failed: Signature verification failed\n\n"
                        f"The stored private key may not match this wallet address.\n"
                        f"Please use /add_wallet to re-verify your wallet with the correct private key."
                    )
                else:
                    # 检查是否有其他常见错误
                    if "rent" in error_msg.lower() or "rent" in details.lower():
                        error_text = (
                            f"❌ Transaction failed: Insufficient funds for rent\n\n"
                            f"Solana requires accounts to maintain a minimum balance for rent.\n"
                            f"After this transaction, your account would fall below the required minimum.\n"
                            f"Try sending a smaller amount or add more SOL to your wallet."
                        )
                    else:
                        error_text = (
                            f"❌ Transaction failed: {error_msg}\n\n"
                            f"Please try again or check your wallet details."
                        )

                await query.edit_message_text(error_text)

            # 修改主菜单显示逻辑，不替换交易消息
            try:
                from telegram_bot.solana_bot import SELECT_OPTION

                if hasattr(
                    context.bot_data.get("bot_instance", None), "send_main_menu"
                ):
                    # 发送新消息显示主菜单，而不是编辑现有消息
                    bot_instance = context.bot_data["bot_instance"]
                    await bot_instance.send_main_menu_as_new_message(update, context)
                    return SELECT_OPTION
            except Exception as e:
                logger.error(f"Error showing main menu: {e}")

            return ConversationHandler.END

        # If we get here, something went wrong with the callback data
        logger.warning(f"Unexpected callback data: {query.data}")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in _handle_send_confirmation: {e}")
        try:
            await query.edit_message_text(f"An error occurred: {str(e)}")
        except:
            pass
        return ConversationHandler.END
