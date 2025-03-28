import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.privy_user_integration import PrivyUserIntegration
from command.utils import _reply

logger = logging.getLogger(__name__)
privy_service = PrivyUserIntegration()

# Callback data prefixes
PRIVY_SEND_WALLET_PREFIX = "privy_send_wallet_"
PRIVY_SEND_CONFIRM_YES = "privy_send_confirm_yes"
PRIVY_SEND_CONFIRM_NO = "privy_send_confirm_no"

# Conversation states for send_privy command
PRIVY_SEND_SELECT_SOURCE = 1
PRIVY_SEND_INPUT_DESTINATION = 2
PRIVY_SEND_INPUT_AMOUNT = 3
PRIVY_SEND_CONFIRM = 4


async def cmd_create_privy_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new Privy wallet for the user."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    # Get the chain type from arguments (default to ethereum)
    chain_type = "ethereum"
    label = None

    if context.args:
        if len(context.args) >= 1:
            if context.args[0].lower() in ["ethereum", "solana"]:
                chain_type = context.args[0].lower()
            else:
                label = context.args[0]

        if len(context.args) >= 2:
            label = context.args[1]

    try:
        success, message, wallet_data = privy_service.create_user_wallet(
            user_id, chain_type, label
        )

        if not success or not wallet_data:
            return await _reply(
                update,
                f"❌ Failed to create {chain_type} wallet: {message}",
                context=context,
            )

        wallet_id = wallet_data.get("id", "Unknown")
        address = wallet_data.get("address", "Unknown")

        await _reply(
            update,
            f"✅ New Privy {chain_type.capitalize()} wallet created and verified!\n\n"
            f"📋 Address: `{address}`\n\n"
            f"🔐 This wallet is securely managed by Privy and doesn't expose a private key.\n"
            f"You can manage it through commands like /privy_balance and /privy_send.",
            parse_mode="Markdown",
            context=context,
        )
    except Exception as e:
        logger.error(f"Error creating Privy wallet: {e}")
        await _reply(update, f"❌ Failed to create wallet: {str(e)}", context=context)


async def cmd_create_privy_solana_wallet(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
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
        success, message, wallet_data = privy_service.create_solana_wallet(
            user_id, label
        )

        if not success or not wallet_data:
            return await _reply(
                update, f"❌ Failed to create Solana wallet: {message}", context=context
            )

        wallet_id = wallet_data.get("id", "Unknown")
        address = wallet_data.get("address", "Unknown")

        await _reply(
            update,
            f"✅ New Privy Solana wallet created and verified!\n\n"
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
        privy_wallets = privy_service.get_user_privy_wallets(user_id)

        if not privy_wallets:
            return await _reply(
                update,
                "You don't have any Privy wallets yet. Use /create_privy_wallet to create one.",
                context=context,
            )

        response = "🔐 Your Privy Wallets:\n\n"

        for wallet in privy_wallets:
            chain_type = wallet.get("chain_type", "unknown").capitalize()
            label = wallet.get("label", "Privy Wallet")
            address = wallet.get("address", "Unknown")
            verification = (
                "✅ Verified" if wallet.get("is_verified", False) else "❓ Unverified"
            )

            response += f"{label} ({chain_type}):\n"
            response += f"📋 `{address}`\n"
            response += f"Status: {verification}\n\n"

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
        privy_wallets = privy_service.get_user_privy_wallets(user_id)

        if not privy_wallets:
            return await _reply(
                update,
                "You don't have any Privy wallets yet. Use /create_privy_wallet to create one.",
                context=context,
            )

        # If no address specified, get all wallet balances
        if not context.args:
            response = "🏦 Privy Wallet Balances:\n\n"

            for wallet in privy_wallets:
                address = wallet.get("address")
                label = wallet.get("label", "Privy Wallet")
                chain_type = wallet.get("chain_type", "unknown").capitalize()

                success, _, balance_data = privy_service.get_wallet_balance(
                    user_id, address
                )

                if success and balance_data:
                    balance = balance_data.get("amount", "0")
                    symbol = balance_data.get("symbol", "Unknown")

                    # Format the balance based on chain type
                    if wallet.get("chain_type") == "ethereum":
                        # Convert wei to ETH (divide by 10^18)
                        try:
                            balance_eth = float(balance) / 1e18
                            formatted_balance = f"{balance_eth:.6f} {symbol}"
                        except (ValueError, TypeError):
                            formatted_balance = f"{balance} {symbol}"
                    elif wallet.get("chain_type") == "solana":
                        # Convert lamports to SOL (divide by 10^9)
                        try:
                            balance_sol = float(balance) / 1e9
                            formatted_balance = f"{balance_sol:.6f} {symbol}"
                        except (ValueError, TypeError):
                            formatted_balance = f"{balance} {symbol}"
                    else:
                        formatted_balance = f"{balance} {symbol}"

                    response += f"{label} ({chain_type}):\n"
                    response += f"📋 `{address}`\n"
                    response += f"💰 Balance: {formatted_balance}\n\n"
                else:
                    response += f"{label} ({chain_type}):\n"
                    response += f"📋 `{address}`\n"
                    response += "❌ Failed to retrieve balance\n\n"

            await _reply(update, response, parse_mode="Markdown", context=context)
        else:
            # Check balance for specific address
            address = context.args[0]

            # Verify address is a Privy wallet
            wallet_exists = any(
                w["address"].lower() == address.lower() for w in privy_wallets
            )

            if not wallet_exists:
                return await _reply(
                    update,
                    f"Address {address} is not a Privy wallet registered to your account.",
                    context=context,
                )

            success, message, balance_data = privy_service.get_wallet_balance(
                user_id, address
            )

            if not success or not balance_data:
                return await _reply(
                    update, f"❌ Failed to retrieve balance: {message}", context=context
                )

            balance = balance_data.get("amount", "0")
            symbol = balance_data.get("symbol", "Unknown")

            # Get wallet details to determine chain type
            wallet = next(
                (w for w in privy_wallets if w["address"].lower() == address.lower()),
                None,
            )

            if wallet and wallet.get("chain_type") == "ethereum":
                # Convert wei to ETH (divide by 10^18)
                try:
                    balance_eth = float(balance) / 1e18
                    formatted_balance = f"{balance_eth:.6f} {symbol}"
                except (ValueError, TypeError):
                    formatted_balance = f"{balance} {symbol}"
            elif wallet and wallet.get("chain_type") == "solana":
                # Convert lamports to SOL (divide by 10^9)
                try:
                    balance_sol = float(balance) / 1e9
                    formatted_balance = f"{balance_sol:.6f} {symbol}"
                except (ValueError, TypeError):
                    formatted_balance = f"{balance} {symbol}"
            else:
                formatted_balance = f"{balance} {symbol}"

            label = wallet.get("label", "Privy Wallet") if wallet else "Privy Wallet"
            chain_type = (
                wallet.get("chain_type", "unknown").capitalize()
                if wallet
                else "Unknown"
            )

            response = f"🏦 Wallet Balance:\n\n"
            response += f"{label} ({chain_type}):\n"
            response += f"📋 `{address}`\n"
            response += f"💰 Balance: {formatted_balance}"

            await _reply(update, response, parse_mode="Markdown", context=context)
    except Exception as e:
        logger.error(f"Error checking Privy wallet balance: {e}")
        await _reply(update, f"❌ Error retrieving balance: {str(e)}", context=context)


async def cmd_privy_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation to send funds from a Privy wallet."""
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    try:
        privy_wallets = privy_service.get_user_privy_wallets(user_id)

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

            # Process based on chain type
            if wallet.get("chain_type") == "ethereum":
                # Convert amount to wei if needed (check if it's already in wei format)
                if "." in amount:
                    try:
                        amount_eth = float(amount)
                        amount_wei = str(int(amount_eth * 1e18))
                    except (ValueError, TypeError):
                        return await _reply(
                            update,
                            "❌ Invalid amount format. Please provide a valid number.",
                            context=context,
                        )
                else:
                    amount_wei = amount

                success, message, tx_data = privy_service.send_transaction(
                    user_id=user_id,
                    from_address=source_address,
                    to_address=destination_address,
                    amount=amount_wei,
                    token_address=token_address,
                )
            elif wallet.get("chain_type") == "solana":
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

                success, message, tx_data = privy_service.send_solana_transaction(
                    user_id=user_id,
                    from_address=source_address,
                    to_address=destination_address,
                    amount=amount_lamports,
                    token_address=token_address,
                )
            else:
                return await _reply(
                    update,
                    f"❌ Unsupported chain type: {wallet.get('chain_type')}",
                    context=context,
                )

            if not success:
                return await _reply(
                    update, f"❌ Transaction failed: {message}", context=context
                )

            tx_hash = tx_data.get("hash") if tx_data else "Unknown"
            chain_type = wallet.get("chain_type", "unknown").capitalize()

            if chain_type.lower() == "ethereum":
                explorer_url = f"https://etherscan.io/tx/{tx_hash}"
                amount_display = f"{float(amount) if '.' in amount else float(amount_wei) / 1e18} ETH"
            elif chain_type.lower() == "solana":
                explorer_url = f"https://explorer.solana.com/tx/{tx_hash}"
                amount_display = f"{float(amount) if '.' in amount else float(amount_lamports) / 1e9} SOL"
            else:
                explorer_url = ""
                amount_display = amount

            response = f"✅ Transaction Successful!\n\n"
            response += f"From: `{source_address}`\n"
            response += f"To: `{destination_address}`\n"
            response += f"Amount: {amount_display}\n"
            if token_address:
                response += f"Token: `{token_address}`\n"
            response += f"TX Hash: `{tx_hash}`\n"

            if explorer_url:
                response += f"\n[View on explorer]({explorer_url})"

            await _reply(update, response, parse_mode="Markdown", context=context)
            return

        # Otherwise start the interactive conversation
        keyboard = []

        for wallet in privy_wallets:
            address = wallet.get("address", "")
            label = wallet.get("label", "Privy Wallet")
            chain_type = wallet.get("chain_type", "unknown").capitalize()

            # Get balance
            success, _, balance_data = privy_service.get_wallet_balance(
                user_id, address
            )

            balance_display = "Unknown"
            if success and balance_data:
                balance = balance_data.get("amount", "0")
                symbol = balance_data.get("symbol", "")

                if wallet.get("chain_type") == "ethereum":
                    try:
                        balance_eth = float(balance) / 1e18
                        balance_display = f"{balance_eth:.6f} {symbol}"
                    except (ValueError, TypeError):
                        balance_display = f"{balance} {symbol}"
                elif wallet.get("chain_type") == "solana":
                    try:
                        balance_sol = float(balance) / 1e9
                        balance_display = f"{balance_sol:.6f} {symbol}"
                    except (ValueError, TypeError):
                        balance_display = f"{balance} {symbol}"
                else:
                    balance_display = f"{balance} {symbol}"

            wallet_text = f"{label} ({chain_type}): {balance_display}"
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
    await query.answer()

    user_id = str(update.effective_user.id)

    # Extract the wallet address from the callback data
    if not query.data.startswith(PRIVY_SEND_WALLET_PREFIX):
        await query.edit_message_text("Invalid selection. Please try again.")
        return

    from_address = query.data[len(PRIVY_SEND_WALLET_PREFIX) :]

    # Verify this is a valid Privy wallet
    privy_wallets = privy_service.get_user_privy_wallets(user_id)
    wallet = next(
        (w for w in privy_wallets if w["address"].lower() == from_address.lower()), None
    )

    if not wallet:
        await query.edit_message_text(
            f"Error: Could not find Privy wallet with address {from_address}"
        )
        return

    # Save the selected wallet
    if context.user_data is not None:
        context.user_data["privy_send_from_address"] = from_address
        context.user_data["privy_send_chain_type"] = wallet.get(
            "chain_type", "ethereum"
        )

    await query.edit_message_text(
        f"Selected wallet: {wallet.get('label', 'Privy Wallet')} ({from_address})\n\n"
        f"Please enter the destination address:"
    )

    # Update conversation state
    if context.user_data is not None:
        context.user_data["privy_send_state"] = PRIVY_SEND_INPUT_DESTINATION

    return PRIVY_SEND_INPUT_DESTINATION


async def handle_privy_send_destination(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle destination address input."""
    user_id = str(update.effective_user.id)
    destination = update.message.text.strip()

    # Basic validation of the destination address
    if not destination or len(destination) < 20:
        await _reply(
            update,
            "Invalid destination address. Please enter a valid address:",
            context=context,
        )
        return PRIVY_SEND_INPUT_DESTINATION

    # Save the destination
    if context.user_data is not None:
        context.user_data["privy_send_to_address"] = destination

    chain_type = (
        context.user_data.get("privy_send_chain_type", "ethereum")
        if context.user_data
        else "ethereum"
    )

    # Ask for amount
    if chain_type == "ethereum":
        await _reply(
            update,
            f"Please enter the amount of ETH to send to {destination}:",
            context=context,
        )
    elif chain_type == "solana":
        await _reply(
            update,
            f"Please enter the amount of SOL to send to {destination}:",
            context=context,
        )
    else:
        await _reply(
            update,
            f"Please enter the amount to send to {destination}:",
            context=context,
        )

    # Update conversation state
    if context.user_data is not None:
        context.user_data["privy_send_state"] = PRIVY_SEND_INPUT_AMOUNT

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
    chain_type = (
        context.user_data.get("privy_send_chain_type")
        if context.user_data
        else "ethereum"
    )

    if not from_address or not to_address:
        await _reply(
            update,
            "⚠️ Session data lost. Please restart with /privy_send.",
            context=context,
        )
        return

    # Format based on chain type
    if chain_type == "ethereum":
        currency = "ETH"
    elif chain_type == "solana":
        currency = "SOL"
    else:
        currency = ""

    # Create confirmation message and buttons
    confirmation_message = f"⚠️ Please confirm the transaction:\n\n"
    confirmation_message += f"From: `{from_address}`\n"
    confirmation_message += f"To: `{to_address}`\n"
    confirmation_message += f"Amount: {amount} {currency}\n\n"
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
    await query.answer()

    user_id = str(update.effective_user.id)

    # Check if user confirmed or cancelled
    if query.data == PRIVY_SEND_CONFIRM_NO:
        await query.edit_message_text("Transaction cancelled.")
        return

    if query.data != PRIVY_SEND_CONFIRM_YES:
        await query.edit_message_text("Invalid selection. Transaction cancelled.")
        return

    # Get transaction details
    if not context.user_data:
        await query.edit_message_text(
            "⚠️ Session data lost. Please restart with /privy_send."
        )
        return

    from_address = context.user_data.get("privy_send_from_address")
    to_address = context.user_data.get("privy_send_to_address")
    amount_text = context.user_data.get("privy_send_amount")
    chain_type = context.user_data.get("privy_send_chain_type", "ethereum")

    if not from_address or not to_address or not amount_text:
        await query.edit_message_text(
            "⚠️ Session data lost. Please restart with /privy_send."
        )
        return

    # Convert amount to float
    try:
        amount = float(amount_text)
    except ValueError:
        await query.edit_message_text(
            "❌ Invalid amount format. Please restart with /privy_send."
        )
        return

    if amount <= 0:
        await query.edit_message_text(
            "❌ Amount must be greater than 0. Please restart with /privy_send."
        )
        return

    # Process based on chain type
    if chain_type == "ethereum":
        # Convert ETH to wei
        amount_wei = str(int(amount * 1e18))

        try:
            success, message, tx_data = privy_service.send_transaction(
                user_id=user_id,
                from_address=from_address,
                to_address=to_address,
                amount=amount_wei,
            )
        except Exception as e:
            logger.error(f"Error sending Ethereum transaction: {e}")
            await query.edit_message_text(f"❌ Error processing transaction: {str(e)}")
            return

        tx_hash = tx_data.get("hash") if tx_data else "Unknown"
        explorer_url = (
            f"https://etherscan.io/tx/{tx_hash}" if tx_hash != "Unknown" else None
        )
        currency = "ETH"

    elif chain_type == "solana":
        # Convert SOL to lamports
        amount_lamports = str(int(amount * 1e9))

        try:
            success, message, tx_data = privy_service.send_solana_transaction(
                user_id=user_id,
                from_address=from_address,
                to_address=to_address,
                amount=amount_lamports,
            )
        except Exception as e:
            logger.error(f"Error sending Solana transaction: {e}")
            await query.edit_message_text(f"❌ Error processing transaction: {str(e)}")
            return

        tx_hash = tx_data.get("hash") if tx_data else "Unknown"
        explorer_url = (
            f"https://explorer.solana.com/tx/{tx_hash}"
            if tx_hash != "Unknown"
            else None
        )
        currency = "SOL"

    else:
        await query.edit_message_text(f"❌ Unsupported chain type: {chain_type}")
        return

    if not success:
        await query.edit_message_text(f"❌ Transaction failed: {message}")
        return

    # Format success message
    response = f"✅ Transaction Successful!\n\n"
    response += f"From: `{from_address}`\n"
    response += f"To: `{to_address}`\n"
    response += f"Amount: {amount} {currency}\n"
    response += f"TX Hash: `{tx_hash}`\n"

    if explorer_url:
        response += f"\n[View on explorer]({explorer_url})"

    await query.edit_message_text(response, parse_mode="Markdown")


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
        privy_wallets = privy_service.get_user_privy_wallets(user_id)
        wallet = next(
            (w for w in privy_wallets if w["address"].lower() == address.lower()), None
        )

        if not wallet:
            return await _reply(
                update,
                f"Address {address} is not a Privy wallet registered to your account.",
                context=context,
            )

        success, message, transactions = privy_service.get_transaction_history(
            user_id, address, limit
        )

        if not success or not transactions:
            return await _reply(
                update,
                f"❌ Failed to retrieve transaction history: {message}",
                context=context,
            )

        chain_type = wallet.get("chain_type", "unknown").capitalize()
        label = wallet.get("label", "Privy Wallet")

        response = f"📜 Transaction History for {label} ({chain_type}):\n"
        response += f"📋 `{address}`\n\n"

        for i, tx in enumerate(transactions, 1):
            tx_hash = tx.get("hash", "Unknown")
            tx_type = tx.get("type", "Unknown")
            tx_status = tx.get("status", "Unknown")

            # Format amount based on chain type
            amount = tx.get("amount", "0")

            if chain_type.lower() == "ethereum":
                try:
                    amount_eth = float(amount) / 1e18
                    amount_display = f"{amount_eth:.6f} ETH"
                except (ValueError, TypeError):
                    amount_display = f"{amount} wei"
            elif chain_type.lower() == "solana":
                try:
                    amount_sol = float(amount) / 1e9
                    amount_display = f"{amount_sol:.6f} SOL"
                except (ValueError, TypeError):
                    amount_display = f"{amount} lamports"
            else:
                amount_display = amount

            # Format timestamps
            timestamp = tx.get("timestamp", 0)
            time_str = "Unknown"
            if timestamp:
                try:
                    from datetime import datetime

                    time_str = datetime.fromtimestamp(int(timestamp) / 1000).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    time_str = str(timestamp)

            response += f"{i}. Hash: `{tx_hash}`\n"
            response += f"   Type: {tx_type}\n"
            response += f"   Status: {tx_status}\n"
            response += f"   Amount: {amount_display}\n"
            response += f"   Time: {time_str}\n"

            # Add explorer link
            if chain_type.lower() == "ethereum":
                response += (
                    f"   [View on Etherscan](https://etherscan.io/tx/{tx_hash})\n"
                )
            elif chain_type.lower() == "solana":
                response += f"   [View on Solana Explorer](https://explorer.solana.com/tx/{tx_hash})\n"

            response += "\n"

        await _reply(update, response, parse_mode="Markdown", context=context)
    except Exception as e:
        logger.error(f"Error getting transaction history: {e}")
        await _reply(
            update,
            f"❌ Error retrieving transaction history: {str(e)}",
            context=context,
        )
