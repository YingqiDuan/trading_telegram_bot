import time
import random
import string
import requests
import base58
import nacl.signing
import nacl.exceptions
import logging
from typing import Tuple, Optional, Dict, Any
from config import WALLET_VERIFICATION_EXPIRY_SECONDS, SOLANA_RPC_URL

logger = logging.getLogger(__name__)


def generate_verification_challenge(
    user_data: Dict[str, Any], user_id: str, address: str, method: str = "signature"
) -> Tuple[bool, str]:
    user = user_data.setdefault(user_id, {"wallets": [], "pending_verifications": {}})
    wallets = user.get("wallets", [])
    wallet = next((w for w in wallets if w["address"].lower() == address.lower()), None)
    if not wallet:
        return False, "This wallet is not registered to your account."
    if wallet.get("verified"):
        return False, "This wallet is already verified."
    pending = user.setdefault("pending_verifications", {})
    now, expire = (
        int(time.time()),
        int(time.time()) + WALLET_VERIFICATION_EXPIRY_SECONDS,
    )

    if method == "signature":
        nonce = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        challenge = (
            f"Verify Telegram Bot Wallet: {address}\nNonce: {nonce}\nTimestamp: {now}"
        )
        pending[address] = {
            "method": "signature",
            "challenge": challenge,
            "nonce": nonce,
            "expires_at": expire,
        }
        msg = (
            f"请使用你的 Solana 钱包签名下面的消息，然后发送签名：\n\n"
            f"```\n{challenge}\n```\n\n"
            f"格式：`/verify_wallet {address} signature YOUR_SIGNATURE_HERE`\n"
            f"该验证将在 {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} 分钟后过期。"
        )
    elif method == "transfer":
        lamports = random.randint(1000, 99000)
        sol_amount = lamports / 1_000_000_000
        pending[address] = {
            "method": "transfer",
            "amount": lamports,
            "expires_at": expire,
        }
        msg = (
            f"请从你的钱包向任意地址转账**恰好 {sol_amount:.9f} SOL**。\n\n"
            f"转账后，使用 `/verify_wallet {address} transfer` 完成验证。\n"
            f"该验证将在 {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} 分钟后过期。"
        )
    elif method == "private_key":
        pending[address] = {"method": "private_key", "expires_at": expire}
        msg = (
            f"⚠️ 安全警告 ⚠️\n使用私钥进行验证存在风险，不推荐使用。\n\n"
            f"若坚持使用，请发送格式：`/verify_wallet {address} private_key YOUR_PRIVATE_KEY`\n"
            f"该验证将在 {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} 分钟后过期。"
        )
    else:
        return False, "无效的验证方式。"
    return True, msg


def verify_wallet(
    user_data: Dict[str, Any],
    user_id: str,
    address: str,
    method: Optional[str] = None,
    verification_data: Optional[str] = None,
) -> Tuple[bool, str]:
    user = user_data.get(user_id, {})
    pending = user.get("pending_verifications", {})
    if address not in pending:
        if not method:
            return False, "请指定验证方式：'signature'、'transfer' 或 'private_key'。"
        if method in ["signature", "transfer", "private_key"]:
            return generate_verification_challenge(user_data, user_id, address, method)
        return False, "无效的验证方式。"

    pdata = pending[address]
    if pdata["expires_at"] < int(time.time()):
        pending.pop(address, None)
        return False, "验证已过期，请重新生成验证挑战。"

    if not method:
        m = pdata.get("method", "signature")
        if m == "signature":
            return True, (
                f"请发送下列消息的签名：\n\n"
                f"```\n{pdata['challenge']}\n```\n\n"
                f"格式：`/verify_wallet {address} signature YOUR_SIGNATURE_HERE`"
            )
        elif m == "transfer":
            sol_amount = pdata["amount"] / 1_000_000_000
            return (
                True,
                f"请转账恰好 {sol_amount:.9f} SOL，然后使用 `/verify_wallet {address} transfer`。",
            )
        elif m == "private_key":
            return (
                True,
                f"请使用格式：`/verify_wallet {address} private_key YOUR_PRIVATE_KEY` 进行验证。",
            )
        return False, "未知的验证方式，请重新开始验证。"

    if method == "signature":
        if not verification_data:
            return False, "请提供签名。"
        if pdata.get("method") != "signature":
            return False, f"待验证方式为 {pdata.get('method')}，请使用该方式。"
        ok, msg = _verify_signature(address, pdata["challenge"], verification_data)
        return (
            (ok, msg if not ok else f"钱包 {address} 验证成功！✅") if ok else (ok, msg)
        )
    elif method == "transfer":
        if pdata.get("method") != "transfer":
            return False, f"待验证方式为 {pdata.get('method')}，请使用该方式。"
        lamports = pdata["amount"]
        sol_amount = lamports / 1_000_000_000
        ok, msg = _verify_transfer(address, lamports)
        return (
            ok,
            (
                f"钱包 {address} 验证成功！✅\n已确认转账 {sol_amount:.9f} SOL。"
                if ok
                else f"转账验证失败：{msg}\n请确保转账恰好 {sol_amount:.9f} SOL。"
            ),
        )
    elif method == "private_key":
        if not verification_data:
            return False, "请提供私钥。"
        if pdata.get("method") != "private_key":
            return False, f"待验证方式为 {pdata.get('method')}，请使用该方式。"
        ok, msg = _verify_private_key(address, verification_data)
        return (
            (ok, msg if not ok else f"钱包 {address} 验证成功！✅") if ok else (ok, msg)
        )
    return False, "无效的验证方式，请使用 'signature'、'transfer' 或 'private_key'。"


def _verify_transfer(wallet_address: str, expected_lamports: int) -> Tuple[bool, str]:
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet_address, {"limit": 10}],
        }
        res = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)
        if res.status_code != 200:
            logger.error(f"Error getting signatures: {res.text}")
            return False, "获取最近交易失败。"
        result = res.json().get("result")
        if not result:
            return False, "未找到最近交易。"
        signatures = [item["signature"] for item in result]
        for sig in signatures:
            tx_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    sig,
                    {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
                ],
            }
            tx_res = requests.post(SOLANA_RPC_URL, headers=headers, json=tx_payload)
            if tx_res.status_code != 200:
                continue
            tx = tx_res.json().get("result")
            if not tx or "meta" not in tx:
                continue
            pre, post = tx["meta"].get("preBalances"), tx["meta"].get("postBalances")
            if not pre or not post:
                continue
            indices = [
                i
                for i, acc in enumerate(tx["transaction"]["message"]["accountKeys"])
                if acc["pubkey"] == wallet_address
            ]
            for i in indices:
                if abs(pre[i] - post[i] - expected_lamports) <= 5000:
                    return True, f"交易 {sig} 验证成功。"
        return False, "未找到匹配的交易。"
    except Exception as e:
        logger.error(f"Error verifying transfer: {e}")
        return False, str(e)


def _verify_private_key(address: str, private_key: str) -> Tuple[bool, str]:
    try:
        try:
            key_bytes = base58.b58decode(private_key)
        except Exception:
            return False, "无效的私钥格式，必须为 base58 格式。"
        if len(key_bytes) not in (32, 64):
            return False, "无效的私钥长度，期望 32 或 64 字节。"
        secret = key_bytes[:32] if len(key_bytes) == 64 else key_bytes
        signing_key = nacl.signing.SigningKey(secret)
        derived = base58.b58encode(signing_key.verify_key.encode()).decode("utf-8")
        return (
            (True, "私钥验证成功。")
            if derived == address
            else (False, "私钥与该钱包地址不匹配。")
        )
    except nacl.exceptions.CryptoError as e:
        logger.error(f"Crypto error: {e}")
        return False, f"加密错误：{str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e)


def _verify_signature(address: str, message: str, signature: str) -> Tuple[bool, str]:
    try:
        try:
            pubkey_bytes = base58.b58decode(address)
            if len(pubkey_bytes) != 32:
                return False, "无效的钱包地址格式。"
        except Exception:
            return False, "无效的钱包地址，应为 base58 格式。"
        verify_key = nacl.signing.VerifyKey(pubkey_bytes)
        try:
            sig_bytes = base58.b58decode(signature)
        except Exception:
            return False, "无效的签名格式，必须为 base58 格式。"
        try:
            verify_key.verify(message.encode("utf-8"), sig_bytes)
            return True, "签名验证成功。"
        except nacl.exceptions.BadSignatureError:
            return False, "签名无效。"
    except nacl.exceptions.CryptoError as e:
        logger.error(f"Crypto error: {e}")
        return False, f"加密错误：{str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e)
