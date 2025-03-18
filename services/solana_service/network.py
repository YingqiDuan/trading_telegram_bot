# solana_service/network.py
import logging
from services.solana_service.base import client

logger = logging.getLogger(__name__)


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
