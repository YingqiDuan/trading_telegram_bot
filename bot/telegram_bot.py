import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    BaseHandler,
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
from typing import cast, List

logger = logging.getLogger(__name__)

# Define conversation states
SELECT_OPTION = 0
WAITING_PARAM = 1


class CommandProcessor:
    """Helper class to process and manage commands"""

    def __init__(self):
        """Initialize command processor with command definitions"""
        self.command_handlers = {
            "sol_balance": {
                "handler": cmd_sol_balance,
                "param_prompt": "Please enter wallet address:",
                "requires_param": True,
            },
            "token_info": {
                "handler": cmd_token_info,
                "param_prompt": "Please enter token address:",
                "requires_param": True,
            },
            "account_details": {
                "handler": cmd_account_details,
                "param_prompt": "Please enter account address:",
                "requires_param": True,
            },
            "transaction": {
                "handler": cmd_transaction,
                "param_prompt": "Please enter transaction signature:",
                "requires_param": True,
            },
            "recent_tx": {
                "handler": cmd_recent_transactions,
                "param_prompt": "Please enter wallet address and optional limit:",
                "requires_param": True,
            },
            "validators": {
                "handler": cmd_validators,
                "param_prompt": "Please enter number of validators to display (optional) or press Enter for default:",
                "requires_param": False,
            },
            "token_accounts": {
                "handler": cmd_token_accounts,
                "param_prompt": "Please enter wallet address:",
                "requires_param": True,
            },
            "latest_block": {"handler": cmd_latest_block, "requires_param": False},
            "network_status": {"handler": cmd_network_status, "requires_param": False},
            "slot": {"handler": cmd_slot, "requires_param": False},
            "help": {"handler": cmd_help, "requires_param": False},
        }

    def get_command_handler(self, command):
        """Get handler for a specific command

        Args:
            command: Command name

        Returns:
            Dict with command handler and metadata or None if not found
        """
        return self.command_handlers.get(command)

    def requires_parameter(self, command):
        """Check if a command requires parameters

        Args:
            command: Command name

        Returns:
            Boolean indicating if command requires parameters
        """
        cmd_info = self.command_handlers.get(command)
        if not cmd_info:
            return False
        return cmd_info.get("requires_param", False)

    def get_parameter_prompt(self, command):
        """Get the prompt text for a command's parameter

        Args:
            command: Command name

        Returns:
            Prompt text or None if not applicable
        """
        cmd_info = self.command_handlers.get(command)
        if not cmd_info:
            return None
        return cmd_info.get("param_prompt")

    async def execute_command(self, command, update, context):
        """Execute a command with the given parameters

        Args:
            command: Command name
            update: Telegram update object
            context: Callback context

        Returns:
            bool: True if command was executed successfully, False otherwise
        """
        if not update.message:
            logger.warning("Cannot execute command, message is None")
            return False

        cmd_info = self.get_command_handler(command)
        if not cmd_info:
            await update.message.reply_text(f"Unknown command: {command}")
            return False

        try:
            await cmd_info["handler"](update, context)
            return True
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            await update.message.reply_text(f"Error executing command: {e}")
            return False


class SolanaTelegramBot:
    """Main Telegram bot class for Solana blockchain assistant"""

    def __init__(self):
        """Initialize the Telegram bot"""
        self.solana_service = SolanaService()
        self.openai_service = OpenAIService()
        self.command_processor = CommandProcessor()
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up bot command handlers and conversation flow"""
        # Set up conversation handler for both natural language and commands
        entry_points: List[BaseHandler] = [CommandHandler("start", self.start_command)]

        # Add all command handlers as entry points
        for cmd_name in self.command_processor.command_handlers:
            entry_points.append(CommandHandler(cmd_name, self.param_handler))

        conv_handler = ConversationHandler(
            entry_points=entry_points,
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
        if (
            not context.args or len(context.args) < 1
        ) and self.command_processor.requires_parameter(command):
            # Store the command in user_data for later
            if context.user_data is not None:
                context.user_data["pending_command"] = command
                logger.info(f"Storing pending command: {command}")

            # Ask for the required parameter based on command
            prompt = self.command_processor.get_parameter_prompt(command)
            if prompt:
                await update.message.reply_text(prompt)
                return WAITING_PARAM

        # If parameters are provided or not required, call the appropriate command handler
        result = await self.command_processor.execute_command(command, update, context)
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
                    "Sorry, I couldn't process your request. Please try again with a command."
                )
            return SELECT_OPTION

        command = context.user_data.get("pending_command", "")
        param_text = update.message.text.strip() if update.message.text else ""

        logger.info(f"Processing parameter for command {command}: {param_text}")

        # If user entered cancel, abort the operation
        if param_text.lower() in ["cancel"]:
            await update.message.reply_text("Operation cancelled.")
            if context.user_data is not None:
                context.user_data.pop("pending_command", None)
            return SELECT_OPTION

        # Set the args based on user input
        context.args = param_text.split()

        # Execute the command
        result = await self.command_processor.execute_command(command, update, context)

        # Clear the pending command
        if context.user_data is not None:
            context.user_data.pop("pending_command", None)

        return SELECT_OPTION

    async def handle_command_in_conversation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle commands that come in during a conversation"""
        if not update.message or not update.message.text:
            return SELECT_OPTION

        command = update.message.text.split()[0][1:]

        if command == "cancel":
            await self.cancel_handler(update, context)
            return SELECT_OPTION

        # For all other commands, pass to param_handler
        return await self.param_handler(update, context)

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
            await update.message.reply_text("Operation cancelled.")

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
                "Please use natural language for your request or use direct commands. For help, type /help"
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
