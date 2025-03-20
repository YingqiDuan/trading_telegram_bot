import logging
import sys, os
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    BaseHandler,
)
from typing import List

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import TELEGRAM_BOT_TOKEN
from services.solana_rpc_service import SolanaService
from services.openai_service import OpenAIService
from services.rate_limiter import RateLimiter
from services.user_service import UserService
from command import (
    get_command_list,
    handle_verification_callback,
    CommandProcessor,
    HELP_TEXT,
)

logger = logging.getLogger(__name__)
SELECT_OPTION, WAITING_PARAM = 0, 1

# Callback data constants and command prefix
SOLANA_TOPIC_CB = "topic_solana"
WALLET_TOPIC_CB = "topic_wallet"
HELP_TOPIC_CB = "topic_help"
CMD_PREFIX = "cmd_"


class SolanaTelegramBot:
    # 初始化 SolanaTelegramBot 类的实例。
    def __init__(self):
        # 创建了多个服务对象，包括与 Solana 相关的服务、
        # OpenAI 服务、限流器、用户服务以及命令处理器。
        self.solana_service = SolanaService()
        self.openai_service = OpenAIService()
        self.rate_limiter = RateLimiter()
        self.user_service = UserService()
        self.processor = CommandProcessor()
        # 使用提供的 Telegram 令牌构建 Telegram 应用
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        # 调用 setup_handlers() 来设置所有消息和回调的处理器。
        self.setup_handlers()

    # 设置 Telegram 机器人的各种命令和消息处理器。
    def setup_handlers(self):
        # 定义了一个入口处理器列表（entry_points），最初包含 /start 和 /help 命令。
        entry_points: List[BaseHandler] = [
            CommandHandler("start", self.start),
            CommandHandler("help", self.help),
        ]
        # 遍历命令处理器列表，将每个命令处理器添加到入口处理器列表中。
        for cmd in self.processor.handlers:
            entry_points.append(CommandHandler(cmd, self.param_handler))
        conv_handler = ConversationHandler(
            entry_points=entry_points,
            states={
                SELECT_OPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handler)
                ],
                WAITING_PARAM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.continue_with_param
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start),
                MessageHandler(filters.COMMAND, self.param_handler),
                MessageHandler(filters.ALL, self.fallback),
            ],
            name="main_conv",
            persistent=False,
        )
        self.app.add_handler(conv_handler)
        self.app.add_handler(
            CallbackQueryHandler(handle_verification_callback, pattern="^verify_")
        )
        self.app.add_handler(
            CallbackQueryHandler(self.handle_topic_selection, pattern="^topic_")
        )
        self.app.add_handler(
            CallbackQueryHandler(self.handle_command_button, pattern=f"^{CMD_PREFIX}")
        )
        self.app.post_init = self.setup_commands

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        if update.message:
            # Create buttons for the help message
            keyboard = [
                [
                    InlineKeyboardButton("Solana 🔍", callback_data=SOLANA_TOPIC_CB),
                    InlineKeyboardButton("Wallet 🔐", callback_data=WALLET_TOPIC_CB),
                ]
            ]

            # Send the help text
            await update.message.reply_text(
                HELP_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )

            # Show main menu after help
            await self.send_main_menu(update, context)

        return SELECT_OPTION

    async def send_main_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = "What would you like to do next?",
    ):
        keyboard = [
            [
                InlineKeyboardButton("Solana 🔍", callback_data=SOLANA_TOPIC_CB),
                InlineKeyboardButton("Wallet 🔐", callback_data=WALLET_TOPIC_CB),
            ],
            [InlineKeyboardButton("Help ❓", callback_data=HELP_TOPIC_CB)],
        ]
        if (
            update.callback_query
            and update.callback_query.message
            and update.callback_query.message.chat
        ):
            await context.bot.send_message(
                chat_id=update.callback_query.message.chat.id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif update.message:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def check_rate(self, update: Update, cmd: str) -> bool:
        if not update.effective_user:
            return True
        uid = str(update.effective_user.id)
        if self.rate_limiter.is_rate_limited(uid, cmd):
            cooldown = self.rate_limiter.get_cooldown_time(uid, cmd)
            if update.message:
                await update.message.reply_text(
                    f"Rate limit exceeded. Try again in {cooldown} seconds."
                )
            return False
        return True

    async def param_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return SELECT_OPTION

        # 提取命令
        message_text = update.message.text.strip()
        # 检查是否是命令格式
        if not message_text.startswith("/"):
            # 如果不是命令格式，交给input_handler处理
            return await self.input_handler(update, context)

        # 解析命令和参数
        parts = message_text[1:].split(maxsplit=1)
        cmd = parts[0] if parts else ""

        # 设置参数（如果有）
        if len(parts) > 1:
            context.args = parts[1].split()
        elif not hasattr(context, "args") or context.args is None:
            context.args = []

        if not await self.check_rate(update, cmd):
            return SELECT_OPTION

        # 检查命令是否存在
        if cmd not in self.processor.handlers:
            await update.message.reply_text(
                f"Unknown command: /{cmd}. Type /help for a list of commands."
            )
            await self.send_main_menu(update, context)
            return SELECT_OPTION

        # 检查是否需要参数但没有提供
        if self.processor.requires_param(cmd) and not context.args:
            if context.user_data is not None:
                context.user_data["pending"] = cmd
                prompt = self.processor.get_prompt(cmd)
                if prompt:
                    await update.message.reply_text(prompt)
            return WAITING_PARAM

        # 执行命令
        try:
            await self.processor.execute(cmd, update, context)
        except Exception as e:
            logger.error(f"Error executing command {cmd}: {e}")
            await update.message.reply_text(f"Error executing command /{cmd}: {str(e)}")

        await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def continue_with_param(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not update.message or not update.message.text:
            return SELECT_OPTION
        if context.user_data is None or "pending" not in context.user_data:
            await update.message.reply_text("No pending command.")
            await self.send_main_menu(update, context)
            return SELECT_OPTION
        cmd = context.user_data.pop("pending")
        user_input = update.message.text.strip()
        if user_input.lower() == "cancel":
            await update.message.reply_text("Operation cancelled.")
            await self.send_main_menu(update, context)
            return SELECT_OPTION

        # 检查输入是否以"/"开头，如果是，可能是用户尝试输入新命令而不是参数
        if user_input.startswith("/"):
            await update.message.reply_text(
                "It seems you're trying to enter a new command. Previous command cancelled."
            )
            await self.send_main_menu(update, context)
            # 处理新命令
            new_cmd = user_input[1:].split()[0]
            if new_cmd in self.processor.handlers:
                context.args = (
                    user_input[1:].split()[1:]
                    if len(user_input[1:].split()) > 1
                    else []
                )
                await self.processor.execute(new_cmd, update, context)
            return SELECT_OPTION

        # 处理普通参数
        context.args = user_input.split()
        try:
            await self.processor.execute(cmd, update, context)
        except Exception as e:
            logger.error(f"Error executing command {cmd}: {e}")
            await update.message.reply_text(
                f"Error: {str(e)}\nPlease try again with valid parameters."
            )

        await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.effective_user:
            name = update.effective_user.first_name or "there"
            await update.message.reply_text(
                f"👋 Hello {name}! Welcome to Solana Assistant Bot.\n\n"
                "I'm your personal assistant for exploring the Solana blockchain. "
                "You can interact with me using commands or natural language.\n\n"
                "Please select an option below to get started:"
            )
            await self.send_main_menu(update, context, "What would you like to do?")
        return SELECT_OPTION

    async def handle_topic_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        if not query or not query.message or not query.from_user:
            return SELECT_OPTION
        await query.answer()
        if query.data == SOLANA_TOPIC_CB:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "SOL Balance 💰", callback_data=f"{CMD_PREFIX}sol_balance"
                    ),
                    InlineKeyboardButton(
                        "Token Info 🔎", callback_data=f"{CMD_PREFIX}token_info"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Transaction 📝", callback_data=f"{CMD_PREFIX}transaction"
                    ),
                    InlineKeyboardButton(
                        "Recent Txs 📜", callback_data=f"{CMD_PREFIX}recent_tx"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Network Status 🌐", callback_data=f"{CMD_PREFIX}network_status"
                    ),
                    InlineKeyboardButton(
                        "Latest Block 📊", callback_data=f"{CMD_PREFIX}latest_block"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Validators ✅", callback_data=f"{CMD_PREFIX}validators"
                    ),
                    InlineKeyboardButton(
                        "Current Slot 🔢", callback_data=f"{CMD_PREFIX}slot"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "« Back to Main Menu", callback_data=HELP_TOPIC_CB
                    )
                ],
            ]
            await query.edit_message_text(
                "📊 Solana Blockchain Commands:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif query.data == WALLET_TOPIC_CB:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Add Wallet ➕", callback_data=f"{CMD_PREFIX}add_wallet"
                    ),
                    InlineKeyboardButton(
                        "Remove Wallet ➖", callback_data=f"{CMD_PREFIX}remove_wallet"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "My Wallets 📋", callback_data=f"{CMD_PREFIX}my_wallets"
                    ),
                    InlineKeyboardButton(
                        "Verify Wallet ✓", callback_data=f"{CMD_PREFIX}verify_wallet"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "My Balance 💵", callback_data=f"{CMD_PREFIX}my_balance"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "« Back to Main Menu", callback_data=HELP_TOPIC_CB
                    )
                ],
            ]
            await query.edit_message_text(
                "🔐 Wallet Management Commands:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif query.data == HELP_TOPIC_CB:
            # Use the shared HELP_TEXT constant
            keyboard = [
                [
                    InlineKeyboardButton("Solana 🔍", callback_data=SOLANA_TOPIC_CB),
                    InlineKeyboardButton("Wallet 🔐", callback_data=WALLET_TOPIC_CB),
                ]
            ]
            await query.edit_message_text(
                HELP_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
        return SELECT_OPTION

    async def handle_command_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        if not query or not query.message or not query.from_user or not query.data:
            return SELECT_OPTION
        await query.answer()
        cmd = query.data[len(CMD_PREFIX) :]
        if not await self.check_rate(update, cmd):
            return SELECT_OPTION
        if self.processor.requires_param(cmd):
            prompt = (
                self.processor.get_prompt(cmd)
                or f"Please provide parameters for /{cmd}:"
            )
            await query.edit_message_text(prompt)
            if context.user_data is not None:
                context.user_data["pending"] = cmd
            return WAITING_PARAM
        if query.message and query.message.chat:
            chat_id = query.message.chat.id
            await query.edit_message_text(f"Executing /{cmd}...")
            temp_message = await context.bot.send_message(
                chat_id=chat_id, text=f"Processing /{cmd}..."
            )
            mock_update = Update(update_id=update.update_id, message=temp_message)
            await self.processor.execute(cmd, mock_update, context)
            await self.send_main_menu(update, context)
        else:
            logger.error("Could not execute command: chat not available")
            await query.edit_message_text(
                f"Error executing command. Please try /{cmd} directly."
            )
            await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def input_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return SELECT_OPTION

        # 检查是否有挂起的命令等待参数输入 - 如果有，应该由continue_with_param处理而不是这里
        if context.user_data is not None and "pending" in context.user_data:
            # 将控制权转交给continue_with_param
            return await self.continue_with_param(update, context)

        if not await self.check_rate(update, "natural_language"):
            return SELECT_OPTION

        user_input = update.message.text.strip()
        if not user_input:
            await update.message.reply_text("Please enter a valid message.")
            return SELECT_OPTION

        # 检查是否是命令形式（以/开头）
        if user_input.startswith("/"):
            cmd_parts = user_input[1:].split(maxsplit=1)
            cmd = cmd_parts[0] if cmd_parts else ""
            if cmd in self.processor.handlers:
                context.args = cmd_parts[1].split() if len(cmd_parts) > 1 else []
                await self.param_handler(update, context)
                return SELECT_OPTION

        await update.message.reply_text("Processing your request...")
        cmd_line = await self.openai_service.convert_to_command(user_input)
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        if cmd == "cannot complete" or not cmd:
            await update.message.reply_text(
                "I couldn't understand your request. Please try again with more specific details or use a command."
            )
            await self.send_main_menu(update, context)
            return SELECT_OPTION
        logger.info(
            f"Converted natural language '{user_input}' to command '/{cmd}'"
            + (f" with args '{parts[1]}'" if len(parts) > 1 else "")
        )
        context.args = parts[1].split() if len(parts) > 1 else []
        if not await self.check_rate(update, cmd):
            await self.send_main_menu(update, context)
            return SELECT_OPTION
        if self.processor.requires_param(cmd) and not context.args:
            if context.user_data is not None:
                context.user_data["pending"] = cmd
                prompt = self.processor.get_prompt(cmd)
                if prompt:
                    await update.message.reply_text(prompt)
            return WAITING_PARAM
        if cmd in self.processor.handlers:
            await self.processor.execute(cmd, update, context)
            await self.send_main_menu(update, context)
            return SELECT_OPTION
        else:
            await update.message.reply_text(
                "Command not recognized. Type /help for assistance."
            )
            await self.send_main_menu(update, context)
            return SELECT_OPTION

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text("Cancelled.")
            if context.user_data is not None:
                context.user_data.pop("pending", None)
            await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text(
                "Please use valid commands or natural language. Type /help for assistance."
            )
            await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def setup_commands(self, app: Application):
        cmd_list = get_command_list()
        cmds = [BotCommand(cmd, desc) for cmd, desc in cmd_list]
        await app.bot.set_my_commands(cmds)
        logger.info("Commands set up.")

    def run(self):
        logger.info("Starting Solana Telegram Bot")
        self.app.run_polling()
