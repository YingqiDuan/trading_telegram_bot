import asyncio
import logging
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from config import OPEN_AI_API_KEY

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API"""

    def __init__(self):
        """Initialize OpenAI service with API client"""
        self.client = OpenAI(api_key=OPEN_AI_API_KEY)

    async def convert_to_command(self, user_input: str) -> str:
        """Convert natural language input to a specific command

        Args:
            user_input: The user's natural language query

        Returns:
            A command string or 'cannot complete' if conversion fails
        """
        system_prompt = (
            "You are an intelligent assistant that can convert a natural language question "
            "into one of the following commands. Only output the command and parameter (separated by a space) with no additional text. "
            "Available commands:\n"
            "sol_balance [wallet address] - Get SOL balance for a wallet\n"
            "token_info [token address] - Get information about a Solana token\n"
            "account_details [account address] - Get details about a Solana account\n"
            "transaction [signature] - Get transaction details by signature\n"
            "recent_tx [wallet address] [limit] - Get recent transactions for a wallet\n"
            "token_accounts [wallet address] - Get token accounts owned by wallet\n"
            "validators [limit] - Get information about active validators\n"
            "latest_block - Get information about the latest block\n"
            "network_status - Get current Solana network status\n"
            "slot - Get current Solana slot number\n"
            "If the question cannot be categorized into one of these commands, output only 'cannot complete'."
        )

        messages = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_input),
        ]

        try:
            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                )
            )

            if response and hasattr(response, "choices") and len(response.choices) > 0:
                if (
                    hasattr(response.choices[0].message, "content")
                    and response.choices[0].message.content
                ):
                    reply = response.choices[0].message.content.strip()
                    logger.info(f"OpenAI returned command: {reply}")
                    return reply

            logger.error("Invalid response format from OpenAI")
            return "cannot complete"
        except Exception as e:
            logger.error(f"Error calling OpenAI model: {e}")
            return "cannot complete"
