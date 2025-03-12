# Solana Telegram Bot

A Telegram bot that uses natural language processing to interact with the Solana blockchain. Users can ask questions in natural language, which will be converted to commands for retrieving Solana blockchain data.

## Features

- **Natural Language Understanding**: Uses LLaMA 3.2 through Hugging Face to interpret user queries
- **Solana Integration**: Interacts with the Solana blockchain via RPC API
- **Conversational Interface**: Simple and intuitive Telegram bot interface

## Supported Commands

The bot can handle the following types of requests:

- Check SOL balance for a wallet address
- Get information about a Solana token
- View details about a Solana account
- Get information about the latest block
- Check Solana network status

## Setup Instructions

1. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Configuration**:
   - Edit `config.py` with your own values:
     - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather
     - `HUGGINGFACE_TOKEN`: Your Hugging Face API token
     - `SOLANA_RPC_URL`: Solana RPC endpoint (default is public mainnet)

3. **Run the Bot**:
   ```
   python bot-3.py
   ```

## Usage Examples

Users can interact with the bot using natural language queries like:

- "What's the balance of wallet address 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV?"
- "Tell me about the token at address EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
- "What's the latest block on Solana?"
- "Show me account details for 9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
- "What's the status of the Solana network?"

## Technical Details

The bot works by:
1. Receiving natural language input from the user
2. Processing the input through an LLM (Llama-3.2-3B-Instruct)
3. Converting the natural language to a structured command
4. Executing the corresponding Solana RPC call
5. Returning the formatted result to the user

## Dependencies

- python-telegram-bot: Telegram Bot API interface
- solana-py: Python client for Solana blockchain
- huggingface-hub: Integration with Hugging Face models
- flask: Web server for additional services

## Copyright Notice

This project is proprietary and may not be distributed or used without authorization.
© 2025 All Rights Reserved

## Technical Acknowledgements

- [Python Telegram Bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Solana-py](https://github.com/michaelhly/solana-py)
- [Hugging Face](https://huggingface.co/) 