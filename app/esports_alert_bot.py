import os
import requests
import schedule
import time
import logging
import re
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import asyncio

API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "5"))
BASE_URL = "https://api.domeapi.io/v1"

def get_headers():
    """Get authorization headers with current API key."""
    return {"Authorization": f"Bearer {os.getenv('DOME_API_KEY', API_KEY)}"}

HEADERS = get_headers()  # Default headers, but will be regenerated in functions
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

# Esports-specific terms that need word boundary matching
ESPORTS_SPECIFIC_KEYWORDS = [
    "lol",  # League of Legends - but be careful of false positives
    "gen.g", "gen g", "kt rolster", "kt", "t1", "top esports", "tes",
    "fnatic", "g2", "cloud9", "c9", "team liquid", "tl", "100 thieves",
    "tsm", "clg", "nautilus", "nrg", "mouz", "team spirit", "team falcons",
]

# Keywords that indicate NON-esports (to filter out)
NON_ESPORTS_KEYWORDS = [
    "nba", "nfl", "nhl", "mlb", "ufc", "boxing", "mma",
    "atp", "wta", "tennis", "f1", "formula", "racing",
    "golf", "soccer", "football", "basketball", "baseball",
    "hockey", "cricket", "rugby", "trump", "biden", "political",
    "election", "president", "congress", "earnings", "stock",
    "house of representatives", "representatives", "senate",
    "approval rating", "will trump", "will biden",
]
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
last_alerted_slugs = set()  # Track already alerted markets to prevent duplicates

# Option to reset tracking (useful for testing or when you want to re-alert)
# Uncomment the line below to reset and allow re-alerting on markets
# last_alerted_slugs.clear()


def fetch_with_retry(url, params=None, retries=3, backoff_factor=0.5):
    """Fetches data from a URL with retry logic."""
    headers = get_headers()  # Use current API key
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)  # Increased timeout to 30s
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.exception(
                f"Request failed for {url} (attempt {i + 1}/{retries}): {e}"
            )
            if i < retries - 1:
                time.sleep(backoff_factor * 2**i)
    return None


def fetch_all_esports_markets():
    """Fetches all active esports markets from Dome API."""
    all_markets = []
    seen_slugs = set()
    offset = 0
    limit = 100  # Max allowed by API
    
    while True:
        url = f"{BASE_URL}/polymarket/markets"
        params = {"limit": limit, "offset": offset}
        data = fetch_with_retry(url, params=params)
        
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
            
            # Check if it matches esports keywords
            # First check for specific esports terms with word boundaries
            is_esports_specific = False
            for keyword in ESPORTS_SPECIFIC_KEYWORDS:
                # Use word boundaries for "lol" to avoid matching "low"
                if keyword == "lol":
                    # Check for "lol" as whole word or as part of "league of legends"
                    import re
                    if re.search(r'\blol\b', title) or re.search(r'\blol\b', slug_lower) or "league of legends" in title:
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
            
            is_esports = is_esports_specific or is_esports_general
            
            # Exclude non-esports markets
            is_non_esports = any(
                keyword in title or keyword in slug_lower
                for keyword in NON_ESPORTS_KEYWORDS
            )
            
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
    
    # Calculate total fetched
    total_fetched = offset
    logging.info(
        f"Total markets searched: {total_fetched}, found {len(all_markets)} relevant esports markets."
    )
    return all_markets


def fetch_price(token_id, platform="polymarket"):
    """Fetches the price for a given token ID."""
    if not token_id:
        return None
    url = f"{BASE_URL}/{platform}/market-price/{token_id}"
    data = fetch_with_retry(url)
    price = data.get("price") if data else None
    # Ensure price is a valid float
    if price is not None:
        try:
            price = float(price)
            # Clamp price to valid range [0.0, 1.0]
            price = max(0.0, min(1.0, price))
        except (ValueError, TypeError):
            return None
    return price


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
    
    # Try to extract game type from title
    game_patterns = {
        "Dota 2": r"dota\s*2|dota2",
        "Counter-Strike": r"counter[\s-]?strike|cs2|csgo|cs\s*2",
        "Valorant": r"valorant",
        "League of Legends": r"league\s+of\s+legends|lol",
        "Overwatch": r"overwatch",
    }
    
    title_lower = title.lower()
    for game, pattern in game_patterns.items():
        if re.search(pattern, title_lower, re.IGNORECASE):
            event_info["game_type"] = game
            break
    
    # Try to extract teams (common pattern: "Team A vs Team B")
    vs_match = re.search(r"([A-Za-z0-9\s&]+)\s+vs\.?\s+([A-Za-z0-9\s&]+)", title, re.IGNORECASE)
    if vs_match:
        event_info["teams"] = {
            "team_a": vs_match.group(1).strip(),
            "team_b": vs_match.group(2).strip(),
        }
    
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
            
        poly_price = fetch_price(yes_token_id, "polymarket")
        if poly_price is None:
            continue
        
        # Dome API uses 'volume_total' instead of 'volume'
        volume = market.get("volume_total", 0)
        if volume > 1000 and (poly_price < 0.05 or poly_price > 0.95):
            # Determine which side to bet on
            if poly_price < 0.05:
                side = "YES"
                side_label = side_a.get("label", "YES")
                price_for_side = max(0.01, round(poly_price, 4))  # Ensure minimum 0.01, round to 4 decimals
            else:  # poly_price > 0.95
                side = "NO"
                side_label = side_b.get("label", "NO")
                price_for_side = max(0.01, round(1.0 - poly_price, 4))  # Ensure minimum 0.01, round to 4 decimals
            
            # Calculate percentage odds
            percentage = round(price_for_side * 100, 2)
            
            # Parse event information
            event_info = format_event_info(market)
            
            # Build enhanced alert message
            alert_parts = []
            alert_parts.append("🎮 **ESPORTS VALUE BET ALERT**\n")
            
            # Match/Game information
            if event_info["teams"]:
                teams_str = f"{event_info['teams']['team_a']} vs {event_info['teams']['team_b']}"
                if event_info["game_type"]:
                    alert_parts.append(f"📅 **Match**: {event_info['game_type']} - {teams_str}")
                else:
                    alert_parts.append(f"📅 **Match**: {teams_str}")
            elif event_info["game_type"]:
                alert_parts.append(f"📅 **Game**: {event_info['game_type']}")
            
            # Market information
            market_desc = event_info["full_title"]
            if event_info["market_type"] and event_info["market_value"]:
                market_desc = f"{event_info['market_type']} {event_info['market_value']}"
            alert_parts.append(f"🎯 **Market**: {market_desc}")
            
            # Bet recommendation
            alert_parts.append(f"💰 **Bet**: `{side_label}` at **${price_for_side:.4f}** ({percentage}% odds)")
            
            # Volume
            alert_parts.append(f"📊 **Volume**: ${volume:,.0f}")
            
            # Direct link to Polymarket
            polymarket_url = f"https://polymarket.com/event/{slug}"
            alert_parts.append(f"🔗 **Trade**: [Click here to trade]({polymarket_url})")
            
            # Analysis/insight
            if price_for_side < 0.05:
                insight = f"💡 **Analysis**: Extremely undervalued opportunity - market shows only {percentage}% chance"
            else:
                insight = f"💡 **Analysis**: High confidence bet - market shows {percentage}% chance (likely outcome)"
            alert_parts.append(insight)
            
            alert_msg = "\n".join(alert_parts)
            alerts.append(alert_msg)
            last_alerted_slugs.add(slug)
    return alerts


async def send_telegram_alerts(bot, alerts):
    """Sends a batch of alerts to the configured Telegram chat."""
    if not alerts:
        logging.info("No new alerts to send.")
        return
    total_alerts = len(alerts)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for i in range(0, total_alerts, 3):  # Reduced to 3 per batch for better readability
        batch = alerts[i : i + 3]
        batch_num = (i // 3) + 1
        total_batches = (total_alerts + 2) // 3  # Ceiling division
        
        # Enhanced header with batch information
        if total_batches > 1:
            header = f"🎮 **Esports Odds Alert** ({timestamp})\n📦 Batch {batch_num}/{total_batches} ({len(batch)} alerts)\n\n"
        else:
            header = f"🎮 **Esports Odds Alert** ({timestamp})\n📦 {total_alerts} alert{'s' if total_alerts > 1 else ''} found\n\n"
        
        # Better separator between alerts
        separator = "\n" + "─" * 50 + "\n\n"
        message = header + separator.join(batch)
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)
            logging.info(f"Successfully sent batch {batch_num}/{total_batches} with {len(batch)} alerts.")
        except TelegramError as e:
            logging.exception(f"Failed to send Telegram message: {e}")
        except Exception as e:
            logging.exception(
                f"An unexpected error occurred during message sending: {e}"
            )


async def job():
    """The main job to be run on a schedule."""
    logging.info("Starting new alert cycle...")
    alerts = analyze_and_prepare_alerts()
    if alerts:
        bot = Bot(token=BOT_TOKEN)
        await send_telegram_alerts(bot, alerts)
    logging.info(f"Alert cycle finished. Next run in {POLL_INTERVAL_MIN} minutes.")


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