"""Test script to send a message to Telegram group."""
import asyncio
import logging
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Get credentials from environment variables
import os
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def send_test_message():
    """Sends a test message to the Telegram group."""
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # Test message similar to the format used in the bot
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_message = (
            f"🎮 **Esports Odds Alert Bot - Test Message**\n\n"
            f"**Timestamp**: {timestamp}\n\n"
            f"✅ Telegram connection successful!\n"
            f"🚀 Bot is ready to send alerts.\n\n"
            f"---\n\n"
            f"💎 **Test Alert**\n"
            f"**Event**: `Test Event - Connection Working`\n"
            f"**Bet**: `YES` at **$0.03**\n"
            f"**Platform**: Polymarket | **Volume**: $1,000"
        )
        
        await bot.send_message(
            chat_id=CHAT_ID,
            text=test_message,
            parse_mode=ParseMode.MARKDOWN
        )
        logging.info("✅ Test message sent successfully!")
        return True
        
    except TelegramError as e:
        logging.error(f"❌ Failed to send Telegram message: {e}")
        return False
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred: {e}")
        return False


if __name__ == "__main__":
    logging.info("Starting Telegram test...")
    success = asyncio.run(send_test_message())
    if success:
        print("\nTest completed successfully! Check your Telegram group.")
    else:
        print("\nTest failed. Check the error messages above.")

