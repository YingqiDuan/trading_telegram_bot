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
            f"Please sign the following message with your Solana wallet, then send the signature:\n\n"
            f"```\n{challenge}\n```\n\n"
            f"Format: `/verify_wallet {address} signature YOUR_SIGNATURE_HERE`\n"
            f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
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
            f"Please transfer **exactly {sol_amount:.9f} SOL** from your wallet to any address.\n\n"
            f"After the transfer, use `/verify_wallet {address} transfer` to complete verification.\n"
            f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
        )
    elif method == "private_key":
        pending[address] = {"method": "private_key", "expires_at": expire}
        msg = (
            f"⚠️ Security Warning ⚠️\nVerifying with a private key is risky and not recommended.\n\n"
            f"If you insist, please use the format: `/verify_wallet {address} private_key YOUR_PRIVATE_KEY`\n"
            f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
        )
    else:
        return False, "Invalid verification method."
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
            return (
                False,
                "Please specify a verification method: 'signature', 'transfer', or 'private_key'.",
            )
        if method in ["signature", "transfer", "private_key"]:
            return generate_verification_challenge(user_data, user_id, address, method)
        return False, "Invalid verification method."

    pdata = pending[address]
    if pdata["expires_at"] < int(time.time()):
        pending.pop(address, None)
        return (
            False,
            "Verification has expired, please generate a new verification challenge.",
        )

    if not method:
        m = pdata.get("method", "signature")
        if m == "signature":
            return True, (
                f"Please send the signature for the following message:\n\n"
                f"```\n{pdata['challenge']}\n```\n\n"
                f"Format: `/verify_wallet {address} signature YOUR_SIGNATURE_HERE`"
            )
        elif m == "transfer":
            sol_amount = pdata["amount"] / 1_000_000_000
            return (
                True,
                f"Please transfer exactly {sol_amount:.9f} SOL, then use `/verify_wallet {address} transfer`.",
            )
        elif m == "private_key":
            return (
                True,
                f"Please use the format: `/verify_wallet {address} private_key YOUR_PRIVATE_KEY` for verification.",
            )
        return False, "Unknown verification method, please restart verification."

    if method == "signature":
        if not verification_data:
            return False, "Please provide a signature."
        if pdata.get("method") != "signature":
            return (
                False,
                f"Pending verification method is {pdata.get('method')}, please use that method.",
            )
        ok, msg = _verify_signature(address, pdata["challenge"], verification_data)
        return (
            (ok, msg if not ok else f"Wallet {address} verified successfully! ✅")
            if ok
            else (ok, msg)
        )
    elif method == "transfer":
        if pdata.get("method") != "transfer":
            return (
                False,
                f"Pending verification method is {pdata.get('method')}, please use that method.",
            )
        lamports = pdata["amount"]
        sol_amount = lamports / 1_000_000_000
        ok, msg = _verify_transfer(address, lamports)
        return (
            ok,
            (
                f"Wallet {address} verified successfully! ✅\nTransfer of {sol_amount:.9f} SOL confirmed."
                if ok
                else f"Transfer verification failed: {msg}\nPlease ensure you transfer exactly {sol_amount:.9f} SOL."
            ),
        )
    elif method == "private_key":
        if not verification_data:
            return False, "Please provide a private key."
        if pdata.get("method") != "private_key":
            return (
                False,
                f"Pending verification method is {pdata.get('method')}, please use that method.",
            )
        ok, msg = _verify_private_key(address, verification_data)
        return (
            (ok, msg if not ok else f"Wallet {address} verified successfully! ✅")
            if ok
            else (ok, msg)
        )
    return (
        False,
        "Invalid verification method, please use 'signature', 'transfer', or 'private_key'.",
    )


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
            return False, "Failed to retrieve recent transactions."
        result = res.json().get("result")
        if not result:
            return False, "No recent transactions found."
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
                    return True, f"Transaction {sig} verified successfully."
        return False, "No matching transaction found."
    except Exception as e:
        logger.error(f"Error verifying transfer: {e}")
        return False, str(e)


def _verify_private_key(address: str, private_key: str) -> Tuple[bool, str]:
    try:
        try:
            key_bytes = base58.b58decode(private_key)
        except Exception:
            return False, "Invalid private key format, must be in base58 format."
        if len(key_bytes) not in (32, 64):
            return False, "Invalid private key length, expected 32 or 64 bytes."
        secret = key_bytes[:32] if len(key_bytes) == 64 else key_bytes
        signing_key = nacl.signing.SigningKey(secret)
        derived = base58.b58encode(signing_key.verify_key.encode()).decode("utf-8")
        return (
            (True, "Private key verified successfully.")
            if derived == address
            else (False, "Private key does not match this wallet address.")
        )
    except nacl.exceptions.CryptoError as e:
        logger.error(f"Crypto error: {e}")
        return False, f"Crypto error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e)


def _verify_signature(address: str, message: str, signature: str) -> Tuple[bool, str]:
    try:
        try:
            pubkey_bytes = base58.b58decode(address)
            if len(pubkey_bytes) != 32:
                return False, "Invalid wallet address format."
        except Exception:
            return False, "Invalid wallet address, should be in base58 format."
        verify_key = nacl.signing.VerifyKey(pubkey_bytes)
        try:
            sig_bytes = base58.b58decode(signature)
        except Exception:
            return False, "Invalid signature format, must be in base58 format."
        try:
            verify_key.verify(message.encode("utf-8"), sig_bytes)
            return True, "Signature verified successfully."
        except nacl.exceptions.BadSignatureError:
            return False, "Invalid signature."
    except nacl.exceptions.CryptoError as e:
        logger.error(f"Crypto error: {e}")
        return False, f"Crypto error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e)
