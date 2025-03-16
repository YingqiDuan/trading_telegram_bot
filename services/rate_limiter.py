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
        """Initialize the rate limiter with empty request history"""
        self.enabled = RATE_LIMIT_ENABLED
        self.max_calls = RATE_LIMIT_MAX_CALLS
        self.window_seconds = RATE_LIMIT_WINDOW_SECONDS
        self.special_commands = RATE_LIMIT_SPECIAL_COMMANDS

        # Store command call history: {user_id: {command: [timestamp1, timestamp2, ...]}}
        self.request_history: Dict[str, Dict[str, list]] = {}

        logger.info(
            f"Rate limiter initialized: enabled={self.enabled}, "
            f"max_calls={self.max_calls}, window={self.window_seconds}s"
        )

    def is_rate_limited(self, user_id: str, command: str) -> bool:
        """Check if a user has exceeded their rate limit for a command

        Args:
            user_id: Telegram user ID
            command: Command being executed

        Returns:
            True if rate limited, False otherwise
        """
        if not self.enabled:
            return False

        current_time = time.time()

        # Initialize request history for user if needed
        if user_id not in self.request_history:
            self.request_history[user_id] = {}

        if command not in self.request_history[user_id]:
            self.request_history[user_id][command] = []

        # Clean up old requests outside the time window
        time_limit = current_time - self.window_seconds
        self.request_history[user_id][command] = [
            t for t in self.request_history[user_id][command] if t > time_limit
        ]

        # Get limit for this specific command or use default
        command_limit = self.special_commands.get(command, self.max_calls)

        # Check if user has exceeded their command-specific limit
        if len(self.request_history[user_id][command]) >= command_limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id}, command {command}: "
                f"{len(self.request_history[user_id][command])}/{command_limit}"
            )
            return True

        # Also check total requests across all commands
        all_requests = []
        for cmd, timestamps in self.request_history[user_id].items():
            all_requests.extend([t for t in timestamps if t > time_limit])

        if len(all_requests) >= self.max_calls:
            logger.warning(
                f"Total rate limit exceeded for user {user_id}: "
                f"{len(all_requests)}/{self.max_calls}"
            )
            return True

        # Add current request to history
        self.request_history[user_id][command].append(current_time)
        return False

    def get_cooldown_time(self, user_id: str, command: Optional[str] = None) -> int:
        """Calculate cooldown time in seconds until user can make another request

        Args:
            user_id: Telegram user ID
            command: Optional specific command to check

        Returns:
            Seconds until next available request (0 if not rate limited)
        """
        if not self.enabled or user_id not in self.request_history:
            return 0

        current_time = time.time()
        time_limit = current_time - self.window_seconds

        if command:
            # Check specific command
            if command in self.request_history[user_id]:
                # Filter requests to get only those within time window
                recent_requests = [
                    t for t in self.request_history[user_id][command] if t > time_limit
                ]

                command_limit = self.special_commands.get(command, self.max_calls)

                if len(recent_requests) >= command_limit and recent_requests:
                    # Sort by timestamp so oldest is first
                    recent_requests.sort()
                    # Calculate time until oldest request expires from window
                    return (
                        int(recent_requests[0] + self.window_seconds - current_time) + 1
                    )

        # Check all commands
        all_requests = []
        for cmd, timestamps in self.request_history[user_id].items():
            all_requests.extend([t for t in timestamps if t > time_limit])

        if all_requests and len(all_requests) >= self.max_calls:
            all_requests.sort()
            return int(all_requests[0] + self.window_seconds - current_time) + 1

        return 0
