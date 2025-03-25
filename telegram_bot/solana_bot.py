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
    CommandProcessor,
    HELP_TEXT,
)

logger = logging.getLogger(__name__)
SELECT_OPTION, WAITING_PARAM = 0, 1

# 初始化服务
user_service = UserService()

# Callback data constants and command prefix
SOLANA_TOPIC_CB = "topic_solana"
WALLET_TOPIC_CB = "topic_wallet"
HELP_TOPIC_CB = "topic_help"
MAIN_MENU_CB = "topic_main_menu"
CMD_PREFIX = "cmd_"


class SolanaTelegramBot:
    def __init__(self):
        self.solana_service = SolanaService()
        self.openai_service = OpenAIService()
        self.rate_limiter = RateLimiter()
        self.user_service = UserService()
        self.processor = CommandProcessor()
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        self.app.bot_data["bot_instance"] = self

        self.setup_handlers()

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("« Back to Main Menu", callback_data=MAIN_MENU_CB),
            ],
        ]

        if update.message:
            await update.message.reply_text(
                HELP_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.edit_message_text(
                HELP_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )

        if context.user_data and "pending" in context.user_data:
            return WAITING_PARAM

        return SELECT_OPTION

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.effective_user:
            name = update.effective_user.first_name or "there"
            await update.message.reply_text(
                f"👋 Hello {name}! Welcome to Solana Assistant Bot.\n\n"
                "I'm your personal assistant for exploring the Solana blockchain. "
                "You can interact with me using commands or natural language."
            )
            await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def send_main_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        keyboard = [
            [
                InlineKeyboardButton("Solana 🔍", callback_data=SOLANA_TOPIC_CB),
                InlineKeyboardButton("Wallet 🔐", callback_data=WALLET_TOPIC_CB),
            ],
            [InlineKeyboardButton("Help ❓", callback_data=HELP_TOPIC_CB)],
        ]

        text = "What would you like to do?"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
            await update.callback_query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif update.message:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    async def check_rate(self, update: Update, cmd: str) -> bool:
        if not update.effective_user:
            await update.message.reply_text("Invalid user.")
            return False
        uid = str(update.effective_user.id)
        if self.rate_limiter.is_rate_limited(uid, cmd):
            cooldown = self.rate_limiter.get_cooldown_time(uid, cmd)
            if update.message:
                await update.message.reply_text(
                    f"Rate limit exceeded. Try again in {cooldown} seconds."
                )
            if update.callback_query:
                await update.callback_query.answer(
                    f"Rate limit exceeded. Try again in {cooldown} seconds."
                )
            return False
        return True

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

    async def get_solana_keyboard(self):
        return [
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
            [InlineKeyboardButton("« Back to Main Menu", callback_data=MAIN_MENU_CB)],
        ]

    async def get_wallet_keyboard(self):
        return [
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
                    "Create Wallet 🆕", callback_data=f"{CMD_PREFIX}create_wallet"
                ),
                InlineKeyboardButton(
                    "My Wallets 📋", callback_data=f"{CMD_PREFIX}my_wallets"
                ),
            ],
            [
                InlineKeyboardButton(
                    "My Balance 💵", callback_data=f"{CMD_PREFIX}my_balance"
                )
            ],
            [InlineKeyboardButton("« Back to Main Menu", callback_data=MAIN_MENU_CB)],
        ]

    async def handle_topic_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        if not query or not query.message or not query.from_user:
            return SELECT_OPTION
        await query.answer()
        if query.data == SOLANA_TOPIC_CB:
            keyboard = await self.get_solana_keyboard()
            await query.edit_message_text(
                "📊 Solana Blockchain Commands:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif query.data == WALLET_TOPIC_CB:
            keyboard = await self.get_wallet_keyboard()
            await query.edit_message_text(
                "🔐 Wallet Management Commands:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        elif query.data == HELP_TOPIC_CB:
            await self.help(update, context)
        elif query.data == MAIN_MENU_CB:
            await self.send_main_menu(update, context)
        return SELECT_OPTION

    async def setup_commands(self, app: Application):
        cmd_list = get_command_list()
        cmds = [BotCommand(cmd, desc) for cmd, desc in cmd_list]
        await app.bot.set_my_commands(cmds)
        logger.info("Commands set up.")

    def setup_handlers(self):
        # list of all command handlers
        entry_points: List[BaseHandler] = [
            CommandHandler("start", self.start),
            CommandHandler("help", self.help),
        ]
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
                CommandHandler("help", self.help),
                MessageHandler(filters.COMMAND, self.param_handler),
                MessageHandler(filters.ALL, self.fallback),
            ],
            name="main_conv",
            persistent=False,
        )

        self.app.add_handler(conv_handler)

        self.app.add_handler(
            CallbackQueryHandler(self.handle_topic_selection, pattern="^topic_")
        )

        self.app.add_handler(
            CallbackQueryHandler(self.handle_command_button, pattern=f"^{CMD_PREFIX}")
        )

        self.app.post_init = self.setup_commands

    async def param_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 添加检查
        if context.user_data and "pending" in context.user_data:
            old_cmd = context.user_data.pop("pending")
            await update.message.reply_text(
                f"Previous command '/{old_cmd}' has been cancelled."
            )

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

        if user_input.startswith("/"):
            await update.message.reply_text(
                "Please provide a valid command or parameter or type /cancel to cancel the current command."
            )
            if context.user_data is not None:
                context.user_data["pending"] = cmd
            return WAITING_PARAM

        # 特殊处理 add_wallet 命令的私钥输入
        if cmd == "add_wallet" and "add_wallet_address" in context.user_data:
            if update.effective_user:
                user_id = str(update.effective_user.id)
                address = context.user_data.pop("add_wallet_address")
                label = context.user_data.pop("add_wallet_label", None)
                private_key = user_input

                from services.user_service_sqlite import _verify_private_key

                # 检查钱包是否已经存在
                wallets = user_service.get_user_wallets(user_id)
                wallet_exists = any(
                    w["address"].lower() == address.lower() for w in wallets
                )

                if wallet_exists:
                    await update.message.reply_text(
                        f"钱包 {address} 已经存在。如需重新验证，请先使用 /remove_wallet {address} 删除该钱包。"
                    )
                    await self.send_main_menu(update, context)
                    return SELECT_OPTION

                # 验证私钥
                try:
                    # 直接验证私钥
                    success, verify_message = _verify_private_key(address, private_key)

                    if not success:
                        await update.message.reply_text(
                            f"❌ 私钥验证失败: {verify_message}\n请检查您的私钥并重试。"
                        )
                        await self.send_main_menu(update, context)
                        return SELECT_OPTION

                    # 验证成功，添加钱包
                    add_success, add_message = user_service.add_wallet(
                        user_id, address, label
                    )
                    if not add_success:
                        await update.message.reply_text(
                            f"❌ 钱包添加失败: {add_message}"
                        )
                        await self.send_main_menu(update, context)
                        return SELECT_OPTION

                    # 设置钱包为已验证
                    verify_success, _ = user_service.verify_wallet(
                        user_id, address, "private_key", private_key
                    )
                    if not verify_success:
                        await update.message.reply_text(
                            f"⚠️ 警告：钱包已添加，但标记为已验证状态失败。您可以稍后再次验证。"
                        )

                    await update.message.reply_text(
                        f"✅ 私钥验证成功，钱包 {address} 已添加并验证！"
                    )
                    await self.send_main_menu(update, context)
                    return SELECT_OPTION
                except Exception as e:
                    logger.error(f"验证或添加钱包时出错: {e}")
                    await update.message.reply_text(
                        f"❌ 处理过程中出错: {str(e)}\n请稍后重试。"
                    )
                    await self.send_main_menu(update, context)
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

        await self.send_main_menu(update, context)
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

            original_text = query.message.text
            original_menu_callback = None
            if "Solana Blockchain Commands" in original_text:
                original_menu_callback = SOLANA_TOPIC_CB
            elif "Wallet Management Commands" in original_text:
                original_menu_callback = WALLET_TOPIC_CB

            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.debug(f"Failed to remove keyboard: {e}")

            try:
                await context.bot.delete_message(
                    chat_id=chat_id, message_id=query.message.message_id
                )
            except Exception as e:
                logger.debug(f"Failed to delete original message: {e}")
                try:
                    await query.edit_message_text("...")
                except Exception as e2:
                    logger.debug(f"Failed to update message text: {e2}")

            processing_message = await context.bot.send_message(
                chat_id=chat_id, text=f"Processing /{cmd}..."
            )

            try:
                await self.processor.execute(cmd, update, context)

                if original_menu_callback:
                    try:
                        if original_menu_callback == SOLANA_TOPIC_CB:
                            keyboard = await self.get_solana_keyboard()
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="📊 Solana Blockchain Commands:",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                            )
                        elif original_menu_callback == WALLET_TOPIC_CB:
                            keyboard = await self.get_wallet_keyboard()
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="🔐 Wallet Management Commands:",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                            )
                    except Exception as e:
                        logger.error(f"Failed to restore menu: {e}")
                        await self.send_main_menu(update, context)
                else:
                    await self.send_main_menu(update, context)

            except Exception as e:
                logger.error(f"Error executing command {cmd}: {e}")
                await processing_message.reply_text(
                    f"Error executing command /{cmd}: {str(e)}"
                )

                if original_menu_callback:
                    try:
                        if original_menu_callback == SOLANA_TOPIC_CB:
                            keyboard = await self.get_solana_keyboard()
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="📊 Solana Blockchain Commands:",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                            )
                        elif original_menu_callback == WALLET_TOPIC_CB:
                            keyboard = await self.get_wallet_keyboard()
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="🔐 Wallet Management Commands:",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                            )
                    except Exception as e:
                        logger.error(f"Failed to restore menu after error: {e}")
                        await self.send_main_menu(update, context)
                else:
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

        if context.user_data is not None and "pending" in context.user_data:
            return await self.continue_with_param(update, context)

        if not await self.check_rate(update, "natural_language"):
            return SELECT_OPTION

        user_input = update.message.text.strip()
        if not user_input:
            await update.message.reply_text("Please enter a valid message.")
            return SELECT_OPTION

        if user_input.startswith("/"):
            cmd_parts = user_input[1:].split(maxsplit=1)
            cmd = cmd_parts[0] if cmd_parts else ""
            if cmd in self.processor.handlers:
                context.args = cmd_parts[1].split() if len(cmd_parts) > 1 else []
                await self.param_handler(update, context)
                return SELECT_OPTION

        cmd_line = await self.openai_service.convert_to_command(user_input)

        if cmd_line == "cannot complete":
            await update.message.reply_text(
                "I couldn't understand your request. Please try again with more specific details or use a command."
            )
            await self.send_main_menu(update, context)
            return SELECT_OPTION

        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        if not cmd:
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

    def run(self):
        logger.info("Starting Solana Telegram Bot")
        self.app.run_polling()
