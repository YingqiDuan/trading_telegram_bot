import sqlite3
import time
import random
import string
import requests
import base58
import nacl.signing
import nacl.exceptions
import logging
import ast
import base64
import json
from typing import Dict, Any, Optional, Tuple, List
from config import (
    USER_WALLET_DB_PATH,
    WALLET_VERIFICATION_EXPIRY_SECONDS,
    SOLANA_RPC_URL,
)

logger = logging.getLogger(__name__)


def configure_sqlite_connection(
    conn: sqlite3.Connection, enable_transaction: bool = False
) -> None:
    """Configure SQLite connection parameters."""
    conn.row_factory = sqlite3.Row
    if enable_transaction:
        conn.isolation_level = None  # Autocommit mode
    else:
        conn.isolation_level = ""  # Default
    conn.execute("PRAGMA foreign_keys = ON")


def init_database() -> None:
    """Initialize SQLite database schema if it doesn't exist."""
    with sqlite3.connect(USER_WALLET_DB_PATH) as conn:
        configure_sqlite_connection(conn, enable_transaction=True)
        cursor = conn.cursor()

        # User wallets table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS user_wallets (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            address TEXT NOT NULL,
            label TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            added_at INTEGER NOT NULL,
            verified_at INTEGER,
            UNIQUE(user_id, address)
        )
        """
        )

        # Pending verifications table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pending_verifications (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            address TEXT NOT NULL,
            method TEXT NOT NULL,
            challenge TEXT,
            nonce TEXT,
            amount INTEGER,
            expires_at INTEGER NOT NULL,
            UNIQUE(user_id, address)
        )
        """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_wallets_user_id ON user_wallets(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_verifications_user_id ON pending_verifications(user_id)"
        )


class UserService:
    """Service for managing user wallets and verification with SQLite backend."""

    def __init__(self):
        self.db_path = USER_WALLET_DB_PATH
        init_database()

    def get_user_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            configure_sqlite_connection(conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT address, label, verified, added_at, verified_at FROM user_wallets WHERE user_id = ?",
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def has_verified_wallet(self, user_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            configure_sqlite_connection(conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM user_wallets WHERE user_id = ? AND verified = 1",
                (user_id,),
            )
            result = cursor.fetchone()
            return result["count"] > 0 if result else False

    def add_wallet(
        self, user_id: str, address: str, label: Optional[str] = None
    ) -> Tuple[bool, str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                # Check if wallet already exists
                cursor.execute(
                    "SELECT 1 FROM user_wallets WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )
                if cursor.fetchone():
                    return False, "This wallet is already registered to your account."

                # Add wallet
                cursor.execute(
                    "INSERT INTO user_wallets (user_id, address, label, verified, added_at) VALUES (?, ?, ?, 0, ?)",
                    (user_id, address, label or "My Wallet", int(time.time())),
                )
                return True, f"Wallet {address} added. Please verify ownership."
        except sqlite3.Error as e:
            logger.error(f"SQLite error when adding wallet: {e}")
            return False, "Database error occurred. Please try again later."

    def remove_wallet(self, user_id: str, address: str) -> Tuple[bool, str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                # Check if wallet exists
                cursor.execute(
                    "SELECT 1 FROM user_wallets WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )
                if not cursor.fetchone():
                    return False, "This wallet is not registered to your account."

                # Remove wallet
                cursor.execute(
                    "DELETE FROM user_wallets WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )

                # Remove any pending verifications
                cursor.execute(
                    "DELETE FROM pending_verifications WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )
                return True, f"Wallet {address} has been removed from your account."
        except sqlite3.Error as e:
            logger.error(f"SQLite error when removing wallet: {e}")
            return False, "Database error occurred. Please try again later."

    def get_default_wallet(self, user_id: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                # Try to get a verified wallet first
                cursor.execute(
                    "SELECT address FROM user_wallets WHERE user_id = ? AND verified = 1 LIMIT 1",
                    (user_id,),
                )
                row = cursor.fetchone()
                if row:
                    return row["address"]

                # If no verified wallet, get the first wallet
                cursor.execute(
                    "SELECT address FROM user_wallets WHERE user_id = ? LIMIT 1",
                    (user_id,),
                )
                row = cursor.fetchone()
                return row["address"] if row else None
        except sqlite3.Error as e:
            logger.error(f"SQLite error when getting default wallet: {e}")
            return None

    def generate_verification_challenge(
        self, user_id: str, address: str, method: str = "signature"
    ) -> Tuple[bool, str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                # Check if wallet exists
                cursor.execute(
                    "SELECT verified FROM user_wallets WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )
                row = cursor.fetchone()
                if not row:
                    return False, "This wallet is not registered to your account."

                if row["verified"]:
                    return False, "This wallet is already verified."

                now = int(time.time())
                expire = now + WALLET_VERIFICATION_EXPIRY_SECONDS

                # Delete any existing verification challenges
                cursor.execute(
                    "DELETE FROM pending_verifications WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                    (user_id, address),
                )

                if method == "signature":
                    nonce = "".join(
                        random.choices(string.ascii_letters + string.digits, k=32)
                    )
                    challenge = f"Verify Telegram Bot Wallet: {address}\nNonce: {nonce}\nTimestamp: {now}"

                    cursor.execute(
                        """INSERT INTO pending_verifications 
                           (user_id, address, method, challenge, nonce, expires_at) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, address, "signature", challenge, nonce, expire),
                    )

                    msg = (
                        f"Please sign the following message with your Solana wallet, then send the signature:\n\n"
                        f"```\n{challenge}\n```\n\n"
                        f"Format: `/verify_wallet {address} signature YOUR_SIGNATURE_HERE`\n"
                        f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
                    )
                elif method == "transfer":
                    lamports = random.randint(1000, 99000)
                    sol_amount = lamports / 1_000_000_000

                    cursor.execute(
                        """INSERT INTO pending_verifications 
                           (user_id, address, method, amount, expires_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (user_id, address, "transfer", lamports, expire),
                    )

                    msg = (
                        f"Please transfer **exactly {sol_amount:.9f} SOL** from your wallet to any address.\n\n"
                        f"After the transfer, use `/verify_wallet {address} transfer` to complete verification.\n"
                        f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
                    )
                elif method == "private_key":
                    cursor.execute(
                        """INSERT INTO pending_verifications 
                           (user_id, address, method, expires_at) 
                           VALUES (?, ?, ?, ?)""",
                        (user_id, address, "private_key", expire),
                    )

                    msg = (
                        f"⚠️ Security Warning ⚠️\nVerifying with a private key is risky and not recommended.\n\n"
                        f"If you insist, please use the format: `/verify_wallet {address} private_key YOUR_PRIVATE_KEY`\n"
                        f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
                    )
                else:
                    return False, "Invalid verification method."

                return True, msg
        except sqlite3.Error as e:
            logger.error(f"SQLite error when generating verification challenge: {e}")
            return False, "Database error occurred. Please try again later."

    def verify_wallet(
        self,
        user_id: str,
        address: str,
        method: Optional[str] = None,
        verification_data: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Verify wallet ownership using various methods."""
        try:
            challenge_generated = False
            info_message = ""

            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                # Check if there's a pending verification
                cursor.execute(
                    """SELECT method, challenge, nonce, amount, expires_at 
                       FROM pending_verifications 
                       WHERE user_id = ? AND LOWER(address) = LOWER(?)""",
                    (user_id, address),
                )
                pending = cursor.fetchone()

                # If there's no pending verification or it expired, generate a new one
                if not pending or pending["expires_at"] < int(time.time()):
                    if pending and pending["expires_at"] < int(time.time()):
                        cursor.execute(
                            "DELETE FROM pending_verifications WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                            (user_id, address),
                        )
                        info_message += (
                            "Verification has expired. Generating a new challenge.\n\n"
                        )

                    if not method:
                        return (
                            False,
                            "Please specify a verification method: 'signature', 'transfer', or 'private_key'.",
                        )

                    if method not in ["signature", "transfer", "private_key"]:
                        return False, "Invalid verification method."

                    success, challenge_msg = self.generate_verification_challenge(
                        user_id, address, method
                    )
                    if not success:
                        return False, challenge_msg

                    info_message += challenge_msg
                    challenge_generated = True

            # If we just generated a challenge and there's no verification data, return the challenge message
            if challenge_generated and not verification_data:
                return False, info_message

            # Re-fetch the pending verification data as it might have been updated
            with sqlite3.connect(self.db_path) as conn:
                configure_sqlite_connection(conn)
                cursor = conn.cursor()

                cursor.execute(
                    """SELECT method, challenge, nonce, amount, expires_at 
                       FROM pending_verifications 
                       WHERE user_id = ? AND LOWER(address) = LOWER(?)""",
                    (user_id, address),
                )
                pdata = cursor.fetchone()

                if not pdata:
                    return False, "No pending verification found. Please try again."

                # If method is not specified, use the one from the pending verification
                if not method:
                    method = pdata["method"]
                    if not method:
                        return False, "Verification method is missing."

                # If the methods don't match, generate a new challenge
                if method != pdata["method"]:
                    info_message += f"Verification method mismatch. Expected: {pdata['method']}, got: {method}. Generating a new challenge with {method} method.\n\n"
                    success, challenge_msg = self.generate_verification_challenge(
                        user_id, address, method
                    )
                    if not success:
                        return False, challenge_msg

                    info_message += challenge_msg
                    return False, info_message

                # If there's no verification data, return appropriate message
                if not verification_data:
                    if method == "signature":
                        return False, "Please provide the signature:"
                    elif method == "private_key":
                        return False, "Please provide the private key:"

                # Perform the actual verification
                if method == "signature":
                    result, message = _verify_signature(
                        address, pdata["challenge"], verification_data
                    )
                elif method == "transfer":
                    result, message = _verify_transfer(address, pdata["amount"])
                elif method == "private_key":
                    result, message = _verify_private_key(address, verification_data)
                else:
                    return False, "Invalid verification method."

                # If verification succeeded, mark the wallet as verified
                if result:
                    cursor.execute(
                        "UPDATE user_wallets SET verified = 1, verified_at = ? WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                        (int(time.time()), user_id, address),
                    )

                    # Remove the pending verification
                    cursor.execute(
                        "DELETE FROM pending_verifications WHERE user_id = ? AND LOWER(address) = LOWER(?)",
                        (user_id, address),
                    )

                    message += "\nWallet verified successfully!"

                # Add any info message to the result
                if info_message:
                    message = info_message + "\n" + message

                return result, message
        except sqlite3.Error as e:
            logger.error(f"SQLite error during wallet verification: {e}")
            return False, "Database error occurred. Please try again later."


# Reuse verification functions from original UserService
def _verify_transfer(wallet_address: str, expected_lamports: int) -> Tuple[bool, str]:
    """Verify a transfer from the wallet."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet_address, {"limit": 10}],
        }
        response = requests.post(SOLANA_RPC_URL, json=payload)
        if response.status_code != 200:
            return False, "Failed to communicate with Solana RPC."
        data = response.json()
        if "error" in data:
            return False, f"RPC error: {data['error']['message']}"
        if not data.get("result"):
            return False, "No recent transactions found."
        for tx_info in data["result"]:
            tx_sig = tx_info["signature"]
            tx_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [tx_sig, {"encoding": "json"}],
            }
            tx_response = requests.post(SOLANA_RPC_URL, json=tx_payload)
            if tx_response.status_code != 200:
                continue
            tx_data = tx_response.json()
            if tx_data.get("error") or not tx_data.get("result"):
                continue
            tx = tx_data["result"]
            timestamp = tx.get("blockTime")
            if (
                not timestamp
                or time.time() - timestamp > WALLET_VERIFICATION_EXPIRY_SECONDS
            ):
                continue
            meta = tx.get("meta", {})
            if "preBalances" in meta and "postBalances" in meta:
                delta = meta["preBalances"][0] - meta["postBalances"][0]
                if delta > 0 and abs(delta - expected_lamports) <= 5000:
                    return True, "Transfer verification successful."
        return (
            False,
            "Could not find a matching transfer. Please try again or use another verification method.",
        )
    except Exception as e:
        logger.error(f"Error in transfer verification: {e}")
        return False, "An error occurred during verification. Please try again later."


def _verify_private_key(address: str, private_key: str) -> Tuple[bool, str]:
    """Verify wallet ownership via private key."""
    try:
        if len(private_key) < 32:
            return False, "Invalid private key format."
        try:
            key_bytes = (
                bytes(ast.literal_eval(private_key))
                if private_key.startswith("[") and private_key.endswith("]")
                else None
            )
            if key_bytes is None:
                try:
                    key_bytes = base58.b58decode(private_key)
                except:
                    key_bytes = bytes.fromhex(private_key.replace("0x", ""))
            signing_key = nacl.signing.SigningKey(key_bytes)
            derived_address = base58.b58encode(bytes(signing_key.verify_key)).decode(
                "utf-8"
            )
            return (
                (
                    True,
                    "Private key verification successful. Warning: Please secure your private key!",
                )
                if derived_address.lower() == address.lower()
                else (False, "Private key does not match this wallet address.")
            )
        except Exception as e:
            logger.error(f"Private key verification error: {e}")
            return False, "Invalid private key format. Please check and try again."
    except Exception as e:
        logger.error(f"Error in private key verification: {e}")
        return False, "An error occurred during verification. Please try again later."


def _verify_signature(address: str, message: str, signature: str) -> Tuple[bool, str]:
    """Verify a signature for a message."""
    try:
        if not message or not signature:
            return False, "Missing message or signature."
        if len(signature) < 32:
            return False, "Invalid signature format."
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "base64"}],
        }
        response = requests.post(SOLANA_RPC_URL, json=payload)
        if response.status_code != 200:
            return False, "Failed to communicate with Solana RPC."
        data = response.json()
        if "error" in data:
            return False, f"RPC error: {data['error']['message']}"
        verify_key = nacl.signing.VerifyKey(base58.b58decode(address))
        try:
            sig_bytes = base58.b58decode(signature)
            verify_key.verify(message.encode(), sig_bytes)
            return True, "Signature verification successful."
        except nacl.exceptions.BadSignatureError:
            return False, "Invalid signature for this message."
        except Exception:
            try:
                sig_bytes = base64.b64decode(signature)
                verify_key.verify(message.encode(), sig_bytes)
                return True, "Signature verification successful."
            except:
                return False, "Invalid signature format or signature does not match."
    except Exception as e:
        logger.error(f"Error in signature verification: {e}")
        return False, "An error occurred during verification. Please try again later."
