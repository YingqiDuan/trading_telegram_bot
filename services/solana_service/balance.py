# solana_service/balance.py
import logging
from solders.pubkey import Pubkey
from base import client

logger = logging.getLogger(__name__)


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
