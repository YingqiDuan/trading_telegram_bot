import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Enable logging to see info and errors in the console (useful for debugging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Define a handler function for the /start command
async def start(update, context):
    """Send a welcome message when /start is issued by the user."""
    await update.message.reply_text(
        "Hello! I'm your Telegram Bot. Type /help to see available commands."
    )  # :contentReference[oaicite:6]{index=6}


# Define a handler function for the /help command
async def help_command(update, context):
    """Send a help message listing available commands."""
    await update.message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Display this help message"
    )  # :contentReference[oaicite:7]{index=7}


# Define a handler for general text messages (echo back the message)
async def echo(update, context):
    """Echo the user's message."""
    await update.message.reply_text(
        update.message.text
    )  # :contentReference[oaicite:8]{index=8}


def main():
    # Initialize the bot application with your API token
    TOKEN = ""  # replace with your BotFather token
    app = Application.builder().token(TOKEN).build()  # Build the Application object

    # Register command handlers to the application
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Register a message handler to echo non-command text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    # The filter above means: all text messages that are not commands (so we don't echo /commands).

    # Start the bot by polling Telegram for new updates
    app.run_polling()
