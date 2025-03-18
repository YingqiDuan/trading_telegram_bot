# solana_service/token.py
import logging
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts
from services.solana_service.base import client

logger = logging.getLogger(__name__)


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
