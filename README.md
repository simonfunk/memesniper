# Meme Coin Sniper Tool

A Python-based tool for analyzing and sniping meme coins on BSC (Binance Smart Chain) with rugpull detection features.

## ⚠️ Warning
This tool is for educational purposes only. Trading cryptocurrencies involves significant risk. Never invest more than you can afford to lose.

## Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Clone the repository 

2. Create and activate virtual environment

On Windows:
```
python -m venv venv
venv\Scripts\activate
```

On Linux:
```
python3 -m venv venv
source venv/bin/activate
```

3. Install the required packages
```
pip install -r requirements.txt
```

## Configuration

1. Copy `config.py.example` to `config.py`:
```
bash
cp config.py.example config.py
```

2. Edit `config.py` and add your wallet's private key and any other configuration options.

## Usage

1. Update the token address in `example_usage.py`
2. Run the script:
```
python example_usage.py
```


## Features

- Rugpull detection:
  - Contract verification check
  - Ownership analysis
  - Mint function detection
  - Trading restrictions check
  - Liquidity lock verification
  - Trade simulation

- Basic trading functionality:
  - Liquidity checking
  - Token buying
  - Transaction monitoring

## Project Structure
meme-coin-sniper/
├── abi/
│ ├── router.json
│ ├── token.json
│ └── pair.json
├── venv/
├── config.py
├── config.py.example
├── memesniper.py
├── example_usage.py
├── requirements.txt
└── README.md


## Dependencies

- web3.py - Ethereum interface
- eth-account - Account management
- python-dotenv (optional) - Environment variable management

## Security Notes

- Never share your private key
- Always verify contracts before trading
- Start with small test amounts
- Be aware of scams and rugpulls
- Use a dedicated wallet for trading

## License

MIT License

## Disclaimer

This tool comes with no warranties. Use at your own risk.