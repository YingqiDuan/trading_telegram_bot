# solana_service/solana_service.py
from .balance import get_sol_balance
from .token import get_token_info, get_token_accounts
from .account import get_account_details
from .block import get_latest_block, get_slot
from .network import get_network_status
from .transaction import get_transaction_details, get_recent_transactions
from .validators import get_validators


class SolanaService:
    """Service for interacting with the Solana blockchain"""

    async def get_sol_balance(self, wallet_address: str) -> dict:
        return await get_sol_balance(wallet_address)

    async def get_token_info(self, token_address: str) -> dict:
        return await get_token_info(token_address)

    async def get_account_details(self, account_address: str) -> dict:
        return await get_account_details(account_address)

    async def get_latest_block(self) -> dict:
        return await get_latest_block()

    async def get_network_status(self) -> dict:
        return await get_network_status()

    async def get_transaction_details(self, signature: str) -> dict:
        return await get_transaction_details(signature)

    async def get_recent_transactions(
        self, wallet_address: str, limit: int = 5
    ) -> list:
        return await get_recent_transactions(wallet_address, limit)

    async def get_validators(self, limit: int = 5) -> list:
        return await get_validators(limit)

    async def get_token_accounts(self, wallet_address: str) -> list:
        return await get_token_accounts(wallet_address)

    async def get_slot(self) -> int:
        return await get_slot()
