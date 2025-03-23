# Solana Telegram Bot

A Telegram bot that uses natural language processing to interact with the Solana blockchain. Users can ask questions in natural language, which will be converted to commands for retrieving Solana blockchain data and managing Solana wallet.

## Features

- **Natural Language Understanding**: Uses gpt-4o-mini to interpret user queries
- **Solana Integration**: Interacts with the Solana blockchain via RPC API
- **User Wallet Management**: Securely store and manage user wallet addresses
- **Rate Limiting**: Built-in protection against API abuse
- **Conversational Interface**: Simple and intuitive Telegram bot interface
- **Data Persistence**: Stores blockchain data in a local database for faster responses
- **Wallet Verification**: Verifies ownership of Solana wallets

## Supported Commands

The bot can handle the following types of requests:

- Check SOL balance for a wallet address
- Get information about a Solana token
- View details about a Solana account
- Get information about the latest block
- Check Solana network status
- View transaction details
- List recent transactions for an address
- View validator information
- Store and manage your wallet addresses
- Verify wallet ownership

## Project Structure

```
├── command/                    # Bot command handlers
│   ├── command_processor.py    # Central command processing
│   ├── general_commands.py     # Basic bot commands
│   ├── solana_commands.py      # Solana blockchain commands
│   ├── wallet_commands.py      # Wallet management commands
│   ├── verification.py         # Wallet verification logic
│   └── utils.py                # Command utilities
├── telegram_bot/               # Core telegram bot functionality
│   ├── solana_bot.py           # Main bot implementation
│   └── __init__.py             # Package initialization
├── database/                   # Database and data collection
│   ├── modal_app.py            # Modal app for blockchain data collection
│   ├── create_database.py      # Database schema and setup
│   ├── common_utils.py         # Common database utilities
│   └── other tools             # Database testing and utilities
├── services/                   # Core services
│   ├── solana_rpc_service.py   # Services for interacting with Solana
│   ├── user_service.py         # User management interface
│   ├── user_service_sqlite.py  # SQLite implementation of user service
│   ├── openai_service.py       # Natural language processing
│   └── rate_limiter.py         # Rate limiting functionality
├── config.py                   # Configuration settings
├── main.py                     # Application entry point
├── requirements.txt            # Project dependencies
└── user_wallets.db             # SQLite database for user wallet storage
```

## Setup Instructions

1. **Clone the Repository**:
   ```
   git clone [repository URL]
   cd trading_telegram_bot
   ```

2. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configuration**:
   - Edit `config.py` with your own values:
     - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather
     - `OPEN_AI_API_KEY`: Your OpenAI API key
     - `SOLANA_RPC_URL`: Solana RPC endpoint (default is public mainnet)

4. **Run the Bot**:
   ```
   python main.py
   ```

5. **Modal Setup** (Optional - for blockchain data collection):
   - To set up the Modal app for blockchain data collection:
   ```
   modal deploy database/modal_app.py
   ```

## Usage Examples

Users can interact with the bot using natural language queries like:

- "What's the balance of wallet address 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV?"
- "Tell me about the token at address EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
- "What's the latest block on Solana?"
- "Show me account details for 9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
- "What's the status of the Solana network?"
- "Show me recent transactions for my wallet"
- "Store this wallet: 5YNmYpZxFVNVx5Yjte7u11eTAdk6uPCKG9QiVViwLtKV"
- "List all validators on Solana"
- "Verify my wallet ownership"

## Wallet Management

The bot provides features to help users manage their Solana wallets:

1. **Store Wallets**: Save your frequently used wallet addresses
2. **Wallet List**: View all your stored wallets
3. **Remove Wallets**: Remove wallets you no longer want to track
4. **Verify Ownership**: Prove ownership through cryptographic signatures

## Technical Details

The bot works by:
1. Receiving natural language input from the user
2. Processing the input through the GPT-4o-mini model
3. Converting the natural language to a structured command
4. Executing the corresponding Solana RPC call
5. Returning the formatted result to the user

### Data Storage

The bot uses SQLite database (user_wallets.db) to store:
- User wallet addresses and labels
- Verification status and timestamps
- Challenge messages for wallet verification

### Rate Limiting

To prevent abuse, the bot implements rate limiting:
- Global limit: 30 commands per minute
- Command-specific limits:
  - Balance queries: 15 per minute
  - Token info: 15 per minute
  - Transactions: 15 per minute
  - Validator lists: 5 per minute

## Dependencies

- python-telegram-bot: Telegram Bot API interface
- solana-py & solders: Python clients for Solana blockchain
- openai: OpenAI API integration for language processing
- aiohttp & asyncio: Asynchronous HTTP requests and operations
- plotly & pandas: Data visualization and manipulation
- flask: Web server for additional services
- modal: Serverless function deployment (for blockchain data collection)

## Copyright Notice

This project is proprietary and may not be distributed or used without authorization.
© 2025 All Rights Reserved

## Technical Acknowledgements

- [Python Telegram Bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Solana-py](https://github.com/michaelhly/solana-py)
- [Modal](https://modal.com/) 