"""Test script to verify Dome API connection."""
import requests
import json
from datetime import datetime

# Get API key from environment variable
import os
API_KEY = os.getenv("DOME_API_KEY", "YOUR_DOME_API_KEY")
BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def test_api_connection():
    """Test basic API connection."""
    print("=" * 60)
    print("Testing Dome API Connection")
    print("=" * 60)
    print(f"API Key: {API_KEY[:20]}...")
    print(f"Base URL: {BASE_URL}")
    print()


def test_list_markets():
    """Test listing markets endpoint - may need different approach."""
    print("-" * 60)
    print("Test 1: List Markets Endpoint")
    print("-" * 60)
    
    url = f"{BASE_URL}/polymarket/list-markets"
    params = {"active": "true", "limit": 10}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 404:
            print("[INFO] Endpoint returned 404 - may need different endpoint or parameters")
            print("[INFO] Trying alternative approaches...")
            return False, None
            
        response.raise_for_status()
        data = response.json()
        
        print(f"[OK] Status Code: {response.status_code}")
        print(f"[OK] Response received successfully")
        
        if "markets" in data:
            print(f"[OK] Found {len(data['markets'])} markets")
            if len(data['markets']) > 0:
                print("\nSample market:")
                sample_market = data['markets'][0]
                print(f"  - Question: {sample_market.get('question', 'N/A')}")
                print(f"  - Slug: {sample_market.get('slug', 'N/A')}")
                print(f"  - Volume: ${sample_market.get('volume', 0):,.0f}")
        else:
            print("[WARNING] Response doesn't contain 'markets' key")
            print(f"Response keys: {list(data.keys())}")
            print(f"Response preview: {json.dumps(data, indent=2)[:300]}")
        
        return True, data
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return False, None


def test_sample_endpoint():
    """Test the sample endpoint from the documentation."""
    print("\n" + "-" * 60)
    print("Test 2: Orders Endpoint (with market_slug filter)")
    print("-" * 60)
    
    url = f"{BASE_URL}/polymarket/orders"
    params = {"limit": 10, "market_slug": "us-government-shutdown-by-october-1"}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"[OK] Status Code: {response.status_code}")
        print(f"[OK] Response received successfully")
        print(f"[OK] Market Slug: us-government-shutdown-by-october-1")
        
        if isinstance(data, list):
            print(f"[OK] Found {len(data)} orders")
            if len(data) > 0:
                print("\nSample order:")
                print(f"  {json.dumps(data[0], indent=2)[:300]}")
        elif isinstance(data, dict):
            print(f"[OK] Response keys: {list(data.keys())}")
            print(f"Response preview: {json.dumps(data, indent=2)[:300]}")
        else:
            print(f"[OK] Response type: {type(data)}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return False


def test_find_esports_market():
    """Try to find an esports market slug to use for testing."""
    print("\n" + "-" * 60)
    print("Test 3: Finding Esports Market Slug")
    print("-" * 60)
    
    # Common esports market slugs to try
    esports_slugs = [
        "dota-2-ti",
        "valorant-champions",
        "league-of-legends-worlds",
        "csgo-major",
        "esports",
    ]
    
    print("Note: We need to find a valid esports market slug.")
    print("Trying common esports-related slugs...")
    
    found_slug = None
    for slug in esports_slugs:
        url = f"{BASE_URL}/polymarket/orders"
        params = {"limit": 1, "market_slug": slug}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    print(f"[OK] Found orders for market: {slug}")
                    found_slug = slug
                    break
                elif isinstance(data, dict) and not data.get("error"):
                    print(f"[OK] Found data for market: {slug}")
                    found_slug = slug
                    break
        except:
            continue
    
    if found_slug:
        print(f"\n[SUCCESS] Found esports market slug: {found_slug}")
        return found_slug
    else:
        print("\n[INFO] Could not find esports market slugs automatically.")
        print("[INFO] You may need to search Polymarket website for esports market slugs.")
        return None


def test_esports_orders(market_slug):
    """Test orders endpoint with an esports market slug."""
    if not market_slug:
        print("\n[SKIP] Skipping esports orders test - no market slug available")
        return False
        
    print("\n" + "-" * 60)
    print(f"Test 4: Esports Orders (market_slug: {market_slug})")
    print("-" * 60)
    
    url = f"{BASE_URL}/polymarket/orders"
    params = {"limit": 10, "market_slug": market_slug}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"[OK] Status Code: {response.status_code}")
        print(f"[OK] Response received successfully")
        
        if isinstance(data, list):
            print(f"[OK] Found {len(data)} orders for esports market")
            if len(data) > 0:
                print("\nSample order:")
                sample_order = data[0]
                print(f"  Order keys: {list(sample_order.keys())}")
        elif isinstance(data, dict):
            print(f"[OK] Response keys: {list(data.keys())}")
            print(f"Response preview: {json.dumps(data, indent=2)[:300]}")
        else:
            print(f"[OK] Response type: {type(data)}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return False


def test_market_price(token_id=None):
    """Test fetching market price for a token."""
    print("\n" + "-" * 60)
    print("Test 5: Market Price")
    print("-" * 60)
    
    if not token_id:
        print("[INFO] No token_id provided. Skipping market price test.")
        print("[INFO] To test this, you need a token_id from an order or market.")
        return False
    
    url = f"{BASE_URL}/polymarket/market-price/{token_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"[OK] Status Code: {response.status_code}")
        print(f"[OK] Token ID: {token_id}")
        
        if "price" in data:
            print(f"[OK] Price: ${data['price']:.4f}")
        else:
            print(f"[OK] Response keys: {list(data.keys())}")
            print(f"   Full response: {json.dumps(data, indent=2)[:200]}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
        return False




if __name__ == "__main__":
    test_api_connection()
    
    # Test 1: List markets (may not work - endpoint might have changed)
    success1, market_data = test_list_markets()
    
    # Test 2: Sample endpoint with market_slug filter
    test_sample_endpoint()
    
    # Test 3: Try to find esports market slugs
    esports_slug = test_find_esports_market()
    
    # Test 4: Test esports orders if we found a slug
    if esports_slug:
        test_esports_orders(esports_slug)
    
    # Test 5: Market price (would need token_id from orders)
    # test_market_price(token_id="some-token-id")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)
    print("\nKey Findings:")
    print("- Orders endpoint requires market_slug, condition_id, user, or token_id filter")
    print("- To get esports data, you need to find esports market slugs")
    print("- You can find market slugs by browsing Polymarket or using their search")

