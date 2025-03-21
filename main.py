import logging
from telegram_bot import SolanaTelegramBot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting Solana Blockchain Assistant Telegram Bot")
    bot = SolanaTelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
