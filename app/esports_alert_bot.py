import os
import requests
import schedule
import time
import logging
import re
from datetime import datetime, timezone
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import asyncio

API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "5"))
VALUE_THRESHOLD = float(os.getenv("VALUE_THRESHOLD", "0.04"))  # 4% minimum true probability for value bets
CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "10"))  # Cache markets for 10 minutes
VOLUME_THRESHOLD = float(os.getenv("VOLUME_THRESHOLD", "100"))  # Minimum volume threshold (lowered to catch more markets)
MAX_MARKET_AGE_DAYS = int(os.getenv("MAX_MARKET_AGE_DAYS", "7"))  # Skip markets older than this
BASE_URL = "https://api.domeapi.io/v1"

# Caching for markets and prices
_markets_cache = {"data": None, "timestamp": None}
_price_cache = {}  # {token_id: {"price": float, "timestamp": float}}
_404_cache = set()  # Cache token_ids that returned 404 to avoid repeated failed fetches

def get_headers():
    """Get authorization headers with current API key."""
    return {"Authorization": f"Bearer {os.getenv('DOME_API_KEY', API_KEY)}"}

HEADERS = get_headers()  # Default headers, but will be regenerated in functions
ESPORTS_KEYWORDS = [
    "esports",
    "dota", "dota2", "dota 2",
    "valorant",
    "league of legends",
    "counter-strike", "counter strike",
    "cs2", "csgo", "cs:go", "cs go",
    "overwatch",
    "rocket league",
    "smash bros",
    "ti",  # The International (Dota)
    "vct",  # Valorant Champions Tour
    "worlds",  # LoL Worlds
    "international",
    "champions", "championship",
    "major",
    "lck",  # LoL Champions Korea
    "lec",  # LoL European Championship
    "lpl",  # LoL Pro League
    "cdl",  # Call of Duty League
    "owc",  # Overwatch Contenders
    "blast",  # BLAST tournaments
    "iem",  # Intel Extreme Masters
    "pgl",  # PGL tournaments
    "msi",  # LoL Mid-Season Invitational
    "majors",  # CS majors
]

# Esports-specific terms that need word boundary matching
ESPORTS_SPECIFIC_KEYWORDS = [
    "lol",  # League of Legends - using word boundary matching
    # LoL Teams
    "gen.g", "gen g", "kt rolster", "kt", "t1", "top esports",
    "fnatic", "g2", "cloud9", "c9", "team liquid", "tl", "100 thieves",
    "tsm", "clg", "nautilus", "nrg",
    # CS Teams
    "mouz", "mousesports", "team spirit", "team falcons", "faze", "navi", "vitality",
    "gambit", "astralis", "heroic", "nip", "complexity", "eg", "evil geniuses",
    # Dota Teams
    "team secret", "og", "liquid", "eg", "psg.lgd", "spirit",
]

# Keywords that indicate NON-esports (to filter out)
NON_ESPORTS_KEYWORDS = [
    # Sports
    "nba", "nfl", "nhl", "mlb", "ufc", "boxing", "mma",
    "atp", "wta", "tennis", "f1", "formula", "racing",
    "golf", "soccer", "football", "basketball", "baseball",
    "hockey", "cricket", "rugby", "marathon", "breeders cup",
    "college football", "cfb", "ncaa", "horse racing", "kentucky derby",
    "preakness", "belmont", "nascar", "indycar", "motorsport",
    # Politics
    "trump", "biden", "political", "election", "president", "congress",
    "house of representatives", "representatives", "senate",
    "approval rating", "will trump", "will biden",
    # Finance/Crypto
    "earnings", "stock", "bitcoin", "ethereum", "crypto", "btc", "eth",
    "solana", "xrp", "up or down", "up/down",
    # Other
    "weather", "temperature", "hurricane", "tornado",
]
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
# Metrics tracking
_metrics = {
    "api_calls": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "api_errors": 0,
    "markets_fetched": 0,
    "alerts_generated": 0,
    "start_time": None,
}

last_alerted_slugs = set()  # Track already alerted markets to prevent duplicates

# Option to reset tracking (useful for testing or when you want to re-alert)
# Uncomment the line below to reset and allow re-alerting on markets
# last_alerted_slugs.clear()


def fetch_with_retry(url, params=None, retries=3, backoff_factor=0.5):
    """Fetches data from a URL with retry logic and improved error handling."""
    headers = get_headers()  # Use current API key
    _metrics["api_calls"] += 1
    
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            # Handle different HTTP status codes appropriately
            if response.status_code == 404:
                # 404 is expected for closed/invalid markets - log as INFO for price fetches
                logging.info(f"Market not found (404): {url}")
                return (None, 404)  # Return tuple with status code for 404 handling
            elif response.status_code == 429:
                # Rate limited - use exponential backoff
                _metrics["api_errors"] += 1
                wait_time = backoff_factor * (2 ** i) + 1  # Extra second for rate limits
                logging.warning(f"Rate limited (429) for {url}, waiting {wait_time}s before retry {i + 1}/{retries}")
                if i < retries - 1:
                    time.sleep(wait_time)
                continue
            elif response.status_code >= 500:
                # Server errors - log as warning, retry
                _metrics["api_errors"] += 1
                logging.warning(f"Server error ({response.status_code}) for {url}, retrying...")
                if i < retries - 1:
                    time.sleep(backoff_factor * 2**i)
                continue
            
            response.raise_for_status()
            return (response.json(), response.status_code)
            
        except requests.exceptions.Timeout as e:
            _metrics["api_errors"] += 1
            logging.warning(f"Timeout for {url} (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * 2**i)
        except requests.exceptions.RequestException as e:
            _metrics["api_errors"] += 1
            # Only log if not a 404 (which is handled above)
            if not hasattr(e, 'response') or (hasattr(e, 'response') and e.response is not None and e.response.status_code != 404):
                logging.warning(f"Request failed for {url} (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * 2**i)
    
    return (None, None)  # Return tuple for consistency (None data, unknown status)


def fetch_all_esports_markets():
    """Fetches all active esports markets from Dome API with caching."""
    global _markets_cache
    
    # Check cache first
    if _markets_cache["data"] is not None and _markets_cache["timestamp"] is not None:
        cache_age = time.time() - _markets_cache["timestamp"]
        if cache_age < (CACHE_TTL_MINUTES * 60):
            _metrics["cache_hits"] += 1
            logging.info(f"Using cached markets data (age: {cache_age:.1f}s)")
            return _markets_cache["data"]
    
    _metrics["cache_misses"] += 1
    all_markets = []
    seen_slugs = set()
    offset = 0
    limit = 100  # Max allowed by API
    start_time = time.time()
    
    while True:
        url = f"{BASE_URL}/polymarket/markets"
        # Don't filter by status in API - we'll filter ourselves
        # API status field is unreliable (shows "open" but prices return 404)
        params = {"limit": limit, "offset": offset}
        data, status_code = fetch_with_retry(url, params=params)
        
        if not data or "markets" not in data:
            logging.error(f"Failed to fetch markets at offset {offset}.")
            break
        
        markets = data.get("markets", [])
        if not markets:
            break
        
        logging.info(f"Fetched {len(markets)} markets at offset {offset}")
        
        # Filter for esports markets
        for market in markets:
            slug = market.get("market_slug", "")
            title = market.get("title", "").lower()
            slug_lower = slug.lower()
            
            # Skip if already seen
            if slug in seen_slugs:
                continue
            
            # Check tags for non-esports indicators (new filtering)
            tags = market.get("tags", [])
            tags_lower = [tag.lower() for tag in tags if isinstance(tag, str)]
            tags_str = " ".join(tags_lower)
            
            # Exclude markets with non-esports tags
            has_non_esports_tags = any(
                keyword in tags_str
                for keyword in ["crypto", "bitcoin", "ethereum", "recurring", "up or down", "weather", "political", "breeders cup", "kentucky derby"]
            )
            
            # Check if it matches esports keywords
            # First check slug patterns (more reliable and inclusive)
            slug_is_esports = False
            # Expanded list of esports slug prefixes
            slug_prefixes = (
                "cs2-", "csgo-", "cs-", "counter-strike-",
                "dota2-", "dota-",
                "lol-", "league-",
                "valorant-", "val-",
                "ow-", "overwatch-",
                "rl-", "rocket-league-",
                "smash-", "smash-bros-",
                "cod-", "call-of-duty-", "cdl-",
                "apex-", "apex-legends-",
                "fortnite-",
                "pubg-",
                "rainbow-", "r6-", "r6s-",
                "fifa-", "fc-",
                "f1-", "formula-1-",
            )
            if slug_lower.startswith(slug_prefixes):
                slug_is_esports = True
            
            # Check for specific esports terms with word boundaries
            is_esports_specific = False
            for keyword in ESPORTS_SPECIFIC_KEYWORDS:
                # Use word boundaries for "lol" to avoid matching "low"
                if keyword == "lol":
                    # Check for "lol" as whole word or as part of "league of legends"
                    import re
                    if re.search(r'\blol\b', title) or re.search(r'\blol\b', slug_lower) or "league of legends" in title:
                        is_esports_specific = True
                        break
                elif keyword == "tes":
                    # "tes" could be "Top Esports" (LoL team) - check for context
                    # Only match if it's in LoL context (slug starts with "lol-" or title has "league")
                    if ("lol" in slug_lower or "lol" in title or "league" in title) and ("tes" in title or "tes" in slug_lower):
                        is_esports_specific = True
                        break
                else:
                    if keyword in title or keyword in slug_lower:
                        is_esports_specific = True
                        break
            
            # Then check general esports keywords
            is_esports_general = any(
                keyword in title or keyword in slug_lower
                for keyword in ESPORTS_KEYWORDS
            )
            
            # Check tags for esports indicators
            has_esports_tags = any(
                keyword in tags_str
                for keyword in ["esports", "counter-strike", "cs2", "dota", "lol", "valorant", "league of legends"]
            )
            
            is_esports = slug_is_esports or is_esports_specific or is_esports_general or has_esports_tags
            
            # Exclude non-esports markets (check title, slug, and tags)
            is_non_esports = any(
                keyword in title or keyword in slug_lower or keyword in tags_str
                for keyword in NON_ESPORTS_KEYWORDS
            ) or has_non_esports_tags
            
            if is_esports and not is_non_esports:
                all_markets.append(market)
                seen_slugs.add(slug)
        
        # Check pagination
        pagination = data.get("pagination", {})
        if not pagination.get("has_more", False):
            break
        
        offset += limit
        
        # Safety limit to prevent infinite loops
        if offset > 1000:  # Max 1000 markets (10 pages)
            logging.warning("Reached safety limit of 1000 markets")
            break
        
        # API requires 1 query per second - wait 1.1 seconds to be safe
        time.sleep(1.1)
    
    # Update cache
    _markets_cache = {"data": all_markets, "timestamp": time.time()}
    
    # Calculate metrics
    fetch_time = time.time() - start_time
    _metrics["markets_fetched"] = len(all_markets)
    
    logging.info(
        f"Fetched {len(all_markets)} esports markets in {fetch_time:.2f}s. "
        f"Total markets searched: {offset}"
    )
    return all_markets


def fetch_price(token_id, platform="polymarket", market_slug=None, game_type=None):
    """Fetches the price for a given token ID with caching."""
    if not token_id:
        return None
    
    # Check 404 cache first - skip markets that previously returned 404
    if token_id in _404_cache:
        logging.debug(f"Skipping token_id={token_id[:20]}... - previously returned 404")
        return None
    
    # Check price cache first
    if token_id in _price_cache:
        cache_entry = _price_cache[token_id]
        cache_age = time.time() - cache_entry["timestamp"]
        if cache_age < 60:  # Cache prices for 1 minute
            _metrics["cache_hits"] += 1
            return cache_entry["price"]
    
    _metrics["cache_misses"] += 1
    url = f"{BASE_URL}/{platform}/market-price/{token_id}"
    
    # Log price fetch attempt with context
    context_info = []
    if game_type:
        context_info.append(f"game={game_type}")
    if market_slug:
        context_info.append(f"slug={market_slug[:50]}")
    context_str = f" ({', '.join(context_info)})" if context_info else ""
    logging.debug(f"Fetching price for token_id={token_id[:20]}...{context_str}")
    
    data, status_code = fetch_with_retry(url)
    
    if data is None:
        # If we got a 404, cache it to avoid repeated failed fetches
        if status_code == 404:
            _404_cache.add(token_id)
            logging.debug(f"Cached 404 for token_id={token_id[:20]}...{context_str}")
        
        # Log failure with context - fetch_with_retry should have logged the specific error
        # This warning provides context about which market failed
        logging.warning(f"Price fetch failed for token_id={token_id[:20]}...{context_str} - Check logs above for specific error (404, 429, etc.)")
        # Don't cache None immediately - let fetch_with_retry handle retries
        # Only cache if we're confident it's a 404 (closed market)
        return None
    
    price = data.get("price") if data else None
    # Ensure price is a valid float
    if price is not None:
        try:
            price = float(price)
            # Clamp price to valid range [0.0, 1.0]
            price = max(0.0, min(1.0, price))
            # Update cache
            _price_cache[token_id] = {"price": price, "timestamp": time.time()}
        except (ValueError, TypeError):
            return None
    
    # API requires 1 query per second - wait 1.1 seconds to be safe
    time.sleep(1.1)
    
    return price


def calculate_roi(market_price, value_threshold=None):
    """
    Calculate potential ROI for a value bet.
    
    Args:
        market_price: The current market price (e.g., 0.01 for 1%)
        value_threshold: Assumed true probability threshold (default: VALUE_THRESHOLD)
    
    Returns:
        ROI percentage as float (e.g., 300.0 for 300% ROI)
    """
    if value_threshold is None:
        value_threshold = VALUE_THRESHOLD
    
    if market_price <= 0 or market_price >= 1:
        return None
    
    # ROI = ((True Probability / Market Price) - 1) * 100%
    roi = ((value_threshold / market_price) - 1) * 100
    
    return round(roi, 1)


def format_event_info(market):
    """Extract and format event information from market data."""
    title = market.get("title", "")
    slug = market.get("market_slug", "")
    side_a = market.get("side_a", {})
    side_b = market.get("side_b", {})
    
    # Parse title to extract match/game info
    # Common patterns: "Team A vs Team B (BO3)", "Counter-Strike: Team A vs Team B"
    event_info = {
        "full_title": title,
        "market_slug": slug,
        "side_a_label": side_a.get("label", "YES"),
        "side_b_label": side_b.get("label", "NO"),
        "game_type": None,
        "teams": None,
        "market_type": None,
        "market_value": None,
    }
    
    # Game patterns for matching
    game_patterns = {
        "Dota 2": r"dota\s*2|dota2",
        "Counter-Strike": r"counter[\s-]?strike|cs2|csgo|cs\s*2",
        "Valorant": r"valorant",
        "League of Legends": r"league\s+of\s+legends|lol",
        "Overwatch": r"overwatch",
    }
    
    # Try to extract teams (common pattern: "Team A vs Team B")
    vs_match = re.search(r"([A-Za-z0-9\s&]+)\s+vs\.?\s+([A-Za-z0-9\s&]+)", title, re.IGNORECASE)
    if vs_match:
        event_info["teams"] = {
            "team_a": vs_match.group(1).strip(),
            "team_b": vs_match.group(2).strip(),
        }
    
    # If title parsing failed, try to extract from slug FIRST (before game type check)
    # Slug format: "lol-t1-tes-2025-11-02-total-games-3pt5" or "dota2-team-falcons-team-liquid-..."
    if not event_info["teams"] and slug:
        slug_lower = slug.lower()
        parts = slug.split("-")
        
        # Pattern: "game-team1-team2-date-market"
        # For "lol-t1-tes-2025-11-02-total-games-3pt5"
        # Parts[0] = "lol", Parts[1] = "t1", Parts[2] = "tes"
        if len(parts) >= 3:
            # Check if parts[1] and parts[2] look like team names
            team1 = parts[1].strip()
            team2 = parts[2].strip()
            
            # Validate - must be alphabetic or alphanumeric, reasonable length
            # Allow numbers in team names (like "100" in "100 thieves")
            if (team1.isalnum() and team2.isalnum() and 
                len(team1) <= 15 and len(team2) <= 15 and
                not team1.isdigit() and not team2.isdigit()):
                event_info["teams"] = {
                    "team_a": team1.upper(),
                    "team_b": team2.upper(),
                }
    
    # Try to extract game type from title FIRST
    title_lower = title.lower()
    for game, pattern in game_patterns.items():
        if re.search(pattern, title_lower, re.IGNORECASE):
            event_info["game_type"] = game
            break
    
    # If still no game type, try from slug
    if not event_info["game_type"] and slug:
        slug_lower = slug.lower()
        if slug_lower.startswith("lol-"):
            event_info["game_type"] = "League of Legends"
        elif slug_lower.startswith("dota2-") or slug_lower.startswith("dota-"):
            event_info["game_type"] = "Dota 2"
        elif slug_lower.startswith("cs2-"):
            event_info["game_type"] = "Counter-Strike"
        elif slug_lower.startswith("valorant-"):
            event_info["game_type"] = "Valorant"
    
    # Extract market type and value
    # Patterns: "O/U 3.5", "Total: 25.5", "Spread: -5.5", etc.
    if re.search(r"o/u|over/under|total", title_lower):
        event_info["market_type"] = "Over/Under"
        num_match = re.search(r"(\d+\.?\d*)", title)
        if num_match:
            event_info["market_value"] = num_match.group(1)
    elif re.search(r"spread", title_lower):
        event_info["market_type"] = "Spread"
        num_match = re.search(r"([+-]?\d+\.?\d*)", title)
        if num_match:
            event_info["market_value"] = num_match.group(1)
    elif "winner" in title_lower or "win" in title_lower:
        event_info["market_type"] = "Moneyline"
    
    return event_info


def analyze_and_prepare_alerts():
    """Analyzes markets for opportunities and prepares alert messages."""
    markets = fetch_all_esports_markets()
    alerts = []
    
    for market in markets:
        slug = market.get("market_slug")  # Dome API uses 'market_slug'
        if not slug or slug in last_alerted_slugs:
            continue
        
        # Dome API has side_a and side_b objects with id fields
        side_a = market.get("side_a", {})
        side_b = market.get("side_b", {})
        yes_token_id = side_a.get("id")
        no_token_id = side_b.get("id")
        
        if not yes_token_id or not no_token_id:
            continue
        
        # Filter by market status - skip closed/resolved markets
        market_status = market.get("status", "").upper()
        if market_status in ["CLOSED", "RESOLVED", "CANCELLED"]:
            logging.debug(f"Skipping {slug}: status={market_status}")
            continue
        
        # Check event timing - skip markets more than 2 days before event
        # Also skip markets that have already ended or are too old
        end_time_str = market.get("end_time")
        if end_time_str:
            try:
                # Handle both string ISO format and Unix timestamp (int)
                if isinstance(end_time_str, str):
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                elif isinstance(end_time_str, (int, float)):
                    # Unix timestamp - convert to datetime
                    end_time = datetime.fromtimestamp(end_time_str, tz=timezone.utc)
                else:
                    end_time = None
                
                if end_time:
                    current_time = datetime.now(end_time.tzinfo)
                    
                    # Calculate time difference
                    time_diff = end_time - current_time
                    days_until_event = time_diff.days
                    
                    # Skip markets where event is more than 2 days in the future
                    if days_until_event > 2:
                        logging.debug(f"Skipping {slug}: event is {days_until_event} days away (more than 2 days)")
                        continue
                    
                    # Skip markets that have already ended
                    if current_time > end_time:
                        logging.debug(f"Skipping {slug}: market already ended")
                        continue
                        
                    # Skip markets that ended more than MAX_MARKET_AGE_DAYS ago
                    if days_until_event < -MAX_MARKET_AGE_DAYS:
                        logging.debug(f"Skipping {slug}: market ended {abs(days_until_event)} days ago")
                        continue
            except (ValueError, TypeError, OSError) as e:
                logging.debug(f"Could not parse end_time for {slug}: {e}")
        
        # Parse event info early to get game type for logging
        event_info = format_event_info(market)
        game_type = event_info.get("game_type", "")
        
        # Fetch price with context for better error logging
        poly_price = fetch_price(yes_token_id, "polymarket", market_slug=slug, game_type=game_type)
        if poly_price is None:
            # If price fetch failed (404), skip this market - it's likely closed/resolved
            # This happens even when API shows status="open"
            logging.debug(f"Skipping {slug}: price fetch failed (market likely closed)")
            continue
        
        # Use volume_total, but fallback to volume_1_week if volume_total is 0
        volume_total = market.get("volume_total", 0)
        volume_1_week = market.get("volume_1_week", 0)
        volume = volume_total if volume_total > 0 else volume_1_week
        
        # Log market details for debugging - use INFO level to see what's happening
        price_str = f"{poly_price:.4f}" if poly_price else "N/A"
        logging.info(f"Checking {slug} ({game_type}): volume=${volume:,.0f} (total=${volume_total:,.0f}, 1week=${volume_1_week:,.0f}), status={market_status}, price={price_str}")
        
        # Check volume threshold first, then price threshold
        if volume <= VOLUME_THRESHOLD:
            logging.debug(f"Skipping {slug}: volume ${volume:,.0f} below threshold ${VOLUME_THRESHOLD}")
            continue
        
        # Perplexity logic: Skip extreme underdogs (< 5%), allow 5-95% range
        if poly_price < 0.05 or poly_price > 0.95:
            logging.debug(f"Skipping {slug}: price {poly_price:.4f} outside range (need 5-95%, skipping extreme odds)")
            continue
        
        # Market qualifies! Generate alert
        # Determine which side to bet on based on price (favor the undervalued side)
        if poly_price < 0.50:  # Price favors "NO" side (< 50%), bet YES
            side = "YES"
            side_label = side_a.get("label", "YES")
            price_for_side = max(0.01, round(poly_price, 4))  # Ensure minimum 0.01, round to 4 decimals
        else:  # Price favors "YES" side (>= 50%), bet NO
            side = "NO"
            side_label = side_b.get("label", "NO")
            price_for_side = max(0.01, round(1.0 - poly_price, 4))  # Ensure minimum 0.01, round to 4 decimals
        
        # Calculate percentage odds
        percentage = round(price_for_side * 100, 2)
        
        # Calculate ROI
        roi = calculate_roi(price_for_side)
        multiplier = None
        if roi is not None and roi > 0:
            # Calculate multiplier: 1 + (ROI/100)
            multiplier = round(1 + (roi / 100), 2)
        
        # IMPORTANT: Verify slug matches the market data
        # Use slug to determine game type if title parsing failed
        slug_lower = slug.lower()
        if not event_info["game_type"]:
            # Try to determine game from slug
            if slug_lower.startswith("lol-"):
                event_info["game_type"] = "League of Legends"
            elif slug_lower.startswith("dota2-") or slug_lower.startswith("dota-"):
                event_info["game_type"] = "Dota 2"
            elif slug_lower.startswith("cs2-"):
                event_info["game_type"] = "Counter-Strike"
            elif slug_lower.startswith("valorant-"):
                event_info["game_type"] = "Valorant"
        
        # Update game_type variable for consistency
        game_type = event_info.get("game_type", "")
        
        # Build enhanced alert message (using HTML formatting for green color)
        alert_parts = []
        alert_parts.append("🎮 <b>ESPORTS VALUE BET ALERT</b>\n")
        
        # Match/Game information - use slug info if title parsing failed
        if event_info["teams"]:
            teams_str = f"{event_info['teams']['team_a']} vs {event_info['teams']['team_b']}"
            if event_info["game_type"]:
                alert_parts.append(f"📅 <b>Match</b>: {event_info['game_type']} - {teams_str}")
            else:
                alert_parts.append(f"📅 <b>Match</b>: {teams_str}")
        elif event_info["game_type"]:
            alert_parts.append(f"📅 <b>Game</b>: {event_info['game_type']}")
        
        # Market information - use full title or parsed description
        market_desc = event_info["full_title"]
        if event_info["market_type"] and event_info["market_value"]:
            market_desc = f"{event_info['market_type']} {event_info['market_value']}"
        alert_parts.append(f"🎯 <b>Market</b>: {market_desc}")
        
        # Direct link to Polymarket - try multiple URL formats
        # Since both /event/{slug} and /market/{condition_id} are failing,
        # we'll use search URL as primary (more reliable) and condition_id as secondary
        clean_slug = str(slug).strip()
        
        # Get condition_id from market object (Polymarket API field)
        condition_id = (
            market.get("condition_id") or 
            market.get("conditionId") or 
            market.get("polymarket_condition_id")
        )
        
        # Also check for direct URL fields that might be in the API response
        polymarket_url_direct = (
            market.get("polymarket_url") or 
            market.get("url") or 
            market.get("market_url")
        )
        
        # Get market title for search
        market_title = market.get("title", clean_slug)
        
        # Construct URL - try condition_id format first (direct link), then search as fallback
        if polymarket_url_direct:
            # Use direct URL if available
            polymarket_url = polymarket_url_direct
            logging.debug(f"Market URL using direct URL field: {polymarket_url}")
        elif condition_id:
            # Try condition_id format first - this is the most specific identifier
            # Keep the 0x prefix as Polymarket might expect it
            polymarket_url = f"https://polymarket.com/market/{condition_id}"
            logging.debug(f"Market URL using condition_id: {polymarket_url} (slug: {clean_slug})")
        else:
            # Fallback to search URL if condition_id not available
            import urllib.parse
            search_query = urllib.parse.quote(market_title)
            polymarket_url = f"https://polymarket.com/search?q={search_query}"
            logging.warning(f"Market URL using search format (condition_id not found): {polymarket_url}")
        
        alert_parts.append(f"🔗 <b>Trade</b>: <a href='{polymarket_url}'>Click here to trade</a>")
        
        # Bet recommendation
        alert_parts.append(f"💰 <b>Bet</b>: <code>{side_label}</code> at <b>${price_for_side:.4f}</b> ({percentage}% odds)")
        
        # ROI calculation - show multiplier prominently (make it stand out)
        if roi is not None and roi > 0 and multiplier:
            # Use bold formatting and emojis to make it stand out (Telegram HTML doesn't support colors)
            alert_parts.append(f"✅ ✅ <b>Potential Return: {multiplier}x</b> ✅ ✅\n💰 (Bet $1 to win ${multiplier:.2f}) 🚀")
        
        # Volume
        alert_parts.append(f"📊 <b>Volume</b>: ${volume:,.0f}")
        
        # Analysis/insight - create varied, engaging messages based on price, volume, and market type
        import random
        import hashlib
        
        # Use slug-based seed to ensure variety but consistency per market
        # This ensures different markets get different analysis, but same market gets same analysis
        slug_hash = int(hashlib.md5(slug.encode()).hexdigest()[:8], 16)
        random.seed(slug_hash)
        
        # Different analysis templates based on price range and volume
        if price_for_side < 0.02:  # Very low odds (< 2%)
            if volume > 50000:
                analysis_templates = [
                    f"🔥 EXTREMELY undervalued opportunity! The market is pricing this at only {percentage}% - that's almost laughable given the context. With {multiplier}x returns, this is a potential goldmine if the market is wrong. Massive volume (${volume:,.0f}) suggests real money is moving here, indicating smart money sees value. <i>Why bet on lower odds? When the market undervalues true probability, even low-probability outcomes become profitable. If the true chance is higher than {percentage}%, betting at {multiplier}x odds creates positive expected value.</i>",
                    f"🚨 This is priced at {percentage}% but we're seeing serious value potential. The {multiplier}x multiplier suggests the market might be massively underestimating this outcome. High volume indicates trader interest. <i>Value betting isn't about picking favorites - it's about finding when payouts exceed true probability. Here, {multiplier}x returns mean you profit if the true chance exceeds {round(100/multiplier, 1)}%, which we believe is the case.</i>",
                    f"⚡️ Massive value alert! Only {percentage}% odds but we see {multiplier}x return potential. This could be a huge opportunity - the numbers don't add up to such low probability. <i>The market may be influenced by public bias or incomplete information. When true probability ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), the expected value is positive. Over many bets, this edge compounds into profit.</i>",
                    f"💎 Hidden gem alert! Market shows {percentage}% chance but we're seeing {multiplier}x value. High volume means real traders are paying attention. <i>Lower market odds don't mean bad bets - they mean higher payouts when the market is wrong. If this outcome happens {round(100/multiplier, 1)}%+ of the time (which we estimate), betting at {percentage}% odds is profitable long-term.</i>",
                ]
            else:
                analysis_templates = [
                    f"💎 Hidden gem alert! Market shows {percentage}% chance but we're seeing {multiplier}x value. Low volume means this might be flying under the radar. <i>Why bet on lower odds? When the market undervalues the true probability, even modest odds can be profitable. Value betting isn't about favorites - it's about finding when the market undervalues probability. Here, {multiplier}x returns mean profit if true chance exceeds {round(100/multiplier, 1)}%.</i>",
                    f"🎯 Undervalued opportunity at {percentage}% odds. The {multiplier}x return suggests significant upside if the market is wrong here. <i>Market odds reflect collective belief, not always true probability. When true probability ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), betting becomes profitable. Over time, these edges compound into consistent profits.</i>",
                    f"🔍 Value bet detected! {percentage}% seems too low - {multiplier}x returns indicate the market might be mispricing this. <i>Lower market odds don't mean bad bets - they mean higher payouts when the market is wrong. If this outcome happens {round(100/multiplier, 1)}%+ of the time (which we estimate), betting at {percentage}% odds creates positive expected value long-term.</i>",
                    f"📊 Market mispricing alert! {percentage}% odds don't match the {multiplier}x payout potential. This looks like an opportunity. <i>Value betting works by finding discrepancies between market odds and true probability. When true chance ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), the expected value is positive. This edge compounds over many bets.</i>",
                ]
        elif price_for_side < 0.05:  # Low odds (2-5%)
            if volume > 50000:
                analysis_templates = [
                    f"📊 Solid value play here! Market pricing at {percentage}% seems conservative given the context. {multiplier}x returns make this worth considering. High volume (${volume:,.0f}) suggests real money sees value. <i>Why bet on lower odds? When the market undervalues true probability, even modest odds can be profitable. If the true chance is higher than {percentage}%, betting at {multiplier}x odds creates positive expected value. Over many bets, this edge compounds into profit.</i>",
                    f"💰 Good value opportunity! {percentage}% odds look low compared to realistic probability. {multiplier}x multiplier suggests decent upside. High volume indicates trader interest. <i>The market may be underestimating this outcome - that's where value lies. Value betting isn't about picking favorites - it's about finding when payouts exceed true probability. Here, {multiplier}x returns mean you profit if true chance exceeds {round(100/multiplier, 1)}%.</i>",
                    f"🎲 Interesting spot - market shows {percentage}% but we see {multiplier}x value. High volume indicates trader interest in this market. <i>Market odds reflect collective belief, not always true probability. When true probability ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), betting becomes profitable. Over time, these edges compound into consistent profits.</i>",
                    f"📈 Value alert! {percentage}% probability seems off compared to the {multiplier}x return. High volume confirms this is worth watching. <i>Lower market odds don't mean bad bets - they mean higher payouts when the market is wrong. If this outcome happens {round(100/multiplier, 1)}%+ of the time (which we estimate), betting at {percentage}% odds is profitable long-term.</i>",
                ]
            else:
                analysis_templates = [
                    f"🔎 Value bet at {percentage}% odds. The {multiplier}x return suggests the market might be undervaluing this outcome. <i>Why bet on lower odds? When the market undervalues the true probability, even modest odds can be profitable. Value betting isn't about favorites - it's about finding when the market undervalues probability. Here, {multiplier}x returns mean profit if true chance exceeds {round(100/multiplier, 1)}%.</i>",
                    f"⚖️ Market pricing seems off here - {percentage}% odds don't match the {multiplier}x return potential we're seeing. <i>Market odds reflect collective belief, not always true probability. When true probability ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), betting becomes profitable. Over time, these edges compound into consistent profits.</i>",
                    f"📈 Decent value play! {percentage}% chance priced but {multiplier}x returns indicate possible upside. <i>Value betting isn't about favorites - it's about finding when the market undervalues probability. Lower market odds don't mean bad bets - they mean higher payouts when the market is wrong. If this outcome happens {round(100/multiplier, 1)}%+ of the time, betting at {percentage}% odds creates positive expected value.</i>",
                    f"🎯 Interesting opportunity at {percentage}% odds. {multiplier}x multiplier suggests the market might be wrong. <i>The market may be influenced by public bias or incomplete information. When true probability ({round(100/multiplier, 1)}%+) exceeds market odds ({percentage}%), the expected value is positive. This edge compounds over many bets.</i>",
                ]
        else:  # High confidence (> 5%)
            if volume > 50000:
                analysis_templates = [
                    f"📈 High confidence play - market shows {percentage}% chance, making this a strong favorite. High volume (${volume:,.0f}) confirms trader conviction. <i>Why bet on favorites? When market odds align with or underestimate true probability, favorites can offer value. With {multiplier}x returns, this represents a solid opportunity where the market recognizes the likely outcome, but we see additional edge in the pricing.</i>",
                    f"✅ Strong favorite at {percentage}% odds. The numbers suggest this is a likely outcome worth considering, especially with {multiplier}x returns. High volume indicates market consensus. <i>Value betting includes favorites too - when true probability meets or exceeds market odds, even strong favorites can be profitable. Here, {percentage}% odds with {multiplier}x returns suggest the market is pricing this correctly or slightly undervaluing it.</i>",
                    f"🎯 Market consensus points to {percentage}% probability here. High volume suggests strong support for this side. <i>High probability plays can still offer value when market odds align with true probability. With {multiplier}x returns, this represents a solid opportunity where the market recognizes the likely outcome, creating a safer but still profitable bet.</i>",
                    f"💪 Clear favorite play! {percentage}% odds with {multiplier}x returns and high volume - this looks like the safe bet. <i>Value betting isn't just about underdogs - favorites can offer value too. When market odds ({percentage}%) align with or slightly underestimate true probability, betting becomes profitable. Over many bets, these consistent edges compound.</i>",
                ]
            else:
                analysis_templates = [
                    f"📊 Market shows {percentage}% chance - solid favorite play. {multiplier}x returns make this worth a look. <i>Why bet on favorites? When market odds align with true probability, even strong favorites can be profitable. Value betting includes favorites too - it's about finding when true probability meets or exceeds market odds. Here, {percentage}% odds with {multiplier}x returns suggest solid value.</i>",
                    f"💪 Strong positioning at {percentage}% odds. The numbers suggest this outcome is likely. <i>High probability plays can still offer value when market odds align with true probability. With {multiplier}x returns, this represents a solid opportunity where the market recognizes the likely outcome, creating a safer but still profitable bet.</i>",
                    f"🎲 High probability play - {percentage}% odds with {multiplier}x returns present a reasonable opportunity. <i>Value betting includes favorites too - when true probability meets or exceeds market odds, even strong favorites can be profitable. Over many bets, these consistent edges compound into profit.</i>",
                    f"⭐ Solid favorite at {percentage}% - market consensus favors this outcome with {multiplier}x returns. <i>Value betting isn't just about underdogs - favorites can offer value too. When market odds ({percentage}%) align with or slightly underestimate true probability, betting becomes profitable long-term.</i>",
                ]
        
        insight = f"💡 <b>Analysis</b>: {random.choice(analysis_templates)}"
        alert_parts.append(insight)
        
        alert_msg = "\n".join(alert_parts)
        alerts.append(alert_msg)
        last_alerted_slugs.add(slug)
    
    _metrics["alerts_generated"] = len(alerts)
    return alerts


async def send_telegram_alerts(bot, alerts):
    """Sends alerts to the configured Telegram chat - one alert per message."""
    if not alerts:
        logging.info("No new alerts to send.")
        return
    total_alerts = len(alerts)
    
    logging.info(f"Sending {total_alerts} alert(s) to Telegram (one per message)...")
    
    for i, alert_msg in enumerate(alerts, 1):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=alert_msg, parse_mode=ParseMode.HTML)
            logging.info(f"Successfully sent alert {i}/{total_alerts}.")
            # Small delay between messages to avoid rate limiting
            if i < total_alerts:
                await asyncio.sleep(0.5)
        except TelegramError as e:
            logging.exception(f"Failed to send Telegram message {i}/{total_alerts}: {e}")
        except Exception as e:
            logging.exception(f"An unexpected error occurred sending alert {i}/{total_alerts}: {e}")


async def job():
    """The main job to be run on a schedule."""
    cycle_start = time.time()
    _metrics["start_time"] = cycle_start
    
    # Reset cycle-specific metrics
    cycle_metrics = {
        "api_calls": _metrics["api_calls"],
        "cache_hits": _metrics["cache_hits"],
        "cache_misses": _metrics["cache_misses"],
        "api_errors": _metrics["api_errors"],
    }
    
    logging.info("Starting new alert cycle...")
    alerts = analyze_and_prepare_alerts()
    
    if alerts:
        bot = Bot(token=BOT_TOKEN)
        await send_telegram_alerts(bot, alerts)
    
    # Calculate cycle metrics
    cycle_time = time.time() - cycle_start
    cycle_api_calls = _metrics["api_calls"] - cycle_metrics["api_calls"]
    cycle_cache_hits = _metrics["cache_hits"] - cycle_metrics["cache_hits"]
    cycle_cache_misses = _metrics["cache_misses"] - cycle_metrics["cache_misses"]
    cycle_api_errors = _metrics["api_errors"] - cycle_metrics["api_errors"]
    
    # Log summary
    logging.info(
        f"Alert cycle finished in {cycle_time:.2f}s. "
        f"API calls: {cycle_api_calls} (hits: {cycle_cache_hits}, misses: {cycle_cache_misses}), "
        f"Errors: {cycle_api_errors}, Alerts: {len(alerts)}. "
        f"Next run in {POLL_INTERVAL_MIN} minutes."
    )
    
    # Clean old price cache entries (older than 5 minutes)
    current_time = time.time()
    expired_keys = [
        token_id for token_id, entry in _price_cache.items()
        if current_time - entry["timestamp"] > 300
    ]
    for key in expired_keys:
        del _price_cache[key]


def run_job_sync():
    """Synchronous wrapper to run the async job."""
    asyncio.run(job())


if __name__ == "__main__":
    if "YOUR_DOME_API_KEY" in API_KEY or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
        logging.error(
            "Configuration placeholders detected. Please replace them with your actual credentials."
        )
    else:
        logging.info("Starting Esports Odds Alert Bot...")
        run_job_sync()
        schedule.every(POLL_INTERVAL_MIN).minutes.do(run_job_sync)
        logging.info(f"Scheduled to run every {POLL_INTERVAL_MIN} minutes.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt as e:
            logging.exception(f"Shutting down bot...: {e}")