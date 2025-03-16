import json
import os
import logging
import time
import random
import string
import requests
from typing import Dict, Optional, Tuple, List, Any
from config import (
    USER_WALLET_STORAGE_FILE,
    WALLET_VERIFICATION_EXPIRY_SECONDS,
    SOLANA_RPC_URL,
)
import base58
import nacl.signing
import nacl.exceptions

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user information and wallet addresses"""

    def __init__(self):
        """Initialize UserService with storage file"""
        self.storage_file = USER_WALLET_STORAGE_FILE
        self._users_data = self._load_user_data()
        # Structure: {
        #   user_id: {
        #     "wallets": [{"address": "address1", "label": "My main wallet", "verified": True}, ...],
        #     "pending_verifications": {"address": "verification_data"}
        #   }
        # }

    def _load_user_data(self) -> Dict[str, Any]:
        """Load user data from storage file"""
        if not os.path.exists(self.storage_file):
            return {}

        try:
            with open(self.storage_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading user data: {e}")
            return {}

    def _save_user_data(self) -> bool:
        """Save user data to storage file"""
        try:
            with open(self.storage_file, "w") as f:
                json.dump(self._users_data, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Error saving user data: {e}")
            return False

    def get_user_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get list of wallets for a user

        Args:
            user_id: Telegram user ID

        Returns:
            List of wallet objects with address, label, and verified status
        """
        if (
            user_id not in self._users_data
            or "wallets" not in self._users_data[user_id]
        ):
            return []

        return self._users_data[user_id]["wallets"]

    def has_verified_wallet(self, user_id: str) -> bool:
        """Check if user has at least one verified wallet

        Args:
            user_id: Telegram user ID

        Returns:
            True if user has a verified wallet, False otherwise
        """
        wallets = self.get_user_wallets(user_id)
        return any(wallet.get("verified", False) for wallet in wallets)

    def add_wallet(
        self, user_id: str, address: str, label: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Add a wallet to user's wallets (unverified)

        Args:
            user_id: Telegram user ID
            address: Solana wallet address
            label: Optional label for the wallet

        Returns:
            Tuple of (success, message)
        """
        # Initialize user data if not exists
        if user_id not in self._users_data:
            self._users_data[user_id] = {"wallets": [], "pending_verifications": {}}

        # Check if wallet already exists for this user
        for wallet in self.get_user_wallets(user_id):
            if wallet["address"].lower() == address.lower():
                return False, "This wallet is already registered to your account."

        # Add wallet (unverified)
        new_wallet = {
            "address": address,
            "label": label or "My Wallet",
            "verified": False,
            "added_at": int(time.time()),
        }

        self._users_data[user_id]["wallets"].append(new_wallet)
        self._save_user_data()

        return True, f"Wallet {address} added. Please verify ownership."

    def generate_verification_challenge(
        self, user_id: str, address: str, method: str = "signature"
    ) -> Tuple[bool, str]:
        """Generate a verification challenge for a wallet

        Args:
            user_id: Telegram user ID
            address: Solana wallet address
            method: Verification method ("signature", "transfer", or "private_key")

        Returns:
            Tuple of (success, verification message or error)
        """
        # Check if the wallet exists and is unverified
        wallet_exists = False
        wallet_verified = False

        for wallet in self.get_user_wallets(user_id):
            if wallet["address"].lower() == address.lower():
                wallet_exists = True
                wallet_verified = wallet.get("verified", False)
                break

        if not wallet_exists:
            return False, "This wallet is not registered to your account."

        if wallet_verified:
            return False, "This wallet is already verified."

        # Initialize pending_verifications if not exists
        if "pending_verifications" not in self._users_data[user_id]:
            self._users_data[user_id]["pending_verifications"] = {}

        # Generate verification based on method
        if method == "signature":
            # Generate nonce for signature challenge
            nonce = "".join(random.choices(string.ascii_letters + string.digits, k=32))

            # Create challenge message
            challenge_message = f"Verify Telegram Bot Wallet: {address}\nNonce: {nonce}\nTimestamp: {int(time.time())}"

            # Store verification data
            self._users_data[user_id]["pending_verifications"][address] = {
                "method": "signature",
                "challenge": challenge_message,
                "nonce": nonce,
                "expires_at": int(time.time()) + WALLET_VERIFICATION_EXPIRY_SECONDS,
            }

            self._save_user_data()

            verification_message = (
                f"To verify your wallet, please sign the following message with your Solana wallet and paste the signature here:\n\n"
                f"```\n{challenge_message}\n```\n\n"
                f"After signing, send the signature in the format: `/verify_wallet {address} signature YOUR_SIGNATURE_HERE`\n\n"
                f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
            )

        elif method == "transfer":
            # Generate a random micro amount for transfer verification (between 0.000001 and 0.000099 SOL)
            # This ensures a unique and very small amount
            lamports = random.randint(
                1000, 99000
            )  # 1000-99000 lamports (0.000001-0.000099 SOL)
            sol_amount = (
                lamports / 1_000_000_000
            )  # Convert to SOL (1 SOL = 1,000,000,000 lamports)
            formatted_amount = (
                f"{sol_amount:.9f}"  # Format with 9 decimal places to show all digits
            )

            # Store verification data
            self._users_data[user_id]["pending_verifications"][address] = {
                "method": "transfer",
                "amount": lamports,  # Store as lamports for precision
                "expires_at": int(time.time()) + WALLET_VERIFICATION_EXPIRY_SECONDS,
            }

            self._save_user_data()

            # Create verification message for transfer method
            verification_message = (
                f"To verify your wallet, please send **exactly {formatted_amount} SOL** from your wallet "
                f"to ANY address of your choice.\n\n"
                f"After sending the transfer, use `/verify_wallet {address} transfer` command to complete verification.\n\n"
                f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes.\n\n"
                f"Note: The amount must be exact for verification to succeed. This uniquely small amount helps verify your wallet ownership."
            )

        elif method == "private_key":
            # Store verification data
            self._users_data[user_id]["pending_verifications"][address] = {
                "method": "private_key",
                "expires_at": int(time.time()) + WALLET_VERIFICATION_EXPIRY_SECONDS,
            }

            self._save_user_data()

            # Warning message about private key security
            verification_message = (
                f"⚠️ SECURITY WARNING ⚠️\n\n"
                f"Using your private key for verification is NOT RECOMMENDED as it can pose security risks.\n\n"
                f"To proceed with this method, send your private key using the format: `/verify_wallet {address} private_key YOUR_PRIVATE_KEY`\n\n"
                f"We strongly recommend using the signature or transfer verification methods instead for better security.\n\n"
                f"This verification will expire in {WALLET_VERIFICATION_EXPIRY_SECONDS // 60} minutes."
            )
        else:
            return False, "Invalid verification method."

        return True, verification_message

    def verify_wallet(
        self,
        user_id: str,
        address: str,
        method: Optional[str] = None,
        verification_data: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Verify a wallet ownership using one of the verification methods

        Args:
            user_id: Telegram user ID
            address: Solana wallet address
            method: Verification method ("signature", "transfer", or "private_key")
            verification_data: Data needed for verification (signature, or private key)

        Returns:
            Tuple of (success, message)
        """
        # Check if verification is pending
        if (
            user_id not in self._users_data
            or "pending_verifications" not in self._users_data[user_id]
            or address not in self._users_data[user_id]["pending_verifications"]
        ):
            # If no verification is pending and no method specified, return options information
            if not method:
                return (
                    False,
                    "Please specify a verification method: 'signature', 'transfer', or 'private_key'.",
                )
            elif method in ["signature", "transfer", "private_key"]:
                return self.generate_verification_challenge(user_id, address, method)
            else:
                return (
                    False,
                    "Invalid verification method. Use 'signature', 'transfer', or 'private_key'.",
                )

        # Get pending verification data
        verification_data_stored = self._users_data[user_id]["pending_verifications"][
            address
        ]

        # Check if verification expired
        if verification_data_stored["expires_at"] < int(time.time()):
            # Remove expired verification
            del self._users_data[user_id]["pending_verifications"][address]
            self._save_user_data()
            return (
                False,
                "Verification expired. Please generate a new verification challenge.",
            )

        # If method is not provided, return verification instructions based on stored method
        if not method:
            stored_method = verification_data_stored.get("method", "signature")
            if stored_method == "signature":
                return True, (
                    f"Please send the signature for this challenge:\n\n"
                    f"```\n{verification_data_stored['challenge']}\n```\n\n"
                    f"Use format: `/verify_wallet {address} signature YOUR_SIGNATURE_HERE`"
                )
            elif stored_method == "transfer":
                # Get the transfer amount in SOL for display
                sol_amount = verification_data_stored["amount"] / 1_000_000_000
                formatted_amount = f"{sol_amount:.9f}"

                return True, (
                    f"Please send **exactly {formatted_amount} SOL** to any address of your choice.\n\n"
                    f"Then use: `/verify_wallet {address} transfer`"
                )
            elif stored_method == "private_key":
                return True, (
                    f"⚠️ SECURITY WARNING ⚠️\n\n"
                    f"To verify with private key, use format: `/verify_wallet {address} private_key YOUR_PRIVATE_KEY`\n\n"
                    f"We strongly recommend using the signature or transfer verification methods instead."
                )
            return (
                False,
                "Unknown verification method. Please start verification again.",
            )

        # Process verification based on method
        if method == "signature":
            if not verification_data:
                return False, "Please provide the signature for verification."

            stored_method = verification_data_stored.get("method")
            if stored_method != "signature":
                return (
                    False,
                    f"The pending verification for this wallet uses {stored_method} method. Please use that method instead.",
                )

            try:
                # Verify the signature
                verification_result = self._verify_signature(
                    address, verification_data_stored["challenge"], verification_data
                )

                if not verification_result[0]:
                    return verification_result

                # Mark wallet as verified
                self._mark_wallet_verified(user_id, address)
                return True, f"Wallet {address} has been verified successfully! ✅"

            except Exception as e:
                logger.error(f"Error verifying signature: {e}")
                return False, f"Error verifying signature: {str(e)}"

        elif method == "transfer":
            stored_method = verification_data_stored.get("method")
            if stored_method != "transfer":
                return (
                    False,
                    f"The pending verification for this wallet uses {stored_method} method. Please use that method instead.",
                )

            # Get the expected transfer amount
            lamports = verification_data_stored["amount"]
            sol_amount = lamports / 1_000_000_000
            formatted_amount = f"{sol_amount:.9f}"

            # Verify the transfer using Solana RPC
            verification_result = self._verify_transfer(address, lamports)
            if not verification_result[0]:
                return (
                    False,
                    f"Transfer verification failed: {verification_result[1]}\n\n"
                    f"Please ensure you've sent exactly {formatted_amount} SOL from your wallet.",
                )

            # Mark wallet as verified after successful verification
            self._mark_wallet_verified(user_id, address)
            return True, (
                f"Wallet {address} has been verified successfully! ✅\n\n"
                f"We've confirmed your transfer of {formatted_amount} SOL from this wallet."
            )

        elif method == "private_key":
            if not verification_data:
                return False, "Please provide the private key for verification."

            stored_method = verification_data_stored.get("method")
            if stored_method != "private_key":
                return (
                    False,
                    f"The pending verification for this wallet uses {stored_method} method. Please use that method instead.",
                )

            try:
                # Validate private key and derive public key
                verification_result = self._verify_private_key(
                    address, verification_data
                )
                if not verification_result[0]:
                    return verification_result

                # Mark wallet as verified
                self._mark_wallet_verified(user_id, address)
                return True, f"Wallet {address} has been verified successfully! ✅"

            except Exception as e:
                logger.error(f"Error verifying private key: {e}")
                return False, f"Error verifying private key: {str(e)}"

        return (
            False,
            "Invalid verification method. Use 'signature', 'transfer', or 'private_key'.",
        )

    def _verify_transfer(
        self, wallet_address: str, expected_lamports: int
    ) -> Tuple[bool, str]:
        """Verify a transfer from the wallet with the exact amount

        Args:
            wallet_address: The wallet address to verify
            expected_lamports: The exact amount in lamports that should be transferred

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get recent transactions for the wallet
            # This would typically be done with a call to the Solana JSON RPC API
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet_address,
                    {"limit": 10},  # Check the 10 most recent transactions
                ],
            }

            headers = {"Content-Type": "application/json"}
            response = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"Error getting signatures: {response.text}")
                return False, "Failed to fetch recent transactions from Solana network."

            data = response.json()
            if "result" not in data or not data["result"]:
                return False, "No recent transactions found for this wallet."

            # Get the signatures from the result
            signatures = [item["signature"] for item in data["result"]]

            # Check each transaction for the expected amount
            for signature in signatures:
                # Get transaction details
                tx_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        signature,
                        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
                    ],
                }

                tx_response = requests.post(
                    SOLANA_RPC_URL, headers=headers, json=tx_payload
                )
                if tx_response.status_code != 200:
                    continue

                tx_data = tx_response.json()
                if "result" not in tx_data or not tx_data["result"]:
                    continue

                # Extract transaction details
                tx_result = tx_data["result"]

                # Check if the transaction is a transfer from the wallet
                if (
                    tx_result["meta"]
                    and "preBalances" in tx_result["meta"]
                    and "postBalances" in tx_result["meta"]
                ):
                    # Get pre and post balances
                    pre_balances = tx_result["meta"]["preBalances"]
                    post_balances = tx_result["meta"]["postBalances"]

                    # Get the account index for the wallet
                    account_indices = []
                    for i, account in enumerate(
                        tx_result["transaction"]["message"]["accountKeys"]
                    ):
                        if account["pubkey"] == wallet_address:
                            account_indices.append(i)

                    # Check if this wallet is in the transaction
                    if not account_indices:
                        continue

                    # For each occurrence of the wallet in the transaction
                    for idx in account_indices:
                        # Calculate the difference in balance
                        balance_diff = pre_balances[idx] - post_balances[idx]

                        # Check if the difference matches our expected amount (with some tolerance for fees)
                        # We consider the transaction fee which can be up to 5000 lamports
                        if abs(balance_diff - expected_lamports) <= 5000:
                            # Found a matching transaction
                            return (
                                True,
                                f"Transaction {signature} verified with expected amount.",
                            )

            # If we get here, no matching transaction was found
            return (
                False,
                "Could not find a recent transaction with the expected amount.",
            )

        except Exception as e:
            logger.error(f"Error verifying transfer: {e}")
            return False, f"Error verifying transfer: {str(e)}"

    def _mark_wallet_verified(self, user_id: str, address: str) -> None:
        """Mark a wallet as verified in user data

        Args:
            user_id: Telegram user ID
            address: Wallet address to mark as verified
        """
        # Find and update the wallet
        for wallet in self._users_data[user_id]["wallets"]:
            if wallet["address"].lower() == address.lower():
                wallet["verified"] = True
                wallet["verified_at"] = int(time.time())

        # Remove pending verification
        if address in self._users_data[user_id]["pending_verifications"]:
            del self._users_data[user_id]["pending_verifications"][address]

        self._save_user_data()

    def remove_wallet(self, user_id: str, address: str) -> Tuple[bool, str]:
        """Remove a wallet from user's account

        Args:
            user_id: Telegram user ID
            address: Solana wallet address

        Returns:
            Tuple of (success, message)
        """
        if (
            user_id not in self._users_data
            or "wallets" not in self._users_data[user_id]
        ):
            return False, "You don't have any registered wallets."

        # Find wallet index
        wallet_index = None
        for i, wallet in enumerate(self._users_data[user_id]["wallets"]):
            if wallet["address"].lower() == address.lower():
                wallet_index = i
                break

        if wallet_index is None:
            return False, "This wallet is not registered to your account."

        # Remove wallet
        del self._users_data[user_id]["wallets"][wallet_index]

        # Remove any pending verifications
        if (
            "pending_verifications" in self._users_data[user_id]
            and address in self._users_data[user_id]["pending_verifications"]
        ):
            del self._users_data[user_id]["pending_verifications"][address]

        self._save_user_data()

        return True, f"Wallet {address} has been removed from your account."

    def get_default_wallet(self, user_id: str) -> Optional[str]:
        """Get user's default wallet address

        Args:
            user_id: Telegram user ID

        Returns:
            Wallet address or None if no verified wallets
        """
        wallets = self.get_user_wallets(user_id)

        # First try to find a verified wallet
        for wallet in wallets:
            if wallet.get("verified", False):
                return wallet["address"]

        # If no verified wallets, return the first wallet (if any)
        if wallets:
            return wallets[0]["address"]

        return None

    def _verify_private_key(self, address: str, private_key: str) -> Tuple[bool, str]:
        """Verify a wallet using its private key

        Args:
            address: Wallet address to verify
            private_key: Private key in base58 format

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate the private key format
            try:
                private_key_bytes = base58.b58decode(private_key)
            except Exception:
                return (
                    False,
                    "Invalid private key format. The private key must be in base58 format.",
                )

            # Solana private keys are either 64 bytes (full keypair) or 32 bytes (only secret)
            if len(private_key_bytes) != 64 and len(private_key_bytes) != 32:
                return (
                    False,
                    "Invalid private key length. Expected 32 or 64 bytes after base58 decoding.",
                )

            # If we have a full keypair (64 bytes), use only the secret part (first 32 bytes)
            secret_bytes = (
                private_key_bytes[:32]
                if len(private_key_bytes) == 64
                else private_key_bytes
            )

            # Create signing key from private key
            signing_key = nacl.signing.SigningKey(secret_bytes)

            # Get public key (verify key) from signing key
            verify_key = signing_key.verify_key

            # Convert public key to base58
            derived_public_key = base58.b58encode(verify_key.encode()).decode("utf-8")

            # Compare derived public key with the address
            if derived_public_key != address:
                return (
                    False,
                    "The private key does not correspond to the provided wallet address.",
                )

            return True, "Private key verified successfully."

        except nacl.exceptions.CryptoError as e:
            logger.error(f"Crypto error in private key verification: {e}")
            return False, f"Cryptographic error during verification: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in private key verification: {e}")
            return False, f"Error verifying private key: {str(e)}"

    def _verify_signature(
        self, address: str, message: str, signature: str
    ) -> Tuple[bool, str]:
        """Verify a signature against a wallet address and message

        Args:
            address: Wallet address (public key in base58)
            message: The message that was signed
            signature: The signature in base58 format

        Returns:
            Tuple of (success, message)
        """
        try:
            # Decode the wallet address from base58 to get the public key bytes
            try:
                pubkey_bytes = base58.b58decode(address)
                if len(pubkey_bytes) != 32:  # Solana public keys are 32 bytes
                    return False, "Invalid wallet address format."
            except Exception:
                return (
                    False,
                    "Invalid wallet address. The address must be in base58 format.",
                )

            # Create verify key from public key bytes
            verify_key = nacl.signing.VerifyKey(pubkey_bytes)

            # Decode the signature from base58
            try:
                signature_bytes = base58.b58decode(signature)
            except Exception:
                return (
                    False,
                    "Invalid signature format. The signature must be in base58 format.",
                )

            # Prepare the message bytes
            message_bytes = message.encode("utf-8")

            # Verify the signature
            try:
                verify_key.verify(message_bytes, signature_bytes)
                return True, "Signature verified successfully."
            except nacl.exceptions.BadSignatureError:
                return (
                    False,
                    "Invalid signature. The signature does not match the message or was not created by this wallet.",
                )

        except nacl.exceptions.CryptoError as e:
            logger.error(f"Crypto error in signature verification: {e}")
            return False, f"Cryptographic error during verification: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in signature verification: {e}")
            return False, f"Error verifying signature: {str(e)}"
