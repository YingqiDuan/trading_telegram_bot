import logging
from config import SOLANA_RPC_URL

# solana / solders 相关依赖
from solana.rpc.api import Client as SolanaRpcClient
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from solders.signature import Signature

logger = logging.getLogger(__name__)

# 初始化Solana RPC客户端 (使用Alchemy提供的RPC URL)
client = SolanaRpcClient(SOLANA_RPC_URL)


class SolanaService:
    """Solana区块链服务，使用Alchemy提供的RPC端点"""

    async def get_sol_balance(self, wallet_address: str) -> dict:
        """获取SOL余额"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = client.get_balance(pubkey)
            balance_sol = response.value / 1_000_000_000
            return {"balance": balance_sol, "address": wallet_address}
        except Exception as e:
            logger.error(f"Error fetching SOL balance: {e}")
            return {}

    async def get_token_info(self, token_address: str) -> dict:
        """获取代币信息"""
        try:
            pubkey = Pubkey.from_string(token_address)
            response = client.get_token_supply(pubkey)
            return {
                "address": token_address,
                "supply": response.value.amount,
                "decimals": response.value.decimals,
            }
        except Exception as e:
            logger.error(f"Error fetching token info: {e}")
            return {}

    async def get_account_details(self, account_address: str) -> dict:
        """获取账户详情"""
        try:
            pubkey = Pubkey.from_string(account_address)
            response = client.get_account_info(pubkey)
            if response.value is not None:
                return {
                    "address": account_address,
                    "lamports": response.value.lamports,
                    "owner": str(response.value.owner),
                    "executable": response.value.executable,
                    "rent_epoch": response.value.rent_epoch,
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching account details: {e}")
            return {}

    async def get_latest_block(self) -> dict:
        """获取最新区块"""
        try:
            response = client.get_latest_blockhash()
            return {
                "blockhash": str(response.value.blockhash),
                "last_valid_block_height": response.value.last_valid_block_height,
            }
        except Exception as e:
            logger.error(f"Error fetching latest block: {e}")
            return {}

    async def get_network_status(self) -> dict:
        """获取网络状态"""
        try:
            response = client.get_version()
            return {
                "solana_core": response.value.solana_core,
                "feature_set": response.value.feature_set,
            }
        except Exception as e:
            logger.error(f"Error fetching network status: {e}")
            return {}

    async def get_transaction_details(self, signature: str) -> dict:
        """获取交易详情"""
        try:
            sig = Signature.from_string(signature)
            response = client.get_transaction(sig)
            if response.value is not None:
                return {
                    "signature": signature,
                    "slot": response.value.slot,
                    "block_time": response.value.block_time,
                    "success": response.value.meta.err is None,
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching transaction details: {e}")
            return {}

    async def get_recent_transactions(
        self, wallet_address: str, limit: int = 5
    ) -> list:
        """获取最近交易"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = client.get_signatures_for_address(pubkey, limit=limit)
            result = []
            for item in response.value:
                tx = {
                    "signature": str(item.signature),
                    "slot": item.slot,
                    "block_time": item.block_time,
                    "success": item.err is None,
                }
                result.append(tx)
            return result
        except Exception as e:
            logger.error(f"Error fetching recent transactions: {e}")
            return []

    async def get_validators(self, limit: int = 5) -> list:
        """获取验证者信息"""
        try:
            response = client.get_vote_accounts()
            validators = response.value.current
            result = []
            for validator in validators[:limit]:
                result.append(
                    {
                        "vote_pubkey": str(validator.vote_pubkey),
                        "activated_stake": validator.activated_stake / 1_000_000_000,
                        "commission": validator.commission,
                        "last_vote": validator.last_vote,
                    }
                )
            return result
        except Exception as e:
            logger.error(f"Error fetching validators: {e}")
            return []

    async def get_token_accounts(self, wallet_address: str) -> list:
        """获取代币账户"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            token_program_id = Pubkey.from_string(
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
            )
            opts = TokenAccountOpts(program_id=token_program_id)
            response = client.get_token_accounts_by_owner(pubkey, opts)
            result = []
            if response.value:
                for item in response.value:
                    account_data = {
                        "pubkey": str(item.pubkey),
                        "mint": "Token Account",
                        "amount": "Available",
                    }
                    result.append(account_data)
            return result
        except Exception as e:
            logger.error(f"Error fetching token accounts: {e}")
            return []

    async def get_slot(self) -> int:
        """获取当前槽位"""
        try:
            response = client.get_slot()
            return response.value
        except Exception as e:
            logger.error(f"Error fetching current slot: {e}")
            return 0
