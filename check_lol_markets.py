"""Check what LoL markets the API is returning vs what's on Polymarket."""
import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.esports_alert_bot import fetch_all_esports_markets

logging.basicConfig(level=logging.WARNING)

markets = fetch_all_esports_markets()

# Filter LoL markets
lol_markets = [m for m in markets if "lol-" in m.get("market_slug", "").lower() or "league" in m.get("title", "").lower()]

print("=" * 80)
print(f"LoL Markets Found by API: {len(lol_markets)}")
print("=" * 80)
print()

for i, market in enumerate(lol_markets, 1):
    slug = market.get("market_slug", "")
    title = market.get("title", "")
    volume_total = market.get("volume_total", 0)
    volume_1_week = market.get("volume_1_week", 0)
    status = market.get("status", "N/A")
    end_time = market.get("end_time", "N/A")
    
    print(f"{i}. {title}")
    print(f"   Slug: {slug}")
    print(f"   Volume Total: ${volume_total:,.0f}")
    print(f"   Volume 1 Week: ${volume_1_week:,.0f}")
    print(f"   Status: {status}")
    print(f"   End Time: {end_time}")
    print()

print("\n" + "=" * 80)
print("Expected from Polymarket website:")
print("  - KCB vs HRTS match (should have volume)")
print("  - T1 vs TES match (completed)")
print("=" * 80)

