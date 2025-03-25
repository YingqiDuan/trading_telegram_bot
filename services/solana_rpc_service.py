import logging
from config import SOLANA_RPC_URL, SOLANA_BACKUP_RPC_URL

# solana / solders 相关依赖
from solana.rpc.api import Client as SolanaRpcClient
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.keypair import Keypair
import base58
import ast

logger = logging.getLogger(__name__)


class SolanaService:
    """Solana区块链服务，支持RPC节点切换"""

    def __init__(self):
        self.primary_client = SolanaRpcClient(SOLANA_RPC_URL)
        self.backup_client = SolanaRpcClient(SOLANA_BACKUP_RPC_URL)
        self.current_client = self.primary_client

    def _switch_to_backup(self):
        """切换到备用RPC节点"""
        logger.info("Switching to backup RPC node...")
        self.current_client = self.backup_client

    def _switch_to_primary(self):
        """切换回主RPC节点"""
        logger.info("Switching back to primary RPC node...")
        self.current_client = self.primary_client

    async def get_sol_balance(self, wallet_address: str) -> dict:
        """获取SOL余额"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = self.current_client.get_balance(pubkey)
            balance_sol = response.value / 1_000_000_000
            return {"balance": balance_sol, "address": wallet_address}
        except Exception as e:
            logger.error(f"Error fetching SOL balance: {e}")
            return {}

    async def send_sol(
        self, from_wallet: str, to_wallet: str, amount: float, private_key: str
    ) -> dict:
        """Send SOL from one wallet to another"""
        try:
            logger.info(
                f"Starting SOL transfer: {amount} SOL from {from_wallet} to {to_wallet}"
            )

            # Convert addresses to Pubkey objects
            try:
                from_pubkey = Pubkey.from_string(from_wallet)
                to_pubkey = Pubkey.from_string(to_wallet)
                logger.info(f"Successfully converted addresses to Pubkey objects")
            except Exception as e:
                logger.error(f"Error converting addresses to Pubkey: {e}")
                return {"error": f"Invalid wallet address: {str(e)}"}

            # Convert SOL amount to lamports
            try:
                lamports = int(amount * 1_000_000_000)
                logger.info(f"Converted {amount} SOL to {lamports} lamports")
            except Exception as e:
                logger.error(f"Error converting SOL to lamports: {e}")
                return {"error": f"Invalid amount: {str(e)}"}

            # Get recent blockhash with finalized commitment
            try:
                logger.info("Attempting to get finalized blockhash...")
                blockhash_resp = self.current_client.get_latest_blockhash(
                    commitment="finalized"
                )
                recent_blockhash = blockhash_resp.value.blockhash
                logger.info(f"Successfully got finalized blockhash: {recent_blockhash}")
            except Exception as e:
                logger.error(f"Error getting finalized blockhash: {e}")
                try:
                    logger.info("Falling back to default blockhash...")
                    blockhash_resp = self.current_client.get_latest_blockhash()
                    recent_blockhash = blockhash_resp.value.blockhash
                    logger.info(
                        f"Successfully got default blockhash: {recent_blockhash}"
                    )
                except Exception as e2:
                    logger.error(f"Error getting default blockhash: {e2}")
                    return {"error": f"Failed to get blockhash: {str(e2)}"}

            # Import and decode private key
            try:
                logger.info("Attempting to decode private key...")
                # Handle different private key formats
                try:
                    key_bytes = base58.b58decode(private_key)
                    logger.info("Successfully decoded private key as base58")
                except:
                    try:
                        key_bytes = bytes.fromhex(private_key.replace("0x", ""))
                        logger.info("Successfully decoded private key as hex")
                    except:
                        try:
                            key_bytes = bytes(ast.literal_eval(private_key))
                            logger.info("Successfully decoded private key as literal")
                        except:
                            logger.error("Failed to decode private key in any format")
                            return {"error": "Invalid private key format"}

                # Create keypair from private key
                if len(key_bytes) == 32:
                    logger.info("Creating keypair from 32-byte private key...")
                    keypair = Keypair.from_seed(key_bytes)
                    logger.info("Successfully created keypair from 32-byte private key")
                else:
                    logger.info(f"Creating keypair from {len(key_bytes)}-byte key...")
                    keypair = Keypair.from_bytes(key_bytes)
                    logger.info(
                        f"Successfully created keypair from {len(key_bytes)}-byte key"
                    )
            except Exception as e:
                logger.error(f"Error creating keypair: {e}")
                return {"error": f"Invalid private key: {str(e)}"}

            # Create transfer instruction
            try:
                logger.info("Creating transfer instruction...")
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=from_pubkey, to_pubkey=to_pubkey, lamports=lamports
                    )
                )
                logger.info("Successfully created transfer instruction")
            except Exception as e:
                logger.error(f"Error creating transfer instruction: {e}")
                return {"error": f"Failed to create transfer instruction: {str(e)}"}

            # Create and sign transaction
            try:
                logger.info("Creating transaction message...")
                from solders.message import Message

                message = Message([transfer_ix], from_pubkey)
                logger.info("Successfully created transaction message")

                logger.info("Creating transaction...")
                tx = Transaction(
                    from_keypairs=[keypair],
                    message=message,
                    recent_blockhash=recent_blockhash,
                )
                logger.info("Successfully created transaction")
            except Exception as e:
                logger.error(f"Error creating transaction: {e}")
                return {
                    "success": False,
                    "error": f"Transaction creation failed: {str(e)}",
                }

            # Send transaction
            try:
                import time

                logger.info("Starting transaction send process...")

                # First attempt with current node
                logger.info("First attempt with current node...")
                result = self.current_client.send_transaction(tx)
                logger.info(f"Got response from network: {result}")

                # If first attempt succeeds, return success
                if result.value:
                    logger.info(f"Transaction successful! Signature: {result.value}")
                    return {
                        "success": True,
                        "signature": str(result.value),
                        "message": f"Sent {amount} SOL to {to_wallet}",
                    }

                # If first attempt fails, switch node and retry
                logger.info("First attempt failed, switching RPC node and retrying...")
                if self.current_client == self.primary_client:
                    self._switch_to_backup()
                else:
                    self._switch_to_primary()

                logger.info("Waiting 1 second before retry...")
                time.sleep(1)

                # Get fresh blockhash with new node
                logger.info("Getting fresh blockhash with finalized commitment...")
                blockhash_resp = self.current_client.get_latest_blockhash(
                    commitment="finalized"
                )
                recent_blockhash = blockhash_resp.value.blockhash
                logger.info(f"Successfully got new blockhash: {recent_blockhash}")

                # Recreate transaction with new blockhash
                logger.info("Recreating transaction with new blockhash...")
                message = Message([transfer_ix], from_pubkey)
                tx = Transaction(
                    from_keypairs=[keypair],
                    message=message,
                    recent_blockhash=recent_blockhash,
                )
                logger.info("Successfully recreated transaction")

                # Second attempt with new node
                logger.info("Second attempt with new node...")
                result = self.current_client.send_transaction(tx)
                logger.info(f"Got response from network: {result}")

                # If second attempt succeeds, return success
                if result.value:
                    logger.info(f"Transaction successful! Signature: {result.value}")
                    return {
                        "success": True,
                        "signature": str(result.value),
                        "message": f"Sent {amount} SOL to {to_wallet}",
                    }

                # If both attempts fail, return error
                logger.error("Transaction failed after trying both RPC nodes")
                return {
                    "success": False,
                    "error": "Transaction failed after trying both RPC nodes",
                    "details": str(result),
                }

            except Exception as e:
                error_str = str(e)
                logger.error(f"Error in send attempt: {error_str}")
                logger.error(f"Full error details: {e}")

                # If first attempt fails with rate limit or send failed, switch node and retry
                if (
                    "429" in error_str
                    or "Too Many Requests" in error_str
                    or "Send failed" in error_str
                ):
                    logger.info(
                        "First attempt failed, switching RPC node and retrying..."
                    )
                    if self.current_client == self.primary_client:
                        self._switch_to_backup()
                    else:
                        self._switch_to_primary()

                    logger.info("Waiting 1 second before retry...")
                    time.sleep(1)

                    # Get fresh blockhash with new node
                    logger.info("Getting fresh blockhash with finalized commitment...")
                    blockhash_resp = self.current_client.get_latest_blockhash(
                        commitment="finalized"
                    )
                    recent_blockhash = blockhash_resp.value.blockhash
                    logger.info(f"Successfully got new blockhash: {recent_blockhash}")

                    # Recreate transaction with new blockhash
                    logger.info("Recreating transaction with new blockhash...")
                    message = Message([transfer_ix], from_pubkey)
                    tx = Transaction(
                        from_keypairs=[keypair],
                        message=message,
                        recent_blockhash=recent_blockhash,
                    )
                    logger.info("Successfully recreated transaction")

                    # Second attempt with new node
                    try:
                        logger.info("Second attempt with new node...")
                        result = self.current_client.send_transaction(tx)
                        logger.info(f"Got response from network: {result}")

                        if result.value:
                            logger.info(
                                f"Transaction successful! Signature: {result.value}"
                            )
                            return {
                                "success": True,
                                "signature": str(result.value),
                                "message": f"Sent {amount} SOL to {to_wallet}",
                            }

                        logger.error("Transaction failed after trying both RPC nodes")
                        return {
                            "success": False,
                            "error": "Transaction failed after trying both RPC nodes",
                            "details": str(result),
                        }

                    except Exception as e2:
                        logger.error(f"Error in second attempt: {e2}")
                        return {
                            "success": False,
                            "error": "Transaction failed after trying both RPC nodes",
                            "details": f"First error: {error_str}, Second error: {str(e2)}",
                        }
                else:
                    # For other errors, return immediately
                    logger.error(f"Error sending transaction: {error_str}")
                    return {
                        "success": False,
                        "error": f"Send failed: {error_str}",
                        "details": error_str,
                    }

        except Exception as e:
            logger.error(f"Error sending SOL: {e}")
            logger.error(f"Full error details: {e}")
            return {"success": False, "error": str(e), "details": str(e)}

    async def get_token_info(self, token_address: str) -> dict:
        """获取代币信息"""
        try:
            pubkey = Pubkey.from_string(token_address)
            response = self.current_client.get_token_supply(pubkey)
            return {
                "address": token_address,
                "supply": response.value.amount,
                "decimals": response.value.decimals,
            }
        except Exception as e:
            logger.error(f"Error fetching token info: {e}")
            return {}

    async def get_account_details(self, account_address: str) -> dict:
        """获取账户详情"""
        try:
            pubkey = Pubkey.from_string(account_address)
            response = self.current_client.get_account_info(pubkey)
            if response.value is not None:
                return {
                    "address": account_address,
                    "lamports": response.value.lamports,
                    "owner": str(response.value.owner),
                    "executable": response.value.executable,
                    "rent_epoch": response.value.rent_epoch,
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching account details: {e}")
            return {}

    async def get_latest_block(self) -> dict:
        """获取最新区块"""
        try:
            response = self.current_client.get_latest_blockhash()
            return {
                "blockhash": str(response.value.blockhash),
                "last_valid_block_height": response.value.last_valid_block_height,
            }
        except Exception as e:
            logger.error(f"Error fetching latest block: {e}")
            return {}

    async def get_network_status(self) -> dict:
        """获取网络状态"""
        try:
            response = self.current_client.get_version()
            return {
                "solana_core": response.value.solana_core,
                "feature_set": response.value.feature_set,
            }
        except Exception as e:
            logger.error(f"Error fetching network status: {e}")
            return {}

    async def get_transaction_details(self, signature: str) -> dict:
        """获取交易详情"""
        try:
            sig = Signature.from_string(signature)
            response = self.current_client.get_transaction(sig)
            if response.value is not None:
                return {
                    "signature": signature,
                    "slot": response.value.slot,
                    "block_time": response.value.block_time,
                    "success": response.value.meta.err is None,
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching transaction details: {e}")
            return {}

    async def get_recent_transactions(
        self, wallet_address: str, limit: int = 5
    ) -> list:
        """获取最近交易"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = self.current_client.get_signatures_for_address(
                pubkey, limit=limit
            )
            result = []
            for item in response.value:
                tx = {
                    "signature": str(item.signature),
                    "slot": item.slot,
                    "block_time": item.block_time,
                    "success": item.err is None,
                }
                result.append(tx)
            return result
        except Exception as e:
            logger.error(f"Error fetching recent transactions: {e}")
            return []

    async def get_validators(self, limit: int = 5) -> list:
        """获取验证者信息"""
        try:
            response = self.current_client.get_vote_accounts()
            validators = response.value.current
            result = []
            for validator in validators[:limit]:
                result.append(
                    {
                        "vote_pubkey": str(validator.vote_pubkey),
                        "activated_stake": validator.activated_stake / 1_000_000_000,
                        "commission": validator.commission,
                        "last_vote": validator.last_vote,
                    }
                )
            return result
        except Exception as e:
            logger.error(f"Error fetching validators: {e}")
            return []

    async def get_token_accounts(self, wallet_address: str) -> list:
        """获取代币账户"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            token_program_id = Pubkey.from_string(
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
            )
            opts = TokenAccountOpts(program_id=token_program_id)
            response = self.current_client.get_token_accounts_by_owner(pubkey, opts)
            result = []
            if response.value:
                for item in response.value:
                    account_data = {
                        "pubkey": str(item.pubkey),
                        "mint": "Token Account",
                        "amount": "Available",
                    }
                    result.append(account_data)
            return result
        except Exception as e:
            logger.error(f"Error fetching token accounts: {e}")
            return []

    async def get_slot(self) -> int:
        """获取当前槽位"""
        try:
            response = self.current_client.get_slot()
            return response.value
        except Exception as e:
            logger.error(f"Error fetching current slot: {e}")
            return 0
