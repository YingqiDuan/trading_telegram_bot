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
                "description": "Register and verify a Solana wallet",
                "parameters": {
                    "wallet_address": {
                        "type": "string",
                        "description": "The Solana wallet address",
                    },
                    "label": {
                        "type": "string",
                        "description": "Custom label for the wallet (optional)",
                    },
                    "private_key": {
                        "type": "string",
                        "description": "Private key to verify wallet ownership (optional)",
                    },
                },
                "required": ["wallet_address"],
            },
            "create_wallet": {
                "description": "Generate a new Solana wallet",
                "parameters": {
                    "label": {
                        "type": "string",
                        "description": "Custom label for the wallet (optional)",
                    },
                },
                "required": [],
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
            "send_sol": {
                "description": "Send SOL from your wallet to another address",
                "parameters": {
                    "from_wallet": {
                        "type": "string",
                        "description": "Source wallet address (optional)",
                    },
                    "to_wallet": {
                        "type": "string",
                        "description": "Destination wallet address",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of SOL to send",
                    },
                },
                "required": [],
            },
            "help": {
                "description": "Display help information",
                "parameters": {},
                "required": [],
            },
        }

    async def convert_to_command(self, user_input: str) -> str:
        """Convert natural language input to a command using a step-by-step approach.

        Steps:
        1. Check if input matches RPC commands without parameters
        2. Check if input matches wallet commands without parameters
        3. If no match so far, return 'cannot complete'
        4. If a command is found, extract parameters if any

        Args:
            user_input: The user's natural language query

        Returns:
            A command string or 'cannot complete' if conversion fails
        """
        try:
            # Step 1: Check if input matches RPC commands (without parameters)
            rpc_command = await self._try_match_command_category(
                user_input,
                [
                    "sol_balance",
                    "token_info",
                    "account_details",
                    "transaction",
                    "recent_tx",
                    "token_accounts",
                    "validators",
                    "latest_block",
                    "network_status",
                    "slot",
                ],
                "You are analyzing if this message is requesting a Solana blockchain query or RPC command.",
            )

            if rpc_command and rpc_command != "cannot complete":
                logger.info(f"Matched RPC command: {rpc_command}")

                # If the command requires parameters, try to extract them
                if self.commands[rpc_command]["required"]:
                    return await self._extract_parameters(user_input, rpc_command)
                else:
                    return rpc_command

            # Step 2: Check if input matches wallet commands (without parameters)
            wallet_command = await self._try_match_command_category(
                user_input,
                [
                    "add_wallet",
                    "create_wallet",
                    "my_wallets",
                    "remove_wallet",
                    "my_balance",
                    "send_sol",
                    "help",
                ],
                "You are analyzing if this message is requesting a wallet management operation.",
            )

            if wallet_command and wallet_command != "cannot complete":
                logger.info(f"Matched wallet command: {wallet_command}")

                # If the command requires parameters, try to extract them
                if self.commands[wallet_command]["required"]:
                    return await self._extract_parameters(user_input, wallet_command)
                else:
                    return wallet_command

            # Step 3: If we get here, no command was matched
            logger.warning("No command matched the user input")
            return "cannot complete"

        except Exception as e:
            logger.error(f"Error in convert_to_command: {e}")
            return "cannot complete"

    async def _try_match_command_category(
        self, user_input: str, command_list: list, system_message: str
    ) -> str:
        """Try to match the user input against a specific category of commands.

        Args:
            user_input: The user's query
            command_list: List of command names to check against
            system_message: System message for the AI model

        Returns:
            A matched command name or 'cannot complete'
        """
        try:
            # Build functions list for just this category
            functions = []
            for cmd_name in command_list:
                if cmd_name in self.commands:
                    function_def = {
                        "type": "function",
                        "function": {
                            "name": cmd_name,
                            "description": self.commands[cmd_name]["description"],
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        },
                    }
                    functions.append(function_def)

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
                return tool_call.function.name
            else:
                return "cannot complete"

        except Exception as e:
            logger.error(f"Error in _try_match_command_category: {e}")
            return "cannot complete"

    async def _extract_parameters(self, user_input: str, command_name: str) -> str:
        """Extract parameters for a specific command from user input.

        Args:
            user_input: The user's query
            command_name: The command to extract parameters for

        Returns:
            Command string with parameters or just the command name
        """
        try:
            # 如果用户输入与命令名非常相似，可能没有包含参数，直接返回命令名
            # 例如用户输入"recent tx"时，不应该把"recent tx"当作参数
            if user_input.lower().replace(
                " ", "_"
            ) == command_name.lower() or user_input.lower() == command_name.lower().replace(
                "_", " "
            ):
                logger.info(
                    f"User input '{user_input}' matches command name '{command_name}', not extracting parameters"
                )
                return command_name

            # 创建函数定义，仅用于此命令
            function_def = {
                "type": "function",
                "function": {
                    "name": command_name,
                    "description": self.commands[command_name]["description"],
                    "parameters": {
                        "type": "object",
                        "properties": self.commands[command_name]["parameters"],
                        "required": self.commands[command_name]["required"],
                    },
                },
            }

            # 增强系统提示，明确参数需求和验证要求
            system_message = (
                f"You are extracting parameters for the '{command_name}' command from the user's message. "
                f"Only extract parameters if they are CLEARLY and EXPLICITLY stated in the message. "
                f"DO NOT extract the command name itself as a parameter. "
                f"For wallet addresses, token addresses, and transaction signatures, only extract them "
                f"if they follow the expected format (base58 or base64 encoded string, at least 32 characters). "
                f"If no valid parameters are found, return an empty object."
            )

            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_input},
                    ],
                    tools=[function_def],
                    tool_choice={
                        "type": "function",
                        "function": {"name": command_name},
                    },
                )
            )

            # 提取函数调用详情
            response_message = response.choices[0].message

            # 检查是否有函数调用响应
            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                import json

                function_args = json.loads(tool_call.function.arguments)

                # 验证参数 - 对于常见参数类型增加额外验证
                valid_args = {}
                for param_name, value in function_args.items():
                    # 跳过空值
                    if not value:
                        continue

                    # 验证地址和签名格式
                    if param_name in [
                        "wallet_address",
                        "token_address",
                        "account_address",
                        "transaction_signature",
                    ]:
                        # 简单验证：地址和签名应至少有32个字符
                        if isinstance(value, str) and len(value) >= 32:
                            valid_args[param_name] = value
                        else:
                            logger.warning(
                                f"Rejected invalid parameter {param_name}: {value}"
                            )
                    # 验证整数参数
                    elif param_name == "limit":
                        try:
                            limit = int(value)
                            if limit > 0:
                                valid_args[param_name] = limit
                        except (ValueError, TypeError):
                            logger.warning(f"Rejected invalid limit parameter: {value}")
                    # 其他参数类型直接添加
                    else:
                        valid_args[param_name] = value

                # 如果没有有效参数，直接返回命令名
                if not valid_args:
                    logger.info(
                        f"No valid parameters found for '{command_name}' in '{user_input}'"
                    )
                    return command_name

                # 构建命令字符串
                command_parts = [command_name]

                # Add arguments in order based on the command definition
                for param_name in self.commands[command_name]["parameters"]:
                    if param_name in valid_args:
                        command_parts.append(str(valid_args[param_name]))

                final_command = " ".join(command_parts)
                logger.info(f"Extracted parameters for command: {final_command}")
                return final_command
            else:
                # 如果没有找到参数，仅返回命令名
                return command_name

        except Exception as e:
            logger.error(f"Error in _extract_parameters: {e}")
            # 错误时返回命令名
            return command_name
