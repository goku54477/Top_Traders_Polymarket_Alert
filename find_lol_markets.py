"""Test specifically for LoL markets with volume."""
import os
import requests
import json

API_KEY = "YOUR_DOME_API_KEY"
BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def find_lol_markets():
    """Find League of Legends markets."""
    print("=" * 70)
    print("Searching for League of Legends (LoL) Markets")
    print("=" * 70)
    
    url = f"{BASE_URL}/polymarket/markets"
    all_lol_markets = []
    offset = 0
    limit = 100
    
    while offset < 500:  # Check first 500 markets
        params = {"limit": limit, "offset": offset}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            if response.status_code != 200:
                break
            
            data = response.json()
            markets = data.get("markets", [])
            
            if not markets:
                break
            
            for market in markets:
                title = market.get("title", "").lower()
                slug = market.get("market_slug", "").lower()
                
                # Check for LoL keywords
                lol_keywords = ["lol", "league of legends", "gen.g", "kt rolster", "t1", "top esports", "tes"]
                is_lol = any(keyword in title or keyword in slug for keyword in lol_keywords)
                
                # Exclude non-esports
                non_esports = ["nba", "nfl", "ufc", "atp", "wta", "tennis", "f1"]
                is_non_esports = any(keyword in title or keyword in slug for keyword in non_esports)
                
                if is_lol and not is_non_esports:
                    volume = market.get("volume_total", 0)
                    all_lol_markets.append({
                        "market": market,
                        "volume": volume
                    })
            
            pagination = data.get("pagination", {})
            if not pagination.get("has_more", False):
                break
            
            offset += limit
            
        except Exception as e:
            print(f"Error at offset {offset}: {e}")
            break
    
    print(f"\nFound {len(all_lol_markets)} LoL markets\n")
    
    # Sort by volume
    all_lol_markets.sort(key=lambda x: x["volume"], reverse=True)
    
    print("-" * 70)
    print("LoL Markets (sorted by volume):")
    print("-" * 70)
    
    for i, item in enumerate(all_lol_markets[:20], 1):  # Show top 20
        market = item["market"]
        volume = item["volume"]
        title = market.get("title", "")
        slug = market.get("market_slug", "")
        side_a = market.get("side_a", {})
        side_b = market.get("side_b", {})
        yes_token_id = side_a.get("id")
        
        print(f"\n{i}. {title}")
        print(f"   Slug: {slug}")
        print(f"   Volume: ${volume:,.0f}")
        
        # Try to fetch price
        if yes_token_id:
            try:
                price_url = f"{BASE_URL}/polymarket/market-price/{yes_token_id}"
                price_response = requests.get(price_url, headers=HEADERS, timeout=10)
                if price_response.status_code == 200:
                    price_data = price_response.json()
                    price = price_data.get("price")
                    if price:
                        print(f"   Price: ${price:.4f}")
                        
                        # Check if it meets alert criteria
                        if volume > 1000 and (price < 0.05 or price > 0.95):
                            print(f"   *** ALERT READY ***")
            except:
                pass
        
        print()
    
    return all_lol_markets

if __name__ == "__main__":
    markets = find_lol_markets()
    print("\n" + "=" * 70)
    print(f"Total LoL markets found: {len(markets)}")
    print("=" * 70)

