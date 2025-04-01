import logging  # error tracking and debugging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.privy_wallet_service import PrivyWalletService
from services.solana_rpc_service import SolanaService
from command.utils import _reply  # sending replies

logger = logging.getLogger(__name__)
privy_service = PrivyWalletService()
solana_service = SolanaService()

# 用于按钮回调的数据前缀标识符
PRIVY_SEND_WALLET_PREFIX = "privy_send_wallet_"
PRIVY_SEND_CONFIRM_YES = "privy_send_confirm_yes"
PRIVY_SEND_CONFIRM_NO = "privy_send_confirm_no"

# 发送资金会话的四个状态，用于实现多步骤对话流程
PRIVY_SEND_SELECT_SOURCE = 1
PRIVY_SEND_INPUT_DESTINATION = 2
PRIVY_SEND_INPUT_AMOUNT = 3
PRIVY_SEND_CONFIRM = 4


# 创建钱包命令
async def cmd_create_privy_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new Privy Solana wallet for the user."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    # Get label from arguments if provided
    label = None
    if context.args and len(context.args) >= 1:
        label = context.args[0]

    try:
        wallet_data = privy_service.create_wallet(
            chain_type="solana", linked_user_id=user_id
        )

        if not wallet_data or "address" not in wallet_data:
            return await _reply(
                update, f"❌ Failed to create Solana wallet", context=context
            )

        wallet_id = wallet_data.get("id", "Unknown")
        address = wallet_data.get("address", "Unknown")

        await _reply(
            update,
            f"✅ New Privy Solana wallet created!\n\n"
            f"📋 Address: `{address}`\n\n"
            f"🔐 This wallet is securely managed by Privy and doesn't expose a private key.\n"
            f"You can manage it through commands like /privy_balance and /privy_send.",
            parse_mode="Markdown",
            context=context,
        )
    except Exception as e:
        logger.error(f"Error creating Privy Solana wallet: {e}")
        await _reply(
            update, f"❌ Failed to create Solana wallet: {str(e)}", context=context
        )


async def cmd_privy_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all Privy wallets for the user."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    try:
        wallets_response = privy_service.list_wallets(linked_user_id=user_id)
        privy_wallets = wallets_response.get("data", [])

        if not privy_wallets:
            return await _reply(
                update,
                "You don't have any Privy wallets yet. Use /create_privy_wallet to create one.",
                context=context,
            )

        response = "🔐 Your Privy Wallets:\n\n"

        for wallet in privy_wallets:
            chain_type = wallet.get("chain_type", "solana").capitalize()
            address = wallet.get("address", "Unknown")
            label = f"Privy Solana Wallet ({wallet.get('id', '')[:6]})"

            response += f"{label}:\n"
            response += f"📋 `{address}`\n\n"

        await _reply(update, response, parse_mode="Markdown", context=context)
    except Exception as e:
        logger.error(f"Error listing Privy wallets: {e}")
        await _reply(update, f"❌ Error retrieving wallets: {str(e)}", context=context)


async def cmd_privy_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check the balance of a Privy wallet."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    try:
        wallets_response = privy_service.list_wallets(linked_user_id=user_id)
        privy_wallets = wallets_response.get("data", [])

        if not privy_wallets:
            return await _reply(
                update,
                "You don't have any Privy wallets yet. Use /create_privy_wallet to create one.",
                context=context,
            )

        # 如果未指定地址，获取所有钱包余额
        if not context.args:
            response = "🏦 Privy Wallet Balances:\n\n"

            for wallet in privy_wallets:
                wallet_id = wallet.get("id")
                address = wallet.get("address")
                label = (
                    f"Privy Solana Wallet ({wallet_id[:6] if wallet_id else 'Unknown'})"
                )

                try:
                    # Use Solana RPC call to get balance instead of Privy service
                    balance_data = await solana_service.get_sol_balance(address)

                    if balance_data:
                        balance_sol = balance_data.get("balance", 0)
                        symbol = "SOL"
                        formatted_balance = f"{balance_sol:.6f} {symbol}"

                        response += f"{label}:\n"
                        response += f"📋 `{address}`\n"
                        response += f"💰 Balance: {formatted_balance}\n\n"
                    else:
                        response += f"{label}:\n"
                        response += f"📋 `{address}`\n"
                        response += "❌ Failed to retrieve balance\n\n"
                except Exception as e:
                    logger.error(
                        f"Error getting balance for wallet address {address}: {e}"
                    )
                    response += f"{label}:\n"
                    response += f"📋 `{address}`\n"
                    response += "❌ Failed to retrieve balance\n\n"

            await _reply(update, response, parse_mode="Markdown", context=context)
        else:
            # Check balance for specific address
            address = context.args[0]

            # Find the wallet with the specified address
            wallet = next(
                (w for w in privy_wallets if w["address"].lower() == address.lower()),
                None,
            )

            if not wallet:
                return await _reply(
                    update,
                    f"Address {address} is not a Privy wallet registered to your account.",
                    context=context,
                )

            wallet_id = wallet.get("id")

            try:
                # Use Solana RPC call to get balance instead of Privy service
                balance_data = await solana_service.get_sol_balance(address)

                if not balance_data:
                    return await _reply(
                        update, f"❌ Failed to retrieve balance", context=context
                    )

                balance_sol = balance_data.get("balance", 0)
                symbol = "SOL"
                formatted_balance = f"{balance_sol:.6f} {symbol}"

                label = (
                    f"Privy Solana Wallet ({wallet_id[:6] if wallet_id else 'Unknown'})"
                )

                response = f"🏦 Wallet Balance:\n\n"
                response += f"{label}:\n"
                response += f"📋 `{address}`\n"
                response += f"💰 Balance: {formatted_balance}"

                await _reply(update, response, parse_mode="Markdown", context=context)
            except Exception as e:
                logger.error(f"Error getting balance for wallet address {address}: {e}")
                await _reply(
                    update, f"❌ Error retrieving balance: {str(e)}", context=context
                )
    except Exception as e:
        logger.error(f"Error checking Privy wallet balance: {e}")
        await _reply(
            update, f"❌ Error retrieving wallet information: {str(e)}", context=context
        )


async def cmd_privy_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation to send sol from a Privy wallet."""
    logger.info("Entering cmd_privy_send")

    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    # Set the flow flag
    if context.user_data is not None:
        # Clean up any existing state first
        context.user_data.pop("privy_send_state", None)
        context.user_data.pop("privy_send_from_address", None)
        context.user_data.pop("privy_send_to_address", None)
        context.user_data.pop("privy_send_amount", None)
        context.user_data.pop("privy_send_wallet_id", None)

        # Set the flow flag
        context.user_data["in_privy_send_flow"] = True

    logger.info(f"Initial user context: {context.user_data}")

    try:
        wallets_response = privy_service.list_wallets(linked_user_id=user_id)
        privy_wallets = wallets_response.get("data", [])

        if not privy_wallets:
            return await _reply(
                update,
                "You don't have any Privy wallets yet. Use /create_privy_wallet to create one.",
                context=context,
            )

        # If we have all parameters, process the transaction directly
        if context.args and len(context.args) >= 3:
            source_address = context.args[0]
            destination_address = context.args[1]
            amount = context.args[2]

            # Optional token address
            token_address = None
            if len(context.args) >= 4:
                token_address = context.args[3]

            # Verify source is a Privy wallet
            wallet = next(
                (
                    w
                    for w in privy_wallets
                    if w["address"].lower() == source_address.lower()
                ),
                None,
            )

            if not wallet:
                return await _reply(
                    update,
                    f"Source address {source_address} is not a Privy wallet registered to your account.",
                    context=context,
                )

            wallet_id = wallet.get("id")

            # Convert amount to lamports if needed
            if "." in amount:
                try:
                    amount_sol = float(amount)
                    amount_lamports = str(int(amount_sol * 1e9))
                except (ValueError, TypeError):
                    return await _reply(
                        update,
                        "❌ Invalid amount format. Please provide a valid number.",
                        context=context,
                    )
            else:
                amount_lamports = amount

            data = {"to_address": destination_address, "amount": amount_lamports}
            if token_address:
                data["token_address"] = token_address

            try:
                # 使用专门的send_solana_transaction方法发送交易
                tx_data = privy_service.send_solana_transaction(
                    wallet_id=wallet_id,
                    to_address=destination_address,
                    amount=amount,
                    token_address=token_address if token_address else None,
                )

                if not tx_data:
                    return await _reply(
                        update, f"❌ Transaction failed", context=context
                    )

                # 从返回的数据中获取交易哈希
                tx_hash = tx_data.get("data", {}).get("hash", "Unknown")
                explorer_url = f"https://explorer.solana.com/tx/{tx_hash}"
                # 显示金额为SOL单位
                amount_display = f"{float(amount)} SOL"

                response = f"✅ Transaction Successful!\n\n"
                response += f"From: `{source_address}`\n"
                response += f"To: `{destination_address}`\n"
                response += f"Amount: {amount_display}\n"
                if token_address:
                    response += f"Token: `{token_address}`\n"
                response += f"TX Hash: `{tx_hash}`\n"
                response += f"\n[View on explorer]({explorer_url})"

                await _reply(update, response, parse_mode="Markdown", context=context)
                return
            except Exception as e:
                logger.error(f"Error sending transaction: {e}")
                return await _reply(
                    update, f"❌ Transaction failed: {str(e)}", context=context
                )

        # Otherwise start the interactive conversation
        keyboard = []

        for wallet in privy_wallets:
            wallet_id = wallet.get("id")
            address = wallet.get("address", "")
            label = f"Privy Solana Wallet ({wallet_id[:6]})"

            # Get balance
            try:
                # Use Solana RPC call to get balance instead of Privy service
                balance_data = await solana_service.get_sol_balance(address)

                balance_display = "Unknown"
                if balance_data:
                    balance_sol = balance_data.get("balance", 0)
                    symbol = "SOL"
                    balance_display = f"{balance_sol:.6f} {symbol}"
            except Exception:
                balance_display = "Unknown"

            wallet_text = f"{label}: {balance_display}"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        wallet_text,
                        callback_data=f"{PRIVY_SEND_WALLET_PREFIX}{address}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await _reply(
            update,
            "Select a wallet to send from:",
            reply_markup=reply_markup,
            context=context,
        )

        # Save conversation state
        if context.user_data is not None:
            context.user_data["privy_send_state"] = PRIVY_SEND_SELECT_SOURCE

        return PRIVY_SEND_SELECT_SOURCE
    except Exception as e:
        logger.error(f"Error initiating Privy send: {e}")
        await _reply(
            update, f"❌ Error starting transaction: {str(e)}", context=context
        )


async def handle_privy_wallet_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle wallet selection for sending funds."""
    query = update.callback_query
    logger.info(f"Privy wallet selection callback received: {query.data}")
    logger.info(f"User context data: {context.user_data}")
    logger.info(
        f"Current conversation state: {context.user_data.get('privy_send_state') if context.user_data else 'None'}"
    )
    await query.answer()

    user_id = str(update.effective_user.id)

    # Extract the wallet address from the callback data
    if not query.data.startswith(PRIVY_SEND_WALLET_PREFIX):
        logger.error(f"Invalid callback data: {query.data}")
        await query.edit_message_text("Invalid selection. Please try again.")
        return

    from_address = query.data[len(PRIVY_SEND_WALLET_PREFIX) :]
    logger.info(f"Selected wallet address: {from_address}")

    # Verify this is a valid Privy wallet
    try:
        wallets_response = privy_service.list_wallets(linked_user_id=user_id)
        privy_wallets = wallets_response.get("data", [])
        wallet = next(
            (w for w in privy_wallets if w["address"].lower() == from_address.lower()),
            None,
        )

        if not wallet:
            logger.error(f"Could not find wallet with address: {from_address}")
            await query.edit_message_text(
                f"Error: Could not find Privy wallet with address {from_address}"
            )
            return

        # Save the selected wallet
        if context.user_data is not None:
            # Always set the in_privy_send_flow flag, in case we got here directly
            context.user_data["in_privy_send_flow"] = True
            context.user_data["privy_send_from_address"] = from_address
            context.user_data["privy_send_wallet_id"] = wallet.get("id")
            # Always set the privy_send_state to ensure correct flow continuation
            context.user_data["privy_send_state"] = PRIVY_SEND_INPUT_DESTINATION

        wallet_id = wallet.get("id", "")
        label = f"Privy Solana Wallet ({wallet_id[:6]})"

        await query.edit_message_text(
            f"Selected wallet: {label} ({from_address})\n\n"
            f"Please enter the destination address:"
        )

        logger.info(f"Updated user context: {context.user_data}")
        # Return the correct next state
        return PRIVY_SEND_INPUT_DESTINATION
    except Exception as e:
        logger.error(f"Error validating wallet selection: {e}")
        await query.edit_message_text(
            f"Error: Could not validate wallet selection. Please try again."
        )
        return


async def handle_privy_send_destination(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle destination address input."""
    logger.info(f"Handling destination address input: {update.message.text}")
    logger.info(f"User context: {context.user_data}")

    user_id = str(update.effective_user.id)
    destination = update.message.text.strip()

    # Basic validation of the destination address
    if not destination or len(destination) < 20:
        logger.warning(f"Invalid destination address: {destination}")
        await _reply(
            update,
            "Invalid destination address. Please enter a valid address:",
            context=context,
        )
        return PRIVY_SEND_INPUT_DESTINATION

    # Save the destination
    if context.user_data is not None:
        context.user_data["privy_send_to_address"] = destination
        logger.info(f"Saved destination address: {destination}")

    # Ask for amount
    await _reply(
        update,
        f"Please enter the amount of SOL to send to {destination}:",
        context=context,
    )

    # Update conversation state
    if context.user_data is not None:
        context.user_data["privy_send_state"] = PRIVY_SEND_INPUT_AMOUNT
        logger.info(f"Updated privy_send_state to {PRIVY_SEND_INPUT_AMOUNT}")

    return PRIVY_SEND_INPUT_AMOUNT


async def handle_privy_send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle amount input."""
    user_id = str(update.effective_user.id)
    amount_text = update.message.text.strip()

    # Validate amount
    try:
        amount = float(amount_text)
        if amount <= 0:
            await _reply(
                update,
                "Amount must be greater than 0. Please enter a valid amount:",
                context=context,
            )
            return PRIVY_SEND_INPUT_AMOUNT
    except ValueError:
        await _reply(
            update, "Invalid amount format. Please enter a number:", context=context
        )
        return PRIVY_SEND_INPUT_AMOUNT

    # Save the amount
    if context.user_data is not None:
        context.user_data["privy_send_amount"] = amount_text

    # Get transaction details for confirmation
    from_address = (
        context.user_data.get("privy_send_from_address") if context.user_data else None
    )
    to_address = (
        context.user_data.get("privy_send_to_address") if context.user_data else None
    )

    if not from_address or not to_address:
        await _reply(
            update,
            "⚠️ Session data lost. Please restart with /privy_send.",
            context=context,
        )
        return

    # Create confirmation message and buttons
    confirmation_message = f"⚠️ Please confirm the transaction:\n\n"
    confirmation_message += f"From: `{from_address}`\n"
    confirmation_message += f"To: `{to_address}`\n"
    confirmation_message += f"Amount: {amount} SOL\n\n"
    confirmation_message += "Proceed with this transaction?"

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=PRIVY_SEND_CONFIRM_YES),
            InlineKeyboardButton("❌ Cancel", callback_data=PRIVY_SEND_CONFIRM_NO),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await _reply(
        update,
        confirmation_message,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        context=context,
    )

    # Update conversation state
    if context.user_data is not None:
        context.user_data["privy_send_state"] = PRIVY_SEND_CONFIRM

    return PRIVY_SEND_CONFIRM


async def handle_privy_send_confirmation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle transaction confirmation."""
    query = update.callback_query
    logger.info(f"Privy send confirmation callback received: {query.data}")
    logger.info(f"User context: {context.user_data}")
    await query.answer()

    user_id = str(update.effective_user.id)

    # Check if user confirmed or cancelled
    if query.data == PRIVY_SEND_CONFIRM_NO:
        logger.info("User cancelled the transaction")
        await query.edit_message_text("Transaction cancelled.")
        # Clean up privy_send flow flag
        if context.user_data:
            context.user_data.pop("in_privy_send_flow", None)
            logger.info("Privy send flow flag cleared")
        return

    if query.data != PRIVY_SEND_CONFIRM_YES:
        logger.error(f"Invalid confirmation data: {query.data}")
        await query.edit_message_text("Invalid selection. Transaction cancelled.")
        # Clean up privy_send flow flag
        if context.user_data:
            context.user_data.pop("in_privy_send_flow", None)
        return

    # Get transaction details
    if not context.user_data:
        logger.error("User context data is missing")
        await query.edit_message_text(
            "⚠️ Session data lost. Please restart with /privy_send."
        )
        return

    from_address = context.user_data.get("privy_send_from_address")
    to_address = context.user_data.get("privy_send_to_address")
    amount_text = context.user_data.get("privy_send_amount")
    wallet_id = context.user_data.get("privy_send_wallet_id")

    logger.info(
        f"Transaction details - From: {from_address}, To: {to_address}, Amount: {amount_text}, Wallet ID: {wallet_id}"
    )

    if not from_address or not to_address or not amount_text or not wallet_id:
        logger.error("Missing transaction details in user context")
        await query.edit_message_text(
            "⚠️ Session data lost. Please restart with /privy_send."
        )
        # Clean up privy_send flow flag
        context.user_data.pop("in_privy_send_flow", None)
        return

    # Convert amount to float
    try:
        amount = float(amount_text)
        logger.info(f"Converted amount to float: {amount}")
    except ValueError:
        logger.error(f"Invalid amount format: {amount_text}")
        await query.edit_message_text(
            "❌ Invalid amount format. Please restart with /privy_send."
        )
        # Clean up privy_send flow flag
        context.user_data.pop("in_privy_send_flow", None)
        return

    if amount <= 0:
        logger.error(f"Invalid amount (must be > 0): {amount}")
        await query.edit_message_text(
            "❌ Amount must be greater than 0. Please restart with /privy_send."
        )
        # Clean up privy_send flow flag
        context.user_data.pop("in_privy_send_flow", None)
        return

    # Convert SOL to lamports
    amount_lamports = str(int(amount * 1e9))
    logger.info(f"Amount in lamports: {amount_lamports}")

    try:
        logger.info(f"Sending transaction request to Privy API")
        # 使用专门的send_solana_transaction方法发送交易
        tx_data = privy_service.send_solana_transaction(
            wallet_id=wallet_id,
            to_address=to_address,
            amount=amount_text,  # 直接传递浮点数字符串，函数内会转换
        )

        if not tx_data:
            logger.error("Empty response from Privy API")
            await query.edit_message_text("❌ Transaction failed")
            # Clean up privy_send flow flag
            context.user_data.pop("in_privy_send_flow", None)
            return

        logger.info(f"Transaction successful. Response data: {tx_data}")
        # 从返回的数据中获取交易哈希
        tx_hash = tx_data.get("data", {}).get("hash", "Unknown")
        explorer_url = f"https://explorer.solana.com/tx/{tx_hash}"

        # Format success message
        response = f"✅ Transaction Successful!\n\n"
        response += f"From: `{from_address}`\n"
        response += f"To: `{to_address}`\n"
        response += f"Amount: {amount} SOL\n"
        response += f"TX Hash: `{tx_hash}`\n"
        response += f"\n[View on explorer]({explorer_url})"

        await query.edit_message_text(response, parse_mode="Markdown")

        # Clean up privy_send flow flag
        context.user_data.pop("in_privy_send_flow", None)
        logger.info("Transaction completed and privy_send flow flag cleared")
    except Exception as e:
        logger.error(f"Error sending Solana transaction: {e}")
        await query.edit_message_text(f"❌ Error processing transaction: {str(e)}")
        # Clean up privy_send flow flag
        context.user_data.pop("in_privy_send_flow", None)
        return


async def cmd_privy_tx_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get transaction history for a Privy wallet."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    try:
        # Check if address is provided
        if not context.args:
            return await _reply(
                update,
                "Usage: /privy_tx_history [wallet_address] [optional: limit]",
                context=context,
            )

        address = context.args[0]

        # Check if limit is provided
        limit = 5  # Default limit
        if len(context.args) > 1:
            try:
                limit = int(context.args[1])
                if limit < 1:
                    limit = 1
                elif limit > 20:
                    limit = 20
            except ValueError:
                pass

        # Verify this is a valid Privy wallet
        wallets_response = privy_service.list_wallets(linked_user_id=user_id)
        privy_wallets = wallets_response.get("data", [])
        wallet = next(
            (w for w in privy_wallets if w["address"].lower() == address.lower()), None
        )

        if not wallet:
            return await _reply(
                update,
                f"Address {address} is not a Privy wallet registered to your account.",
                context=context,
            )

        wallet_id = wallet.get("id")

        # Get transaction history using Solana RPC
        await _reply(
            update,
            f"⏳ Fetching transaction history...",
            context=context,
        )

        transactions = await solana_service.get_recent_transactions(address, limit)

        if not transactions:
            return await _reply(
                update,
                f"No transaction history found for this wallet.",
                context=context,
            )

        label = f"Privy Solana Wallet ({wallet_id[:6]})"

        response = f"📜 Transaction History for {label}:\n"
        response += f"📋 `{address}`\n\n"

        for i, tx in enumerate(transactions, 1):
            tx_signature = tx.get("signature", "Unknown")
            tx_status = "✅ Successful" if tx.get("success", False) else "❌ Failed"

            # Format timestamps
            block_time = tx.get("block_time", 0)
            time_str = "Unknown"
            if block_time:
                try:
                    from datetime import datetime

                    time_str = datetime.fromtimestamp(int(block_time)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    time_str = str(block_time)

            # Fetch more transaction details if needed
            # Note: We don't fetch full details for each transaction to avoid rate limiting
            # Only get essential information from the signature list

            response += f"{i}. Signature: `{tx_signature[:12]}...`\n"
            response += f"   Status: {tx_status}\n"
            response += f"   Slot: {tx.get('slot', 'Unknown')}\n"
            response += f"   Time: {time_str}\n"
            response += f"   [View on Solana Explorer](https://explorer.solana.com/tx/{tx_signature})\n\n"

        # Add a note about the data source
        response += f"ℹ️ _Transaction data provided directly from Solana blockchain_"

        await _reply(update, response, parse_mode="Markdown", context=context)
    except Exception as e:
        logger.error(f"Error getting transaction history: {e}")
        await _reply(
            update,
            f"❌ Error retrieving transaction history: {str(e)}",
            context=context,
        )
