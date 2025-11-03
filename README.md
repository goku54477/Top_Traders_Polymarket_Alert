# Esports Odds Alert Bot

A Python bot that continuously monitors esports prediction markets via the DOME API and sends Telegram alerts when value betting opportunities are detected.

## Features

- 🤖 **24/7 Market Scanning**: Automatically scans esports markets (LoL, Dota 2, CS2, Valorant, etc.)
- 💰 **Value Bet Detection**: Identifies opportunities where market odds differ from true probability
- 📊 **Smart Filtering**: Volume, price range, timing, and status filters
- 📱 **Telegram Alerts**: Sends formatted alerts with market details and trade links
- 📈 **Daily Summaries**: Sends morning and evening summaries showing bot activity
- 🎯 **Multi-Game Support**: Detects and alerts for multiple esports titles

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/goku54477/Esports-Odds-Monitor.git
   cd Esports-Odds-Monitor
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run the bot:**
   ```bash
   python app/esports_alert_bot.py
   ```

## Project Structure

```
Esports-Odds-Monitor/
├── app/
│   └── esports_alert_bot.py    # Main bot application
├── scripts/
│   ├── tests/                  # Test scripts
│   └── diagnostics/            # Diagnostic tools
├── docs/                       # Documentation files
├── .env.example                # Environment variables template
├── requirements.txt            # Python dependencies
├── Procfile                    # Deployment configuration
└── README.md                   # This file
```

## Configuration

### Environment Variables

Required:
- `DOME_API_KEY` - Your Dome API key
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat/group ID

Optional:
- `POLL_INTERVAL_MIN` - Minutes between market scans (default: 5)
- `VOLUME_THRESHOLD` - Minimum market volume in USD (default: 100)
- `VALUE_THRESHOLD` - Minimum value threshold (default: 0.04)
- `CACHE_TTL_MINUTES` - Cache duration (default: 10)
- `MAX_MARKET_AGE_DAYS` - Maximum market age (default: 7)

## Deployment

### Heroku/Render/Railway

This repo includes a `Procfile` with a worker entry:

```
worker: python app/esports_alert_bot.py
```

Steps:
1. Set environment variables in your platform's dashboard
2. Deploy the repository
3. Scale the worker to 1 dyno/instance

The process runs continuously and sends alert batches every `POLL_INTERVAL_MIN` minutes (default 5).

### Railway Quick Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new?template=https://github.com/goku54477/Esports-Odds-Monitor)

Manual Railway steps:
1. Create a new project → Deploy from GitHub → select this repo
2. Set Start Command: `python app/esports_alert_bot.py`
3. Add Environment Variables in Settings
4. Watch logs for: "Starting Esports Odds Alert Bot…"

## Features Details

- **Market Detection**: Automatically detects esports markets via slug patterns, keywords, and tags
- **Value Betting Logic**: Calculates ROI and identifies opportunities where market odds differ from true probability
- **Multi-Game Support**: Works with LoL, Dota 2, Counter-Strike, Valorant, and more
- **Smart Filtering**: Filters by volume, price range (5-95%), market status, and event timing
- **Daily Summaries**: Sends morning (09:00 UTC) and evening (21:00 UTC) summaries

## Development

### Testing

Test scripts are located in `scripts/tests/`:

```bash
# Run complete flow test
python scripts/tests/test_complete_flow.py

# Test esports detection
python scripts/tests/test_all_esports_detection.py
```

### Diagnostic Tools

Diagnostic scripts are in `scripts/diagnostics/` for troubleshooting and analysis.

## Security

- **Never commit `.env` file** - It's in `.gitignore`
- **Use `.env.example`** as a template for required variables
- **API keys** should only be set as environment variables

## License

[Add your license here]
