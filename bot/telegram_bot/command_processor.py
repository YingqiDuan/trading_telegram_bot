import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    BaseHandler,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)

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
    cmd_add_wallet,
    cmd_verify_wallet,
    cmd_list_wallets,
    cmd_remove_wallet,
    cmd_my_balance,
)
from bot.command_handlers.commands.general_commands import get_command_list

logger = logging.getLogger(__name__)


class CommandProcessor:
    def __init__(self):
        # 定义每个命令的处理函数、参数提示信息和是否需要参数
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
