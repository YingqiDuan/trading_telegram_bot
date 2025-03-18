import logging
from typing import Optional, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def _reply(update: Update, text: str) -> Optional[Any]:
    """如果 update.message 存在，则发送回复消息，否则返回 None"""
    if update.message:
        return await update.message.reply_text(text)
    return None
