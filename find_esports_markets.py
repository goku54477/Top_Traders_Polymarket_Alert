"""Explore esports markets in Polymarket via Dome API."""
import requests
import json

import os
API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

ESPORTS_KEYWORDS = [
    "esports", "dota", "valorant", "lol", "league of legends",
    "csgo", "counter-strike", "overwatch", "rocket league",
    "smash bros", "ti", "vct", "worlds", "international",
    "champions", "major", "lck", "lec", "lpl", "cdl", "owc",
    "blast", "iem", "pgl", "battle", "tournament", "championship"
]

def search_esports_markets():
    """Search for esports markets."""
    print("=" * 60)
    print("Searching for Esports Markets in Polymarket")
    print("=" * 60)
    
    url = f"{BASE_URL}/polymarket/markets"
    
    # Try fetching multiple pages
    all_esports_markets = []
    seen_slugs = set()
    
    for offset in [0, 100, 200, 300, 400]:
        params = {"limit": 100, "offset": offset}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            if response.status_code != 200:
                print(f"Error at offset {offset}: {response.status_code}")
                break
                
            data = response.json()
            markets = data.get("markets", [])
            
            if not markets:
                break
            
            print(f"\nFetched {len(markets)} markets at offset {offset}...")
            
            for market in markets:
                slug = market.get("market_slug", "")
                title = market.get("title", "").lower()
                slug_lower = slug.lower()
                
                # Check if it matches esports keywords
                if any(keyword in title or keyword in slug_lower for keyword in ESPORTS_KEYWORDS):
                    if slug not in seen_slugs:
                        all_esports_markets.append(market)
                        seen_slugs.add(slug)
                        print(f"  Found: {market.get('title', 'N/A')[:60]}")
                        print(f"    Slug: {slug}")
            
            # Check pagination
            pagination = data.get("pagination", {})
            if not pagination.get("has_more", False):
                break
                
        except Exception as e:
            print(f"Error at offset {offset}: {e}")
            break
    
    print(f"\n" + "=" * 60)
    print(f"Total Esports Markets Found: {len(all_esports_markets)}")
    print("=" * 60)
    
    if all_esports_markets:
        print("\nEsports Market Slugs:")
        for market in all_esports_markets:
            print(f"  - {market.get('market_slug', 'N/A')}")
            print(f"    Title: {market.get('title', 'N/A')[:70]}")
            print(f"    Volume: ${market.get('volume_total', 0):,.0f}")
            print()
    
    return all_esports_markets

if __name__ == "__main__":
    markets = search_esports_markets()

