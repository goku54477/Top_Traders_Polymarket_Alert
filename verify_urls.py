"""Quick test to verify URL format in alerts."""
import os
import sys
import logging

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.esports_alert_bot import analyze_and_prepare_alerts

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

print("=" * 80)
print("Verifying Alert URLs")
print("=" * 80)
print()

alerts = analyze_and_prepare_alerts()

if alerts:
    print(f"Found {len(alerts)} alert(s)\n")
    for i, alert in enumerate(alerts, 1):
        print(f"--- Alert {i} ---")
        # Extract URL from alert message
        import re
        url_match = re.search(r'https://polymarket\.com/[^\s<>"\']+', alert)
        if url_match:
            url = url_match.group(0)
            print(f"URL: {url}")
            
            # Check if it's a LoL market
            if "lol-" in alert.lower() or "league of legends" in alert.lower():
                print("✓ LoL market detected")
                if "/market/0x" in url:
                    print("✓ Using condition_id format (correct for LoL)")
                elif "/event/" in url:
                    print("⚠ Using event/slug format (fallback)")
            elif "dota" in alert.lower():
                print("✓ Dota market detected")
                if "/event/" in url:
                    print("✓ Using event/slug format (correct for Dota)")
        else:
            print("⚠ No URL found in alert")
        
        # Show first few lines of alert
        lines = alert.split('\n')[:5]
        print("\nAlert preview:")
        for line in lines:
            print(f"  {line}")
        print()
else:
    print("No alerts generated (no markets meet criteria)")

print("=" * 80)
print("Check your Telegram group to verify the link works!")
print("=" * 80)

