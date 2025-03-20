import asyncio
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from config import OPEN_AI_API_KEY

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=OPEN_AI_API_KEY)

        # Command definitions
        self.commands = {
            # RPC commands
            "sol_balance": {
                "description": "Check SOL balance of a wallet",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address",
                    }
                },
                "required": ["wallet_address"],
            },
            "token_info": {
                "description": "Get information about a Solana token",
                "parameters": {
                    "token_address": {
                        "type": "string",
                        "description": "The Solana token address",
                    }
                },
                "required": ["token_address"],
            },
            "account_details": {
                "description": "Get detailed information about a Solana account",
                "parameters": {
                    "account_address": {
                        "type": "string",
                        "description": "The Solana account address",
                    }
                },
                "required": ["account_address"],
            },
            "transaction": {
                "description": "Get transaction details",
                "parameters": {
                    "transaction_signature": {
                        "type": "string",
                        "description": "The Solana transaction signature",
                    }
                },
                "required": ["transaction_signature"],
            },
            "recent_tx": {
                "description": "Get recent transaction records",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of transactions to retrieve (optional)",
                    },
                },
                "required": ["wallet_address"],
            },
            "token_accounts": {
                "description": "Get token accounts owned by a wallet",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address",
                    }
                },
                "required": ["wallet_address"],
            },
            "validators": {
                "description": "Get information about validator nodes",
                "parameters": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of validators to retrieve (optional)",
                    }
                },
                "required": [],
            },
            "latest_block": {
                "description": "Get information about the latest block",
                "parameters": {},
                "required": [],
            },
            "network_status": {
                "description": "Get current Solana network status",
                "parameters": {},
                "required": [],
            },
            "slot": {
                "description": "Get current Solana slot number",
                "parameters": {},
                "required": [],
            },
            # Wallet commands
            "add_wallet": {
                "description": "Register a Solana wallet",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address",
                    },
                    "label": {
                        "type": "string",
                        "description": "Custom label for the wallet",
                    },
                },
                "required": ["wallet_address"],
            },
            "verify_wallet": {
                "description": "Verify wallet ownership",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address to verify",
                    }
                },
                "required": ["wallet_address"],
            },
            "my_wallets": {
                "description": "List registered wallets",
                "parameters": {},
                "required": [],
            },
            "remove_wallet": {
                "description": "Remove a registered wallet",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address to remove",
                    }
                },
                "required": ["wallet_address"],
            },
            "my_balance": {
                "description": "Check default wallet balance",
                "parameters": {},
                "required": [],
            },
            "help": {
                "description": "Display help information",
                "parameters": {},
                "required": [],
            },
        }

    async def convert_to_command(self, user_input: str) -> str:
        """Convert natural language input to a command using function calling

        Args:
            user_input: The user's natural language query

        Returns:
            A command string or 'cannot complete' if conversion fails
        """
        try:
            # Create function definitions for OpenAI function calling
            functions = []
            for cmd_name, cmd_def in self.commands.items():
                function_def = {
                    "type": "function",
                    "function": {
                        "name": cmd_name,
                        "description": cmd_def["description"],
                        "parameters": {
                            "type": "object",
                            "properties": cmd_def["parameters"],
                            "required": cmd_def["required"],
                        },
                    },
                }
                functions.append(function_def)

            system_message = (
                "You are a helpful assistant that processes natural language to execute Solana blockchain commands. "
                "Determine which command the user wants to execute and extract any required parameters. "
                "If you're unsure about the user's intention, choose the command that best matches the request."
            )

            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_input},
                    ],
                    tools=functions,
                    tool_choice="auto",
                )
            )

            # Extract function call details
            response_message = response.choices[0].message

            # Check if there's a function call response
            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                function_name = tool_call.function.name

                # Get arguments as a dict
                import json

                function_args = json.loads(tool_call.function.arguments)

                # Build the command string
                command_parts = [function_name]

                # Add arguments in order based on the command definition
                for param_name in self.commands[function_name]["parameters"]:
                    if param_name in function_args and function_args[param_name]:
                        command_parts.append(str(function_args[param_name]))

                final_command = " ".join(command_parts)
                logger.info(f"Function call produced command: {final_command}")
                return final_command
            else:
                logger.warning("No function call in response")
                return "cannot complete"

        except Exception as e:
            logger.error(f"Error in function calling: {e}")
            return "cannot complete"
