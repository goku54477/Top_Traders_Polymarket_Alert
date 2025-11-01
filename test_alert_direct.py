"""Direct test of alert sending with new format."""
import os
import sys
import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode

# Set environment variables
os.environ["TELEGRAM_BOT_TOKEN"] = "YOUR_TELEGRAM_BOT_TOKEN"
os.environ["TELEGRAM_CHAT_ID"] = "YOUR_TELEGRAM_CHAT_ID"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

async def test_alert_send():
    """Test sending a sample alert with new format."""
    bot = Bot(token=BOT_TOKEN)
    
    # Create a sample alert with new format
    sample_alert = """🎮 **ESPORTS VALUE BET ALERT**

📅 **Match**: Counter-Strike - Team A vs Team B
🎯 **Market**: Over/Under 25.5
💰 **Bet**: `YES` at **$0.0300** (3.0% odds)
📊 **Volume**: $606,887
🔗 **Trade**: [Click here to trade](https://polymarket.com/event/test-market-slug)

💡 **Analysis**: Extremely undervalued opportunity - market shows only 3.0% chance"""
    
    try:
        print("Sending test alert to Telegram...")
        await bot.send_message(
            chat_id=CHAT_ID,
            text=sample_alert,
            parse_mode=ParseMode.MARKDOWN
        )
        print("SUCCESS: Alert sent successfully!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to send alert: {e}")
        logging.exception("Send error")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_alert_send())
    sys.exit(0 if success else 1)

