"""Test the fixed filtering and send test alert to Telegram."""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Set environment variables
# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Set environment variables if not already set (for testing)
import os
if not os.getenv("DOME_API_KEY"):
    print("ERROR: DOME_API_KEY environment variable not set!")
    sys.exit(1)
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set!")
    sys.exit(1)
if not os.getenv("TELEGRAM_CHAT_ID"):
    print("ERROR: TELEGRAM_CHAT_ID environment variable not set!")
    sys.exit(1)

# Import after setting env vars
from app.esports_alert_bot import (
    fetch_all_esports_markets,
    analyze_and_prepare_alerts,
    send_telegram_alerts,
    Bot
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

async def test_fixed_filtering():
    """Test the fixed filtering logic."""
    print("=" * 70)
    print("Testing Fixed Filtering Logic")
    print("=" * 70)
    print()
    
    print("Step 1: Fetching esports markets with improved filters...")
    print("-" * 70)
    markets = fetch_all_esports_markets()
    print(f"\n[RESULT] Found {len(markets)} esports markets\n")
    
    if len(markets) == 0:
        print("No esports markets found.")
        return
    
    # Show breakdown by game type
    game_types = {}
    for market in markets:
        title = market.get("title", "").lower()
        slug = market.get("market_slug", "").lower()
        
        game_type = "Unknown"
        if any(k in title or k in slug for k in ["cs", "counter-strike", "cs2", "csgo"]):
            game_type = "Counter-Strike"
        elif any(k in title or k in slug for k in ["lol", "league of legends"]):
            game_type = "League of Legends"
        elif any(k in title or k in slug for k in ["dota", "dota2"]):
            game_type = "Dota 2"
        elif any(k in title or k in slug for k in ["valorant"]):
            game_type = "Valorant"
        elif any(k in title or k in slug for k in ["overwatch"]):
            game_type = "Overwatch"
        
        game_types[game_type] = game_types.get(game_type, 0) + 1
    
    print("\nMarkets by Game Type:")
    for game_type, count in sorted(game_types.items(), key=lambda x: -x[1]):
        print(f"  {game_type}: {count} markets")
    
    print("\n\nSample Markets Found:")
    for i, market in enumerate(markets[:10], 1):
        print(f"\n{i}. {market.get('title', 'N/A')}")
        print(f"   Slug: {market.get('market_slug', 'N/A')}")
        print(f"   Volume: ${market.get('volume_total', 0):,.0f}")
    
    print("\n\nStep 2: Analyzing markets for alert opportunities...")
    print("-" * 70)
    alerts = analyze_and_prepare_alerts()
    print(f"\n[RESULT] Generated {len(alerts)} alerts\n")
    
    print("\n\nStep 3: Sending test message to Telegram...")
    print("-" * 70)
    
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create summary message
    market_list = "\n".join([
        f"• {m.get('title', 'N/A')[:55]}... (Vol: ${m.get('volume_total', 0):,.0f})"
        for m in markets[:15]
    ])
    
    summary_message = (
        f"🔧 **FILTERING UPDATE TEST**\n\n"
        f"**Time**: {timestamp}\n\n"
        f"✅ **Filtering Fixed!**\n\n"
        f"**Total Esports Markets Found**: {len(markets)}\n\n"
        f"**Markets by Game Type:**\n"
    )
    
    for game_type, count in sorted(game_types.items(), key=lambda x: -x[1]):
        summary_message += f"• {game_type}: {count}\n"
    
    summary_message += f"\n**Alerts Generated**: {len(alerts)}\n\n"
    summary_message += f"**Sample Markets:**\n{market_list}\n\n"
    
    if len(alerts) > 0:
        summary_message += f"🎯 **{len(alerts)} alert(s) ready to send!**"
    else:
        summary_message += "*No alerts generated - markets need volume > $1,000 and extreme prices (< $0.05 or > $0.95)*"
    
    summary_message += "\n\n⚠️ **Disclaimer**: Not financial advice. 18+ only. Gamble responsibly."
    
    try:
        from telegram.constants import ParseMode
        await bot.send_message(
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            text=summary_message,
            parse_mode=ParseMode.MARKDOWN
        )
        print(f"\n[SUCCESS] Sent test message to Telegram group!")
        print(f"  - Found {len(markets)} esports markets")
        print(f"  - Generated {len(alerts)} alerts")
        print(f"\nCheck your Telegram group to see the results!")
    except Exception as e:
        print(f"\n[ERROR] Failed to send Telegram message: {e}")
        logging.exception("Telegram send error")
    
    # If there are alerts, send them too
    if alerts:
        print("\n\nSending alerts...")
        await send_telegram_alerts(bot, alerts)
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_fixed_filtering())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        logging.exception("Test error")
        sys.exit(1)

