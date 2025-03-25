import logging
from telegram import Update
from telegram.ext import ContextTypes
from . import (
    cmd_sol_balance,
    cmd_token_info,
    cmd_account_details,
    cmd_latest_block,
    cmd_network_status,
    cmd_transaction,
    cmd_recent_transactions,
    cmd_validators,
    cmd_token_accounts,
    cmd_slot,
    cmd_add_wallet,
    cmd_list_wallets,
    cmd_remove_wallet,
    cmd_my_balance,
    cmd_create_wallet,
    cmd_send_sol,
)

logger = logging.getLogger(__name__)


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
            "add_wallet": {
                "handler": cmd_add_wallet,
                "prompt": "Enter wallet address, optional label and private key:",
                "requires": True,
            },
            "my_wallets": {"handler": cmd_list_wallets, "requires": False},
            "remove_wallet": {
                "handler": cmd_remove_wallet,
                "prompt": "Enter wallet address to remove:",
                "requires": True,
            },
            "my_balance": {"handler": cmd_my_balance, "requires": False},
            "create_wallet": {
                "handler": cmd_create_wallet,
                "prompt": "Enter optional label for the new wallet:",
                "requires": False,
            },
            "send_sol": {
                "handler": cmd_send_sol,
                "prompt": "Follow the steps to send SOL from your wallet:",
                "requires": False,
            },
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
