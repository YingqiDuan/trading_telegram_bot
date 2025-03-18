# solana_service/transaction.py
import logging
from solders.signature import Signature
from base import client

logger = logging.getLogger(__name__)


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
        from solders.pubkey import Pubkey

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
