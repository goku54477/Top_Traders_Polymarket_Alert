"""
Test different URL formats to find what works for Polymarket
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Find a specific market
response = requests.get(f"{BASE_URL}/polymarket/markets", headers=headers, params={"limit": 100})
markets = response.json().get("markets", [])

# Find the LoL market
target_market = None
for market in markets:
    if "lol-kcb-hrts-2025-11-02-game1" in market.get("market_slug", ""):
        target_market = market
        break

if target_market:
    slug = target_market.get("market_slug")
    condition_id = target_market.get("condition_id")
    title = target_market.get("title", "")
    
    print(f"Market: {slug}")
    print(f"Title: {title}")
    print(f"Condition ID: {condition_id}")
    print("\n" + "="*80)
    print("Testing different URL formats:")
    print("="*80)
    
    # Try different formats
    formats = [
        f"https://polymarket.com/event/{slug}",
        f"https://polymarket.com/market/{condition_id}",
        f"https://polymarket.com/markets/{condition_id}",
        f"https://polymarket.com/market/{condition_id.replace('0x', '') if condition_id else ''}",
        f"https://polymarket.com/markets/{condition_id.replace('0x', '') if condition_id else ''}",
        f"https://polymarket.com/search?q={slug}",
        f"https://polymarket.com/search?q={title.replace(' ', '+')}",
    ]
    
    for i, url_format in enumerate(formats, 1):
        print(f"\n{i}. {url_format}")
    
    print("\n" + "="*80)
    print("NOTE: You'll need to manually test these URLs in your browser")
    print("to see which one works. The working format can then be used in the bot.")
    print("="*80)
else:
    print("Market not found in API response")

