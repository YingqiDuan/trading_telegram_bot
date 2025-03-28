import requests
import base64
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
import config

logger = logging.getLogger(__name__)


class PrivyWalletService:
    def __init__(self):
        self.app_id = config.PRIVY_APP_ID
        self.app_secret = config.PRIVY_APP_SECRET
        self.base_url = config.PRIVY_API_BASE_URL
        self.auth_header = self._create_auth_header()

    def _create_auth_header(self) -> str:
        """Create the Basic Authorization header for Privy API."""
        credentials = f"{self.app_id}:{self.app_secret}"
        encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode(
            "utf-8"
        )
        return f"Basic {encoded_credentials}"

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Privy API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/v1/wallets')
            data: Request payload for POST requests

        Returns:
            Response data as a dictionary
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "privy-app-id": self.app_id,
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            error_detail = e.response.text if hasattr(e, "response") else str(e)
            logger.error(f"Error details: {error_detail}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise

    # Wallet Management

    def create_wallet(
        self, chain_type: str = "ethereum", linked_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new wallet.

        Args:
            chain_type: Blockchain type ("ethereum" or "solana")
            linked_user_id: Optional user ID to associate with this wallet

        Returns:
            Wallet details including ID and address
        """
        data = {"chain_type": chain_type}

        if linked_user_id:
            data["linked_user_id"] = linked_user_id

        return self._make_request("POST", "/v1/wallets", data)

    def get_wallet(self, wallet_id: str) -> Dict[str, Any]:
        """Get details of a specific wallet.

        Args:
            wallet_id: The ID of the wallet to retrieve

        Returns:
            Wallet details
        """
        return self._make_request("GET", f"/v1/wallets/{wallet_id}")

    def list_wallets(
        self, limit: int = 100, starting_after: Optional[str] = None
    ) -> Dict[str, Any]:
        """List wallets associated with the app.

        Args:
            limit: Maximum number of wallets to return
            starting_after: Wallet ID to start listing after

        Returns:
            List of wallets
        """
        endpoint = f"/v1/wallets?limit={limit}"
        if starting_after:
            endpoint += f"&starting_after={starting_after}"

        return self._make_request("GET", endpoint)

    def delete_wallet(self, wallet_id: str) -> Dict[str, Any]:
        """Delete a wallet.

        Args:
            wallet_id: The ID of the wallet to delete

        Returns:
            Deletion confirmation
        """
        return self._make_request("DELETE", f"/v1/wallets/{wallet_id}")

    # Transaction Management

    def get_balance(
        self, wallet_id: str, token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the balance of a wallet.

        Args:
            wallet_id: The ID of the wallet
            token_address: Optional token address to check balance for

        Returns:
            Balance information
        """
        endpoint = f"/v1/wallets/{wallet_id}/balance"
        if token_address:
            endpoint += f"?token_address={token_address}"

        return self._make_request("GET", endpoint)

    def send_transaction(
        self,
        wallet_id: str,
        to_address: str,
        amount: str,
        token_address: Optional[str] = None,
        gas_limit: Optional[str] = None,
        max_fee_per_gas: Optional[str] = None,
        max_priority_fee_per_gas: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a transaction from a wallet.

        Args:
            wallet_id: The ID of the source wallet
            to_address: Recipient address
            amount: Amount to send (in wei for Ethereum)
            token_address: Optional token address for token transfers
            gas_limit: Optional gas limit
            max_fee_per_gas: Optional max fee per gas
            max_priority_fee_per_gas: Optional max priority fee per gas

        Returns:
            Transaction details
        """
        data = {"to_address": to_address, "amount": amount}

        # Add optional parameters if provided
        if token_address:
            data["token_address"] = token_address
        if gas_limit:
            data["gas_limit"] = gas_limit
        if max_fee_per_gas:
            data["max_fee_per_gas"] = max_fee_per_gas
        if max_priority_fee_per_gas:
            data["max_priority_fee_per_gas"] = max_priority_fee_per_gas

        return self._make_request("POST", f"/v1/wallets/{wallet_id}/send", data)

    def get_transaction(self, wallet_id: str, transaction_id: str) -> Dict[str, Any]:
        """Get details of a specific transaction.

        Args:
            wallet_id: The ID of the wallet
            transaction_id: The ID of the transaction

        Returns:
            Transaction details
        """
        return self._make_request(
            "GET", f"/v1/wallets/{wallet_id}/transactions/{transaction_id}"
        )

    def list_transactions(self, wallet_id: str, limit: int = 10) -> Dict[str, Any]:
        """List transactions for a wallet.

        Args:
            wallet_id: The ID of the wallet
            limit: Maximum number of transactions to return

        Returns:
            List of transactions
        """
        return self._make_request(
            "GET", f"/v1/wallets/{wallet_id}/transactions?limit={limit}"
        )

    # Solana-specific methods

    def create_solana_wallet(
        self, linked_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new Solana wallet.

        Args:
            linked_user_id: Optional user ID to associate with this wallet

        Returns:
            Wallet details including ID and address
        """
        return self.create_wallet(chain_type="solana", linked_user_id=linked_user_id)

    def send_solana_transaction(
        self,
        wallet_id: str,
        to_address: str,
        amount: str,
        token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a Solana transaction from a wallet.

        Args:
            wallet_id: The ID of the source wallet
            to_address: Recipient address
            amount: Amount to send (in lamports for SOL)
            token_address: Optional SPL token mint address for token transfers

        Returns:
            Transaction details
        """
        data = {"to_address": to_address, "amount": amount}

        if token_address:
            data["token_address"] = token_address

        return self._make_request("POST", f"/v1/wallets/{wallet_id}/send", data)
