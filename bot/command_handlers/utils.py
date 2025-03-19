import logging
from typing import Optional, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def _reply(update: Update, text: str) -> Optional[Any]:
    """If update.message exists, send a reply message, otherwise return None"""
    if update.message:
        return await update.message.reply_text(text)
    return None
