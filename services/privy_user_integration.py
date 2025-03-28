import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from services.privy_wallet_service import PrivyWalletService
from services.user_service import UserService
import sqlite3
import time

logger = logging.getLogger(__name__)


class PrivyUserIntegration:
    """
    A service to integrate Privy's embedded wallets with the existing user system.
    This service provides methods to create, manage, and use Privy wallets for users.
    """

    def __init__(self):
        self.privy_service = PrivyWalletService()
        self.user_service = UserService()

    def create_user_wallet(
        self, user_id: str, chain_type: str = "ethereum", label: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Create a new Privy wallet for a user and register it in the user system.

        Args:
            user_id: Telegram user ID
            chain_type: Blockchain type ("ethereum" or "solana")
            label: Optional label for the wallet

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - Wallet data if successful, None otherwise
        """
        try:
            # Create wallet in Privy
            wallet_data = self.privy_service.create_wallet(
                chain_type=chain_type, linked_user_id=user_id
            )

            if not wallet_data or "address" not in wallet_data:
                return False, "Failed to create wallet with Privy", None

            wallet_id = wallet_data.get("id")
            address = wallet_data.get("address")

            # Add wallet to user's account
            success, message = self.user_service.add_wallet(
                user_id, address, label or f"Privy {chain_type.capitalize()} Wallet"
            )

            if success:
                # Store wallet_id as private_key (we're using this field to store Privy's wallet ID)
                self.user_service.set_wallet_private_key(user_id, address, wallet_id)

                # Auto-verify the wallet since it's created by our service
                self.user_service.verify_wallet(
                    user_id, address, method="privy", verification_data="auto_verified"
                )

                return (
                    True,
                    f"Successfully created and registered {chain_type} wallet",
                    wallet_data,
                )
            else:
                # If we failed to register the wallet in our system, we should delete it from Privy
                try:
                    self.privy_service.delete_wallet(wallet_id)
                except Exception as e:
                    logger.error(
                        f"Failed to delete wallet from Privy after registration failure: {e}"
                    )

                return (
                    False,
                    f"Created wallet with Privy but failed to register it: {message}",
                    None,
                )

        except Exception as e:
            logger.error(f"Error creating Privy wallet for user {user_id}: {e}")
            return False, f"Error creating wallet: {str(e)}", None

    def get_user_privy_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all Privy wallets for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of wallet data dictionaries
        """
        privy_wallets = []
        all_wallets = self.user_service.get_user_wallets(user_id)

        for wallet in all_wallets:
            # Get the wallet_id (stored in private_key field)
            wallet_id = self.user_service.get_wallet_private_key(
                user_id, wallet["address"]
            )

            if wallet_id:
                try:
                    # Try to get the wallet from Privy - if it exists, it's a Privy wallet
                    privy_wallet_data = self.privy_service.get_wallet(wallet_id)
                    if privy_wallet_data and "address" in privy_wallet_data:
                        # Merge wallet data from our DB with Privy data
                        privy_wallet_data.update(
                            {
                                "label": wallet.get("label", "Privy Wallet"),
                                "is_verified": bool(wallet.get("verified", 0)),
                                "added_at": wallet.get("added_at"),
                                "verified_at": wallet.get("verified_at"),
                            }
                        )
                        privy_wallets.append(privy_wallet_data)
                except Exception as e:
                    logger.error(
                        f"Error getting Privy wallet {wallet_id} for user {user_id}: {e}"
                    )
                    continue

        return privy_wallets

    def get_wallet_balance(
        self, user_id: str, address: str, token_address: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Get the balance of a user's Privy wallet.

        Args:
            user_id: Telegram user ID
            address: Wallet address
            token_address: Optional token address to check balance for

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - Balance data if successful, None otherwise
        """
        # Get the wallet_id (stored in private_key field)
        wallet_id = self.user_service.get_wallet_private_key(user_id, address)

        if not wallet_id:
            return False, "This doesn't appear to be a Privy managed wallet", None

        try:
            balance_data = self.privy_service.get_balance(wallet_id, token_address)
            return True, "Successfully retrieved balance", balance_data
        except Exception as e:
            logger.error(
                f"Error getting balance for wallet {address}, user {user_id}: {e}"
            )
            return False, f"Error retrieving balance: {str(e)}", None

    def send_transaction(
        self,
        user_id: str,
        from_address: str,
        to_address: str,
        amount: str,
        token_address: Optional[str] = None,
        gas_limit: Optional[str] = None,
        max_fee_per_gas: Optional[str] = None,
        max_priority_fee_per_gas: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Send a transaction from a user's Privy wallet.

        Args:
            user_id: Telegram user ID
            from_address: Sender wallet address
            to_address: Recipient address
            amount: Amount to send
            token_address: Optional token address for token transfers
            gas_limit: Optional gas limit
            max_fee_per_gas: Optional max fee per gas
            max_priority_fee_per_gas: Optional max priority fee per gas

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - Transaction data if successful, None otherwise
        """
        # Get the wallet_id (stored in private_key field)
        wallet_id = self.user_service.get_wallet_private_key(user_id, from_address)

        if not wallet_id:
            return False, "This doesn't appear to be a Privy managed wallet", None

        try:
            tx_data = self.privy_service.send_transaction(
                wallet_id=wallet_id,
                to_address=to_address,
                amount=amount,
                token_address=token_address,
                gas_limit=gas_limit,
                max_fee_per_gas=max_fee_per_gas,
                max_priority_fee_per_gas=max_priority_fee_per_gas,
            )
            return True, "Transaction sent successfully", tx_data
        except Exception as e:
            logger.error(
                f"Error sending transaction from {from_address} to {to_address}, user {user_id}: {e}"
            )
            return False, f"Error sending transaction: {str(e)}", None

    def send_solana_transaction(
        self,
        user_id: str,
        from_address: str,
        to_address: str,
        amount: str,
        token_address: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Send a Solana transaction from a user's Privy wallet.

        Args:
            user_id: Telegram user ID
            from_address: Sender wallet address
            to_address: Recipient address
            amount: Amount to send (in lamports for SOL)
            token_address: Optional SPL token mint address for token transfers

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - Transaction data if successful, None otherwise
        """
        # Get the wallet_id (stored in private_key field)
        wallet_id = self.user_service.get_wallet_private_key(user_id, from_address)

        if not wallet_id:
            return False, "This doesn't appear to be a Privy managed wallet", None

        try:
            tx_data = self.privy_service.send_solana_transaction(
                wallet_id=wallet_id,
                to_address=to_address,
                amount=amount,
                token_address=token_address,
            )
            return True, "Solana transaction sent successfully", tx_data
        except Exception as e:
            logger.error(
                f"Error sending Solana transaction from {from_address} to {to_address}, user {user_id}: {e}"
            )
            return False, f"Error sending transaction: {str(e)}", None

    def create_solana_wallet(
        self, user_id: str, label: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Create a new Solana wallet for a user using Privy.

        Args:
            user_id: Telegram user ID
            label: Optional label for the wallet

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - Wallet data if successful, None otherwise
        """
        return self.create_user_wallet(
            user_id, chain_type="solana", label=label or "Privy Solana Wallet"
        )

    def get_transaction_history(
        self, user_id: str, address: str, limit: int = 10
    ) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """
        Get transaction history for a user's Privy wallet.

        Args:
            user_id: Telegram user ID
            address: Wallet address
            limit: Maximum number of transactions to return

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - List of transaction data if successful, None otherwise
        """
        # Get the wallet_id (stored in private_key field)
        wallet_id = self.user_service.get_wallet_private_key(user_id, address)

        if not wallet_id:
            return False, "This doesn't appear to be a Privy managed wallet", None

        try:
            tx_data = self.privy_service.list_transactions(wallet_id, limit)
            return (
                True,
                "Successfully retrieved transaction history",
                tx_data.get("data", []),
            )
        except Exception as e:
            logger.error(
                f"Error getting transaction history for {address}, user {user_id}: {e}"
            )
            return False, f"Error retrieving transaction history: {str(e)}", None
