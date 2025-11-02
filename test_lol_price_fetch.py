"""
Test script to manually fetch prices for LoL markets and investigate API failures.
This helps diagnose why LoL markets might be failing price fetches.
"""

import os
import sys
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"

if not API_KEY:
    print("ERROR: DOME_API_KEY environment variable not set!")
    sys.exit(1)

def get_headers():
    """Get authorization headers."""
    return {"Authorization": f"Bearer {API_KEY}"}

def fetch_markets():
    """Fetch esports markets from the API."""
    url = f"{BASE_URL}/polymarket/markets"
    params = {"limit": 100, "offset": 0}
    
    print(f"Fetching markets from {url}...")
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    markets = data.get("markets", [])
    print(f"Found {len(markets)} markets\n")
    
    return markets

def fetch_price(token_id, market_slug=None, game_type=None):
    """Fetch price for a specific token_id."""
    url = f"{BASE_URL}/polymarket/market-price/{token_id}"
    
    context_str = ""
    if game_type:
        context_str += f"game={game_type}, "
    if market_slug:
        context_str += f"slug={market_slug[:50]}"
    
    print(f"Fetching price for token_id={token_id[:30]}... ({context_str})")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=get_headers(), timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 404:
            print("❌ 404 - Market not found (likely closed/resolved)")
            return None, 404
        
        if response.status_code == 429:
            print("⚠️ 429 - Rate limited")
            return None, 429
        
        if response.status_code >= 500:
            print(f"⚠️ Server error ({response.status_code})")
            return None, response.status_code
        
        response.raise_for_status()
        data = response.json()
        price = data.get("price")
        
        if price is not None:
            print(f"✅ Success! Price: {price:.4f} ({price*100:.2f}%)")
            return price, response.status_code
        else:
            print("⚠️ Price field not found in response")
            print(f"Response: {data}")
            return None, response.status_code
            
    except requests.exceptions.Timeout:
        print("❌ Timeout - Request took too long")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None, None
    
    time.sleep(1.1)  # Rate limiting

def main():
    """Main test function."""
    print("=" * 80)
    print("LoL Market Price Fetch Test Script")
    print("=" * 80)
    print()
    
    # Fetch markets
    markets = fetch_markets()
    
    # Filter for LoL markets
    lol_markets = []
    for market in markets:
        slug = market.get("market_slug", "").lower()
        title = market.get("title", "").lower()
        
        if "lol" in slug or "lol-" in slug or "league" in title or "league of legends" in title:
            lol_markets.append(market)
    
    print(f"Found {len(lol_markets)} LoL markets\n")
    
    if not lol_markets:
        print("No LoL markets found. Testing with a sample token_id...")
        print("Please provide a token_id to test manually:")
        token_id = input("Token ID (or press Enter to skip): ").strip()
        if token_id:
            fetch_price(token_id, "test-market", "League of Legends")
        return
    
    # Test price fetching for each LoL market
    print("Testing price fetching for LoL markets:\n")
    print("-" * 80)
    
    for i, market in enumerate(lol_markets[:10], 1):  # Test first 10
        slug = market.get("market_slug", "unknown")
        title = market.get("title", "unknown")
        side_a = market.get("side_a", {})
        yes_token_id = side_a.get("id")
        status = market.get("status", "unknown")
        volume_total = market.get("volume_total", 0)
        volume_1_week = market.get("volume_1_week", 0)
        
        print(f"\n[{i}/{min(10, len(lol_markets))}] Market: {slug}")
        print(f"  Title: {title[:60]}")
        print(f"  Status: {status}")
        print(f"  Volume: total=${volume_total:,.0f}, 1week=${volume_1_week:,.0f}")
        
        if not yes_token_id:
            print("  ❌ No token_id found for side_a")
            continue
        
        price, status_code = fetch_price(yes_token_id, slug, "League of Legends")
        
        if price is None:
            print(f"  ❌ Failed to fetch price (status: {status_code})")
        else:
            print(f"  ✅ Price fetched successfully: {price:.4f}")
        
        print("-" * 80)
        time.sleep(1.1)  # Rate limiting
    
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()

