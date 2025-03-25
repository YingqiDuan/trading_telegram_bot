import json, time, random, string, requests, base58, nacl.signing, nacl.exceptions, logging, ast, base64
from typing import Dict, Any, Optional, Tuple, List

# Import the SQLite-based implementation
from services.user_service_sqlite import UserService as SQLiteUserService

logger = logging.getLogger(__name__)


# Proxy class that forwards calls to SQLite implementation
class UserService:
    """Service for managing user wallets and verification."""

    def __init__(self):
        # Initialize the SQLite-based service
        self._service = SQLiteUserService()

    def get_user_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        return self._service.get_user_wallets(user_id)

    def has_verified_wallet(self, user_id: str) -> bool:
        return self._service.has_verified_wallet(user_id)

    def add_wallet(
        self, user_id: str, address: str, label: Optional[str] = None
    ) -> Tuple[bool, str]:
        return self._service.add_wallet(user_id, address, label)

    def remove_wallet(self, user_id: str, address: str) -> Tuple[bool, str]:
        return self._service.remove_wallet(user_id, address)

    def get_default_wallet(self, user_id: str) -> Optional[str]:
        return self._service.get_default_wallet(user_id)

    def generate_verification_challenge(
        self, user_id: str, address: str, method: str = "signature"
    ) -> Tuple[bool, str]:
        return self._service.generate_verification_challenge(user_id, address, method)

    def verify_wallet(
        self,
        user_id: str,
        address: str,
        method: Optional[str] = None,
        verification_data: Optional[str] = None,
    ) -> Tuple[bool, str]:
        return self._service.verify_wallet(user_id, address, method, verification_data)


# Keep the functions below as they might be imported directly in some parts of the code
# but delegate the implementation to SQLiteUserService's internal functions

# These functions below are kept for backwards compatibility
# but they should not be used directly anymore


def load_user_data(storage_file: str) -> Dict[str, Any]:
    logger.warning("Legacy load_user_data called - deprecated")
    return {}


def save_user_data(storage_file: str, data: Dict[str, Any]) -> bool:
    logger.warning("Legacy save_user_data called - deprecated")
    return True


def get_user_wallets(user_data: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
    logger.warning("Legacy get_user_wallets called - deprecated")
    service = SQLiteUserService()
    return service.get_user_wallets(user_id)


def has_verified_wallet(user_data: Dict[str, Any], user_id: str) -> bool:
    logger.warning("Legacy has_verified_wallet called - deprecated")
    service = SQLiteUserService()
    return service.has_verified_wallet(user_id)


def add_wallet(
    user_data: Dict[str, Any], user_id: str, address: str, label: Optional[str] = None
) -> Tuple[bool, str]:
    logger.warning("Legacy add_wallet called - deprecated")
    service = SQLiteUserService()
    return service.add_wallet(user_id, address, label)


def remove_wallet(
    user_data: Dict[str, Any], user_id: str, address: str
) -> Tuple[bool, str]:
    logger.warning("Legacy remove_wallet called - deprecated")
    service = SQLiteUserService()
    return service.remove_wallet(user_id, address)


def get_default_wallet(user_data: Dict[str, Any], user_id: str) -> Optional[str]:
    logger.warning("Legacy get_default_wallet called - deprecated")
    service = SQLiteUserService()
    return service.get_default_wallet(user_id)


def mark_wallet_verified(user_data: Dict[str, Any], user_id: str, address: str) -> None:
    logger.warning("Legacy mark_wallet_verified called - deprecated")
    # No direct equivalent in the SQLite service structure
    # This is handled internally within verify_wallet


def generate_verification_challenge(
    user_data: Dict[str, Any], user_id: str, address: str, method: str = "signature"
) -> Tuple[bool, str]:
    logger.warning("Legacy generate_verification_challenge called - deprecated")
    service = SQLiteUserService()
    return service.generate_verification_challenge(user_id, address, method)


def verify_wallet(
    user_data: Dict[str, Any],
    user_id: str,
    address: str,
    method: Optional[str] = None,
    verification_data: Optional[str] = None,
) -> Tuple[bool, str]:
    logger.warning("Legacy verify_wallet called - deprecated")
    service = SQLiteUserService()
    return service.verify_wallet(user_id, address, method, verification_data)
