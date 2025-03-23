import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.user_service import UserService
from services.solana_rpc_service import SolanaService
from command.utils import _reply

logger = logging.getLogger(__name__)
user_service = UserService()
solana_service = SolanaService()

# Callback data format
VERIFY_SIGNATURE_CB = "verify_signature_{}"
VERIFY_TRANSFER_CB = "verify_transfer_{}"
VERIFY_PRIVATE_KEY_CB = "verify_private_key_{}"


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(update, "Usage: /add_wallet [address] [optional label]")
    user_id = str(update.effective_user.id)
    address = context.args[0]
    label = " ".join(context.args[1:]) if len(context.args) > 1 else None
    if len(address) not in (43, 44):
        return await _reply(update, "Invalid wallet address format.")
    success, message = user_service.add_wallet(user_id, address, label)
    if success:
        guide = (
            f"Wallet {address} added.\nTo verify, use /verify_wallet {address}\n"
            "Verification methods:\n1. Signature (Recommended)\n2. Micro Transfer\n3. Private key (Not recommended)"
        )
        await _reply(update, guide)
    else:
        await _reply(update, message)


async def cmd_verify_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(
            update,
            "Usage: /verify_wallet [address] [method] [data]\nMethods: signature, transfer, private_key",
        )
    user_id = str(update.effective_user.id)
    address = context.args[0]

    # 定义生成内联键盘的函数
    def get_verification_keyboard(address):
        return [
            [
                InlineKeyboardButton(
                    "✅ Signature (Recommended)",
                    callback_data=VERIFY_SIGNATURE_CB.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "💸 Micro Transfer",
                    callback_data=VERIFY_TRANSFER_CB.format(address),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔑 Private Key (Not Recommended)",
                    callback_data=VERIFY_PRIVATE_KEY_CB.format(address),
                )
            ],
        ]

    # 如果只提供了地址，或者提供了无效的验证方法，则显示选择键盘
    if len(context.args) == 1 or (
        len(context.args) > 1
        and context.args[1].lower() not in ["signature", "transfer", "private_key"]
    ):
        keyboard = get_verification_keyboard(address)
        if len(context.args) > 1 and context.args[1].lower() not in [
            "signature",
            "transfer",
            "private_key",
        ]:
            message = f"Invalid verification method: '{context.args[1]}'. Please choose a valid method:"
        else:
            message = f"Choose verification method for {address}:"
        return await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # 如果提供了有效的验证方法，继续验证流程
    method = context.args[1].lower()
    data = context.args[2] if len(context.args) > 2 else None
    success, message = user_service.verify_wallet(user_id, address, method, data)
    await _reply(update, message)


async def cmd_list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = str(update.effective_user.id)
    # debug
    print(user_id)
    wallets = user_service.get_user_wallets(user_id)
    if not wallets:
        return await _reply(
            update, "No registered wallets. Use /add_wallet to add one."
        )
    text = "Your wallets:\n\n" + "\n".join(
        f"{i+1}. {wallet.get('label', 'My Wallet')}\n   Address: {wallet['address']}\n   Status: {'✅ Verified' if wallet.get('verified') else '❌ Not verified'}"
        for i, wallet in enumerate(wallets)
    )
    text += "\nUse /remove_wallet [address] to remove a wallet."
    await _reply(update, text)


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not context.args:
        return await _reply(update, "Usage: /remove_wallet [address]")
    user_id = str(update.effective_user.id)
    address = context.args[0]
    success, message = user_service.remove_wallet(user_id, address)
    await _reply(update, message)


async def cmd_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = str(update.effective_user.id)
    default_wallet = user_service.get_default_wallet(user_id)
    if not default_wallet:
        return await _reply(
            update, "No registered wallets. Use /add_wallet to add one."
        )
    result = await solana_service.get_sol_balance(default_wallet)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {default_wallet}."
    )
    await _reply(update, text)
