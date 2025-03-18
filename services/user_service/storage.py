import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_user_data(storage_file: str) -> Dict[str, Any]:
    if not os.path.exists(storage_file):
        return {}
    try:
        with open(storage_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading user data: {e}")
        return {}


def save_user_data(storage_file: str, data: Dict[str, Any]) -> bool:
    try:
        with open(storage_file, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Error saving user data: {e}")
        return False
