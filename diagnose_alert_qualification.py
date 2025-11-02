"""Diagnostic script to show why markets are/aren't qualifying for alerts."""
import os
import sys
import logging

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.esports_alert_bot import (
    fetch_all_esports_markets,
    fetch_price,
    format_event_info,
    last_alerted_slugs,
    API_KEY
)

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)

def diagnose_markets():
    """Show why each market qualifies or doesn't qualify for alerts."""
    print("=" * 80)
    print("Market Qualification Diagnosis")
    print("=" * 80)
    print()
    
    print("Fetching esports markets...")
    markets = fetch_all_esports_markets()
    
    print(f"\nFound {len(markets)} esports markets")
    print(f"Already alerted markets: {len(last_alerted_slugs)}")
    print()
    
    qualified = []
    not_qualified = []
    
    for market in markets:
        slug = market.get("market_slug", "")
        title = market.get("title", "")[:60]
        volume = market.get("volume_total", 0)
        
        event_info = format_event_info(market)
        game_type = event_info.get("game_type", "Unknown")
        
        # Check reasons
        reasons = []
        disqualify_reasons = []
        
        # Check 1: Already alerted
        if slug in last_alerted_slugs:
            disqualify_reasons.append(f"Already alerted (in last_alerted_slugs)")
        else:
            reasons.append("✓ Not yet alerted")
        
        # Check 2: Has token IDs
        side_a = market.get("side_a", {})
        side_b = market.get("side_b", {})
        yes_token_id = side_a.get("id")
        no_token_id = side_b.get("id")
        
        if not yes_token_id or not no_token_id:
            disqualify_reasons.append(f"Missing token IDs")
        else:
            reasons.append("✓ Has token IDs")
        
        # Check 3: Fetch price
        poly_price = None
        if yes_token_id:
            poly_price = fetch_price(yes_token_id, "polymarket")
            if poly_price is None:
                disqualify_reasons.append(f"Price fetch failed")
            else:
                reasons.append(f"✓ Price fetched: {poly_price:.4f}")
        
        # Check 4: Volume threshold
        if volume <= 1000:
            disqualify_reasons.append(f"Volume too low: ${volume:,.0f} (need > $1,000)")
        else:
            reasons.append(f"✓ Volume sufficient: ${volume:,.0f}")
        
        # Check 5: Extreme price threshold
        if poly_price is not None:
            if not (poly_price < 0.05 or poly_price > 0.95):
                disqualify_reasons.append(f"Price not extreme: {poly_price:.4f} (need < 0.05 or > 0.95)")
            else:
                reasons.append(f"✓ Extreme price: {poly_price:.4f}")
        
        # Determine if qualified
        is_qualified = (
            slug not in last_alerted_slugs and
            yes_token_id and no_token_id and
            poly_price is not None and
            volume > 1000 and
            (poly_price < 0.05 or poly_price > 0.95)
        )
        
        market_info = {
            "slug": slug,
            "title": title,
            "game_type": game_type,
            "volume": volume,
            "price": poly_price,
            "reasons": reasons,
            "disqualify_reasons": disqualify_reasons,
            "qualified": is_qualified
        }
        
        if is_qualified:
            qualified.append(market_info)
        else:
            not_qualified.append(market_info)
    
    # Print qualified markets
    print("=" * 80)
    print(f"QUALIFIED MARKETS ({len(qualified)})")
    print("=" * 80)
    if qualified:
        for i, m in enumerate(qualified, 1):
            print(f"\n{i}. {m['game_type']} - {m['title']}")
            print(f"   Slug: {m['slug']}")
            print(f"   Volume: ${m['volume']:,.0f}")
            print(f"   Price: {m['price']:.4f}")
            print(f"   Reasons: {', '.join(m['reasons'])}")
    else:
        print("No markets currently qualify for alerts")
    
    # Print not qualified markets
    print("\n" + "=" * 80)
    print(f"NOT QUALIFIED MARKETS ({len(not_qualified)})")
    print("=" * 80)
    
    # Group by game type
    by_game = {}
    for m in not_qualified:
        game = m['game_type']
        if game not in by_game:
            by_game[game] = []
        by_game[game].append(m)
    
    for game_type in sorted(by_game.keys()):
        game_markets = by_game[game_type]
        print(f"\n{game_type} ({len(game_markets)} market(s)):")
        for m in game_markets:
            print(f"\n  • {m['title']}")
            print(f"    Slug: {m['slug']}")
            print(f"    Volume: ${m['volume']:,.0f}")
            if m['price'] is not None:
                print(f"    Price: {m['price']:.4f}")
            else:
                print(f"    Price: Failed to fetch")
            
            if m['disqualify_reasons']:
                print(f"    Reasons: {'; '.join(m['disqualify_reasons'])}")
            if m['reasons']:
                print(f"    ✓ {', '.join(m['reasons'])}")
    
    print("\n" + "=" * 80)
    print("Summary:")
    print(f"  Total markets: {len(markets)}")
    print(f"  Qualified: {len(qualified)}")
    print(f"  Not qualified: {len(not_qualified)}")
    print("=" * 80)

if __name__ == "__main__":
    try:
        if not API_KEY or API_KEY == "YOUR_DOME_API_KEY":
            print("ERROR: DOME_API_KEY not set!")
            sys.exit(1)
        
        diagnose_markets()
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        logging.exception("Error")

