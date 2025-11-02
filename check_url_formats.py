"""
Check what URL format actually works for Polymarket markets
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Find the specific markets
response = requests.get(f"{BASE_URL}/polymarket/markets", headers=headers, params={"limit": 100})
markets = response.json().get("markets", [])

target_slugs = [
    "lol-kcb-hrts-2025-11-02-game1",
    "dota2-bb4-flc-2025-11-02-total-games-4pt5",
    "dota2-bb4-flc-2025-11-02-game3"
]

print("Checking markets for correct URL format...\n")

for market in markets:
    slug = market.get("market_slug", "")
    if slug in target_slugs:
        print(f"=" * 80)
        print(f"Market: {slug}")
        print(f"=" * 80)
        print(f"Condition ID: {market.get('condition_id')}")
        print(f"\nTrying different URL formats:")
        
        # Try /event/{slug}
        print(f"1. /event/{{slug}}: https://polymarket.com/event/{slug}")
        
        # Try /market/{condition_id}
        condition_id = market.get("condition_id")
        if condition_id:
            print(f"2. /market/{{condition_id}}: https://polymarket.com/market/{condition_id}")
        
        # Check for any URL fields
        url_fields = {k: v for k, v in market.items() if 'url' in k.lower() or 'link' in k.lower()}
        if url_fields:
            print(f"\nDirect URL fields found:")
            for k, v in url_fields.items():
                print(f"  {k}: {v}")
        
        print("\n")

