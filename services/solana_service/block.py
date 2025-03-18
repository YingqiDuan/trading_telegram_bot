# solana_service/block.py
import logging
from services.solana_service.base import client

logger = logging.getLogger(__name__)


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
