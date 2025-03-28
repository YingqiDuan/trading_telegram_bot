"""
This file contains the patch code to add Privy wallet command handlers to the SolanaTelegramBot.
The contents of this file should be applied to the original SolanaTelegramBot implementation
to enable Privy wallet functionality.
"""

from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from command.privy_wallet_commands import (
    cmd_privy_send,
    handle_privy_wallet_selection,
    handle_privy_send_destination,
    handle_privy_send_amount,
    handle_privy_send_confirmation,
    PRIVY_SEND_SELECT_SOURCE,
    PRIVY_SEND_INPUT_DESTINATION,
    PRIVY_SEND_INPUT_AMOUNT,
    PRIVY_SEND_CONFIRM,
    PRIVY_SEND_WALLET_PREFIX,
    PRIVY_SEND_CONFIRM_YES,
    PRIVY_SEND_CONFIRM_NO,
)

# Constants
CMD_PREFIX = "cmd_"
SELECT_OPTION = 0


# This function should be called in the setup_handlers method of SolanaTelegramBot
def add_privy_handlers(bot_instance):
    """
    Add Privy wallet handlers to the bot instance.

    Args:
        bot_instance: The instance of SolanaTelegramBot
    """
    # Create a conversation handler for privy_send command
    privy_send_handler = ConversationHandler(
        entry_points=[
            CommandHandler("privy_send", cmd_privy_send),
            CallbackQueryHandler(
                bot_instance.handle_command_button, pattern=f"^{CMD_PREFIX}privy_send$"
            ),
        ],
        states={
            PRIVY_SEND_SELECT_SOURCE: [
                CallbackQueryHandler(
                    handle_privy_wallet_selection,
                    pattern=f"^{PRIVY_SEND_WALLET_PREFIX}.*",
                ),
                CallbackQueryHandler(bot_instance.cancel, pattern="^cancel$"),
            ],
            PRIVY_SEND_INPUT_DESTINATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_privy_send_destination
                )
            ],
            PRIVY_SEND_INPUT_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_privy_send_amount
                )
            ],
            PRIVY_SEND_CONFIRM: [
                CallbackQueryHandler(
                    handle_privy_send_confirmation,
                    pattern=f"^{PRIVY_SEND_CONFIRM_YES}$|^{PRIVY_SEND_CONFIRM_NO}$",
                ),
            ],
            SELECT_OPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, bot_instance.input_handler
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", bot_instance.cancel),
            CommandHandler("start", bot_instance.start),
            CommandHandler("help", bot_instance.help),
        ],
        name="privy_send_conv",
        persistent=False,
        per_message=True,
        per_chat=True,
        allow_reentry=True,
    )

    # Add privy_send handler to the application
    bot_instance.app.add_handler(privy_send_handler)

    # Add a direct callback handler for Privy wallet selection buttons
    bot_instance.app.add_handler(
        CallbackQueryHandler(
            handle_privy_wallet_selection, pattern=f"^{PRIVY_SEND_WALLET_PREFIX}"
        )
    )

    # Add a direct callback handler for confirmation buttons
    bot_instance.app.add_handler(
        CallbackQueryHandler(
            handle_privy_send_confirmation,
            pattern=f"^{PRIVY_SEND_CONFIRM_YES}$|^{PRIVY_SEND_CONFIRM_NO}$",
        )
    )
