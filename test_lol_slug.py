import os
import requests
import sys

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("DOME_API_KEY")
if not API_KEY:
    print("ERROR: DOME_API_KEY environment variable not set!")
    print("Please set it before running:")
    print("  Windows: $env:DOME_API_KEY='your_key_here'")
    print("  Linux/Mac: export DOME_API_KEY='your_key_here'")
    print("  Or create a .env file with: DOME_API_KEY=your_key_here")
    sys.exit(1)

BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

print("Fetching LoL markets...")
url = f"{BASE_URL}/polymarket/markets"
params = {"limit": 100}
response = requests.get(url, headers=HEADERS, params=params)
data = response.json()

markets = data.get("markets", [])
lol_markets = [m for m in markets if "lol-" in m.get("market_slug", "").lower()]

print(f"\nFound {len(lol_markets)} LoL markets:\n")
for i, market in enumerate(lol_markets[:3], 1):
    slug = market.get("market_slug", "")
    title = market.get("title", "")
    print(f"Market {i}:")
    print(f"  Title: {title}")
    print(f"  Slug: {slug}")
    print(f"  URL: https://polymarket.com/event/{slug}")
    print(f"  Slug length: {len(slug)}")
    print(f"  Slug repr: {repr(slug)}")
    print()

params = {"limit": 100}
response = requests.get(url, headers=HEADERS, params=params)
data = response.json()

markets = data.get("markets", [])
lol_markets = [m for m in markets if "lol-" in m.get("market_slug", "").lower()]

print(f"\nFound {len(lol_markets)} LoL markets:\n")
for i, market in enumerate(lol_markets[:3], 1):
    slug = market.get("market_slug", "")
    title = market.get("title", "")
    print(f"Market {i}:")
    print(f"  Title: {title}")
    print(f"  Slug: {slug}")
    print(f"  URL: https://polymarket.com/event/{slug}")
    print(f"  Slug length: {len(slug)}")
    print(f"  Slug repr: {repr(slug)}")
    print()

