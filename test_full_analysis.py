"""Test the bot with detailed output showing all esports markets and price checks."""
import os
import sys
import logging
from app.esports_alert_bot import fetch_all_esports_markets, fetch_price, analyze_and_prepare_alerts

# Set environment variables
os.environ["DOME_API_KEY"] = "YOUR_DOME_API_KEY"
os.environ["TELEGRAM_BOT_TOKEN"] = "YOUR_TELEGRAM_BOT_TOKEN"
os.environ["TELEGRAM_CHAT_ID"] = "YOUR_TELEGRAM_CHAT_ID"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("=" * 70)
    print("Comprehensive Esports Market Analysis")
    print("=" * 70)
    print()
    
    print("Step 1: Fetching all esports markets from Polymarket...")
    markets = fetch_all_esports_markets()
    
    print(f"\n[RESULT] Found {len(markets)} esports markets\n")
    
    if len(markets) == 0:
        print("No esports markets found!")
        sys.exit(0)
    
    print("-" * 70)
    print("Step 2: Testing price fetching for each market...")
    print("-" * 70)
    
    markets_with_prices = []
    markets_without_prices = []
    
    for i, market in enumerate(markets[:10], 1):  # Test first 10
        slug = market.get("market_slug", "")
        title = market.get("title", "")
        volume = market.get("volume_total", 0)
        side_a = market.get("side_a", {})
        yes_token_id = side_a.get("id")
        
        print(f"\n{i}. {title[:60]}")
        print(f"   Slug: {slug}")
        print(f"   Volume: ${volume:,.0f}")
        
        if yes_token_id:
            price = fetch_price(yes_token_id, "polymarket")
            if price is not None:
                print(f"   Price: ${price:.4f}")
                markets_with_prices.append({
                    "market": market,
                    "price": price,
                    "volume": volume
                })
            else:
                print(f"   Price: Could not fetch")
                markets_without_prices.append(market)
        else:
            print(f"   Price: No token ID available")
            markets_without_prices.append(market)
    
    print(f"\n" + "-" * 70)
    print(f"Summary:")
    print(f"  Total esports markets: {len(markets)}")
    print(f"  Markets with prices: {len(markets_with_prices)}")
    print(f"  Markets without prices: {len(markets_without_prices)}")
    
    if markets_with_prices:
        print(f"\n" + "-" * 70)
        print("Markets with prices (potential alerts):")
        print("-" * 70)
        for item in markets_with_prices:
            market = item["market"]
            price = item["price"]
            volume = item["volume"]
            title = market.get("title", "")
            slug = market.get("market_slug", "")
            
            # Check if it meets alert criteria
            meets_volume = volume > 1000
            meets_price = price < 0.05 or price > 0.95
            
            status = ""
            if meets_volume and meets_price:
                status = " [ALERT READY]"
            elif not meets_volume:
                status = f" [Volume too low: ${volume:,.0f} < $1,000]"
            elif not meets_price:
                status = f" [Price not extreme: ${price:.4f} not < 0.05 or > 0.95]"
            
            print(f"\n  {title[:60]}")
            print(f"    Slug: {slug}")
            print(f"    Price: ${price:.4f}")
            print(f"    Volume: ${volume:,.0f}{status}")
    
    print(f"\n" + "-" * 70)
    print("Step 3: Running alert analysis...")
    print("-" * 70)
    
    alerts = analyze_and_prepare_alerts()
    
    print(f"\n[RESULT] Prepared {len(alerts)} alerts")
    
    if len(alerts) > 0:
        print("\nGenerated Alerts:")
        for i, alert in enumerate(alerts, 1):
            print(f"\n  Alert {i}:")
            print(f"  {alert}")
    else:
        print("\n[INFO] No alerts generated.")
        if markets_with_prices:
            print("[INFO] This is because:")
            print("  - Markets have volume < $1,000, OR")
            print("  - Prices are not extreme (< $0.05 or > $0.95)")
        else:
            print("[INFO] Could not fetch prices for markets.")
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

