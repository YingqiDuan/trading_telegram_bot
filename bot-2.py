import logging
import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import (
    TELEGRAM_BOT_TOKEN,
    ALPHAVANTAGE_API_KEY,
    ALPHAVANTAGE_URL,
    COINGECKO_API_URL,
    DOMAIN_URL,
)

# Define conversation states
SELECT_OPTION, WAIT_INPUT = range(2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def build_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("Real-Time Stock", callback_data="real_stock"),
            InlineKeyboardButton("Real-Time Crypto", callback_data="real_crypto"),
        ],
        [
            InlineKeyboardButton("Stock Chart", callback_data="chart_stock"),
            InlineKeyboardButton("Crypto Chart", callback_data="chart_crypto"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Async function to fetch stock data via Alpha Vantage
async def get_stock_price(symbol: str) -> dict:
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol.upper(),
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ALPHAVANTAGE_URL, params=params) as resp:
                data = await resp.json()
                if "Global Quote" in data and data["Global Quote"]:
                    quote = data["Global Quote"]
                    return {
                        "price": float(quote.get("05. price", "0")),
                        "volume": int(quote.get("06. volume", "0")),
                    }
    except Exception as e:
        logger.error(f"Error fetching stock data: {e}")
    return {}


# Async function to fetch crypto price via CoinGecko
async def get_crypto_price(coin_id: str) -> dict:
    params = {"ids": coin_id.lower(), "vs_currencies": "usd"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_API_URL, params=params) as resp:
                data = await resp.json()
                if coin_id.lower() in data:
                    return {"price": data[coin_id.lower()]["usd"]}
    except Exception as e:
        logger.error(f"Error fetching crypto data: {e}")
    return {}


# Command: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please choose an option:", reply_markup=build_main_menu()
    )
    return SELECT_OPTION


# Callback handler for menu button clicks
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Set the query type based on the selected option and prompt for symbol input.
    if data == "real_stock":
        await query.edit_message_text("Please enter the stock symbol (e.g. AAPL):")
        context.user_data["query_type"] = "real_stock"
        return WAIT_INPUT
    elif data == "real_crypto":
        await query.edit_message_text("Please enter the crypto ID (e.g. bitcoin):")
        context.user_data["query_type"] = "real_crypto"
        return WAIT_INPUT
    elif data == "chart_stock":
        await query.edit_message_text(
            "Please enter the stock symbol for the chart (e.g. AAPL):"
        )
        context.user_data["query_type"] = "chart_stock"
        return WAIT_INPUT
    elif data == "chart_crypto":
        await query.edit_message_text(
            "Please enter the crypto ID for the chart (e.g. bitcoin):"
        )
        context.user_data["query_type"] = "chart_crypto"
        return WAIT_INPUT


# Input handler for symbol/ID responses
async def input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    query_type = context.user_data.get("query_type", "")
    if query_type == "real_stock":
        result = await get_stock_price(user_input)
        if result:
            text = f"Stock {user_input.upper()}:\nPrice: {result['price']}\nVolume: {result['volume']}"
        else:
            text = f"Could not fetch data for stock {user_input.upper()}."
        await update.message.reply_text(text, reply_markup=build_main_menu())
    elif query_type == "real_crypto":
        result = await get_crypto_price(user_input)
        if result:
            text = f"Crypto {user_input.lower()}:\nPrice: {result['price']} USD"
        else:
            text = f"Could not fetch data for crypto {user_input.lower()}."
        await update.message.reply_text(text, reply_markup=build_main_menu())
    elif query_type == "chart_stock":
        # Build the URL for the interactive stock chart
        url = f"{DOMAIN_URL}/chart/stock/{user_input.upper()}"
        keyboard = [
            [
                InlineKeyboardButton(
                    f"Open {user_input.upper()} Chart", web_app=WebAppInfo(url=url)
                )
            ]
        ]
        await update.message.reply_text(
            f"Click the button below to view the interactive chart for {user_input.upper()}:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif query_type == "chart_crypto":
        url = f"{DOMAIN_URL}/chart/crypto/{user_input.lower()}"
        keyboard = [
            [
                InlineKeyboardButton(
                    f"Open {user_input.lower()} Chart", web_app=WebAppInfo(url=url)
                )
            ]
        ]
        await update.message.reply_text(
            f"Click the button below to view the interactive chart for {user_input.lower()}:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(
            "Unknown request type. Please try again.", reply_markup=build_main_menu()
        )
    return SELECT_OPTION


# Cancel handler to exit the conversation
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=build_main_menu()
    )
    return SELECT_OPTION


# Fallback handler for unexpected input
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please use the provided buttons to select an option.",
        reply_markup=build_main_menu(),
    )
    return SELECT_OPTION


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            SELECT_OPTION: [CallbackQueryHandler(menu_callback)],
            WAIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            MessageHandler(filters.ALL, fallback_handler),
        ],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
