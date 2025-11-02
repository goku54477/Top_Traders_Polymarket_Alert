"""Test script to verify LoL market URL construction."""
import os
import sys
import logging

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import bot functions
from app.esports_alert_bot import (
    fetch_all_esports_markets,
    format_event_info,
    API_KEY
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def test_url_construction():
    """Test URL construction for LoL and Dota markets."""
    print("=" * 80)
    print("Testing URL Construction for LoL and Dota Markets")
    print("=" * 80)
    print()
    
    print("Fetching esports markets...")
    markets = fetch_all_esports_markets()
    
    # Separate LoL and Dota markets
    lol_markets = []
    dota_markets = []
    
    for market in markets:
        slug = market.get("market_slug", "").lower()
        if slug.startswith("lol-"):
            lol_markets.append(market)
        elif slug.startswith("dota2-") or slug.startswith("dota-"):
            dota_markets.append(market)
    
    print(f"\nFound {len(lol_markets)} LoL markets and {len(dota_markets)} Dota markets")
    print()
    
    # Test LoL markets
    print("=" * 80)
    print("LoL MARKET URL TESTING")
    print("=" * 80)
    
    if not lol_markets:
        print("No LoL markets found to test.")
    else:
        for i, market in enumerate(lol_markets[:5], 1):  # Test first 5 LoL markets
            print(f"\n--- LoL Market {i} ---")
            slug = market.get("market_slug", "")
            title = market.get("title", "")
            print(f"Title: {title}")
            print(f"Slug: {slug}")
            
            # Show available fields
            condition_id = (
                market.get("condition_id") or 
                market.get("conditionId") or 
                market.get("polymarket_condition_id")
            )
            polymarket_url_direct = (
                market.get("polymarket_url") or 
                market.get("url") or 
                market.get("market_url")
            )
            side_a = market.get("side_a", {})
            yes_token_id = side_a.get("id")
            
            print(f"  Available fields:")
            print(f"    - condition_id: {condition_id}")
            print(f"    - conditionId: {market.get('conditionId')}")
            print(f"    - polymarket_url: {market.get('polymarket_url')}")
            print(f"    - url: {market.get('url')}")
            print(f"    - market_url: {market.get('market_url')}")
            print(f"    - yes_token_id: {yes_token_id}")
            
            # Parse event info
            event_info = format_event_info(market)
            game_type = event_info.get("game_type", "")
            
            # Simulate URL construction logic
            clean_slug = str(slug).strip()
            
            print(f"\n  URL Construction Logic:")
            print(f"    - Game Type detected: {game_type}")
            
            if game_type == "League of Legends":
                if polymarket_url_direct:
                    polymarket_url = polymarket_url_direct
                    print(f"    ✓ Using direct URL field: {polymarket_url}")
                elif condition_id:
                    polymarket_url = f"https://polymarket.com/market/{condition_id}"
                    print(f"    ✓ Using condition_id format: {polymarket_url}")
                elif yes_token_id:
                    polymarket_url = f"https://polymarket.com/market/{yes_token_id}"
                    print(f"    ✓ Using token_id format: {polymarket_url}")
                else:
                    polymarket_url = f"https://polymarket.com/event/{clean_slug}"
                    print(f"    ⚠ Falling back to slug format: {polymarket_url}")
                
                print(f"\n  FINAL URL: {polymarket_url}")
            else:
                print(f"    ⚠ Game type not detected as LoL!")
    
    # Test Dota markets for comparison
    print("\n")
    print("=" * 80)
    print("DOTA MARKET URL TESTING (for comparison)")
    print("=" * 80)
    
    if not dota_markets:
        print("No Dota markets found to test.")
    else:
        for i, market in enumerate(dota_markets[:3], 1):  # Test first 3 Dota markets
            print(f"\n--- Dota Market {i} ---")
            slug = market.get("market_slug", "")
            title = market.get("title", "")
            print(f"Title: {title}")
            print(f"Slug: {slug}")
            
            event_info = format_event_info(market)
            game_type = event_info.get("game_type", "")
            clean_slug = str(slug).strip()
            
            # Dota uses slug format
            polymarket_url = f"https://polymarket.com/event/{clean_slug}"
            print(f"Game Type: {game_type}")
            print(f"URL: {polymarket_url}")
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Copy the LoL URLs from above")
    print("2. Test them manually in your browser")
    print("3. Check which format works correctly")
    print("4. Update the code if needed based on results")

if __name__ == "__main__":
    try:
        if not API_KEY or API_KEY == "YOUR_DOME_API_KEY":
            print("ERROR: DOME_API_KEY not set!")
            print("Please set it in your environment or .env file")
            sys.exit(1)
        
        test_url_construction()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        logging.exception("Test error")
        sys.exit(1)

