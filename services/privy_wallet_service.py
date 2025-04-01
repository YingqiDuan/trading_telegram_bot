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
        self, chain_type: str = "solana", linked_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {"chain_type": chain_type}

        if linked_user_id:
            data["linked_user_id"] = linked_user_id

        return self._make_request("POST", "/v1/wallets", data)

    def get_wallet(self, wallet_id: str) -> Dict[str, Any]:
        return self._make_request("GET", f"/v1/wallets/{wallet_id}")

    def list_wallets(
        self,
        limit: int = 100,
        starting_after: Optional[str] = None,
        linked_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        endpoint = f"/v1/wallets?limit={limit}"
        if starting_after:
            endpoint += f"&starting_after={starting_after}"
        if linked_user_id:
            endpoint += f"&linked_user_id={linked_user_id}"

        return self._make_request("GET", endpoint)

    def delete_wallet(self, wallet_id: str) -> Dict[str, Any]:
        return self._make_request("DELETE", f"/v1/wallets/{wallet_id}")

    # Transaction Management

    def get_balance(
        self, wallet_id: str, token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            endpoint = f"/v1/wallets/{wallet_id}/balance"
            if token_address:
                endpoint += f"?token_address={token_address}"

            return self._make_request("GET", endpoint)
        except requests.exceptions.HTTPError as e:
            if hasattr(e, "response") and e.response.status_code == 404:
                # If wallet not found, try to get wallet info first to confirm it exists
                try:
                    self.get_wallet(wallet_id)
                    # If we get here, wallet exists but balance endpoint failed
                    logger.warning(
                        f"Wallet {wallet_id} exists but balance endpoint returned 404"
                    )
                    raise
                except:
                    # Wallet doesn't exist
                    logger.error(f"Wallet {wallet_id} not found")
                    raise
            else:
                raise

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
        return self._make_request(
            "GET", f"/v1/wallets/{wallet_id}/transactions/{transaction_id}"
        )

    def list_transactions(self, wallet_id: str, limit: int = 10) -> Dict[str, Any]:
        return self._make_request(
            "GET", f"/v1/wallets/{wallet_id}/transactions?limit={limit}"
        )

    # Solana-specific methods

    def create_solana_wallet(
        self, linked_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return self.create_wallet(chain_type="solana", linked_user_id=linked_user_id)

    def send_solana_transaction(
        self,
        wallet_id: str,
        to_address: str,
        amount: str,
        token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Privy的Solana交易需要使用正确的方法和参数
        # 参考文档：https://docs.privy.io/api-reference/wallets/solana/sign-and-send-transaction

        # 对于简单的SOL转账，我们使用rpc端点和signAndSendTransaction方法
        # 注意：这里的实现可能需要根据Privy的具体API要求进行调整

        # 1. 将金额转换为lamports（SOL的最小单位，1 SOL = 10^9 lamports）
        try:
            # 如果amount是浮点数字符串（例如"0.001"），转换为lamports
            if "." in amount:
                sol_amount = float(amount)
                lamports = int(sol_amount * 1e9)
            else:
                # 如果已经是整数字符串，假设已经是lamports
                lamports = int(amount)
        except ValueError:
            raise ValueError(f"Invalid amount format: {amount}")

        logger.info(f"Converting {amount} SOL to {lamports} lamports")

        # 2. 构建RPC请求
        rpc_data = {
            "method": "signAndSendTransaction",
            "caip2": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
            "params": {"to_address": to_address, "amount": str(lamports)},
        }

        if token_address:
            rpc_data["params"]["token_address"] = token_address

        logger.info(
            f"Sending RPC request to wallet {wallet_id}: {json.dumps(rpc_data)}"
        )
        return self._make_request("POST", f"/v1/wallets/{wallet_id}/rpc", rpc_data)
