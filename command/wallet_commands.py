import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.user_service import UserService
from services.solana_rpc_service import SolanaService
from services.user_service_sqlite import _verify_private_key
from command.utils import _reply
from nacl.signing import SigningKey
import base58

logger = logging.getLogger(__name__)
user_service = UserService()
solana_service = SolanaService()


async def cmd_create_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)

    # Generate new keypair
    try:
        # Create new random keypair
        signing_key = SigningKey.generate()
        private_key = base58.b58encode(bytes(signing_key)).decode("utf-8")
        public_key = base58.b58encode(bytes(signing_key.verify_key)).decode("utf-8")

        # Create label (default or from args)
        label = None
        if context.args:
            label = context.args[0]

        # Add wallet to user's account and verify it
        success, message = user_service.add_wallet(user_id, public_key, label)
        if not success:
            return await _reply(
                update, f"❌ Failed to add wallet: {message}", context=context
            )

        # Verify the wallet
        verify_success, _ = user_service.verify_wallet(
            user_id, public_key, "private_key", private_key
        )

        await _reply(
            update,
            f"✅ New wallet created!\n\n📋 Address: `{public_key}`\n\n🔑 Private Key: `{private_key}`\n\n⚠️ **SAVE YOUR PRIVATE KEY** - This is the only time it will be shown to you.",
            parse_mode="Markdown",
            context=context,
        )
    except Exception as e:
        logger.error(f"Error creating wallet: {e}")
        await _reply(update, f"❌ Failed to create wallet: {str(e)}", context=context)


async def cmd_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    if not context.args:
        return await _reply(
            update,
            "Usage: /add_wallet [address] [optional label] [private_key]]",
            context=context,
        )

    user_id = str(effective_user.id)
    address = context.args[0]

    # 验证钱包地址格式
    if len(address) not in (43, 44):
        return await _reply(update, "无效的钱包地址格式。", context=context)

    # 检查参数数量确定是否提供了标签和私钥
    if len(context.args) == 1:  # 只有地址
        label = None
        private_key = None
    elif len(context.args) == 2:  # 地址和第二个参数(可能是标签或私钥)
        # 判断第二个参数是标签还是私钥
        if len(context.args[1]) >= 32:  # 如果长度≥32，可能是私钥
            label = None
            private_key = context.args[1]
        else:  # 否则视为标签
            label = context.args[1]
            private_key = None
    else:  # 地址、标签和私钥都有
        label = context.args[1]
        private_key = context.args[2]

    # 如果没有私钥，保存当前状态并请求用户输入私钥
    if not private_key:
        if context.user_data is not None:
            context.user_data["pending"] = "add_wallet"
            context.user_data["add_wallet_address"] = address
            context.user_data["add_wallet_label"] = label

            await _reply(
                update, f"请输入您的私钥以验证钱包 {address} 的所有权:", context=context
            )
            return
        return await _reply(
            update,
            "无法保存会话状态，请使用完整命令: /add_wallet [address] [label] [private_key]",
            context=context,
        )

    # 有私钥，先验证再添加
    # 先检查钱包是否已经存在
    wallets = user_service.get_user_wallets(user_id)
    wallet_exists = any(w["address"].lower() == address.lower() for w in wallets)

    if wallet_exists:
        return await _reply(
            update,
            f"钱包 {address} 已经存在。如需重新验证，请先使用 /remove_wallet {address} 删除该钱包。",
            context=context,
        )

    # 验证私钥
    try:
        # 直接使用_verify_private_key函数验证
        success, verify_message = _verify_private_key(address, private_key)

        if not success:
            return await _reply(
                update,
                f"❌ 私钥验证失败: {verify_message}\n请检查您的私钥并重试。",
                context=context,
            )

        # 验证成功，添加钱包
        add_success, add_message = user_service.add_wallet(user_id, address, label)
        if not add_success:
            return await _reply(
                update, f"❌ 钱包添加失败: {add_message}", context=context
            )

        # 直接使用verify_wallet方法设置验证状态
        verify_success, _ = user_service.verify_wallet(
            user_id, address, "private_key", private_key
        )
        if not verify_success:
            await _reply(
                update,
                f"⚠️ 警告：钱包已添加，但标记为已验证状态失败。您可以稍后再次验证。",
                context=context,
            )

        await _reply(
            update, f"✅ 私钥验证成功，钱包 {address} 已添加并验证！", context=context
        )
    except Exception as e:
        logger.error(f"验证或添加钱包时出错: {e}")
        await _reply(
            update, f"❌ 处理过程中出错: {str(e)}\n请稍后重试。", context=context
        )


async def cmd_list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Make sure we can get the user ID regardless of whether this is a message or callback
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)
    wallets = user_service.get_user_wallets(user_id)
    if not wallets:
        return await _reply(
            update,
            "No registered wallets. Use /add_wallet to add one.",
            context=context,
        )

    text = "Your wallets:\n\n" + "\n".join(
        f"{i+1}. {wallet.get('label', 'My Wallet')}\n   Address: {wallet['address']}\n   Status: {'✅ Verified' if wallet.get('verified') else '❌ Not verified'}"
        for i, wallet in enumerate(wallets)
    )
    text += "\nUse /remove_wallet [address] to remove a wallet."
    await _reply(update, text, context=context)


async def cmd_remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    if not context.args:
        return await _reply(update, "Usage: /remove_wallet [address]", context=context)

    user_id = str(effective_user.id)
    address = context.args[0]
    success, message = user_service.remove_wallet(user_id, address)
    await _reply(update, message, context=context)


async def cmd_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    if not effective_user:
        return

    user_id = str(effective_user.id)
    default_wallet = user_service.get_default_wallet(user_id)
    if not default_wallet:
        return await _reply(
            update,
            "No registered wallets. Use /add_wallet to add one.",
            context=context,
        )
    result = await solana_service.get_sol_balance(default_wallet)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {default_wallet}."
    )
    await _reply(update, text, context=context)
