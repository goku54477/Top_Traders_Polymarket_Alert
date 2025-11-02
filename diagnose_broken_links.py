"""
Diagnostic script to check available fields for markets with broken links
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"

if not API_KEY:
    print("ERROR: DOME_API_KEY environment variable not set!")
    sys.exit(1)

def get_headers():
    return {"Authorization": f"Bearer {API_KEY}"}

def fetch_markets():
    """Fetch markets and find the specific ones with broken links."""
    url = f"{BASE_URL}/polymarket/markets"
    params = {"limit": 100, "offset": 0}
    
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    markets = data.get("markets", [])
    
    # Find the specific markets mentioned
    target_slugs = [
        "lol-kcb-hrts-2025-11-02-game1",
        "dota2-bb4-flc-2025-11-02-total-games-4pt5",
        "dota2-bb4-flc-2025-11-02-game3"
    ]
    
    found_markets = []
    for market in markets:
        slug = market.get("market_slug", "")
        if slug in target_slugs:
            found_markets.append(market)
            print(f"\n{'='*80}")
            print(f"Market: {slug}")
            print(f"{'='*80}")
            
            # Print all available fields
            print("\nAll available fields:")
            for key, value in market.items():
                if isinstance(value, (dict, list)):
                    print(f"  {key}: {type(value).__name__} (length: {len(value) if isinstance(value, list) else 'N/A'})")
                    if key == "side_a" or key == "side_b":
                        print(f"    {key} details: {value}")
                else:
                    print(f"  {key}: {value}")
            
            # Check for URL-related fields
            print("\n\nURL-related fields:")
            url_fields = ["polymarket_url", "url", "market_url", "condition_id", "conditionId", 
                          "polymarket_condition_id", "market_id", "id"]
            for field in url_fields:
                value = market.get(field)
                if value:
                    print(f"  {field}: {value}")
            
            # Check side_a and side_b for relevant IDs
            print("\n\nSide A & B details:")
            side_a = market.get("side_a", {})
            side_b = market.get("side_b", {})
            print(f"  side_a: {side_a}")
            print(f"  side_b: {side_b}")
            
            # Try to construct potential URLs
            print("\n\nPotential URL formats:")
            slug = market.get("market_slug", "")
            
            # Try /event/{slug}
            print(f"  1. /event/{slug}: https://polymarket.com/event/{slug}")
            
            # Try /market/{condition_id} if available
            condition_id = market.get("condition_id") or market.get("conditionId") or market.get("polymarket_condition_id")
            if condition_id:
                print(f"  2. /market/{condition_id}: https://polymarket.com/market/{condition_id}")
            
            # Try /market/{yes_token_id} (current broken format)
            yes_token_id = side_a.get("id") if side_a else None
            if yes_token_id:
                print(f"  3. /market/{yes_token_id}: https://polymarket.com/market/{yes_token_id}")
            
            # Try /market/{market_id} if available
            market_id = market.get("market_id") or market.get("id")
            if market_id:
                print(f"  4. /market/{market_id}: https://polymarket.com/market/{market_id}")
            
            print("\n")
    
    return found_markets

if __name__ == "__main__":
    print("=" * 80)
    print("Diagnosing Broken Links - Checking Market Fields")
    print("=" * 80)
    markets = fetch_markets()
    
    if not markets:
        print("\n⚠️  Could not find all target markets. They may have been paginated.")
        print("Checking first 100 markets for any LoL or Dota markets...")
        
        url = f"{BASE_URL}/polymarket/markets"
        params = {"limit": 100, "offset": 0}
        response = requests.get(url, headers=get_headers(), params=params, timeout=30)
        data = response.json()
        all_markets = data.get("markets", [])
        
        for market in all_markets[:5]:  # Show first 5 as example
            slug = market.get("market_slug", "")
            if "lol" in slug.lower() or "dota" in slug.lower():
                print(f"\nExample market: {slug}")
                print(f"  Available fields: {list(market.keys())[:15]}")

