"""Test complete bot flow - fetch markets, analyze, and send to Telegram."""
import os
import sys
import asyncio
import logging

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get environment variables (set these in your environment or .env file)
# Do NOT hardcode credentials here - they will be exposed in git!
# Example: export DOME_API_KEY="your_key_here"

# Now import after setting env vars
from app.esports_alert_bot import (
    fetch_all_esports_markets,
    analyze_and_prepare_alerts,
    send_telegram_alerts,
    Bot
)

# Get from environment to ensure we have the correct values
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

async def test_complete_flow():
    """Test the complete bot flow."""
    print("=" * 70)
    print("Testing Complete Bot Flow")
    print("=" * 70)
    print()
    
    print("Step 1: Fetching esports markets from Polymarket...")
    print("-" * 70)
    markets = fetch_all_esports_markets()
    print(f"\n[RESULT] Found {len(markets)} esports markets\n")
    
    if len(markets) == 0:
        print("No esports markets found. Cannot continue test.")
        return
    
    print("Step 2: Analyzing markets for alert opportunities...")
    print("-" * 70)
    alerts = analyze_and_prepare_alerts()
    print(f"\n[RESULT] Generated {len(alerts)} alerts\n")
    
    print("Step 3: Sending alerts to Telegram group...")
    print("-" * 70)
    
    bot = Bot(token=BOT_TOKEN)
    
    if len(alerts) > 0:
        print(f"\nGenerated {len(alerts)} alert(s)")
        print("Sending alerts to Telegram...")
        
        # Send alerts first before printing (to avoid console encoding issues)
        await send_telegram_alerts(bot, alerts)
        print(f"\n[SUCCESS] Sent {len(alerts)} alert(s) to Telegram group!")
        print(f"Check your Telegram group to see the alerts!")
    else:
        # Send a summary message even if no alerts
        from datetime import datetime
        from telegram.constants import ParseMode
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Show sample markets found
        sample_markets = markets[:5]
        market_list = "\n".join([
            f"• {m.get('title', 'N/A')[:50]}... (Vol: ${m.get('volume_total', 0):,.0f})"
            for m in sample_markets
        ])
        
        summary_message = (
            f"🎮 **Esports Odds Monitor - Status Update**\n\n"
            f"**Time**: {timestamp}\n\n"
            f"✅ **Bot is running successfully!**\n\n"
            f"**Markets Found**: {len(markets)} esports markets\n"
            f"**Alerts Generated**: {len(alerts)}\n\n"
            f"**Sample Markets**:\n{market_list}\n\n"
            f"*No alerts generated yet - markets need volume > $1,000 and extreme prices (< $0.05 or > $0.95)*"
        )
        
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=summary_message,
                parse_mode=ParseMode.MARKDOWN
            )
            print(f"\n[SUCCESS] Sent status summary to Telegram group!")
            print(f"  - Found {len(markets)} esports markets")
            print(f"  - No alerts generated (markets don't meet criteria)")
            print(f"\n✅ Check your Telegram group to see the status update!")
        except Exception as e:
            print(f"\n[ERROR] Failed to send Telegram message: {e}")
            logging.exception("Telegram send error")
    
    print("\n" + "=" * 70)
    print("Complete Flow Test Finished!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_complete_flow())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        logging.exception("Test error")
        sys.exit(1)

