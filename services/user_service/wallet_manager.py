import time
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def get_user_wallets(user_data: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
    return user_data.get(user_id, {}).get("wallets", [])


def has_verified_wallet(user_data: Dict[str, Any], user_id: str) -> bool:
    wallets = get_user_wallets(user_data, user_id)
    return any(wallet.get("verified") for wallet in wallets)


def add_wallet(
    user_data: Dict[str, Any], user_id: str, address: str, label: Optional[str] = None
) -> tuple[bool, str]:
    user = user_data.setdefault(user_id, {"wallets": [], "pending_verifications": {}})
    if any(w["address"].lower() == address.lower() for w in user["wallets"]):
        return False, "This wallet is already registered to your account."
    user["wallets"].append(
        {
            "address": address,
            "label": label or "My Wallet",
            "verified": False,
            "added_at": int(time.time()),
        }
    )
    return True, f"Wallet {address} added. Please verify ownership."


def remove_wallet(
    user_data: Dict[str, Any], user_id: str, address: str
) -> tuple[bool, str]:
    user = user_data.get(user_id, {})
    wallets = user.get("wallets", [])
    for i, wallet in enumerate(wallets):
        if wallet["address"].lower() == address.lower():
            del wallets[i]
            user.get("pending_verifications", {}).pop(address, None)
            return True, f"Wallet {address} has been removed from your account."
    return False, "This wallet is not registered to your account."


def get_default_wallet(user_data: Dict[str, Any], user_id: str) -> Optional[str]:
    wallets = get_user_wallets(user_data, user_id)
    verified = next((w for w in wallets if w.get("verified")), None)
    return (
        verified["address"]
        if verified
        else (wallets[0]["address"] if wallets else None)
    )


def mark_wallet_verified(user_data: Dict[str, Any], user_id: str, address: str) -> None:
    for wallet in user_data.get(user_id, {}).get("wallets", []):
        if wallet["address"].lower() == address.lower():
            wallet.update({"verified": True, "verified_at": int(time.time())})
    user_data.get(user_id, {}).get("pending_verifications", {}).pop(address, None)
