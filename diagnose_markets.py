"""Diagnostic script to investigate market filtering and data collection from Dome API."""
import os
import sys
import requests
import json
from collections import defaultdict
from datetime import datetime

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to get API key from environment or from bot module
API_KEY = os.getenv("DOME_API_KEY")
if not API_KEY or API_KEY == "YOUR_DOME_API_KEY":
    # Try importing from bot module as fallback
    try:
        from app.esports_alert_bot import API_KEY as BOT_API_KEY
        if BOT_API_KEY and BOT_API_KEY != "YOUR_DOME_API_KEY":
            API_KEY = BOT_API_KEY
            print("Using API key from bot module...")
    except:
        pass

if not API_KEY or API_KEY == "YOUR_DOME_API_KEY":
    print("ERROR: DOME_API_KEY environment variable not set!")
    print("Please set it before running:")
    print("  Windows: $env:DOME_API_KEY='your_key_here'")
    print("  Linux/Mac: export DOME_API_KEY='your_key_here'")
    print("  Or create a .env file with: DOME_API_KEY=your_key_here")
    sys.exit(1)

BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Copy keywords from main bot
ESPORTS_KEYWORDS = [
    "esports",
    "dota",
    "valorant",
    "league of legends",
    "counter-strike",
    "cs2",
    "csgo",
    "overwatch",
    "rocket league",
    "smash bros",
    "ti",
    "vct",
    "worlds",
    "international",
    "champions",
    "major",
    "lck",
    "lec",
    "lpl",
    "cdl",
    "owc",
    "blast",
    "iem",
    "pgl",
]

ESPORTS_SPECIFIC_KEYWORDS = [
    "lol",
    "gen.g", "gen g", "kt rolster", "kt", "t1", "top esports", "tes",
    "fnatic", "g2", "cloud9", "c9", "team liquid", "tl", "100 thieves",
    "tsm", "clg", "nautilus", "nrg", "mouz", "team spirit", "team falcons",
]

NON_ESPORTS_KEYWORDS = [
    "nba", "nfl", "nhl", "mlb", "ufc", "boxing", "mma",
    "atp", "wta", "tennis", "f1", "formula", "racing",
    "golf", "soccer", "football", "basketball", "baseball",
    "hockey", "cricket", "rugby", "trump", "biden", "political",
    "election", "president", "congress", "earnings", "stock",
    "house of representatives", "representatives", "senate",
    "approval rating", "will trump", "will biden",
]


def fetch_markets_sample(limit=100, offset=0):
    """Fetch a sample of markets from Dome API."""
    url = f"{BASE_URL}/polymarket/markets"
    params = {"limit": limit, "offset": offset}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return None


def fetch_all_markets_paginated(max_pages=20):
    """Fetch markets across multiple pages to find esports markets."""
    all_markets = []
    offset = 0
    limit = 100
    
    for page in range(max_pages):
        print(f"Fetching page {page + 1} (offset {offset})...")
        data = fetch_markets_sample(limit=limit, offset=offset)
        
        if not data:
            break
            
        markets = data.get("markets", [])
        if not markets:
            break
            
        all_markets.extend(markets)
        pagination = data.get("pagination", {})
        
        if not pagination.get("has_more", False):
            break
            
        offset += limit
        
        # Check if we found any esports markets yet
        esports_found = sum(1 for m in all_markets 
                           if any(kw in m.get("title", "").lower() or kw in m.get("market_slug", "").lower() 
                                  for kw in ESPORTS_KEYWORDS + ESPORTS_SPECIFIC_KEYWORDS))
        
        if esports_found > 0 and page >= 2:  # Found some and fetched at least 3 pages
            print(f"Found {esports_found} esports markets so far. Continuing...")
    
    return all_markets


def analyze_market_structure(markets):
    """Analyze the structure of market objects."""
    if not markets:
        print("No markets to analyze")
        return
    
    print("\n" + "="*80)
    print("MARKET DATA STRUCTURE ANALYSIS")
    print("="*80)
    
    # Show first market as example
    sample = markets[0]
    print("\nSample Market Object Structure:")
    print(json.dumps(sample, indent=2))
    
    # List all available keys
    print("\n\nAvailable Fields in Market Objects:")
    all_keys = set()
    for market in markets[:10]:  # Check first 10 markets
        all_keys.update(market.keys())
    for key in sorted(all_keys):
        print(f"  - {key}")
    
    # Check for category/tags/sport fields
    print("\n\nChecking for Category/Sport Fields:")
    category_fields = ["category", "sport", "tags", "type", "subcategory", "group"]
    for field in category_fields:
        if field in sample:
            print(f"  [FOUND] '{field}': {sample.get(field)}")
        else:
            print(f"  [NOT FOUND] '{field}' not found")


def categorize_markets_by_keyword(markets):
    """Categorize markets by which keywords match."""
    keyword_matches = defaultdict(list)
    game_type_counts = defaultdict(int)
    
    for market in markets:
        title = market.get("title", "").lower()
        slug = market.get("market_slug", "").lower()
        
        # Check each keyword
        matched_keywords = []
        for keyword in ESPORTS_KEYWORDS + ESPORTS_SPECIFIC_KEYWORDS:
            if keyword in title or keyword in slug:
                matched_keywords.append(keyword)
                keyword_matches[keyword].append(market)
        
        # Determine game type
        game_type = "Unknown"
        if any(k in title or k in slug for k in ["cs", "counter-strike", "cs2", "csgo"]):
            game_type = "Counter-Strike"
        elif any(k in title or k in slug for k in ["lol", "league of legends"]):
            game_type = "League of Legends"
        elif any(k in title or k in slug for k in ["dota", "dota2"]):
            game_type = "Dota 2"
        elif any(k in title or k in slug for k in ["valorant"]):
            game_type = "Valorant"
        elif any(k in title or k in slug for k in ["overwatch"]):
            game_type = "Overwatch"
        elif any(k in title or k in slug for k in ["rocket league"]):
            game_type = "Rocket League"
        
        game_type_counts[game_type] += 1
    
    return keyword_matches, game_type_counts


def test_filtering_logic(markets):
    """Test the exact filtering logic from the bot."""
    print("\n" + "="*80)
    print("FILTERING LOGIC TEST")
    print("="*80)
    
    passed_markets = []
    failed_markets = []
    failure_reasons = defaultdict(int)
    
    for market in markets:
        slug = market.get("market_slug", "")
        title = market.get("title", "").lower()
        slug_lower = slug.lower()
        
        # Skip if already seen (simulating seen_slugs)
        # (We'll track in this function)
        
        # Check if it matches esports keywords (EXACT LOGIC FROM BOT)
        is_esports_specific = False
        for keyword in ESPORTS_SPECIFIC_KEYWORDS:
            if keyword == "lol":
                import re
                if re.search(r'\blol\b', title) or re.search(r'\blol\b', slug_lower) or "league of legends" in title:
                    is_esports_specific = True
                    break
            else:
                if keyword in title or keyword in slug_lower:
                    is_esports_specific = True
                    break
        
        is_esports_general = any(
            keyword in title or keyword in slug_lower
            for keyword in ESPORTS_KEYWORDS
        )
        
        is_esports = is_esports_specific or is_esports_general
        
        # Exclude non-esports markets
        is_non_esports = any(
            keyword in title or keyword in slug_lower
            for keyword in NON_ESPORTS_KEYWORDS
        )
        
        if is_esports and not is_non_esports:
            passed_markets.append(market)
        else:
            failed_markets.append(market)
            if not is_esports:
                failure_reasons["Not matching esports keywords"] += 1
            if is_non_esports:
                failure_reasons["Matched non-esports keywords"] += 1
    
    print(f"\nTotal Markets Tested: {len(markets)}")
    print(f"Markets That PASSED Filter: {len(passed_markets)}")
    print(f"Markets That FAILED Filter: {len(failed_markets)}")
    
    print("\n\nFailure Reasons:")
    for reason, count in failure_reasons.items():
        print(f"  - {reason}: {count}")
    
    print("\n\nPassed Markets (First 10):")
    for i, market in enumerate(passed_markets[:10], 1):
        print(f"\n{i}. {market.get('title', 'N/A')}")
        print(f"   Slug: {market.get('market_slug', 'N/A')}")
        print(f"   Volume: ${market.get('volume_total', 0):,.0f}")
    
    if len(failed_markets) > 0:
        print("\n\nFailed Markets (First 10 - Examples):")
        for i, market in enumerate(failed_markets[:10], 1):
            title = market.get('title', 'N/A')
            print(f"\n{i}. {title}")
            # Check why it failed
            title_lower = title.lower()
            slug_lower = market.get('market_slug', '').lower()
            matched_esports = [k for k in ESPORTS_KEYWORDS + ESPORTS_SPECIFIC_KEYWORDS if k in title_lower or k in slug_lower]
            matched_non = [k for k in NON_ESPORTS_KEYWORDS if k in title_lower or k in slug_lower]
            if matched_esports:
                print(f"   Matched esports keywords: {matched_esports}")
            if matched_non:
                print(f"   Matched NON-esports keywords: {matched_non}")
    
    return passed_markets, failed_markets


def main():
    print("="*80)
    print("DIAGNOSTIC: Market Filtering Investigation")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Endpoint: {BASE_URL}/polymarket/markets")
    
    # Fetch sample markets
    print("\n\nFetching markets from Dome API...")
    data = fetch_markets_sample(limit=100, offset=0)
    
    if not data:
        print("FAILED: Could not fetch markets from API")
        return
    
    markets = fetch_all_markets_paginated(max_pages=10)
    
    if not markets:
        print("FAILED: Could not fetch markets from API")
        return
    
    print(f"\n[OK] Fetched {len(markets)} total markets across multiple pages")
    
    if not markets:
        print("No markets returned!")
        return
    
    # Analyze structure
    analyze_market_structure(markets)
    
    # Categorize by keywords
    print("\n" + "="*80)
    print("KEYWORD MATCHING ANALYSIS")
    print("="*80)
    
    keyword_matches, game_type_counts = categorize_markets_by_keyword(markets)
    
    print("\nMarkets Matched by Keyword:")
    for keyword in sorted(keyword_matches.keys()):
        count = len(keyword_matches[keyword])
        print(f"  '{keyword}': {count} markets")
    
    print("\n\nMarkets by Game Type:")
    for game_type, count in sorted(game_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {game_type}: {count} markets")
    
    # Test filtering logic
    passed, failed = test_filtering_logic(markets)
    
    # Final summary
    print("\n" + "="*80)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*80)
    
    cs_count = game_type_counts.get("Counter-Strike", 0)
    total_esports = sum(game_type_counts.values()) - game_type_counts.get("Unknown", 0)
    
    print(f"\nCounter-Strike Markets: {cs_count}")
    print(f"Total Esports Markets Found: {total_esports}")
    print(f"Markets Passing Current Filter: {len(passed)}")
    
    if cs_count > 0 and len(passed) == cs_count:
        print("\n[ISSUE] Only CS markets are passing the filter!")
        print("   This suggests:")
        print("   1. Other esports markets may not match current keywords")
        print("   2. Market titles may use different terminology")
        print("   3. Filter may be too restrictive")
    
    print("\n\nRecommendations:")
    if len(passed) < len(keyword_matches):
        print("  - Review keyword matching - some keywords match but filter rejects")
    if game_type_counts.get("Unknown", 0) > 0:
        print("  - Many markets categorized as 'Unknown' - may need better game detection")
    if len(failed) > len(passed):
        print("  - More markets failing than passing - consider relaxing filters")


if __name__ == "__main__":
    main()

