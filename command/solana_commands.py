import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.solana_rpc_service import SolanaService
from command.utils import _reply

logger = logging.getLogger(__name__)
solana_service = SolanaService()


async def cmd_sol_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /sol_balance [wallet address]")
    address = context.args[0]
    result = await solana_service.get_sol_balance(address)
    text = (
        f"SOL Balance for {result['address']}:\n{result['balance']} SOL"
        if result
        else f"Unable to retrieve balance for {address}."
    )
    await _reply(update, text)


async def cmd_token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /token_info [token address]")
    address = context.args[0]
    result = await solana_service.get_token_info(address)
    if result:
        text = (
            f"Token Information:\nAddress: {result['address']}\n"
            f"Supply: {result['supply']}\nDecimals: {result['decimals']}"
        )
    else:
        text = f"Unable to retrieve token info for {address}."
    await _reply(update, text)


async def cmd_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /account_details [account address]")
    address = context.args[0]
    result = await solana_service.get_account_details(address)
    if result:
        text = (
            f"Account Details:\nAddress: {result['address']}\nLamports: {result['lamports']}\n"
            f"Owner: {result['owner']}\nExecutable: {result['executable']}\nRent Epoch: {result['rent_epoch']}"
        )
    else:
        text = f"Unable to retrieve account details for {address}."
    await _reply(update, text)


async def cmd_latest_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    result = await solana_service.get_latest_block()
    text = (
        f"Latest Block:\nBlockhash: {result['blockhash']}\n"
        f"Last Valid Block Height: {result['last_valid_block_height']}"
        if result
        else "Unable to retrieve latest block information."
    )
    await _reply(update, text)


async def cmd_network_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    result = await solana_service.get_network_status()
    text = (
        f"Network Status:\nSolana Core: {result['solana_core']}\n"
        f"Feature Set: {result['feature_set']}"
        if result
        else "Unable to retrieve network status."
    )
    await _reply(update, text)


async def cmd_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /transaction [signature]")
    signature = context.args[0]
    result = await solana_service.get_transaction_details(signature)
    if result:
        status = "✅ Successful" if result.get("success", False) else "❌ Failed"
        text = (
            f"Transaction Details:\nSignature: {result['signature']}\nStatus: {status}\n"
            f"Slot: {result.get('slot', 'Unknown')}\nBlock Time: {result.get('block_time', 'Unknown')}"
        )
    else:
        text = f"Unable to retrieve transaction details for {signature}."
    await _reply(update, text)


async def cmd_recent_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /recent_tx [wallet address] [limit]")
    address = context.args[0]
    limit = 5
    if len(context.args) > 1:
        try:
            limit = max(1, min(int(context.args[1]), 10))
        except ValueError:
            pass
    transactions = await solana_service.get_recent_transactions(address, limit)
    if transactions:
        text = f"Recent Transactions for {address}:\n\n"
        for i, tx in enumerate(transactions, 1):
            status = "✅" if tx.get("success", False) else "❌"
            text += f"{i}. {status} {tx.get('signature', 'Unknown')[:12]}...\n   Slot: {tx.get('slot', 'Unknown')}\n"
    else:
        text = f"No recent transactions found for {address}."
    await _reply(update, text)


async def cmd_validators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    limit = 5
    if context.args:
        try:
            limit = max(1, min(int(context.args[0]), 10))
        except ValueError:
            pass
    validators = await solana_service.get_validators(limit)
    if validators:
        text = f"Top {len(validators)} Active Validators:\n\n"
        for i, v in enumerate(validators, 1):
            text += (
                f"{i}. Node: {v.get('node_pubkey', 'Unknown')[:8]}...\n"
                f"   Vote: {v.get('vote_pubkey', 'Unknown')[:8]}...\n"
                f"   Stake: {v.get('activated_stake', 'Unknown')} SOL\n"
                f"   Commission: {v.get('commission', 'Unknown')}%\n\n"
            )
    else:
        text = "Unable to retrieve validator information."
    await _reply(update, text)


async def cmd_token_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        return await _reply(update, "Usage: /token_accounts [wallet address]")
    address = context.args[0]
    accounts = await solana_service.get_token_accounts(address)
    if accounts:
        text = f"Token Accounts for {address}:\n\n" + "\n".join(
            f"{i+1}. {acc.get('pubkey', 'Unknown')[:10]}...{' - ' + acc.get('data') if acc.get('data') else ''}"
            for i, acc in enumerate(accounts)
        )
    else:
        text = f"No token accounts found for {address}."
    await _reply(update, text)


async def cmd_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    slot = await solana_service.get_slot()
    text = (
        f"Current Solana Slot: {slot}"
        if slot > 0
        else "Unable to retrieve current slot."
    )
    await _reply(update, text)
