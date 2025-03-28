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
from command.wallet_commands import (
    _handle_send_wallet_selection,
    _handle_send_confirmation,
    _handle_send_destination,
    _handle_send_amount,
    SEND_WALLET_PREFIX,
    SEND_CONFIRM_YES,
    SEND_CONFIRM_NO,
    SEND_SELECT_SOURCE,
    SEND_INPUT_DESTINATION,
    SEND_INPUT_AMOUNT,
    SEND_CONFIRM,
    cmd_send_sol,
)

# Import Privy wallet commands
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

logger = logging.getLogger(__name__)
SELECT_OPTION, WAITING_PARAM = 0, 1

# 初始化服务
user_service = UserService()

# Callback data constants and command prefix
SOLANA_TOPIC_CB = "topic_solana"
WALLET_TOPIC_CB = "topic_wallet"
PRIVY_WALLET_TOPIC_CB = "topic_privy_wallet"  # New topic for Privy wallets
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
        if not update.effective_chat:
            return SELECT_OPTION

        keyboard = [
            [
                InlineKeyboardButton(
                    "📊 Solana Blockchain", callback_data=SOLANA_TOPIC_CB
                ),
                InlineKeyboardButton("🔑 Wallets", callback_data=WALLET_TOPIC_CB),
            ],
            [
                InlineKeyboardButton(
                    "🔐 Privy Wallets", callback_data=PRIVY_WALLET_TOPIC_CB
                ),
                InlineKeyboardButton("❓ Help", callback_data=HELP_TOPIC_CB),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.edit_text(
                    "✨ Welcome to the Solana Blockchain Assistant! ✨\n\n"
                    "Please select an option:",
                    reply_markup=reply_markup,
                )
            elif update.message:
                await update.message.reply_text(
                    "✨ Welcome to the Solana Blockchain Assistant! ✨\n\n"
                    "Please select an option:",
                    reply_markup=reply_markup,
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="✨ Welcome to the Solana Blockchain Assistant! ✨\n\n"
                    "Please select an option:",
                    reply_markup=reply_markup,
                )
        except Exception as e:
            logger.error(f"Error sending main menu: {e}")

        return SELECT_OPTION

    async def send_main_menu_as_new_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """发送主菜单作为新消息，而不替换现有消息"""
        keyboard = [
            [
                InlineKeyboardButton("Solana 🔍", callback_data=SOLANA_TOPIC_CB),
                InlineKeyboardButton("Wallet 🔐", callback_data=WALLET_TOPIC_CB),
            ],
            [InlineKeyboardButton("Help ❓", callback_data=HELP_TOPIC_CB)],
        ]

        text = "What would you like to do?"

        # 获取chat_id
        chat_id = None
        if update.callback_query and update.callback_query.message:
            chat_id = update.callback_query.message.chat_id
        elif update.message:
            chat_id = update.message.chat_id

        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            logger.error("Could not determine chat_id to send main menu")

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
                # Clean up any pending command
                context.user_data.pop("pending", None)

                # Clean up any send_sol state
                if "send_sol_state" in context.user_data:
                    context.user_data.pop("send_sol_state", None)
                    context.user_data.pop("send_sol_source", None)
                    context.user_data.pop("send_sol_destination", None)
                    context.user_data.pop("send_sol_amount", None)

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
                ),
                InlineKeyboardButton(
                    "Send SOL 💸", callback_data=f"{CMD_PREFIX}send_sol"
                ),
            ],
            [InlineKeyboardButton("« Back to Main Menu", callback_data=MAIN_MENU_CB)],
        ]

    async def get_privy_wallet_keyboard(self):
        """Generate keyboard for Privy wallet commands."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "Create Ethereum/Solana Wallet",
                    callback_data=f"{CMD_PREFIX}create_privy_wallet",
                )
            ],
            [
                InlineKeyboardButton(
                    "Create Solana Wallet",
                    callback_data=f"{CMD_PREFIX}create_privy_solana",
                )
            ],
            [
                InlineKeyboardButton(
                    "List My Privy Wallets", callback_data=f"{CMD_PREFIX}privy_wallets"
                )
            ],
            [
                InlineKeyboardButton(
                    "Check Wallet Balance", callback_data=f"{CMD_PREFIX}privy_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    "Send Funds", callback_data=f"{CMD_PREFIX}privy_send"
                )
            ],
            [
                InlineKeyboardButton(
                    "View Transaction History",
                    callback_data=f"{CMD_PREFIX}privy_tx_history",
                )
            ],
            [
                InlineKeyboardButton("« Back to Main Menu", callback_data=MAIN_MENU_CB),
            ],
        ]
        return keyboard

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
        elif query.data == PRIVY_WALLET_TOPIC_CB:
            keyboard = await self.get_privy_wallet_keyboard()
            await query.edit_message_text(
                "🔐 Privy Wallet Management Commands:",
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
            if (
                cmd != "send_sol" and cmd != "privy_send"
            ):  # Skip send_sol and privy_send as we'll handle them separately
                entry_points.append(CommandHandler(cmd, self.param_handler))

        # Import send_sol command states
        from command.wallet_commands import (
            SEND_SELECT_SOURCE,
            SEND_INPUT_DESTINATION,
            SEND_INPUT_AMOUNT,
            SEND_CONFIRM,
            cmd_send_sol,
            _handle_send_destination,
            _handle_send_amount,
            _handle_send_wallet_selection,
        )

        # Create a separate conversation handler for send_sol command
        send_sol_handler = ConversationHandler(
            entry_points=[
                CommandHandler("send_sol", cmd_send_sol),
                CallbackQueryHandler(
                    self.handle_command_button, pattern=f"^{CMD_PREFIX}send_sol$"
                ),
                # Add a message handler that matches the NLP-detected send_sol pattern
                # This is handled by the input_handler which redirects to cmd_send_sol
            ],
            states={
                SEND_SELECT_SOURCE: [
                    CallbackQueryHandler(
                        _handle_send_wallet_selection,
                        pattern=f"^{SEND_WALLET_PREFIX}.*",
                    ),
                    CallbackQueryHandler(
                        _handle_send_wallet_selection, pattern="^send_cancel$"
                    ),
                ],
                SEND_INPUT_DESTINATION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, _handle_send_destination
                    )
                ],
                SEND_INPUT_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_send_amount)
                ],
                SEND_CONFIRM: [
                    CallbackQueryHandler(
                        _handle_send_confirmation,
                        pattern=f"^{SEND_CONFIRM_YES}$|^{SEND_CONFIRM_NO}$",
                    ),
                ],
                SELECT_OPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handler)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start),
                CommandHandler("help", self.help),
            ],
            name="send_sol_conv",
            persistent=False,
            per_message=True,
            per_chat=True,
            allow_reentry=True,
        )

        # Add send_sol handler first to give it priority
        self.app.add_handler(send_sol_handler)

        # Add a direct callback handler for wallet selection buttons for NLP-triggered flows
        self.app.add_handler(
            CallbackQueryHandler(
                _handle_send_wallet_selection, pattern=f"^{SEND_WALLET_PREFIX}"
            )
        )

        # Create a conversation handler for privy_send command
        privy_send_handler = ConversationHandler(
            entry_points=[
                CommandHandler("privy_send", cmd_privy_send),
                CallbackQueryHandler(
                    self.handle_command_button, pattern=f"^{CMD_PREFIX}privy_send$"
                ),
            ],
            states={
                PRIVY_SEND_SELECT_SOURCE: [
                    CallbackQueryHandler(
                        handle_privy_wallet_selection,
                        pattern=f"^{PRIVY_SEND_WALLET_PREFIX}.*",
                    ),
                    CallbackQueryHandler(self.cancel, pattern="^cancel$"),
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
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handler)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start),
                CommandHandler("help", self.help),
            ],
            name="privy_send_conv",
            persistent=False,
            per_message=True,
            per_chat=True,
            allow_reentry=True,
        )

        # Add privy_send handler
        self.app.add_handler(privy_send_handler)

        # Add a direct callback handler for Privy wallet selection buttons
        self.app.add_handler(
            CallbackQueryHandler(
                handle_privy_wallet_selection, pattern=f"^{PRIVY_SEND_WALLET_PREFIX}"
            )
        )

        # Main conversation handler
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
                wallets = self.user_service.get_user_wallets(user_id)
                wallet_exists = any(
                    w["address"].lower() == address.lower() for w in wallets
                )

                if wallet_exists:
                    await update.message.reply_text(
                        f"Wallet {address} already exists. To re-verify, please first remove the wallet using /remove_wallet {address}."
                    )
                    await self.send_main_menu(update, context)
                    return SELECT_OPTION

                # 验证私钥
                try:
                    # 直接验证私钥
                    success, verify_message = _verify_private_key(address, private_key)

                    if not success:
                        await update.message.reply_text(
                            f"❌ Private key verification failed: {verify_message}\nPlease check your private key and try again."
                        )
                        await self.send_main_menu(update, context)
                        return SELECT_OPTION

                    # 验证成功，添加钱包
                    add_success, add_message = self.user_service.add_wallet(
                        user_id, address, label
                    )
                    if not add_success:
                        await update.message.reply_text(
                            f"❌ Failed to add wallet: {add_message}"
                        )
                        await self.send_main_menu(update, context)
                        return SELECT_OPTION

                    # 设置钱包为已验证
                    verify_success, _ = self.user_service.verify_wallet(
                        user_id, address, "private_key", private_key
                    )
                    if not verify_success:
                        await update.message.reply_text(
                            f"⚠️ Warning: Wallet has been added, but marking it as verified failed. You can verify it again later."
                        )

                    await update.message.reply_text(
                        f"✅ Private key verification successful, wallet {address} has been added and verified!"
                    )
                    await self.send_main_menu(update, context)
                    return SELECT_OPTION
                except Exception as e:
                    logger.error(f"Error verifying or adding wallet: {e}")
                    await update.message.reply_text(
                        f"❌ Error occurred during processing: {str(e)}\nPlease try again later."
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

        # For add_wallet command, don't show the main menu as it's already shown in the command handler
        if cmd == "add_wallet":
            # Skip showing main menu again - it's already shown in the command handler
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

        # Special handling for send_sol command from menu button
        if cmd == "send_sol":
            # This will be handled by the ConversationHandler,
            # we just remove the keyboard and let cmd_send_sol handle the rest
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            try:
                await query.edit_message_text("Starting send SOL operation...")
            except Exception:
                pass

            # Return to the ConversationHandler
            from command.wallet_commands import cmd_send_sol

            # Set a flag to prevent main menu from being shown during this flow
            if context.user_data is not None:
                context.user_data["in_send_sol_flow"] = True

            return await cmd_send_sol(update, context)

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

                # For add_wallet command, don't show the main menu if it's waiting for input
                if (
                    cmd == "add_wallet"
                    and context.user_data
                    and "pending" in context.user_data
                ):
                    # Skip showing main menu while waiting for private key input
                    return WAITING_PARAM

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

        # Check if we're in the send_sol flow
        if context.user_data and context.user_data.get("in_send_sol_flow", False):
            # If we're in the send_sol flow, just pass the message to the conversation handler
            # It will be handled by the appropriate state handler
            user_input = update.message.text.strip()
            logger.info(f"In send_sol flow, passing message: {user_input}")
            # Don't return SELECT_OPTION here as it might interfere with the conversation
            return

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

        # Special handling for send_sol command
        if cmd == "send_sol":
            logger.info("NLP triggered send_sol command, using direct handler")
            from command.wallet_commands import cmd_send_sol

            # Set a flag to prevent main menu from being shown during this flow
            if context.user_data is not None:
                context.user_data["in_send_sol_flow"] = True

            return await cmd_send_sol(update, context)

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
