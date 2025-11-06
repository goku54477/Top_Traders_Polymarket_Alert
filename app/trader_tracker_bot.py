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
def normalize_chat_id(chat_id):
    """Normalize chat ID to ensure consistent format."""
    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        return None
    chat_id = str(chat_id).strip()
    while len(chat_id) >= 2 and (
        (chat_id[0] == '"' and chat_id[-1] == '"') or
        (chat_id[0] == "'" and chat_id[-1] == "'") or
        (chat_id[0] == '`' and chat_id[-1] == '`')
    ):
        chat_id = chat_id[1:-1].strip()
    try:
        chat_id_int = int(chat_id)
        return str(chat_id_int)
    except ValueError:
        return chat_id

CHAT_ID = normalize_chat_id(CHAT_ID)

def get_chat_id_for_telegram():
    """Get chat ID in the format that works best for Telegram API."""
    if not CHAT_ID:
        return None, None
    try:
        chat_id_int = int(CHAT_ID)
        return chat_id_int, str(chat_id_int)
    except (ValueError, TypeError):
        return None, str(CHAT_ID)

# Trader configuration - list of traders to track
# Can be configured via environment variable TRADER_WALLETS (comma-separated wallet:username pairs)
# Or set directly here (wallet addresses are public, but usernames can be customized)
TRADER_WALLETS_ENV = os.getenv("TRADER_WALLETS", "")
if TRADER_WALLETS_ENV:
    # Parse from environment: "wallet1:username1,wallet2:username2"
    TRADERS = []
    for pair in TRADER_WALLETS_ENV.split(","):
        if ":" in pair:
            wallet, username = pair.strip().split(":", 1)
            TRADERS.append({"username": username.strip(), "wallet": wallet.strip()})
else:
    # Default trader (example - replace with your own)
    TRADERS = [
        {"username": "Sharky6999", "wallet": "0x751a2b86cab503496efd325c8344e10159349ea1"}
    ]

BASE_URL = "https://api.domeapi.io/v1"  # Still used for market volume
POLYMARKET_API_URL = "https://data-api.polymarket.com"

# Caching for orders
_orders_cache = {}  # {wallet: {"data": list, "timestamp": float}}
_last_alerted_positions = set()  # Track orders we've already alerted on
_market_volume_cache = {}  # {market_slug: {"volume": float, "timestamp": float}}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_headers():
    """Get authorization headers with current API key."""
    return {
        "Authorization": f"Bearer {os.getenv('DOME_API_KEY', API_KEY)}",
        "accept": "application/json"
    }

def fetch_with_retry(url, params=None, retries=3, backoff_factor=0.5):
    """Fetches data from a URL with retry logic and improved error handling."""
    headers = get_headers()
    
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 404:
                logging.info(f"Resource not found (404): {url}")
                return (None, 404)
            elif response.status_code == 429:
                wait_time = 5 + (backoff_factor * (2 ** i))
                logging.warning(f"Rate limited (429) for {url}, waiting {wait_time:.1f}s before retry {i + 1}/{retries}")
                if i < retries - 1:
                    time.sleep(wait_time)
                continue
            elif response.status_code >= 500:
                logging.warning(f"Server error ({response.status_code}) for {url}, retrying...")
                if i < retries - 1:
                    time.sleep(backoff_factor * 2**i)
                continue
            
            response.raise_for_status()
            return (response.json(), response.status_code)
            
        except requests.exceptions.Timeout as e:
            logging.warning(f"Timeout for {url} (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * 2**i)
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed for {url} (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * 2**i)
    
    return (None, None)

def fetch_trader_positions(wallet_address):
    """Fetch actual positions (filled holdings) for a trader wallet address from Polymarket API."""
    url = f"{POLYMARKET_API_URL}/positions"
    params = {"user": wallet_address}
    
    logging.info(f"Fetching positions for wallet: {wallet_address[:10]}...")
    
    try:
        # Polymarket API is public, no authentication needed
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            positions = response.json()
            if not isinstance(positions, list):
                positions = []
            
            logging.info(f"Found {len(positions)} positions for wallet {wallet_address[:10]}...")
            return positions
        else:
            logging.warning(f"Polymarket API returned status {response.status_code} for wallet {wallet_address[:10]}...")
            return []
    except Exception as e:
        logging.error(f"Error fetching positions from Polymarket API: {e}")
        return []

def parse_position(position_data, trader_username):
    """Parse a single position from Polymarket positions API."""
    try:
        # Extract position details from Polymarket API response
        shares = position_data.get("size", 0)  # Actual shares held
        outcome = position_data.get("outcome", "")  # YES/NO
        market_slug = position_data.get("slug", "")
        market_title = position_data.get("title", "Unknown Market")
        avg_price = position_data.get("avgPrice", 0)  # Entry price per share
        cur_price = position_data.get("curPrice", 0)  # Current price per share
        current_value = position_data.get("currentValue", 0)  # Current total value
        initial_value = position_data.get("initialValue", 0)  # Entry cost (what they paid)
        cash_pnl = position_data.get("cashPnl", 0)  # Profit/loss in dollars
        percent_pnl = position_data.get("percentPnl", 0)  # Profit/loss percentage
        condition_id = position_data.get("conditionId", "")
        asset = position_data.get("asset", "")
        
        # Convert to floats
        shares = float(shares) if shares else 0.0
        avg_price = float(avg_price) if avg_price else 0.0
        cur_price = float(cur_price) if cur_price else 0.0
        current_value = float(current_value) if current_value else 0.0
        initial_value = float(initial_value) if initial_value else 0.0
        cash_pnl = float(cash_pnl) if cash_pnl else 0.0
        percent_pnl = float(percent_pnl) if percent_pnl else 0.0
        
        # Extract event info for URL building
        event_slug = position_data.get("eventSlug", "")
        event_id = position_data.get("eventId", "")
        
        return {
            "trader": trader_username,
            "condition_id": condition_id,
            "asset": asset,
            "market_slug": market_slug,
            "event_slug": event_slug,  # For URL building
            "event_id": event_id,  # Alternative for URL building
            "market_title": market_title,
            "outcome": outcome,
            "shares": shares,
            "avg_price": avg_price,  # Entry price per share
            "cur_price": cur_price,  # Current price per share
            "current_value": current_value,  # Current total value (for sorting)
            "initial_value": initial_value,  # Entry cost (what they paid)
            "cash_pnl": cash_pnl,  # Profit/loss in dollars
            "percent_pnl": percent_pnl,  # Profit/loss percentage
            "raw_data": position_data  # Keep raw data for debugging
        }
    except Exception as e:
        logging.warning(f"Error parsing position: {e}")
        logging.debug(f"Position data: {position_data}")
        return None

def build_polymarket_url(position_data):
    """Build Polymarket URL from position data (prefers eventSlug, falls back to market slug)."""
    # Try event_slug first (most reliable)
    event_slug = position_data.get("event_slug", "")
    if event_slug:
        return f"https://polymarket.com/event/{event_slug}"
    
    # Try event_id as fallback
    event_id = position_data.get("event_id", "")
    if event_id:
        return f"https://polymarket.com/event/{event_id}"
    
    # Fallback to market slug
    market_slug = position_data.get("market_slug", "")
    if not market_slug:
        return None
    
    # Clean slug
    clean_slug = str(market_slug).strip()
    
    # For "up or down" markets, use search URL as they may not have direct event pages
    if "up-or-down" in clean_slug.lower():
        # Use search URL for up/down markets
        search_query = clean_slug.replace("-", " ")
        return f"https://polymarket.com/search?q={search_query}"
    
    # For regular markets, try to build event URL
    slug_parts = clean_slug.split("-")
    base_slug = clean_slug
    
    # Find date pattern (YYYY-MM-DD) and extract up to that point
    for i, part in enumerate(slug_parts):
        if len(part) == 4 and part.isdigit() and i + 2 < len(slug_parts):
            if slug_parts[i+1].isdigit() and slug_parts[i+2].isdigit():
                base_slug = "-".join(slug_parts[:i+3])
                break
    
    # Remove market suffixes after date
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
    
    return f"https://polymarket.com/event/{base_slug}"

def format_timestamp_utc(timestamp):
    """Convert Unix timestamp to human-readable UTC format."""
    if not timestamp:
        return "N/A"
    
    try:
        # Handle both integer and string timestamps
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        elif not isinstance(timestamp, (int, float)):
            return "N/A"
        
        # Convert to datetime in UTC
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        # Format as: YYYY-MM-DD HH:MM:SS UTC
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OSError, OverflowError) as e:
        logging.warning(f"Error formatting timestamp {timestamp}: {e}")
        return "N/A"

def format_shares(shares):
    """Format shares in abbreviated format (e.g., 21.17M, 1.5K)."""
    if not shares or shares == 0:
        return "0"
    
    shares_float = float(shares)
    
    # Format with appropriate suffix
    if shares_float >= 1_000_000:
        return f"{shares_float / 1_000_000:.2f}M"
    elif shares_float >= 1_000:
        return f"{shares_float / 1_000:.2f}K"
    else:
        return f"{shares_float:,.2f}"

def fetch_market_volume(market_slug):
    """Fetch total market volume for a given market slug."""
    if not market_slug:
        return None
    
    # Check cache first (5 minute TTL)
    if market_slug in _market_volume_cache:
        cache_entry = _market_volume_cache[market_slug]
        cache_age = time.time() - cache_entry["timestamp"]
        if cache_age < 300:  # 5 minutes
            return cache_entry["volume"]
    
    try:
        # Search through markets to find the one matching our slug
        # Try up to 10 pages (1000 markets) to find the market, especially for "up or down" markets
        url = f"{BASE_URL}/polymarket/markets"
        limit = 100
        max_pages = 10
        
        for page in range(max_pages):
            offset = page * limit
            params = {"limit": limit, "offset": offset}
            
            data, status_code = fetch_with_retry(url, params=params)
            
            if not data or "markets" not in data:
                break
            
            markets = data.get("markets", [])
            if not markets:
                break
            
            # Search for matching market - try exact match first
            for market in markets:
                market_slug_from_api = market.get("market_slug", "")
                if market_slug_from_api == market_slug:
                    # Extract volume (same logic as esports bot)
                    volume_total = market.get("volume_total", 0)
                    volume_1_week = market.get("volume_1_week", 0)
                    volume = volume_total if volume_total > 0 else volume_1_week
                    
                    # Cache the result
                    _market_volume_cache[market_slug] = {
                        "volume": volume,
                        "timestamp": time.time()
                    }
                    logging.debug(f"Found market volume for {market_slug}: ${volume:,.0f}")
                    return volume
            
            # Small delay to avoid rate limiting
            if page < max_pages - 1:
                time.sleep(0.3)
        
        # Market not found - cache None to avoid repeated lookups
        _market_volume_cache[market_slug] = {
            "volume": None,
            "timestamp": time.time()
        }
        logging.debug(f"Market volume not found for {market_slug} after searching {max_pages} pages")
        return None
        
    except Exception as e:
        logging.warning(f"Error fetching market volume for {market_slug}: {e}")
        return None

def generate_trader_alerts(all_positions):
    """Generate alert messages for top trader positions."""
    if not all_positions:
        return []
    
    # Sort by current value (descending) and take top 5
    sorted_positions = sorted(all_positions, key=lambda x: x["current_value"], reverse=True)
    top_positions = sorted_positions[:5]
    
    alerts = []
    for i, pos in enumerate(top_positions, 1):
        alert_parts = []
        alert_parts.append(f"🐋 <b>TOP TRADER ALERT</b> #{i}\n")
        alert_parts.append(f"👤 <b>Trader</b>: {pos['trader']}")
        alert_parts.append(f"📊 <b>Market</b>: {pos['market_title']}")
        
        # Fetch and display total market volume
        market_volume = fetch_market_volume(pos['market_slug'])
        if market_volume is not None and market_volume > 0:
            alert_parts.append(f"📊 <b>Total Market Volume</b>: ${market_volume:,.0f}")
        else:
            alert_parts.append(f"📊 <b>Total Market Volume</b>: N/A")
        
        alert_parts.append(f"📈 <b>Position</b>: <code>{pos['outcome']}</code>")
        
        # Show entry price per share
        if pos.get('avg_price'):
            alert_parts.append(f"💰 <b>Entry Price</b>: ${pos['avg_price']:.4f}")
        
        # Show current price per share
        if pos.get('cur_price'):
            alert_parts.append(f"📊 <b>Current Price</b>: ${pos['cur_price']:.4f}")
        
        # Show shares in abbreviated format
        formatted_shares = format_shares(pos['shares'])
        alert_parts.append(f"📦 <b>Shares</b>: {formatted_shares}")
        
        # Show entry cost (what they paid)
        if pos.get('initial_value'):
            alert_parts.append(f"💵 <b>Entry Cost</b>: ${pos['initial_value']:,.2f}")
        
        # Show current value (what it's worth now)
        if pos.get('current_value'):
            alert_parts.append(f"💎 <b>Current Value</b>: ${pos['current_value']:,.2f}")
        
        # Show P&L with color indicator
        if pos.get('cash_pnl') is not None:
            pnl = pos['cash_pnl']
            pnl_percent = pos.get('percent_pnl', 0)
            if pnl >= 0:
                alert_parts.append(f"🟢 <b>Profit</b>: +${abs(pnl):,.2f} (+{abs(pnl_percent):.2f}%)")
            else:
                alert_parts.append(f"🔴 <b>Loss</b>: -${abs(pnl):,.2f} ({pnl_percent:.2f}%)")
        
        # Add Polymarket link (pass entire position data for URL building)
        market_url = build_polymarket_url(pos)
        if market_url:
            alert_parts.append(f"🔗 <b>Trade</b>: <a href='{market_url}'>Click here to view market</a>")
        else:
            alert_parts.append(f"🔗 <b>Market Slug</b>: <code>{pos['market_slug']}</code>")
        
        # Add analysis
        formatted_shares_full = format_shares(pos['shares'])
        analysis = f"💡 <b>Analysis</b>: {pos['trader']} holds {formatted_shares_full} shares of <code>{pos['outcome']}</code> in this market."
        if pos.get('cash_pnl') is not None:
            pnl = pos['cash_pnl']
            if pnl >= 0:
                analysis += f" Currently up ${abs(pnl):,.2f} ({abs(pos.get('percent_pnl', 0)):.2f}%)."
            else:
                analysis += f" Currently down ${abs(pnl):,.2f} ({pos.get('percent_pnl', 0):.2f}%)."
        analysis += f" This indicates significant interest in the {pos['outcome']} outcome."
        alert_parts.append(analysis)
        
        alert_msg = "\n".join(alert_parts)
        alerts.append(alert_msg)
    
    return alerts

async def send_telegram_alerts(bot, alerts):
    """Send alerts to Telegram."""
    if not alerts:
        logging.info("No alerts to send.")
        return
    
    total_alerts = len(alerts)
    logging.info(f"Sending {total_alerts} trader alert(s) to Telegram...")
    
    if not CHAT_ID:
        logging.error("❌ CHAT_ID is not set or invalid. Cannot send alerts.")
        return
    
    chat_id_int, chat_id_str = get_chat_id_for_telegram()
    
    for i, alert_msg in enumerate(alerts, 1):
        success = await send_telegram_message_with_retry(bot, alert_msg, parse_mode=ParseMode.HTML)
        if success:
            logging.info(f"Successfully sent alert {i}/{total_alerts}.")
            if i < total_alerts:
                await asyncio.sleep(1.0)
        else:
            logging.error(f"Failed to send alert {i}/{total_alerts}.")
            break

async def send_telegram_message_with_retry(bot, text, parse_mode=None):
    """Send a Telegram message trying both int and string chat ID formats."""
    if not CHAT_ID:
        return False
    
    chat_id_int, chat_id_str = get_chat_id_for_telegram()
    
    if chat_id_int is not None:
        try:
            await bot.send_message(chat_id=chat_id_int, text=text, parse_mode=parse_mode)
            return True
        except BadRequest:
            pass
    
    try:
        await bot.send_message(chat_id=chat_id_str, text=text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False

async def trader_tracking_job():
    """Main job to track trader positions and send alerts."""
    cycle_start = time.time()
    logging.info("Starting trader tracking cycle...")
    
    all_positions = []
    
    # Fetch positions for all traders
    for trader in TRADERS:
        username = trader["username"]
        wallet = trader["wallet"]
        
        try:
            positions = fetch_trader_positions(wallet)
            
            for position_data in positions:
                parsed_position = parse_position(position_data, username)
                if parsed_position and parsed_position["current_value"] > 0:
                    # Create unique key for tracking (use condition_id or asset)
                    position_key = f"{wallet}_{parsed_position.get('condition_id') or parsed_position.get('asset')}_{parsed_position.get('market_slug')}"
                    if position_key not in _last_alerted_positions:
                        all_positions.append(parsed_position)
                        _last_alerted_positions.add(position_key)
        except Exception as e:
            logging.exception(f"Error fetching positions for {username}: {e}")
    
    if not all_positions:
        logging.info("No new positions found.")
        return
    
    # Generate alerts for top 5 positions by current value
    alerts = generate_trader_alerts(all_positions)
    
    if alerts:
        bot = Bot(token=BOT_TOKEN)
        try:
            await send_telegram_alerts(bot, alerts)
        finally:
            await bot.close()
    
    cycle_time = time.time() - cycle_start
    logging.info(f"Trader tracking cycle finished in {cycle_time:.2f}s. Alerts sent: {len(alerts)}")

def run_trader_job_sync():
    """Synchronous wrapper to run the async trader job."""
    asyncio.run(trader_tracking_job())

async def validate_telegram_chat():
    """Validate that the bot can send messages to the configured Telegram chat."""
    bot = None
    try:
        if not CHAT_ID:
            logging.error("❌ CHAT_ID is empty or invalid")
            return False
        
        bot = Bot(token=BOT_TOKEN)
        chat_id_int, chat_id_str = get_chat_id_for_telegram()
        
        for chat_id_to_try in [chat_id_int, chat_id_str]:
            if chat_id_to_try is None:
                continue
            try:
                chat = await asyncio.wait_for(bot.get_chat(chat_id=chat_id_to_try), timeout=10.0)
                logging.info(f"✅ Telegram chat validated: {chat.title if hasattr(chat, 'title') else 'Chat'}")
                if bot:
                    try:
                        await bot.close()
                    except:
                        pass
                return True
            except Exception:
                continue
        
        if bot:
            try:
                await bot.close()
            except:
                pass
        return False
    except Exception as e:
        logging.warning(f"⚠️ Validation error (non-critical): {e}")
        if bot:
            try:
                await bot.close()
            except:
                pass
        return False

if __name__ == "__main__":
    # Validate environment variables
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
        if missing_vars:
            error_msg += f"⚠️  Missing environment variables: {', '.join(missing_vars)}\n"
        logging.error(error_msg)
        exit(1)
    
    logging.info("✅ All environment variables validated successfully")
    
    # Validate Telegram chat (non-blocking)
    logging.info("Validating Telegram chat connection...")
    validation_result = asyncio.run(validate_telegram_chat())
    if not validation_result:
        logging.warning("⚠️ Telegram chat validation failed, but continuing anyway.")
    else:
        logging.info("✅ Telegram chat validated successfully")
    
    logging.info("Starting Top Trader Tracker Bot...")
    
    # Schedule to run every 1 hour
    schedule.every(1).hour.do(run_trader_job_sync)
    logging.info(f"Scheduled trader tracking to run every 1 hour.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down trader tracker bot...")

