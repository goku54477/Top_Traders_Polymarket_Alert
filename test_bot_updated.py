"""Test the updated bot code with Dome API."""
import os
import sys
import logging
from app.esports_alert_bot import fetch_all_esports_markets, analyze_and_prepare_alerts

# Set environment variables
os.environ["DOME_API_KEY"] = "YOUR_DOME_API_KEY"
os.environ["TELEGRAM_BOT_TOKEN"] = "YOUR_TELEGRAM_BOT_TOKEN"
os.environ["TELEGRAM_CHAT_ID"] = "YOUR_TELEGRAM_CHAT_ID"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Updated Bot Code with Dome API")
    print("=" * 60)
    print()
    
    print("Step 1: Fetching esports markets...")
    markets = fetch_all_esports_markets()
    
    print(f"\n[RESULT] Found {len(markets)} esports markets")
    
    if len(markets) > 0:
        print("\nSample esports markets:")
        for i, market in enumerate(markets[:5], 1):
            print(f"\n  {i}. {market.get('title', 'N/A')}")
            print(f"     Slug: {market.get('market_slug', 'N/A')}")
            print(f"     Volume: ${market.get('volume_total', 0):,.0f}")
            print(f"     Status: {market.get('status', 'N/A')}")
    
    print("\n" + "-" * 60)
    print("Step 2: Analyzing markets for alerts...")
    print("-" * 60)
    
    alerts = analyze_and_prepare_alerts()
    
    print(f"\n[RESULT] Prepared {len(alerts)} alerts")
    
    if len(alerts) > 0:
        print("\nSample alerts:")
        for i, alert in enumerate(alerts[:3], 1):
            print(f"\n  Alert {i}:")
            print(f"  {alert}")
    else:
        print("\n[INFO] No alerts generated.")
        print("[INFO] This could mean:")
        print("  - No markets meet the criteria (volume > 1000, price < 0.05 or > 0.95)")
        print("  - No esports markets found")
        print("  - Price fetching failed")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

