"""
Check Dome API response for URL fields
"""

import os
import requests
import json
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

print("Checking Dome API response for URL fields...\n")

for market in markets:
    slug = market.get("market_slug", "")
    if slug in target_slugs:
        print(f"=" * 80)
        print(f"Market: {slug}")
        print(f"=" * 80)
        
        # Check for any URL-related fields
        print("\nChecking for URL-related fields:")
        url_fields = {k: v for k, v in market.items() if 'url' in k.lower() or 'link' in k.lower() or 'href' in k.lower()}
        if url_fields:
            for k, v in url_fields.items():
                print(f"  {k}: {v}")
        else:
            print("  No URL fields found")
        
        # Check condition_id
        condition_id = market.get("condition_id")
        print(f"\nCondition ID: {condition_id}")
        
        # Check if there's a polymarket-specific field
        print(f"\nAll field names containing 'poly' or 'market':")
        poly_fields = {k: v for k, v in market.items() if 'poly' in k.lower() or 'market' in k.lower()}
        for k, v in poly_fields.items():
            print(f"  {k}: {v}")
        
        print("\n")

