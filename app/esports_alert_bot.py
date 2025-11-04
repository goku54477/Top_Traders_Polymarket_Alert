import os
import requests
import schedule
import time
import logging
import re
from datetime import datetime, timezone
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, BadRequest
import asyncio

API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# Normalize CHAT_ID - Telegram accepts both int and string, but we'll normalize to string
# For group IDs (negative integers), convert to string but keep the numeric value
def normalize_chat_id(chat_id):
    """Normalize chat ID to ensure consistent format."""
    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        return None
    # Strip whitespace and quotes (handle all quote types)
    chat_id = str(chat_id).strip()
    # Remove any surrounding quotes (single, double, or smart quotes)
    while len(chat_id) >= 2 and (
        (chat_id[0] == '"' and chat_id[-1] == '"') or
        (chat_id[0] == "'" and chat_id[-1] == "'") or
        (chat_id[0] == '`' and chat_id[-1] == '`')
    ):
        chat_id = chat_id[1:-1].strip()
    # Try to convert to int if it's numeric (Telegram group IDs are negative integers)
    try:
        chat_id_int = int(chat_id)
        # Return as string (Telegram API accepts both, but string is more reliable)
        return str(chat_id_int)
    except ValueError:
        # If not numeric, return as-is (for channel usernames like @channelname)
        return chat_id

# Normalize at module load time
CHAT_ID = normalize_chat_id(CHAT_ID)

# Helper function to get chat ID in the format that works best for Telegram
def get_chat_id_for_telegram():
    """Get chat ID in the format that works best with Telegram API.
    Returns both int (if numeric) and string formats for flexibility."""
    if not CHAT_ID:
        return None, None
    try:
        # Try to convert to int for numeric chat IDs
        chat_id_int = int(CHAT_ID)
        return chat_id_int, str(chat_id_int)
    except (ValueError, TypeError):
        # For non-numeric chat IDs (like @channelname), return as string
        return None, str(CHAT_ID)
POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "5"))
VALUE_THRESHOLD = float(os.getenv("VALUE_THRESHOLD", "0.04"))  # 4% minimum true probability for value bets
CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "10"))  # Cache markets for 10 minutes
VOLUME_THRESHOLD = float(os.getenv("VOLUME_THRESHOLD", "100"))  # Minimum volume threshold (lowered to catch more markets)
MAX_MARKET_AGE_DAYS = int(os.getenv("MAX_MARKET_AGE_DAYS", "7"))  # Skip markets older than this
BASE_URL = "https://api.domeapi.io/v1"

# Caching for markets and prices
_markets_cache = {"data": None, "timestamp": None}
_kalshi_markets_cache = {"data": None, "timestamp": None}
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
    "ucl", "uefa", "champions league", "europa league", "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "preakness", "belmont", "nascar", "indycar", "motorsport",
    # Politics - Expanded list
    "trump", "biden", "political", "election", "president", "congress",
    "house of representatives", "representatives", "senate",
    "approval rating", "will trump", "will biden",
    "mayor", "mayoral", "democratic party", "republican party",
    "federal reserve", "fed", "rate cut", "rate hike", "interest rate",
    "government shutdown", "gov shut", "shutdown",
    "cuomo", "mamdani", "zohran", "andrew",  # Political figures
    "victory", "concession", "speech", "say", "will say",  # Political speech patterns
    "anti-semitic", "democracy",  # Political terms
    "governor", "governor race", "race", "campaign",
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
                # Rate limited - use exponential backoff with longer wait times
                _metrics["api_errors"] += 1
                # Increased wait time: base 5 seconds + exponential backoff
                wait_time = 5 + (backoff_factor * (2 ** i))
                logging.warning(f"Rate limited (429) for {url}, waiting {wait_time:.1f}s before retry {i + 1}/{retries}")
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
            
            # Then check general esports keywords (but require stricter matching)
            is_esports_general = any(
                keyword in title.lower() or keyword in slug_lower
                for keyword in ESPORTS_KEYWORDS
            )
            
            # Check tags for esports indicators
            has_esports_tags = any(
                keyword in tags_str.lower()
                for keyword in ["esports", "counter-strike", "cs2", "dota", "lol", "valorant", "league of legends"]
            )
            
            # Require at least one strong esports indicator (slug prefix is strongest)
            # If no slug prefix, require multiple esports indicators for safety
            is_esports = slug_is_esports or (is_esports_specific and is_esports_general) or has_esports_tags
            
            # STRICT FILTERING: Exclude non-esports markets FIRST (priority check)
            # If market has non-esports indicators, reject it immediately
            # Check for non-esports keywords first (priority exclusion)
            # Use word boundaries for better matching to avoid false positives
            is_non_esports = False
            
            # Check for non-esports keywords with word boundaries where appropriate
            for keyword in NON_ESPORTS_KEYWORDS:
                # For short keywords or names, check if they appear as whole words
                if len(keyword) <= 4 or keyword in ["say", "will say", "victory", "concession", "speech"]:
                    # Use word boundary matching for short keywords
                    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                    if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, slug_lower, re.IGNORECASE):
                        is_non_esports = True
                        logging.debug(f"Non-esports keyword detected (word boundary): {keyword} in market: {slug}")
                        break
                else:
                    # For longer keywords, simple substring match is fine
                    if keyword.lower() in title.lower() or keyword.lower() in slug_lower:
                        is_non_esports = True
                        logging.debug(f"Non-esports keyword detected: {keyword} in market: {slug}")
                        break
            
            # Check tags
            if not is_non_esports and has_non_esports_tags:
                is_non_esports = True
                logging.debug(f"Non-esports tags detected in market: {slug}")
            
            # Additional strict checks for political/speech patterns
            # Patterns like "will [name] say" or "during his/her speech" are political
            if not is_non_esports:
                # Check both title and slug (slug may have hyphens instead of spaces)
                text_to_check = f"{title} {slug_lower}"
                political_patterns = [
                    r"will[- ]+\w+[- ]+say",  # "will X say" or "will-x-say"
                    r"will[- ]+say[- ]+\d+",  # "will say 2+" or "will-say-2"
                    r"during[- ]+(his|her)[- ]+(victory|concession|speech)",  # "during his victory speech" or "during-his-victory-speech"
                    r"victory.*speech|concession.*speech",  # victory/concession speech
                    r"victoryconcession",  # "victoryconcession" (combined word)
                    r"will[- ]+\w+[- ]+say[- ]+\d+[- ]+times",  # "will X say 2 times" or "will-x-say-2-times"
                    r"will[- ]+(zohran|mamdani|cuomo|andrew)[- ]+say",  # "will zohran say" or "will-mamdani-say"
                    r"(zohran|mamdani).*(say|speech|victory|concession)",  # "zohran ... say" or "mamdani ... speech"
                ]
                for pattern in political_patterns:
                    if re.search(pattern, text_to_check, re.IGNORECASE):
                        is_non_esports = True
                        logging.debug(f"Political pattern detected: {pattern} in market: {slug}")
                        break
            
            # Only include if it's clearly esports AND has no non-esports indicators
            # Priority: exclude non-esports first, then check esports
            if is_non_esports:
                # Skip this market - it's clearly not esports
                logging.debug(f"Skipping non-esports market: {slug} (title: {market.get('title', '')[:50]})")
                continue
            
            if is_esports:
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
        
        # API requires 1 query per second - wait 1.5 seconds to be safe and avoid rate limiting
        time.sleep(1.5)
    
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


def fetch_kalshi_markets():
    """Fetches all active esports markets from Kalshi via Dome API with caching."""
    # TEMPORARILY DISABLED FOR MAIN BRANCH TESTING - Polymarket only
    return []
    global _kalshi_markets_cache
    
    # Check cache first
    if _kalshi_markets_cache["data"] is not None and _kalshi_markets_cache["timestamp"] is not None:
        cache_age = time.time() - _kalshi_markets_cache["timestamp"]
        if cache_age < (CACHE_TTL_MINUTES * 60):
            _metrics["cache_hits"] += 1
            logging.info(f"Using cached Kalshi markets data (age: {cache_age:.1f}s)")
            return _kalshi_markets_cache["data"]
    
    _metrics["cache_misses"] += 1
    all_markets = []
    seen_tickers = set()
    offset = 0
    limit = 100  # Max allowed by API
    start_time = time.time()
    
    while True:
        url = f"{BASE_URL}/kalshi/markets"
        # Filter for open markets only, and use min_volume to reduce noise
        # Volume is in cents, so $100 = 10000 cents
        min_volume_cents = int(VOLUME_THRESHOLD * 100)
        params = {
            "limit": limit,
            "offset": offset,
            "status": "open",
            "min_volume": min_volume_cents
        }
        data, status_code = fetch_with_retry(url, params=params)
        
        if not data or "markets" not in data:
            logging.error(f"Failed to fetch Kalshi markets at offset {offset}.")
            break
        
        markets = data.get("markets", [])
        if not markets:
            break
        
        logging.info(f"Fetched {len(markets)} Kalshi markets at offset {offset}")
        
        # Filter for esports markets
        for market in markets:
            market_ticker = market.get("market_ticker", "")
            title = market.get("title", "").lower()
            ticker_lower = market_ticker.lower()
            
            # Skip if already seen
            if market_ticker in seen_tickers:
                continue
            
            # Kalshi markets may use different ticker formats
            # Check title and ticker for esports keywords
            # First check ticker patterns (Kalshi uses ticker format like "KXMAYORNYCPARTY-25-D")
            # Esports markets might have patterns in the ticker, but title is more reliable
            
            # Check for specific esports terms with word boundaries
            is_esports_specific = False
            for keyword in ESPORTS_SPECIFIC_KEYWORDS:
                if keyword == "lol":
                    import re
                    if re.search(r'\blol\b', title) or re.search(r'\blol\b', ticker_lower) or "league of legends" in title:
                        is_esports_specific = True
                        break
                elif keyword == "tes":
                    if ("lol" in ticker_lower or "lol" in title or "league" in title) and ("tes" in title or "tes" in ticker_lower):
                        is_esports_specific = True
                        break
                else:
                    if keyword in title or keyword in ticker_lower:
                        is_esports_specific = True
                        break
            
            # Check general esports keywords
            # For Kalshi, be more strict - require specific esports game names, not generic terms
            # Generic terms like "champions", "international" can appear in non-esports contexts
            strict_esports_keywords = [
                "esports", "dota", "dota2", "dota 2",
                "valorant", "league of legends",
                "counter-strike", "counter strike",
                "cs2", "csgo", "cs:go", "cs go",
                "overwatch", "rocket league", "smash bros"
            ]
            is_esports_general = any(
                keyword in title or keyword in ticker_lower
                for keyword in strict_esports_keywords
            )
            
            # Check ticker patterns (Kalshi might use different formats)
            # Look for common esports indicators in ticker
            ticker_is_esports = False
            esports_indicators = ["cs", "dota", "lol", "league", "val", "valorant", "cs2", "csgo"]
            if any(indicator in ticker_lower for indicator in esports_indicators):
                ticker_is_esports = True
            
            is_esports = ticker_is_esports or is_esports_specific or is_esports_general
            
            # Exclude non-esports markets
            is_non_esports = any(
                keyword in title or keyword in ticker_lower
                for keyword in NON_ESPORTS_KEYWORDS
            )
            
            if is_esports and not is_non_esports:
                # Add platform identifier to market
                market["platform"] = "kalshi"
                all_markets.append(market)
                seen_tickers.add(market_ticker)
        
        # Check pagination
        pagination = data.get("pagination", {})
        if not pagination.get("has_more", False):
            break
        
        offset += limit
        
        # Safety limit to prevent infinite loops
        if offset > 1000:  # Max 1000 markets (10 pages)
            logging.warning("Reached safety limit of 1000 Kalshi markets")
            break
        
        # API requires 1 query per second - wait 1.5 seconds to be safe and avoid rate limiting
        time.sleep(1.5)
    
    # Update cache
    _kalshi_markets_cache = {"data": all_markets, "timestamp": time.time()}
    
    # Calculate metrics
    fetch_time = time.time() - start_time
    _metrics["markets_fetched"] = len(all_markets)  # Update total (includes Kalshi now)
    
    logging.info(
        f"Fetched {len(all_markets)} Kalshi esports markets in {fetch_time:.2f}s. "
        f"Total markets searched: {offset}"
    )
    return all_markets


def build_kalshi_url(market):
    """Builds a Kalshi URL for a given market.
    
    Working format based on user testing:
    https://kalshi.com/markets/{event_slug}/{title_slug}/{market_ticker}
    
    Example: https://kalshi.com/markets/govpartynj/new-jersey-governor-race/govpartynj-25
    
    Pattern analysis:
    - Event slug: Base identifier without trailing numbers (e.g., "govpartynj" not "govpartynj-25")
    - Title slug: Slugified title
    - Market ticker: Lowercase market ticker (e.g., "govpartynj-25")
    """
    import re
    
    market_ticker = market.get("market_ticker", "")
    event_ticker = market.get("event_ticker", "")
    title = market.get("title", "")
    
    # Check if API provides a direct URL field
    direct_url = market.get("url") or market.get("kalshi_url") or market.get("market_url")
    if direct_url:
        return direct_url
    
    if not market_ticker or not event_ticker:
        return "https://kalshi.com/markets"
    
    # Extract base event slug (remove trailing numbers like "-25")
    # Example: "KXMAYORNYCPARTY-25" -> "kxmayornycparty"
    # Pattern: Remove trailing "-{number}" from event ticker
    event_slug = event_ticker.lower()
    event_slug = re.sub(r'-\d+$', '', event_slug)  # Remove trailing "-25", "-2025", etc.
    
    # Create slug from title (lowercase, replace spaces with hyphens, remove special chars)
    # Example: "Will a representative..." -> "will-a-representative-of-the-democratic-party-win-the-nyc-mayor-race-in-2025"
    if title:
        # Convert to lowercase
        title_slug = title.lower()
        # Remove question marks, periods, commas
        title_slug = re.sub(r'[?.,!;:()]', '', title_slug)
        # Replace spaces and multiple spaces with single hyphen
        title_slug = re.sub(r'\s+', '-', title_slug)
        # Remove any remaining special characters except hyphens
        title_slug = re.sub(r'[^a-z0-9-]', '', title_slug)
        # Remove leading/trailing hyphens
        title_slug = title_slug.strip('-')
        # Limit length to reasonable size
        if len(title_slug) > 100:
            title_slug = title_slug[:100].rstrip('-')
    else:
        # Fallback: use event slug as title slug if no title
        title_slug = event_slug
    
    # Market ticker should be lowercase
    # Example: "KXMAYORNYCPARTY-25-D" -> "kxmayornycparty-25-d"
    market_ticker_slug = market_ticker.lower()
    
    # Build URL: /markets/{event_slug}/{title_slug}/{market_ticker}
    return f"https://kalshi.com/markets/{event_slug}/{title_slug}/{market_ticker_slug}"


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
    
    # API requires 1 query per second - wait 1.5 seconds to be safe and avoid rate limiting
    time.sleep(1.5)
    
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
    # Fetch markets from both platforms
    polymarket_markets = fetch_all_esports_markets()
    kalshi_markets = fetch_kalshi_markets()
    
    # Combine markets and mark platform
    all_markets = []
    for market in polymarket_markets:
        market["platform"] = "polymarket"
        all_markets.append(market)
    for market in kalshi_markets:
        market["platform"] = "kalshi"
        all_markets.append(market)
    
    alerts = []
    
    for market in all_markets:
        platform = market.get("platform", "polymarket")
        
        # Handle different platforms
        if platform == "kalshi":
            # Kalshi market structure
            market_ticker = market.get("market_ticker", "")
            if not market_ticker or market_ticker in last_alerted_slugs:
                continue
            
            # Kalshi already has price in the response (last_price in cents, 0-100)
            # Convert from cents to decimal (e.g., 89 cents = 0.89)
            last_price_cents = market.get("last_price")
            if last_price_cents is None:
                continue
            poly_price = last_price_cents / 100.0  # Convert cents to decimal
            
            # For Kalshi, we use YES price (last_price) and NO price (100 - last_price)
            yes_price = poly_price
            no_price = 1.0 - poly_price
            
            # Kalshi doesn't have separate token IDs, price is already in market data
            yes_token_id = None  # Not needed for Kalshi
            no_token_id = None  # Not needed for Kalshi
            
            # Use market_ticker as unique identifier
            slug = market_ticker
        else:
            # Polymarket market structure
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
            
            # Fetch price for Polymarket
            poly_price = fetch_price(yes_token_id, platform="polymarket", market_slug=slug)
            if poly_price is None:
                continue
            
            # Polymarket price is for YES side, NO is 1 - YES
            yes_price = poly_price
            no_price = 1.0 - poly_price
        
        # Filter by market status - skip closed/resolved markets
        market_status = market.get("status", "")
        # Handle both Polymarket ("OPEN", "CLOSED") and Kalshi ("open", "closed") formats
        market_status_upper = market_status.upper()
        if market_status_upper in ["CLOSED", "RESOLVED", "CANCELLED"]:
            logging.debug(f"Skipping {slug}: status={market_status}")
            continue
        
        # Check event timing - skip markets more than 2 days before event
        # Also skip markets that have already ended or are too old
        # Kalshi uses end_time, close_time, or both
        end_time_str = market.get("end_time") or market.get("close_time")
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
                    
                    # Skip markets where event is more than 7 days in the future
                    if days_until_event > 7:
                        logging.debug(f"Skipping {slug}: event is {days_until_event} days away (more than 7 days)")
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
        
        # Get volume - handle both platforms
        if platform == "kalshi":
            # Kalshi volume is in cents, convert to dollars
            volume_cents = market.get("volume", 0) or market.get("volume_24h", 0)
            volume = volume_cents / 100.0  # Convert cents to dollars
            logging.info(f"Checking {slug} ({game_type}): volume=${volume:,.0f} (from {volume_cents} cents), status={market_status}, price={poly_price:.4f}")
        else:
            # Polymarket volume is in dollars
            volume_total = market.get("volume_total", 0)
            volume_1_week = market.get("volume_1_week", 0)
            volume = volume_total if volume_total > 0 else volume_1_week
            price_str = f"{poly_price:.4f}" if poly_price else "N/A"
            logging.info(f"Checking {slug} ({game_type}): volume=${volume:,.0f} (total=${volume_total:,.0f}, 1week=${volume_1_week:,.0f}), status={market_status}, price={price_str}")
        
        # STRICT volume threshold check - must be strictly greater than threshold
        if volume < VOLUME_THRESHOLD:
            logging.debug(f"Skipping {slug}: volume ${volume:,.0f} below threshold ${VOLUME_THRESHOLD}")
            continue
        
        # Perplexity logic: Skip extreme underdogs (< 5%), allow 5-95% range
        if poly_price < 0.05 or poly_price > 0.95:
            logging.debug(f"Skipping {slug}: price {poly_price:.4f} outside range (need 5-95%, skipping extreme odds)")
            continue
        
        # Market qualifies! Generate alert
        # Determine which side to bet on based on price (favor the undervalued side)
        if platform == "kalshi":
            # Kalshi uses YES/NO sides directly
            if poly_price < 0.50:  # Price favors "NO" side (< 50%), bet YES
                side = "YES"
                side_label = "YES"
                price_for_side = max(0.01, round(poly_price, 4))
            else:  # Price favors "YES" side (>= 50%), bet NO
                side = "NO"
                side_label = "NO"
                price_for_side = max(0.01, round(1.0 - poly_price, 4))
        else:
            # Polymarket structure
            side_a = market.get("side_a", {})
            side_b = market.get("side_b", {})
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
            
        # IMPORTANT: Verify slug/ticker matches the market data
        # Use slug/ticker to determine game type if title parsing failed
        identifier = slug.lower() if platform == "polymarket" else market.get("market_ticker", "").lower()
        if not event_info["game_type"]:
            # Try to determine game from slug (Polymarket) or ticker (Kalshi)
            if identifier.startswith("lol-") or "lol" in identifier:
                event_info["game_type"] = "League of Legends"
            elif identifier.startswith("dota2-") or identifier.startswith("dota-") or "dota" in identifier:
                event_info["game_type"] = "Dota 2"
            elif identifier.startswith("cs2-") or identifier.startswith("csgo-") or "cs2" in identifier or "csgo" in identifier:
                event_info["game_type"] = "Counter-Strike"
            elif identifier.startswith("valorant-") or "valorant" in identifier:
                event_info["game_type"] = "Valorant"
            
        # Update game_type variable for consistency
        game_type = event_info.get("game_type", "")
        
        # Build enhanced alert message (using HTML formatting for green color)
        alert_parts = []
        platform_emoji = "🔵" if platform == "polymarket" else "🟢"
        platform_name = "Polymarket" if platform == "polymarket" else "Kalshi"
        alert_parts.append(f"🎮 <b>ESPORTS VALUE BET ALERT</b> {platform_emoji}\n")
        alert_parts.append(f"📱 <b>Platform</b>: {platform_name}\n")
        
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
            
        # Generate trade URL based on platform
        if platform == "kalshi":
            trade_url = build_kalshi_url(market)
            market_ticker = market.get("market_ticker", "N/A")
            event_ticker = market.get("event_ticker", "")
            
            # Kalshi URL format: /markets/{event_slug}/{title_slug}/{market_ticker}
            if trade_url:
                # Use double quotes for Telegram HTML (single quotes don't work properly)
                alert_parts.append(f"🔗 <b>Trade</b>: <a href=\"{trade_url}\">Click here to trade on Kalshi</a>")
            else:
                alert_parts.append(f"🔗 <b>Trade</b>: Market ticker: {market_ticker}")
                alert_parts.append(f"📝 <i>Search for '{market_ticker}' on kalshi.com</i>")
        else:
            # Polymarket URL generation
            # Direct link to Polymarket - use game-specific URL formats
            # Strategy: Try direct market URLs first, fall back to match/event page URLs
            clean_slug = str(slug).strip()
            
            # Get IDs for direct market URL attempts
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
            
            # Extract market name for enhanced context (Option 2 fallback)
            market_name = event_info.get("market_type", "")
            if event_info.get("market_value"):
                market_name = f"{market_name} {event_info['market_value']}".strip()
            if not market_name:
                market_name = "this market"
            
            # Construct URL - game-specific logic
            if polymarket_url_direct:
                # Use direct URL if available from API
                polymarket_url = polymarket_url_direct
                url_type = "direct_api_field"
                logging.debug(f"Market URL using direct API field: {polymarket_url}")
            elif game_type == "League of Legends":
                # For LoL markets, use match page URL (special format for LoL)
                # Direct market URLs with condition_id return 404 - confirmed by user testing
                # Match page URL format: /sports/league-of-legends/games/week/1/{match-slug}
                url_type = "match_page"
                slug_parts = clean_slug.split("-")
                match_slug = clean_slug
                
                # Find date pattern (YYYY-MM-DD) and extract up to that point
                # Remove game-specific suffixes like -game1, -game3, -total-games-3pt5
                for i, part in enumerate(slug_parts):
                    if len(part) == 4 and part.isdigit() and i + 2 < len(slug_parts):
                        if slug_parts[i+1].isdigit() and slug_parts[i+2].isdigit():
                            match_slug = "-".join(slug_parts[:i+3])
                            break
                
                polymarket_url = f"https://polymarket.com/sports/league-of-legends/games/week/1/{match_slug}"
                logging.debug(f"LoL market URL (match page): {polymarket_url} (from slug: {clean_slug})")
            else:
                # For CS2, Dota, and other games, use /event/{slug} format (this was working)
                # BUT: Tournament winner markets need search URLs since they don't have date patterns
                
                # Check if this is a tournament winner market (no date pattern, has "win" and "tournament")
                slug_lower = clean_slug.lower()
                title_lower = market.get("title", "").lower()
                
                # Check for date pattern (YYYY-MM-DD) in slug
                slug_parts = clean_slug.split("-")
                has_date_pattern = False
                for i, part in enumerate(slug_parts):
                    if len(part) == 4 and part.isdigit() and i + 2 < len(slug_parts):
                        if slug_parts[i+1].isdigit() and slug_parts[i+2].isdigit():
                            has_date_pattern = True
                            break
                
                # Tournament markets: have "tournament" and "win"/"winner", but no date pattern
                # Also check for "intel extreme masters", "iem", "championship", etc.
                is_tournament_market = (
                    (("tournament" in slug_lower or "tournament" in title_lower) or
                     ("championship" in slug_lower or "championship" in title_lower) or
                     ("intel extreme masters" in title_lower or "iem" in slug_lower) or
                     ("masters" in slug_lower and "chengdu" in slug_lower)) and
                    ("win" in slug_lower or "winner" in slug_lower or "will" in slug_lower) and
                    not has_date_pattern
                )
                
                if is_tournament_market:
                    # Tournament markets: Use search URL since /event/{slug} doesn't work
                    market_title = market.get("title", clean_slug)
                    market_title_encoded = requests.utils.quote(market_title)
                    polymarket_url = f"https://polymarket.com/search?q={market_title_encoded}"
                    url_type = "search_tournament"
                    logging.debug(f"Tournament market URL using search: {polymarket_url} (slug: {clean_slug})")
                else:
                    # Regular match markets: Use /event/{slug} format
                    # Remove market-specific suffixes to get base match slug
                    slug_parts = clean_slug.split("-")
                    base_slug = clean_slug
                    
                    # Find date pattern (YYYY-MM-DD) and extract up to that point (inclusive)
                    # Remove market suffixes like -total-games-2pt5, -game1, -game3, -btts, etc.
                    date_index = -1
                    for i, part in enumerate(slug_parts):
                        if len(part) == 4 and part.isdigit() and i + 2 < len(slug_parts):
                            if slug_parts[i+1].isdigit() and slug_parts[i+2].isdigit():
                                # Found date pattern (YYYY-MM-DD), extract up to date (inclusive)
                                date_index = i + 2  # Index of the day part
                                base_slug = "-".join(slug_parts[:i+3])
                                break
                    
                    # If no date found, try to detect and remove common market suffixes
                    if date_index == -1:
                        # No date pattern found - check for known market suffixes
                        market_suffixes = [
                            "-total-games-", "-total-games", "-game1", "-game2", "-game3",
                            "-btts", "-over", "-under", "-winner", "-map1", "-map2", "-map3"
                        ]
                        for suffix in market_suffixes:
                            if clean_slug.endswith(suffix) or suffix in clean_slug:
                                # Remove everything from the suffix onwards
                                idx = clean_slug.find(suffix)
                                if idx > 0:
                                    base_slug = clean_slug[:idx]
                                    break
                    else:
                        # Date found - ensure we don't include market suffixes after date
                        # Double-check: if base_slug still has market suffixes after date, remove them
                        market_suffix_patterns = [
                            r"-total-games-.*$",
                            r"-game[123].*$",
                            r"-btts.*$",
                            r"-over.*$",
                            r"-under.*$",
                            r"-winner.*$",
                            r"-map[123].*$"
                        ]
                        for pattern in market_suffix_patterns:
                            base_slug = re.sub(pattern, "", base_slug)
                    
                    polymarket_url = f"https://polymarket.com/event/{base_slug}"
                    url_type = "event_slug"
                    if game_type:
                        logging.debug(f"{game_type} market URL using /event/: {polymarket_url} (from slug: {clean_slug}, base: {base_slug})")
                    else:
                        logging.debug(f"Market URL using /event/: {polymarket_url} (from slug: {clean_slug}, base: {base_slug})")
            
            # Trade link with enhanced context for different URL types
            # Ensure polymarket_url is set before using it
            if not polymarket_url:
                logging.warning(f"⚠️ polymarket_url is empty for slug: {slug}, skipping trade link")
                alert_parts.append(f"🔗 <b>Trade</b>: Market slug: <code>{slug}</code>")
            elif game_type == "League of Legends" and url_type == "match_page":
                # For LoL match page URLs, add context about which market to find
                alert_parts.append(f"🔗 <b>Trade</b>: <a href='{polymarket_url}'>Click here to trade</a>")
                alert_parts.append(f"📌 <i>Note: Link goes to match page. Look for '{market_name}' market below.</i>")
            elif url_type == "search_tournament":
                # For tournament markets, use search URL
                alert_parts.append(f"🔗 <b>Trade</b>: <a href='{polymarket_url}'>Click here to trade</a>")
                alert_parts.append(f"📌 <i>Note: Link goes to search results. Look for the tournament winner market.</i>")
            else:
                # Standard trade link for /event/ URLs and direct URLs
                alert_parts.append(f"🔗 <b>Trade</b>: <a href='{polymarket_url}'>Click here to trade</a>")
            
            # Bet recommendation
            alert_parts.append(f"💰 <b>Bet</b>: <code>{side_label}</code> at <b>${price_for_side:.4f}</b> ({percentage}% odds)")
            
            # ROI calculation - show multiplier prominently (make it stand out)
            if roi is not None and roi > 0 and multiplier:
                # Use bold formatting and emojis to make it stand out (Telegram HTML doesn't support colors)
                alert_parts.append(f"✅ ✅ <b>Potential Return: {multiplier}x</b> ✅ ✅\n💰 (Bet $1 to win ${multiplier:.2f}) 🚀")
            
        # Volume - show market-specific volume (not match total)
        # Add note if using match page URL that shows total volume (LoL only)
        if game_type == "League of Legends" and url_type == "match_page":
            alert_parts.append(f"📊 <b>Market Volume</b>: ${volume:,.0f} <i>(Match page shows total volume for all markets)</i>")
        else:
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
            
            # Calculate alert score for ranking (higher is better)
            # Score = (ROI * 100) + (volume / 1000) + (value indicator)
            # This prioritizes high ROI, high volume, and good value bets
            alert_score = 0.0
            
            # ROI component (most important for value)
            if roi is not None and roi > 0:
                alert_score += roi * 10  # Multiply ROI by 10 for better scaling
            
            # Volume component (higher volume = more liquid = better)
            alert_score += volume / 100.0  # Divide by 100 to scale volume
            
            # Value indicator: lower price for better value (if price < 0.5, bet YES; if price > 0.5, bet NO)
            # The further from 0.5, the more value (but we already filter 5-95% range)
            value_component = abs(price_for_side - 0.5) * 2  # Max 1.0 when price is 0.05 or 0.95
            alert_score += value_component * 5
            
            # Store alert with its score
            alerts.append({
                "message": alert_msg,
                "score": alert_score,
                "roi": roi if roi is not None else 0,
                "volume": volume,
                "slug": slug
            })
            last_alerted_slugs.add(slug)
    
    # Rank alerts by score (highest first) and select top 5 (3-5 max per cycle)
    alerts.sort(key=lambda x: x["score"], reverse=True)
    # Select up to 5 alerts, but send all if fewer are found
    top_alerts = alerts[:min(5, len(alerts))]
    
    # Extract just the messages for the selected alerts
    final_alerts = [alert["message"] for alert in top_alerts]
    
    if len(alerts) > 5:
        logging.info(f"📊 Generated {len(alerts)} alerts, selecting top {len(final_alerts)} by value score (3-5 max per cycle)")
        logging.info(f"   Top alerts: {[alert['slug'] for alert in top_alerts]}")
    elif len(alerts) > 0:
        logging.info(f"📊 Generated {len(alerts)} alerts, sending all {len(final_alerts)} (3-5 max per cycle)")
    else:
        logging.info(f"📊 No alerts generated")
    
    _metrics["alerts_generated"] = len(final_alerts)
    return final_alerts


async def send_telegram_alerts(bot, alerts):
    """Sends alerts to the configured Telegram chat - one alert per message."""
    if not alerts:
        logging.info("No new alerts to send.")
        return
    total_alerts = len(alerts)
    
    logging.info(f"Sending {total_alerts} alert(s) to Telegram (one per message)...")
    
    # Use the normalized CHAT_ID (already normalized at module load)
    if not CHAT_ID:
        logging.error("❌ CHAT_ID is not set or invalid. Cannot send alerts.")
        return
    
    chat_id_int, chat_id_str = get_chat_id_for_telegram()
    logging.info(f"🔍 Using chat_id_int: {chat_id_int}, chat_id_str: '{chat_id_str}'")
    
    for i, alert_msg in enumerate(alerts, 1):
        # Use the retry helper function that tries both formats
        success = await send_telegram_message_with_retry(bot, alert_msg, parse_mode=ParseMode.HTML)
        if success:
            logging.info(f"Successfully sent alert {i}/{total_alerts}.")
            # Delay between messages to avoid rate limiting
            if i < total_alerts:
                await asyncio.sleep(1.0)
        else:
            # If sending failed, log and stop trying to send remaining alerts
            logging.error(f"Failed to send alert {i}/{total_alerts}. Skipping remaining alerts to avoid repeated errors.")
            break  # Stop trying to send remaining alerts


def generate_daily_summary():
    """Generate a daily summary of bot activity and market scanning."""
    from collections import defaultdict
    
    # Fetch markets for summary
    esports_markets = fetch_all_esports_markets()
    
    # Group by game type
    games = defaultdict(list)
    total_volume = 0
    qualifying_markets = 0
    VOLUME_THRESHOLD = float(os.getenv("VOLUME_THRESHOLD", "100"))
    
    for market in esports_markets:
        event_info = format_event_info(market)
        game_type = event_info.get("game_type") or "Unknown"
        games[game_type].append(market)
        
        volume_total = market.get("volume_total", 0)
        volume_1_week = market.get("volume_1_week", 0)
        volume = volume_total if volume_total > 0 else volume_1_week
        total_volume += volume
        
        if volume >= VOLUME_THRESHOLD:
            qualifying_markets += 1
    
    # Build summary message
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    time_of_day = "Morning" if datetime.now().hour < 12 else "Evening"
    
    summary_parts = []
    summary_parts.append(f"🤖 <b>ESPORTS BOT DAILY {time_of_day.upper()} SUMMARY</b>")
    summary_parts.append(f"📅 {current_time}")
    summary_parts.append("")
    summary_parts.append("📊 <b>Scanning Activity (24/7)</b>")
    summary_parts.append(f"✅ Bot is actively scanning markets")
    summary_parts.append(f"🌐 Total esports markets detected: <b>{len(esports_markets)}</b>")
    summary_parts.append(f"💰 Markets with volume ≥${VOLUME_THRESHOLD:.0f}: <b>{qualifying_markets}</b>")
    summary_parts.append(f"💵 Total volume across all markets: <b>${total_volume:,.0f}</b>")
    summary_parts.append("")
    
    if games:
        summary_parts.append("🎮 <b>Esports Breakdown:</b>")
        for game_name in sorted(games.keys(), key=lambda x: x or ""):
            markets_list = games[game_name]
            game_volume = sum(
                max(m.get("volume_total", 0), m.get("volume_1_week", 0))
                for m in markets_list
            )
            qualifying = sum(
                1 for m in markets_list
                if max(m.get("volume_total", 0), m.get("volume_1_week", 0)) >= VOLUME_THRESHOLD
            )
            
            icon = "✅" if qualifying > 0 else "⏳"
            summary_parts.append(f"{icon} <b>{game_name}</b>: {len(markets_list)} markets (${game_volume:,.0f} vol)")
        
        summary_parts.append("")
    
    summary_parts.append("📈 <b>Bot Status:</b>")
    summary_parts.append("✅ Market detection: Active")
    summary_parts.append("✅ Alert generation: Active")
    summary_parts.append("✅ 24/7 monitoring: Enabled")
    summary_parts.append("")
    summary_parts.append("💡 <i>Alerts are sent automatically when value opportunities are detected!</i>")
    
    return "\n".join(summary_parts)


async def send_daily_summary(bot):
    """Send daily summary to Telegram."""
    try:
        summary = generate_daily_summary()
        chat_id_str = str(CHAT_ID)  # Already normalized at module load
        await bot.send_message(chat_id=chat_id_str, text=summary, parse_mode=ParseMode.HTML)
        logging.info("Successfully sent daily summary to Telegram.")
    except BadRequest as e:
        error_msg = str(e).lower()
        if "chat not found" in error_msg or "chat_id" in error_msg:
            logging.error(f"❌ Telegram Chat Error: Chat not found or invalid chat ID: {chat_id_str}")
            logging.error(f"   Please verify that the TELEGRAM_CHAT_ID is correct and the bot has permission to send messages.")
        else:
            logging.exception(f"Telegram BadRequest error sending daily summary: {e}")
    except TelegramError as e:
        logging.exception(f"Failed to send daily summary: {e}")
    except Exception as e:
        logging.exception(f"Error generating daily summary: {e}")


def run_summary_job_sync():
    """Synchronous wrapper to run the async summary job."""
    bot = Bot(token=BOT_TOKEN)
    asyncio.run(send_daily_summary(bot))


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
        try:
            await send_telegram_alerts(bot, alerts)
        finally:
            await bot.close()
    
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


async def send_telegram_message_with_retry(bot, text, parse_mode=None):
    """Send a Telegram message trying both int and string chat ID formats.
    Returns True if successful, False otherwise."""
    if not CHAT_ID:
        logging.error("❌ CHAT_ID is not set or invalid. Cannot send message.")
        return False
    
    chat_id_int, chat_id_str = get_chat_id_for_telegram()
    
    # Try int format first (for numeric chat IDs, Telegram sometimes prefers int)
    if chat_id_int is not None:
        try:
            await bot.send_message(chat_id=chat_id_int, text=text, parse_mode=parse_mode)
            logging.debug(f"✅ Message sent successfully using int chat_id: {chat_id_int}")
            return True
        except BadRequest as e:
            error_msg = str(e).lower()
            if "chat not found" not in error_msg:
                # If it's not a "chat not found" error, try string format
                logging.debug(f"   Int format failed (non-chat-not-found error), trying string format...")
            else:
                # If it's "chat not found", still try string as fallback
                logging.debug(f"   Int format failed with 'chat not found', trying string format...")
    
    # Try string format (either as fallback or primary for non-numeric IDs)
    try:
        await bot.send_message(chat_id=chat_id_str, text=text, parse_mode=parse_mode)
        logging.debug(f"✅ Message sent successfully using string chat_id: {chat_id_str}")
        return True
    except BadRequest as e:
        error_msg = str(e).lower()
        logging.error(f"❌ Telegram message send failed (both formats):")
        logging.error(f"   Int chat_id tried: {chat_id_int}")
        logging.error(f"   String chat_id tried: '{chat_id_str}'")
        logging.error(f"   Error message: {str(e)}")
        if "chat not found" in error_msg or "chat_id" in error_msg:
            logging.error(f"   Error: Chat not found or invalid chat ID")
            logging.error(f"   Please verify:")
            logging.error(f"   1. The TELEGRAM_CHAT_ID is correct: '{chat_id_str}'")
            logging.error(f"   2. The bot has been added to the group/channel")
            logging.error(f"   3. For groups: The bot has permission to send messages")
            logging.error(f"   4. For channels: The bot is added as an administrator")
        return False
    except Exception as e:
        logging.exception(f"❌ Unexpected error sending Telegram message: {e}")
        return False


async def validate_telegram_chat():
    """Validate that the bot can send messages to the configured Telegram chat.
    Returns True if successful, False otherwise. Does not raise exceptions."""
    bot = None
    try:
        # Log the raw chat ID for debugging
        raw_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        logging.info(f"🔍 Validating Telegram chat connection...")
        logging.info(f"   Raw CHAT_ID from env: '{raw_chat_id}' (type: {type(raw_chat_id)}, length: {len(raw_chat_id)})")
        logging.info(f"   Normalized CHAT_ID: '{CHAT_ID}' (type: {type(CHAT_ID)}, length: {len(str(CHAT_ID))})")
        
        if not CHAT_ID:
            logging.error("❌ CHAT_ID is empty or invalid")
            return False
        
        bot = Bot(token=BOT_TOKEN)
        chat_id_int, chat_id_str = get_chat_id_for_telegram()
        
        logging.info(f"   Int chat_id: {chat_id_int} (type: {type(chat_id_int)})")
        logging.info(f"   String chat_id: '{chat_id_str}' (type: {type(chat_id_str)}, length: {len(chat_id_str)})")
        
        # Try to get chat info to validate the chat ID (try both formats with timeout)
        chat_validated = False
        chat_title = "Unknown"
        
        for chat_id_to_try in [chat_id_int, chat_id_str]:
            if chat_id_to_try is None:
                continue
            try:
                # Add timeout to prevent hanging
                chat = await asyncio.wait_for(bot.get_chat(chat_id=chat_id_to_try), timeout=10.0)
                chat_title = chat.title if hasattr(chat, 'title') and chat.title else 'Chat ID'
                logging.info(f"✅ Telegram chat validated successfully: {chat_title} (using {type(chat_id_to_try).__name__}: {chat_id_to_try})")
                chat_validated = True
                break
            except asyncio.TimeoutError:
                logging.warning(f"   Timeout validating chat with {type(chat_id_to_try).__name__} - trying next format...")
                continue
            except BadRequest:
                # Try next format
                continue
            except Exception as e:
                logging.warning(f"   Error validating chat with {type(chat_id_to_try).__name__}: {e}")
                continue
        
        if not chat_validated:
            logging.error(f"❌ Telegram Chat Validation Failed: Could not validate chat with either format")
            logging.error(f"   Int chat_id tried: {chat_id_int}")
            logging.error(f"   String chat_id tried: '{chat_id_str}'")
            logging.error(f"   This may be a temporary network issue. Bot will continue but alerts may fail.")
            if bot:
                try:
                    await bot.close()
                except:
                    pass
            return False
        
        # Validation successful - don't send startup message here to avoid spam on restarts
        # The startup message will be sent only once when the bot actually starts processing
        logging.info("✅ Telegram chat validation successful - ready to send alerts")
        if bot:
            try:
                await bot.close()
            except:
                pass
        return True
    except asyncio.TimeoutError:
        logging.warning("⚠️ Validation timed out - this may be a temporary network issue")
        if bot:
            try:
                await bot.close()
            except:
                pass
        return False
    except Exception as e:
        logging.warning(f"⚠️ Failed to validate Telegram chat (non-critical): {e}")
        logging.warning(f"   Bot will continue - validation errors may be temporary network issues")
        if bot:
            try:
                await bot.close()
            except:
                pass
        return False


def run_job_sync():
    """Synchronous wrapper to run the async job."""
    asyncio.run(job())


if __name__ == "__main__":
    # Validate all required environment variables
    missing_vars = []
    placeholder_vars = []
    
    if not API_KEY or API_KEY == "YOUR_DOME_API_KEY" or "YOUR_DOME_API_KEY" in API_KEY:
        if API_KEY == "YOUR_DOME_API_KEY" or "YOUR_DOME_API_KEY" in API_KEY:
            placeholder_vars.append("DOME_API_KEY")
        else:
            missing_vars.append("DOME_API_KEY")
    
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
        if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
            placeholder_vars.append("TELEGRAM_BOT_TOKEN")
        else:
            missing_vars.append("TELEGRAM_BOT_TOKEN")
    
    if not CHAT_ID or (isinstance(CHAT_ID, str) and (CHAT_ID == "YOUR_TELEGRAM_CHAT_ID" or "YOUR_TELEGRAM_CHAT_ID" in CHAT_ID)):
        if isinstance(CHAT_ID, str) and (CHAT_ID == "YOUR_TELEGRAM_CHAT_ID" or "YOUR_TELEGRAM_CHAT_ID" in CHAT_ID):
            placeholder_vars.append("TELEGRAM_CHAT_ID")
        else:
            missing_vars.append("TELEGRAM_CHAT_ID")
    
    if missing_vars or placeholder_vars:
        error_msg = "❌ Configuration Error:\n\n"
        if placeholder_vars:
            error_msg += f"⚠️  Placeholder values detected for: {', '.join(placeholder_vars)}\n"
            error_msg += "   Please set these environment variables on Railway.\n\n"
        if missing_vars:
            error_msg += f"⚠️  Missing environment variables: {', '.join(missing_vars)}\n"
            error_msg += "   Please set these environment variables on Railway.\n\n"
        error_msg += "📋 Required Railway Environment Variables:\n"
        error_msg += "   - DOME_API_KEY\n"
        error_msg += "   - TELEGRAM_BOT_TOKEN\n"
        error_msg += "   - TELEGRAM_CHAT_ID\n\n"
        error_msg += "💡 To set them: Railway Dashboard → Your Service → Variables → Add Variable"
        logging.error(error_msg)
        exit(1)
    
    logging.info("✅ All environment variables validated successfully")
    
    # Validate Telegram chat before starting (non-blocking - don't exit on failure)
    logging.info("Validating Telegram chat connection...")
    validation_result = asyncio.run(validate_telegram_chat())
    if not validation_result:
        logging.warning("⚠️ Telegram chat validation failed, but continuing anyway.")
        logging.warning("⚠️ Bot will attempt to send alerts - if this fails, check your TELEGRAM_CHAT_ID and bot permissions.")
    else:
        logging.info("✅ Telegram chat validated successfully - ready to send alerts")
    
    logging.info("Starting Esports Odds Alert Bot...")
    
    # Schedule regular alert checks - every 8 hours (3 times per day)
    # First run will be 8 hours from now, or schedule to start at specific times
    schedule.every(8).hours.do(run_job_sync)
    logging.info(f"Scheduled alert checks to run every 8 hours (3 times per day).")
    logging.info(f"First alert cycle will run in 8 hours. Bot is now monitoring in background.")
    
    # Schedule daily summaries (twice per day - morning and evening)
    schedule.every().day.at("09:00").do(run_summary_job_sync)
    schedule.every().day.at("21:00").do(run_summary_job_sync)
    logging.info("Scheduled daily summaries at 09:00 and 21:00 UTC.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt as e:
        logging.exception(f"Shutting down bot...: {e}")