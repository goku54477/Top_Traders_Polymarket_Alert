"""Check all volume fields available in market objects."""
import os
import sys
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.esports_alert_bot import fetch_all_esports_markets

markets = fetch_all_esports_markets()

# Find CS markets
cs_markets = [m for m in markets if "counter-strike" in m.get("title", "").lower() or m.get("market_slug", "").startswith("cs2-")]

if cs_markets:
    print("=" * 80)
    print("Checking all volume-related fields in CS markets:")
    print("=" * 80)
    print()
    
    market = cs_markets[0]
    print(f"Sample market: {market.get('title', 'N/A')}")
    print(f"Slug: {market.get('market_slug', 'N/A')}")
    print()
    print("All fields containing 'volume' or 'vol':")
    for key in sorted(market.keys()):
        if 'vol' in key.lower():
            print(f"  {key}: {market.get(key)}")
    
    print()
    print("Full market object keys:")
    print(json.dumps(list(market.keys()), indent=2))
    
    print()
    print("\nChecking if there are other volume fields:")
    volume_fields = [k for k in market.keys() if 'vol' in k.lower() or 'trade' in k.lower() or 'liquidity' in k.lower()]
    print(f"Found: {volume_fields}")
    
    if volume_fields:
        print("\nValues:")
        for field in volume_fields:
            print(f"  {field}: {market.get(field)}")

