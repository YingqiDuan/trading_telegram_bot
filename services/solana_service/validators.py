# solana_service/validators.py
import logging
from base import client

logger = logging.getLogger(__name__)


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
