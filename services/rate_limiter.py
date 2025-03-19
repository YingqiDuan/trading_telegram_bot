import time
import logging
from typing import Dict, Optional
from config import (
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_MAX_CALLS,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_SPECIAL_COMMANDS,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter to prevent abuse of the bot"""

    def __init__(self):
        self.enabled = RATE_LIMIT_ENABLED
        self.max_calls = RATE_LIMIT_MAX_CALLS
        self.window = RATE_LIMIT_WINDOW_SECONDS
        self.special = RATE_LIMIT_SPECIAL_COMMANDS
        self.history: Dict[str, Dict[str, list]] = {}
        logger.info(
            f"Rate limiter initialized: enabled={self.enabled}, max_calls={self.max_calls}, window={self.window}s"
        )

    def is_rate_limited(self, user_id: str, command: str) -> bool:
        if not self.enabled:
            return False

        now = time.time()
        self.history.setdefault(user_id, {}).setdefault(command, [])
        cutoff = now - self.window

        # Clean up expired requests
        self.history[user_id][command] = [
            t for t in self.history[user_id][command] if t > cutoff
        ]
        cmd_limit = self.special.get(command, self.max_calls)
        if len(self.history[user_id][command]) >= cmd_limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id}, command {command}: {len(self.history[user_id][command])}/{cmd_limit}"
            )
            return True

        # Check total requests across all commands
        all_requests = [
            t for cmds in self.history[user_id].values() for t in cmds if t > cutoff
        ]
        if len(all_requests) >= self.max_calls:
            logger.warning(
                f"Total rate limit exceeded for user {user_id}: {len(all_requests)}/{self.max_calls}"
            )
            return True

        self.history[user_id][command].append(now)
        return False

    def get_cooldown_time(self, user_id: str, command: Optional[str] = None) -> int:
        if not self.enabled or user_id not in self.history:
            return 0

        now = time.time()
        cutoff = now - self.window

        def calc_cd(times: list, limit: int) -> int:
            if len(times) >= limit:
                return int(min(times) + self.window - now) + 1
            return 0

        if command and command in self.history[user_id]:
            recent = [t for t in self.history[user_id][command] if t > cutoff]
            cd = calc_cd(recent, self.special.get(command, self.max_calls))
            if cd:
                return cd

        all_recent = [
            t for cmds in self.history[user_id].values() for t in cmds if t > cutoff
        ]
        return calc_cd(all_recent, self.max_calls)
