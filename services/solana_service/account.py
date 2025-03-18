# solana_service/account.py
import logging
from solders.pubkey import Pubkey
from services.solana_service.base import client

logger = logging.getLogger(__name__)


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
