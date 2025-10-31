import os
import requests
import schedule
import time
import logging
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import asyncio

API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
POLL_INTERVAL_MIN = 5
BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"X-API-Key": API_KEY}
ESPORTS_KEYWORDS = [
    "esports",
    "dota",
    "valorant",
    "lol",
    "league of legends",
    "csgo",
    "counter-strike",
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
]
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
last_alerted_slugs = set()


def fetch_with_retry(url, params=None, retries=3, backoff_factor=0.5):
    """Fetches data from a URL with retry logic."""
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
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
    url = f"{BASE_URL}/polymarket/list-markets"
    params = {"active": "true", "limit": 150}
    data = fetch_with_retry(url, params=params)
    if not data or "markets" not in data:
        logging.error("Failed to fetch markets or data is malformed.")
        return []
    esports_markets = []
    for market in data["markets"]:
        question_lower = market.get("question", "").lower()
        slug_lower = market.get("slug", "").lower()
        if any(
            (
                keyword in question_lower or keyword in slug_lower
                for keyword in ESPORTS_KEYWORDS
            )
        ):
            esports_markets.append(market)
    logging.info(
        f"Fetched {len(data['markets'])} markets, found {len(esports_markets)} relevant esports markets."
    )
    return esports_markets


def fetch_price(token_id, platform="polymarket"):
    """Fetches the price for a given token ID."""
    if not token_id:
        return None
    url = f"{BASE_URL}/{platform}/market-price/{token_id}"
    data = fetch_with_retry(url)
    return data.get("price") if data else None


def analyze_and_prepare_alerts():
    """Analyzes markets for opportunities and prepares alert messages."""
    markets = fetch_all_esports_markets()
    alerts = []
    for market in markets:
        slug = market.get("slug")
        if not slug or slug in last_alerted_slugs:
            continue
        token_ids = market.get("token_ids", [])
        if len(token_ids) < 2:
            continue
        yes_token_id = token_ids[0]
        poly_price = fetch_price(yes_token_id, "polymarket")
        if poly_price is None:
            continue
        volume = market.get("volume", 0)
        if volume > 1000 and (poly_price < 0.05 or poly_price > 0.95):
            side = "YES" if poly_price < 0.05 else "NO"
            price_for_side = poly_price if side == "YES" else 1 - poly_price
            alert_msg = f"💎 **VALUE BET**\n**Event**: `{market['question']}`\n**Bet**: `{side}` at **${price_for_side:.2f}**\n**Platform**: Polymarket | **Volume**: ${volume:,.0f}"
            alerts.append(alert_msg)
            last_alerted_slugs.add(slug)
    return alerts


async def send_telegram_alerts(bot, alerts):
    """Sends a batch of alerts to the configured Telegram chat."""
    if not alerts:
        logging.info("No new alerts to send.")
        return
    for i in range(0, len(alerts), 5):
        batch = alerts[i : i + 5]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"🎮 **Esports Odds Alert** ({timestamp})\n\n"
        message = (
            header
            + """

---

""".join(batch)
        )
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)
            logging.info(f"Successfully sent a batch of {len(batch)} alerts.")
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