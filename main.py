"""
Solana Telegram Bot

This application provides a Telegram bot interface to interact with the Solana blockchain.
It supports both natural language queries and direct commands to fetch information
such as account balances, token data, transaction details, and network status.

Usage:
    python main.py
"""

import logging
from bot.telegram_bot import SolanaTelegramBot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Solana Telegram Bot"""
    logger.info("Starting Solana Blockchain Assistant Telegram Bot")
    bot = SolanaTelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
