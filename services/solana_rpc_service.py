import logging

from config import SOLANA_RPC_URL

# solana / solders 相关依赖
from solana.rpc.api import Client as SolanaRpcClient
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from solders.signature import Signature

logger = logging.getLogger(__name__)

client = SolanaRpcClient(SOLANA_RPC_URL)


class SolanaService:
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


async def get_account_details(account_address: str) -> dict:
    try:
        pubkey = Pubkey.from_string(account_address)
        response = client.get_account_info(pubkey)
        if hasattr(response, "value") and response.value is not None:
            return {
                "address": account_address,
                "lamports": response.value.lamports,
                "owner": str(response.value.owner),
                "executable": response.value.executable,
                "rent_epoch": response.value.rent_epoch,
            }
        elif (
            isinstance(response, dict)
            and "result" in response
            and "value" in response["result"]
        ):
            account_data = response["result"]["value"]
            return {
                "address": account_address,
                "lamports": account_data["lamports"],
                "owner": account_data["owner"],
                "executable": account_data["executable"],
                "rent_epoch": account_data["rentEpoch"],
            }
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching account details: {e}")
    return {}


async def get_sol_balance(wallet_address: str) -> dict:
    try:
        pubkey = Pubkey.from_string(wallet_address)
        response = client.get_balance(pubkey)
        if hasattr(response, "value"):
            balance_sol = response.value / 1_000_000_000
            return {"balance": balance_sol, "address": wallet_address}
        elif isinstance(response, dict) and "result" in response:
            if "value" in response["result"]:
                balance_sol = response["result"]["value"] / 1_000_000_000
                return {"balance": balance_sol, "address": wallet_address}
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching SOL balance: {e}")
    return {}


async def get_token_info(token_address: str) -> dict:
    try:
        pubkey = Pubkey.from_string(token_address)
        response = client.get_token_supply(pubkey)
        if hasattr(response, "value"):
            return {
                "address": token_address,
                "supply": response.value.amount,
                "decimals": response.value.decimals,
            }
        elif (
            isinstance(response, dict)
            and "result" in response
            and "value" in response["result"]
        ):
            token_data = response["result"]["value"]
            return {
                "address": token_address,
                "supply": token_data["amount"],
                "decimals": token_data["decimals"],
            }
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching token info: {e}")
    return {}


async def get_token_accounts(wallet_address: str) -> list:
    try:
        pubkey = Pubkey.from_string(wallet_address)
        token_program_id = Pubkey.from_string(
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        )
        opts = TokenAccountOpts(program_id=token_program_id)
        response = client.get_token_accounts_by_owner(pubkey, opts)
        result = []
        if hasattr(response, "value") and response.value:
            for item in response.value:
                account_data = {"pubkey": str(getattr(item, "pubkey", "Unknown"))}
                try:
                    if hasattr(item, "account") and hasattr(item.account, "data"):
                        account_data["data"] = "Token Account Data Available"
                except AttributeError:
                    pass
                result.append(account_data)
        elif isinstance(response, dict) and "result" in response:
            for item in response["result"].get("value", []):
                account_data = {
                    "pubkey": item.get("pubkey", "Unknown"),
                    "data": "Token Account Data Available",
                }
                result.append(account_data)
        return result
    except Exception as e:
        logger.error(f"Error fetching token accounts: {e}")
    return []


async def get_latest_block() -> dict:
    try:
        response = client.get_latest_blockhash()
        if hasattr(response, "value"):
            return {
                "blockhash": response.value.blockhash,
                "last_valid_block_height": response.value.last_valid_block_height,
            }
        elif (
            isinstance(response, dict)
            and "result" in response
            and "value" in response["result"]
        ):
            block_data = response["result"]["value"]
            return {
                "blockhash": block_data["blockhash"],
                "last_valid_block_height": block_data["lastValidBlockHeight"],
            }
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching latest block: {e}")
    return {}


async def get_slot() -> int:
    try:
        response = client.get_slot()
        if hasattr(response, "value"):
            return response.value
        elif isinstance(response, dict) and "result" in response:
            return response["result"]
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching current slot: {e}")
    return 0


async def get_network_status() -> dict:
    try:
        response = client.get_version()
        if hasattr(response, "value"):
            version_data = response.value
            return {
                "solana_core": getattr(version_data, "solana_core", "Unknown"),
                "feature_set": getattr(version_data, "feature_set", "Unknown"),
            }
        elif hasattr(response, "version") or hasattr(response, "solana_core"):
            return {
                "solana_core": getattr(
                    response, "solana_core", getattr(response, "version", "Unknown")
                ),
                "feature_set": getattr(response, "feature_set", "Unknown"),
            }
        elif isinstance(response, dict) and "result" in response:
            version_data = response["result"]
            return {
                "solana_core": version_data.get("solana-core", "Unknown"),
                "feature_set": version_data.get("feature-set", "Unknown"),
            }
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching network status: {e}")
    return {}


async def get_transaction_details(signature: str) -> dict:
    try:
        sig = Signature.from_string(signature)
        response = client.get_transaction(sig)
        if hasattr(response, "value") and response.value is not None:
            result = {
                "signature": signature,
                "slot": getattr(response.value, "slot", None),
                "block_time": getattr(response.value, "block_time", None),
                "success": True,
            }
            meta = getattr(response.value, "meta", None)
            if meta is not None:
                err = getattr(meta, "err", None)
                if err is not None:
                    result["success"] = False
            return result
        elif isinstance(response, dict) and "result" in response:
            if response["result"] is not None:
                tx_data = response["result"]
                return {
                    "signature": signature,
                    "slot": tx_data.get("slot"),
                    "block_time": tx_data.get("blockTime"),
                    "success": "err" not in tx_data.get("meta", {})
                    or tx_data["meta"]["err"] is None,
                }
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching transaction details: {e}")
    return {}


async def get_recent_transactions(wallet_address: str, limit: int = 5) -> list:
    try:
        pubkey = Pubkey.from_string(wallet_address)
        response = client.get_signatures_for_address(pubkey, limit=limit)
        result = []
        if hasattr(response, "value") and response.value:
            for item in response.value:
                tx = {
                    "signature": str(getattr(item, "signature", "Unknown")),
                    "slot": getattr(item, "slot", None),
                    "block_time": getattr(item, "block_time", None),
                    "success": not (hasattr(item, "err") and item.err is not None),
                }
                result.append(tx)
            return result
        elif isinstance(response, dict) and "result" in response:
            for item in response["result"]:
                tx = {
                    "signature": item.get("signature"),
                    "slot": item.get("slot"),
                    "block_time": item.get("blockTime"),
                    "success": "err" not in item or item["err"] is None,
                }
                result.append(tx)
            return result
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching recent transactions: {e}")
    return []


async def get_validators(limit: int = 5) -> list:
    try:
        response = client.get_vote_accounts()
        result = []
        if hasattr(response, "value"):
            validators = getattr(response.value, "current", [])
            for validator in validators[:limit]:
                result.append(
                    {
                        "node_pubkey": str(
                            getattr(validator, "node_pubkey", "Unknown")
                        ),
                        "vote_pubkey": str(
                            getattr(validator, "vote_pubkey", "Unknown")
                        ),
                        "activated_stake": getattr(validator, "activated_stake", 0)
                        / 1_000_000_000,
                        "commission": getattr(validator, "commission", 0),
                        "last_vote": getattr(validator, "last_vote", 0),
                    }
                )
            return result
        elif isinstance(response, dict) and "result" in response:
            validators = response["result"].get("current", [])
            for validator in validators[:limit]:
                result.append(
                    {
                        "node_pubkey": validator.get("nodePubkey"),
                        "vote_pubkey": validator.get("votePubkey"),
                        "activated_stake": validator.get("activatedStake", 0)
                        / 1_000_000_000,
                        "commission": validator.get("commission"),
                        "last_vote": validator.get("lastVote"),
                    }
                )
            return result
        logger.error(f"Unexpected response format from Solana RPC: {response}")
    except Exception as e:
        logger.error(f"Error fetching validators: {e}")
    return []
