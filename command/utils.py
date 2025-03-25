import logging
from typing import Optional, Any, Union
from telegram import Update, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def _reply(
    update: Update,
    text: str,
    parse_mode: Optional[str] = None,
    context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    reply_markup: Optional[
        Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, Any]
    ] = None,
) -> Optional[Any]:
    """Reply to either a message or a callback query"""
    try:
        # If we have a direct message, reply to it
        if update.message:
            return await update.message.reply_text(
                text, parse_mode=parse_mode, reply_markup=reply_markup
            )

        # If it's a callback query with context, use context.bot
        elif update.callback_query and context:
            chat_id = (
                update.effective_chat.id
                if update.effective_chat
                else update.callback_query.message.chat_id
            )
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )

        # Last resort fallback
        elif update.effective_chat:
            logger.warning("Using fallback reply mechanism - missing context object")
            try:
                if update.callback_query and update.callback_query.message:
                    return await update.callback_query.edit_message_text(
                        text, parse_mode=parse_mode, reply_markup=reply_markup
                    )
            except Exception:
                pass

        logger.error("Could not send reply: no valid methods available")
        return None
    except Exception as e:
        logger.error(f"Error in _reply: {str(e)}")
        return None
