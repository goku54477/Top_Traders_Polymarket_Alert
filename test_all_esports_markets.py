"""Diagnostic script to verify all esports markets are included."""
import os
import sys
import logging
from collections import defaultdict

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
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)

def test_all_esports_markets():
    """Test to see all esports markets found by game type."""
    print("=" * 80)
    print("Testing All Esports Markets Detection")
    print("=" * 80)
    print()
    
    print("Fetching esports markets...")
    markets = fetch_all_esports_markets()
    
    # Group by game type
    games = defaultdict(list)
    no_game_type = []
    
    for market in markets:
        event_info = format_event_info(market)
        game_type = event_info.get("game_type", "Unknown")
        slug = market.get("market_slug", "")
        
        if game_type == "Unknown":
            # Try to infer from slug
            slug_lower = slug.lower()
            if slug_lower.startswith("cs2-") or slug_lower.startswith("csgo-"):
                game_type = "Counter-Strike"
            elif slug_lower.startswith("valorant-"):
                game_type = "Valorant"
            elif slug_lower.startswith("ow-"):
                game_type = "Overwatch"
            elif slug_lower.startswith("rl-"):
                game_type = "Rocket League"
            elif "counter-strike" in slug_lower or "cs2" in slug_lower or "csgo" in slug_lower:
                game_type = "Counter-Strike"
            elif "valorant" in slug_lower:
                game_type = "Valorant"
            elif "overwatch" in slug_lower:
                game_type = "Overwatch"
            elif "rocket league" in slug_lower:
                game_type = "Rocket League"
            elif "smash" in slug_lower:
                game_type = "Smash Bros"
        
        games[game_type].append(market)
    
    print(f"\n{'='*80}")
    print(f"FOUND {len(markets)} TOTAL ESPORTS MARKETS")
    print(f"{'='*80}\n")
    
    for game_type in sorted(games.keys()):
        game_markets = games[game_type]
        print(f"{game_type}: {len(game_markets)} market(s)")
        for i, market in enumerate(game_markets[:5], 1):  # Show first 5
            slug = market.get("market_slug", "")
            title = market.get("title", "")[:70]
            volume = market.get("volume_total", 0)
            print(f"  {i}. {title}")
            print(f"     Slug: {slug}")
            print(f"     Volume: ${volume:,.0f}")
        if len(game_markets) > 5:
            print(f"     ... and {len(game_markets) - 5} more")
        print()
    
    # Check for the specific LoL market
    print(f"{'='*80}")
    print("CHECKING SPECIFIC LoL MARKET")
    print(f"{'='*80}\n")
    target_slug = "lol-t1-tes-2025-11-02-total-games-3pt5"
    found = False
    for market in markets:
        if market.get("market_slug", "") == target_slug:
            found = True
            print(f"✓ Found target market: {target_slug}")
            event_info = format_event_info(market)
            game_type = event_info.get("game_type", "Unknown")
            print(f"  Game Type: {game_type}")
            
            condition_id = (
                market.get("condition_id") or 
                market.get("conditionId") or 
                market.get("polymarket_condition_id")
            )
            side_a = market.get("side_a", {})
            yes_token_id = side_a.get("id")
            
            if game_type == "League of Legends":
                if condition_id:
                    url = f"https://polymarket.com/market/{condition_id}"
                    print(f"  ✓ URL: {url}")
                elif yes_token_id:
                    url = f"https://polymarket.com/market/{yes_token_id}"
                    print(f"  ✓ URL (using token_id): {url}")
                else:
                    url = f"https://polymarket.com/event/{target_slug}"
                    print(f"  ⚠ URL (fallback): {url}")
            break
    
    if not found:
        print(f"✗ Target market NOT FOUND: {target_slug}")
        print("  This might mean:")
        print("  - Market no longer exists")
        print("  - Market was filtered out")
        print("  - Market slug changed")
    
    print(f"\n{'='*80}")
    print("Summary:")
    print(f"  Total markets found: {len(markets)}")
    print(f"  Game types detected: {len(games)}")
    print(f"  Games: {', '.join(sorted(games.keys()))}")
    print(f"{'='*80}")

if __name__ == "__main__":
    try:
        if not API_KEY or API_KEY == "YOUR_DOME_API_KEY":
            print("ERROR: DOME_API_KEY not set!")
            print("Please set it in your environment or .env file")
            sys.exit(1)
        
        test_all_esports_markets()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        logging.exception("Test error")
        sys.exit(1)

