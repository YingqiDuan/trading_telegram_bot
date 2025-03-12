import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import TELEGRAM_BOT_TOKEN
from services.solana_service import SolanaService
from services.openai_service import OpenAIService
from bot.command_handlers import (
    cmd_sol_balance,
    cmd_token_info,
    cmd_account_details,
    cmd_latest_block,
    cmd_network_status,
    cmd_help,
    cmd_transaction,
    cmd_recent_transactions,
    cmd_validators,
    cmd_token_accounts,
    cmd_slot,
    get_command_list,
)

logger = logging.getLogger(__name__)

# Define conversation states
SELECT_OPTION = 0
WAITING_PARAM = 1


class SolanaTelegramBot:
    """Main Telegram bot class for Solana blockchain assistant"""

    def __init__(self):
        """Initialize the Telegram bot"""
        self.solana_service = SolanaService()
        self.openai_service = OpenAIService()
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up bot command handlers and conversation flow"""
        # Set up conversation handler for both natural language and commands
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start_command),
                CommandHandler("sol_balance", self.param_handler),
                CommandHandler("token_info", self.param_handler),
                CommandHandler("account_details", self.param_handler),
                CommandHandler("transaction", self.param_handler),
                CommandHandler("recent_tx", self.param_handler),
                CommandHandler("validators", self.param_handler),
                CommandHandler("token_accounts", self.param_handler),
                CommandHandler("latest_block", cmd_latest_block),
                CommandHandler("network_status", cmd_network_status),
                CommandHandler("slot", cmd_slot),
                CommandHandler("help", cmd_help),
            ],
            states={
                SELECT_OPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handler)
                ],
                WAITING_PARAM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.continue_with_param
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_handler),
                MessageHandler(filters.COMMAND, self.handle_command_in_conversation),
                MessageHandler(filters.ALL, self.fallback_handler),
            ],
            name="main_conversation",
            persistent=False,
        )

        self.app.add_handler(conv_handler)

        # Set up command menu
        self.app.post_init = self.setup_commands

    async def param_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle commands that require parameters"""
        if not update.message:
            return ConversationHandler.END

        command = update.message.text.split()[0][1:] if update.message.text else ""
        logger.info(f"Param handler called for command: {command}")

        # Check if parameters are provided
        if not context.args or len(context.args) < 1:
            # Store the command in user_data for later
            if context.user_data is not None:
                context.user_data["pending_command"] = command
                logger.info(f"Storing pending command: {command}")

            # Ask for the required parameter based on command
            if command in ["sol_balance", "account_details", "token_accounts"]:
                await update.message.reply_text(f"请输入钱包地址:")
            elif command == "token_info":
                await update.message.reply_text(f"请输入代币地址:")
            elif command == "transaction":
                await update.message.reply_text(f"请输入交易签名:")
            elif command == "recent_tx":
                await update.message.reply_text(f"请输入钱包地址和可选的交易数量限制:")
            elif command == "validators":
                await update.message.reply_text(
                    f"请输入要显示的验证者数量(可选)，或直接按回车使用默认值:"
                )

            return WAITING_PARAM

        # If parameters are provided, call the appropriate command handler
        result = await self._execute_command(command, update, context)
        return SELECT_OPTION if result else ConversationHandler.END

    async def continue_with_param(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Continue processing a command with parameters provided by the user"""
        if not update.message:
            logger.warning("No message in continue_with_param")
            return SELECT_OPTION

        if context.user_data is None or "pending_command" not in context.user_data:
            logger.warning("No pending command found in user_data")
            if update.message:
                await update.message.reply_text(
                    "抱歉，无法处理您的请求。请重新输入命令。"
                )
            return SELECT_OPTION

        command = context.user_data.get("pending_command", "")
        param_text = update.message.text.strip() if update.message.text else ""

        logger.info(f"Processing parameter for command {command}: {param_text}")

        # If user entered cancel, abort the operation
        if param_text.lower() in ["cancel", "取消"]:
            await update.message.reply_text("操作已取消。")
            if context.user_data is not None:
                context.user_data.pop("pending_command", None)
            return SELECT_OPTION

        # Set the args based on user input
        context.args = param_text.split()

        # Execute the command
        result = await self._execute_command(command, update, context)

        # Clear the pending command
        if context.user_data is not None:
            context.user_data.pop("pending_command", None)

        return SELECT_OPTION

    async def _execute_command(
        self, command: str, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Execute a command with the given parameters

        Returns:
            bool: True if command was executed successfully, False otherwise
        """
        if not update.message:
            logger.warning("Cannot execute command, message is None")
            return False

        try:
            if command == "sol_balance":
                await cmd_sol_balance(update, context)
            elif command == "token_info":
                await cmd_token_info(update, context)
            elif command == "account_details":
                await cmd_account_details(update, context)
            elif command == "transaction":
                await cmd_transaction(update, context)
            elif command == "recent_tx":
                await cmd_recent_transactions(update, context)
            elif command == "validators":
                await cmd_validators(update, context)
            elif command == "token_accounts":
                await cmd_token_accounts(update, context)
            else:
                await update.message.reply_text(f"未知命令: {command}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            await update.message.reply_text(f"执行命令时出错: {e}")
            return False

    async def handle_command_in_conversation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle commands that come in during a conversation"""
        if not update.message:
            return SELECT_OPTION

        if not update.message.text:
            return SELECT_OPTION

        command = update.message.text.split()[0][1:]

        # Handle direct commands
        if command == "latest_block":
            await cmd_latest_block(update, context)
        elif command == "network_status":
            await cmd_network_status(update, context)
        elif command == "slot":
            await cmd_slot(update, context)
        elif command == "help":
            await cmd_help(update, context)
        elif command in [
            "sol_balance",
            "token_info",
            "account_details",
            "transaction",
            "recent_tx",
            "validators",
            "token_accounts",
        ]:
            return await self.param_handler(update, context)
        elif command == "cancel":
            await self.cancel_handler(update, context)
            return SELECT_OPTION
        else:
            if update.message:
                await update.message.reply_text(f"未知命令: {command}")

        return SELECT_OPTION

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command: introduce bot functionality"""
        if update.message and update.effective_user:
            first_name = update.effective_user.first_name or "there"
            await update.message.reply_text(
                f"👋 Hello {first_name}! Welcome to the Solana Blockchain Assistant. "
                f"I can help you query various information on Solana, including wallet balances, token information, and blockchain status."
            )
            await update.message.reply_text(
                "You can interact with me in two ways:\n\n"
                "1️⃣ Use natural language, for example:\n"
                "• 'What's the balance of wallet address 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV?'\n"
                "• 'Tell me about the latest Solana block'\n"
                "• 'Show me information about token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'\n"
                "• 'What are the recent transactions for wallet 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV?'\n"
                "• 'Show me transaction details for 5rUk2MP3NrAUo3x3kEaKvA3mFKiKgsGSqMkjbw9V33JhRBRBxUKpVmpjEhYKcyFkBX9JroQkGEqRAksVZxBuBkwP'\n\n"
                "2️⃣ Use direct commands:\n"
                "• /sol_balance [wallet address]\n"
                "• /token_info [token address]\n"
                "• /account_details [account address]\n"
                "• /transaction [signature]\n"
                "• /recent_tx [address] [limit]\n"
                "• /token_accounts [address]\n"
                "• /validators [limit]\n"
                "• /latest_block\n"
                "• /network_status\n"
                "• /slot\n"
                "• /help - Show this help message"
            )
        return SELECT_OPTION

    async def input_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user natural language input: convert to command and execute"""
        if not update.message or not update.message.text:
            return SELECT_OPTION

        user_input = update.message.text.strip()
        if not user_input:
            await update.message.reply_text(
                "I couldn't understand that request. Please provide a text message."
            )
            return SELECT_OPTION

        # Call OpenAI to convert natural language to command
        command_line = await self.openai_service.convert_to_command(user_input)
        tokens = command_line.split(maxsplit=1)
        command = tokens[0] if tokens else ""
        argument = tokens[1] if len(tokens) > 1 else ""

        if command == "sol_balance" and argument:
            result = await self.solana_service.get_sol_balance(argument)
            if result:
                text = f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
            else:
                text = f"Unable to retrieve SOL balance for address {argument}."

        elif command == "token_info" and argument:
            result = await self.solana_service.get_token_info(argument)
            if result:
                text = (
                    f"Token Information:\n"
                    f"Address: {result['address']}\n"
                    f"Supply: {result['supply']}\n"
                    f"Decimals: {result['decimals']}"
                )
            else:
                text = f"Unable to retrieve token information for {argument}."

        elif command == "account_details" and argument:
            result = await self.solana_service.get_account_details(argument)
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
                text = f"Unable to retrieve account details for {argument}."

        elif command == "latest_block":
            result = await self.solana_service.get_latest_block()
            if result:
                text = (
                    f"Latest Block:\n"
                    f"Blockhash: {result['blockhash']}\n"
                    f"Last Valid Block Height: {result['last_valid_block_height']}"
                )
            else:
                text = "Unable to retrieve latest block information."

        elif command == "network_status":
            result = await self.solana_service.get_network_status()
            if result:
                text = (
                    f"Solana Network Status:\n"
                    f"Solana Core: {result['solana_core']}\n"
                    f"Feature Set: {result['feature_set']}"
                )
            else:
                text = "Unable to retrieve Solana network status."

        elif command == "transaction" and argument:
            result = await self.solana_service.get_transaction_details(argument)
            if result:
                status = (
                    "✅ Successful" if result.get("success", False) else "❌ Failed"
                )
                text = (
                    f"Transaction Details:\n"
                    f"Signature: {result['signature']}\n"
                    f"Status: {status}\n"
                    f"Slot: {result.get('slot', 'Unknown')}\n"
                    f"Block Time: {result.get('block_time', 'Unknown')}"
                )
            else:
                text = (
                    f"Unable to retrieve transaction details for signature {argument}."
                )

        elif command == "recent_tx" and argument:
            # Check if there's a limit specified after the address
            parts = argument.split()
            address = parts[0]
            limit = 5
            if len(parts) > 1:
                try:
                    limit = int(parts[1])
                    if limit < 1:
                        limit = 1
                    elif limit > 10:
                        limit = 10
                except ValueError:
                    pass

            transactions = await self.solana_service.get_recent_transactions(
                address, limit
            )
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

        elif command == "validators":
            # Extract limit if provided in argument
            limit = 5
            if argument:
                try:
                    limit = int(argument)
                    if limit < 1:
                        limit = 1
                    elif limit > 10:
                        limit = 10
                except ValueError:
                    pass

            validators = await self.solana_service.get_validators(limit)
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

        elif command == "token_accounts" and argument:
            accounts = await self.solana_service.get_token_accounts(argument)
            if accounts:
                text = f"Token Accounts for {argument}:\n\n"
                for i, account in enumerate(accounts, 1):
                    text += (
                        f"{i}. Account: {account.get('pubkey', 'Unknown')[:10]}...\n"
                    )
                    if "data" in account:
                        text += f"   Data: {account['data']}\n"
            else:
                text = f"No token accounts found for {argument}."

        elif command == "slot":
            slot = await self.solana_service.get_slot()
            if slot > 0:
                text = f"Current Solana Slot: {slot}"
            else:
                text = "Unable to retrieve current slot information."

        else:
            text = "Command not recognized or missing parameter."

        await update.message.reply_text(text)
        return SELECT_OPTION

    async def cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        if update.message:
            await update.message.reply_text("操作已取消。")

            # Clear any pending command
            if context.user_data is not None and "pending_command" in context.user_data:
                context.user_data.pop("pending_command", None)

        return SELECT_OPTION

    async def fallback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle unrecognized input"""
        if update.message:
            await update.message.reply_text(
                "请使用自然语言输入您的请求，或使用直接命令。如需帮助，请输入 /help"
            )
        return SELECT_OPTION

    async def setup_commands(self, application: Application):
        """Set up Telegram command menu for better UX"""
        commands = []
        for command, description in get_command_list():
            commands.append(BotCommand(command, description))

        await application.bot.set_my_commands(commands)
        logger.info("Telegram command menu set up successfully")

    def run(self):
        """Start the bot"""
        logger.info("Starting Solana Telegram Bot")
        self.app.run_polling()
