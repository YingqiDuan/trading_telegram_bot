import logging
import sys, os
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
    MAX_TRANSACTIONS_DISPLAY,
    DEFAULT_TRANSACTIONS_DISPLAY,
)
from services.solana_service import SolanaService
from services.openai_service import OpenAIService
from services.rate_limiter import RateLimiter
from services.user_service import UserService
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
    cmd_add_wallet,
    cmd_verify_wallet,
    cmd_list_wallets,
    cmd_remove_wallet,
    cmd_my_balance,
    handle_verification_callback,
)
from typing import List, Sequence, Dict, Any, Optional, Union, cast

logger = logging.getLogger(__name__)
SELECT_OPTION, WAITING_PARAM = 0, 1


class CommandProcessor:
    def __init__(self):
        self.handlers = {
            "sol_balance": {
                "handler": cmd_sol_balance,
                "prompt": "Enter wallet address:",
                "requires": True,
            },
            "token_info": {
                "handler": cmd_token_info,
                "prompt": "Enter token address:",
                "requires": True,
            },
            "account_details": {
                "handler": cmd_account_details,
                "prompt": "Enter account address:",
                "requires": True,
            },
            "transaction": {
                "handler": cmd_transaction,
                "prompt": "Enter transaction signature:",
                "requires": True,
            },
            "recent_tx": {
                "handler": cmd_recent_transactions,
                "prompt": "Enter wallet address and limit:",
                "requires": True,
            },
            "validators": {
                "handler": cmd_validators,
                "prompt": "Enter number of validators (optional):",
                "requires": False,
            },
            "token_accounts": {
                "handler": cmd_token_accounts,
                "prompt": "Enter wallet address:",
                "requires": True,
            },
            "latest_block": {"handler": cmd_latest_block, "requires": False},
            "network_status": {"handler": cmd_network_status, "requires": False},
            "slot": {"handler": cmd_slot, "requires": False},
            "help": {"handler": cmd_help, "requires": False},
            "add_wallet": {
                "handler": cmd_add_wallet,
                "prompt": "Enter wallet address and label:",
                "requires": True,
            },
            "verify_wallet": {
                "handler": cmd_verify_wallet,
                "prompt": "Enter wallet address to verify:",
                "requires": True,
            },
            "my_wallets": {"handler": cmd_list_wallets, "requires": False},
            "remove_wallet": {
                "handler": cmd_remove_wallet,
                "prompt": "Enter wallet address to remove:",
                "requires": True,
            },
            "my_balance": {"handler": cmd_my_balance, "requires": False},
        }

    def get(self, cmd: str):
        return self.handlers.get(cmd)

    def requires_param(self, cmd: str) -> bool:
        info = self.get(cmd)
        return info.get("requires", False) if info else False

    def get_prompt(self, cmd: str) -> str:
        info = self.get(cmd)
        return info.get("prompt", "") if info else ""

    async def execute(
        self, cmd: str, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        info = self.get(cmd)
        if not info:
            if update.message:
                await update.message.reply_text(f"Unknown command: {cmd}")
            return False
        try:
            await info["handler"](update, context)
            return True
        except Exception as e:
            logger.error(f"Error in {cmd}: {e}")
            if update.message:
                await update.message.reply_text(f"Error: {e}")
            return False


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
        entry_points: List[BaseHandler] = [CommandHandler("start", self.start)]
        # 每个命令均通过 param_handler 入口处理
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
        cmd_line = await self.openai_service.convert_to_command(user_input)
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        context.args = parts[1].split() if len(parts) > 1 else []
        if cmd != "cannot complete" and not await self.check_rate(update, cmd):
            return SELECT_OPTION
        # 简化：仅处理部分命令示例
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
                (
                    f"Token Info:\nAddress: {result['address']}\nSupply: {result['supply']}\n"
                    f"Decimals: {result['decimals']}"
                )
                if result
                else f"Failed to get token info for {context.args[0]}"
            )
        elif cmd == "latest_block":
            result = await self.solana_service.get_latest_block()
            text = (
                (
                    f"Latest Block:\nBlockhash: {result['blockhash']}\n"
                    f"Last Valid Block Height: {result['last_valid_block_height']}"
                )
                if result
                else "Failed to get latest block."
            )
        elif cmd == "network_status":
            result = await self.solana_service.get_network_status()
            text = (
                (
                    f"Network Status:\nSolana Core: {result['solana_core']}\n"
                    f"Feature Set: {result['feature_set']}"
                )
                if result
                else "Failed to get network status."
            )
        elif cmd == "transaction" and context.args:
            result = await self.solana_service.get_transaction_details(context.args[0])
            status = "✅ Successful" if result.get("success") else "❌ Failed"
            text = (
                (
                    f"Transaction Details:\nSignature: {result.get('signature','Unknown')}\n"
                    f"Status: {status}\nSlot: {result.get('slot','Unknown')}\n"
                    f"Block Time: {result.get('block_time','Unknown')}"
                )
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
