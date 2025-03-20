import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.user_service import UserService

logger = logging.getLogger(__name__)
user_service = UserService()


async def handle_verification_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    method = None

    if not data:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Invalid callback data."
            )
        return

    if data.startswith("verify_signature_"):
        method = "signature"
        address = data[len("verify_signature_") :]
    elif data.startswith("verify_transfer_"):
        method = "transfer"
        address = data[len("verify_transfer_") :]
    elif data.startswith("verify_private_key_"):
        method = "private_key"
        address = data[len("verify_private_key_") :]
    else:
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="Invalid selection."
            )
        return

    success, message = user_service.verify_wallet(user_id, address, method)
    try:
        await query.edit_message_text(f"Selected {method} verification for {address}.")
    except Exception as e:
        logger.error(f"Edit message error: {e}")

    if update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
