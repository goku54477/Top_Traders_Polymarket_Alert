"""Test script to explore Dome API endpoints for markets."""
import requests
import json

# Your Dome API credentials
API_KEY = "YOUR_DOME_API_KEY"
BASE_URL = "https://api.domeapi.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def test_endpoints():
    """Test various Dome API endpoints to find how to list markets."""
    print("=" * 60)
    print("Exploring Dome API Endpoints")
    print("=" * 60)
    print(f"API Key: {API_KEY[:20]}...")
    print(f"Base URL: {BASE_URL}")
    print()

    # Try different endpoint variations
    endpoints_to_test = [
        "/polymarket/list-markets",
        "/polymarket/markets",
        "/markets",
        "/polymarket/search-markets",
        "/polymarket/markets/list",
    ]

    print("-" * 60)
    print("Testing Market Listing Endpoints")
    print("-" * 60)

    for endpoint in endpoints_to_test:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTrying: {endpoint}")
        
        try:
            # Try with common parameters
            params = {"limit": 10}
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  [SUCCESS] Response received!")
                    print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'List/Array'}")
                    if isinstance(data, dict) and "markets" in data:
                        print(f"  Found {len(data.get('markets', []))} markets")
                    elif isinstance(data, list):
                        print(f"  Found {len(data)} items")
                    print(f"  Sample: {json.dumps(data, indent=2)[:400]}")
                    return endpoint, data
                except:
                    print(f"  Could not parse JSON")
            elif response.status_code == 404:
                print(f"  [NOT FOUND]")
            else:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  [ERROR] {e}")

    return None, None


def test_kalshi_endpoints():
    """Test Kalshi endpoints."""
    print("\n" + "-" * 60)
    print("Testing Kalshi Endpoints")
    print("-" * 60)

    kalshi_endpoints = [
        "/kalshi/markets",
        "/kalshi/list-markets",
        "/kalshi/markets/list",
    ]

    for endpoint in kalshi_endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTrying: {endpoint}")
        
        try:
            params = {"limit": 10}
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  [SUCCESS] Response received!")
                    print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'List/Array'}")
                    if isinstance(data, dict) and "markets" in data:
                        print(f"  Found {len(data.get('markets', []))} markets")
                    elif isinstance(data, list):
                        print(f"  Found {len(data)} items")
                    print(f"  Sample: {json.dumps(data, indent=2)[:400]}")
                    return endpoint, data
                except:
                    print(f"  Could not parse JSON")
            elif response.status_code == 404:
                print(f"  [NOT FOUND]")
            else:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  [ERROR] {e}")

    return None, None


def test_orders_endpoint_without_filter():
    """Test if orders endpoint can work without filters (to see what markets exist)."""
    print("\n" + "-" * 60)
    print("Testing Orders Endpoint Behavior")
    print("-" * 60)

    url = f"{BASE_URL}/polymarket/orders"
    
    # Try without any filter (should fail per founder's message)
    print("\n1. Testing without filters (should fail):")
    try:
        response = requests.get(url, headers=HEADERS, params={"limit": 10}, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"   Error: {e}")

    # Try with token_id filter
    print("\n2. Testing with token_id filter:")
    print("   (Need a token_id from previous order test)")
    print("   This would require a token_id from an order")


if __name__ == "__main__":
    # Test Polymarket endpoints
    endpoint, data = test_endpoints()
    
    # Test Kalshi endpoints
    kalshi_endpoint, kalshi_data = test_kalshi_endpoints()
    
    # Test orders endpoint behavior
    test_orders_endpoint_without_filter()
    
    print("\n" + "=" * 60)
    print("Exploration Complete!")
    print("=" * 60)
    
    if endpoint:
        print(f"\n[FOUND] Working endpoint: {endpoint}")
    if kalshi_endpoint:
        print(f"[FOUND] Working Kalshi endpoint: {kalshi_endpoint}")
    
    print("\nNote: The Dome API provides unified access to both Polymarket and Kalshi.")
    print("You may need to use different endpoints or search methods to find markets.")

