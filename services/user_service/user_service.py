import logging
from typing import Dict, Any, Optional, Tuple, List
from config import USER_WALLET_STORAGE_FILE
from .storage import load_user_data, save_user_data
from .wallet_manager import (
    get_user_wallets,
    has_verified_wallet,
    add_wallet,
    remove_wallet,
    get_default_wallet,
    mark_wallet_verified,
)
from .verification import generate_verification_challenge, verify_wallet

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self):
        self.storage_file = USER_WALLET_STORAGE_FILE
        self._users_data: Dict[str, Any] = load_user_data(self.storage_file)

    def _save(self) -> None:
        save_user_data(self.storage_file, self._users_data)

    def get_user_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        return get_user_wallets(self._users_data, user_id)

    def has_verified_wallet(self, user_id: str) -> bool:
        return has_verified_wallet(self._users_data, user_id)

    def add_wallet(
        self, user_id: str, address: str, label: Optional[str] = None
    ) -> Tuple[bool, str]:
        success, msg = add_wallet(self._users_data, user_id, address, label)
        if success:
            self._save()
        return success, msg

    def remove_wallet(self, user_id: str, address: str) -> Tuple[bool, str]:
        success, msg = remove_wallet(self._users_data, user_id, address)
        if success:
            self._save()
        return success, msg

    def get_default_wallet(self, user_id: str) -> Optional[str]:
        return get_default_wallet(self._users_data, user_id)

    def generate_verification_challenge(
        self, user_id: str, address: str, method: str = "signature"
    ) -> Tuple[bool, str]:
        success, msg = generate_verification_challenge(
            self._users_data, user_id, address, method
        )
        if success:
            self._save()
        return success, msg

    def verify_wallet(
        self,
        user_id: str,
        address: str,
        method: Optional[str] = None,
        verification_data: Optional[str] = None,
    ) -> Tuple[bool, str]:
        success, msg = verify_wallet(
            self._users_data, user_id, address, method, verification_data
        )
        if success:
            self._save()
        return success, msg
