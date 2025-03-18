# solana_service/base.py
import logging
from solana.rpc.api import Client as SolanaRpcClient
from config import SOLANA_RPC_URL

logger = logging.getLogger(__name__)
client = SolanaRpcClient(SOLANA_RPC_URL)
