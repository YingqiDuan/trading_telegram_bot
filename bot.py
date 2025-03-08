# bot.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import aiohttp
from config import (
    TELEGRAM_BOT_TOKEN,
    ALPHAVANTAGE_API_KEY,
    ALPHAVANTAGE_URL,
    COINGECKO_API_URL,
    DOMAIN_URL,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update, context):
    await update.message.reply_text(
        "Hello! I'm your Telegram Bot.\n" "Type /help to see available commands."
    )


async def help_command(update, context):
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Display this help message\n"
        "\n"
        "== prices ==\n"
        "/stock <symbol> - Get real-time stock quote (e.g. /stock AAPL)\n"
        "/crypto <coin_id> - Get real-time crypto quote (e.g. /crypto bitcoin)\n"
        "\n"
        "== K lines ==\n"
        "/stockchart <symbol> - Get daily candlestick chart for a stock (e.g. /stockchart AAPL)\n"
        "/cryptochart <coin_id> - Get daily candlestick chart for a crypto (e.g. /cryptochart bitcoin)\n"
    )
    await update.message.reply_text(help_text)


async def get_stock_price(symbol: str) -> dict:
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol.upper(),
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(ALPHAVANTAGE_URL, params=params) as resp:
            data = await resp.json()
            if "Global Quote" in data:
                quote = data["Global Quote"]
                return {
                    "price": float(quote["05. price"]),
                    "volume": int(quote["06. volume"]),
                }
    return {}


async def get_crypto_price(coin_id: str) -> dict:
    params = {
        "ids": coin_id.lower(),
        "vs_currencies": "usd",
        "include_market_cap": "true",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(COINGECKO_API_URL, params=params) as resp:
            data = await resp.json()
            if coin_id in data:
                return {"price": data[coin_id]["usd"]}
    return {}


async def stockchart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /stockchart <symbol>")
        return
    symbol = context.args[0].upper()
    webapp_url = f"{DOMAIN_URL}/chart/stock/{symbol}"
    keyboard = [
        [
            InlineKeyboardButton(
                f"View {symbol} Chart", web_app=WebAppInfo(url=webapp_url)
            )
        ]
    ]
    await update.message.reply_text(
        "Click to view chart:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cryptochart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /cryptochart <coin_id>")
        return
    coin_id = context.args[0].lower()
    webapp_url = f"{DOMAIN_URL}/chart/crypto/{coin_id}"
    keyboard = [
        [
            InlineKeyboardButton(
                f"View {coin_id.capitalize()} Chart", web_app=WebAppInfo(url=webapp_url)
            )
        ]
    ]
    await update.message.reply_text(
        "Click to view chart:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /stock <symbol>")
        return
    result = await get_stock_price(context.args[0])
    await update.message.reply_text(
        f"Stock Price: {result['price']}, Volume: {result['volume']}"
    )


async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /crypto <coin_id>")
        return
    result = await get_crypto_price(context.args[0])
    await update.message.reply_text(f"Crypto Price: {result['price']} USD")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stock", stock_command))
    app.add_handler(CommandHandler("crypto", crypto_command))
    app.add_handler(CommandHandler("stockchart", stockchart_command))
    app.add_handler(CommandHandler("cryptochart", cryptochart_command))
    app.run_polling()


if __name__ == "__main__":
    main()
