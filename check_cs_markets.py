"""Check what Counter-Strike markets are actually available vs what we're detecting."""
import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.esports_alert_bot import fetch_all_esports_markets, format_event_info

logging.basicConfig(level=logging.WARNING)

markets = fetch_all_esports_markets()

# Filter Counter-Strike markets
cs_markets = [m for m in markets if "counter-strike" in m.get("title", "").lower() or m.get("market_slug", "").startswith("cs2-")]

print("=" * 80)
print(f"Counter-Strike Markets Found: {len(cs_markets)}")
print("=" * 80)
print()

for i, market in enumerate(cs_markets[:10], 1):
    slug = market.get("market_slug", "")
    title = market.get("title", "")
    volume = market.get("volume_total", 0)
    tags = market.get("tags", [])
    
    print(f"{i}. {title}")
    print(f"   Slug: {slug}")
    print(f"   Volume: ${volume:,.0f}")
    print(f"   Tags: {tags}")
    print()

print(f"\nTotal CS markets: {len(cs_markets)}")
print("\nNote: Check if these match what's on Polymarket website")

