import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    BaseHandler,
)
from config import (
    TELEGRAM_BOT_TOKEN,
)
from services.solana_service import SolanaService
from services.openai_service import OpenAIService
from services.rate_limiter import RateLimiter
from services.user_service import UserService

# Import previously organized command handlers and callback functions
from bot.command_handlers.commands import (
    get_command_list,
)
from bot.command_handlers.handlers import handle_verification_callback

from bot.telegram_bot.command_processor import CommandProcessor

from typing import List

logger = logging.getLogger(__name__)
SELECT_OPTION, WAITING_PARAM = 0, 1


class SolanaTelegramBot:
    def __init__(self):
        self.solana_service = SolanaService()
        self.openai_service = OpenAIService()
        self.rate_limiter = RateLimiter()
        self.user_service = UserService()
        self.processor = CommandProcessor()
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        # Define all entry handlers
        entry_points: List[BaseHandler] = [CommandHandler("start", self.start)]
        # Each command is processed through the param_handler entry
        for cmd in self.processor.handlers:
            entry_points.append(CommandHandler(cmd, self.param_handler))
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
                CommandHandler("cancel", self.cancel),
                MessageHandler(filters.COMMAND, self.param_handler),
                MessageHandler(filters.ALL, self.fallback),
            ],
            name="main_conv",
            persistent=False,
        )
        self.app.add_handler(conv_handler)
        self.app.add_handler(
            CallbackQueryHandler(handle_verification_callback, pattern="^verify_")
        )
        self.app.post_init = self.setup_commands

    async def check_rate(self, update: Update, cmd: str) -> bool:
        if not update.effective_user:
            return True
        uid = str(update.effective_user.id)
        if self.rate_limiter.is_rate_limited(uid, cmd):
            cooldown = self.rate_limiter.get_cooldown_time(uid, cmd)
            if update.message:
                await update.message.reply_text(
                    f"Rate limit exceeded. Try again in {cooldown} seconds."
                )
            return False
        return True

    async def param_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return SELECT_OPTION

        cmd = update.message.text.split()[0][1:]
        if not await self.check_rate(update, cmd):
            return SELECT_OPTION

        if self.processor.requires_param(cmd) and not context.args:
            if context.user_data is not None:
                context.user_data["pending"] = cmd
                prompt = self.processor.get_prompt(cmd)
                if prompt:
                    await update.message.reply_text(prompt)
            return WAITING_PARAM

        await self.processor.execute(cmd, update, context)
        return SELECT_OPTION

    async def continue_with_param(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not update.message or not update.message.text:
            return SELECT_OPTION

        if context.user_data is None or "pending" not in context.user_data:
            await update.message.reply_text("No pending command.")
            return SELECT_OPTION

        cmd = context.user_data.pop("pending")
        if update.message.text.lower() == "cancel":
            await update.message.reply_text("Operation cancelled.")
            return SELECT_OPTION

        context.args = update.message.text.strip().split()
        await self.processor.execute(cmd, update, context)
        return SELECT_OPTION

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.effective_user:
            name = update.effective_user.first_name or "there"
            await update.message.reply_text(
                f"Hello {name}! Welcome to Solana Assistant."
            )
            await update.message.reply_text(
                "Commands: /sol_balance, /token_info, /account_details, /transaction, "
                "/recent_tx, /validators, /token_accounts, /latest_block, /network_status, "
                "/slot, /help, /add_wallet, /verify_wallet, /my_wallets, /remove_wallet, /my_balance"
            )
        return SELECT_OPTION

    async def input_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return SELECT_OPTION
        if not await self.check_rate(update, "natural_language"):
            return SELECT_OPTION
        user_input = update.message.text.strip()
        if not user_input:
            await update.message.reply_text("Please enter a valid message.")
            return SELECT_OPTION
        # Using OpenAIService to convert natural language to command line (keep interface consistent with original)
        cmd_line = await self.openai_service.convert_to_command(user_input)
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        context.args = parts[1].split() if len(parts) > 1 else []
        if cmd != "cannot complete" and not await self.check_rate(update, cmd):
            return SELECT_OPTION
        # Simple example: process some commands
        if cmd == "sol_balance" and context.args:
            result = await self.solana_service.get_sol_balance(context.args[0])
            text = (
                f"SOL Balance for {result['address']}: {result['balance']} SOL"
                if result
                else f"Failed to get balance for {context.args[0]}"
            )
        elif cmd == "token_info" and context.args:
            result = await self.solana_service.get_token_info(context.args[0])
            text = (
                f"Token Info:\nAddress: {result['address']}\nSupply: {result['supply']}\n"
                f"Decimals: {result['decimals']}"
                if result
                else f"Failed to get token info for {context.args[0]}"
            )
        elif cmd == "latest_block":
            result = await self.solana_service.get_latest_block()
            text = (
                f"Latest Block:\nBlockhash: {result['blockhash']}\n"
                f"Last Valid Block Height: {result['last_valid_block_height']}"
                if result
                else "Failed to get latest block."
            )
        elif cmd == "network_status":
            result = await self.solana_service.get_network_status()
            text = (
                f"Network Status:\nSolana Core: {result['solana_core']}\n"
                f"Feature Set: {result['feature_set']}"
                if result
                else "Failed to get network status."
            )
        elif cmd == "transaction" and context.args:
            result = await self.solana_service.get_transaction_details(context.args[0])
            status = "✅ Successful" if result.get("success") else "❌ Failed"
            text = (
                f"Transaction Details:\nSignature: {result.get('signature','Unknown')}\n"
                f"Status: {status}\nSlot: {result.get('slot','Unknown')}\n"
                f"Block Time: {result.get('block_time','Unknown')}"
                if result
                else f"Failed to get transaction details for {context.args[0]}"
            )
        else:
            text = "Command not recognized or missing parameter."
        await update.message.reply_text(text)
        return SELECT_OPTION

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text("Cancelled.")
            if context.user_data is not None:
                context.user_data.pop("pending", None)
        return SELECT_OPTION

    async def fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text(
                "Please use valid commands or natural language. Type /help for assistance."
            )
        return SELECT_OPTION

    async def setup_commands(self, app: Application):
        cmds = [BotCommand(cmd, desc) for cmd, desc in get_command_list()]
        await app.bot.set_my_commands(cmds)
        logger.info("Commands set up.")

    def run(self):
        logger.info("Starting Solana Telegram Bot")
        self.app.run_polling()
