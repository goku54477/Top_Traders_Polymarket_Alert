"""
BNB Testnet Oracle Bridge
Bridges Polymarket trader signals to BNB Testnet smart contract
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timezone

from web3 import Web3
from eth_account import Account

# Ensure we can import from app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from trader_tracker_bot import fetch_trader_positions, parse_position

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Environment variables (add to .env)
# BNB_RPC_URL=https://bsc-testnet.bnbchain.org
# BNB_PRIVATE_KEY=0x... (testnet key)
# BNB_CONTRACT_ADDRESS=0x... (deployed EsportsOracle address)

BNB_RPC_URL = os.getenv("BNB_RPC_URL", "https://bsc-testnet.bnbchain.org")
PRIVATE_KEY = os.getenv("BNB_PRIVATE_KEY", "")
CONTRACT_ADDRESS = os.getenv("BNB_CONTRACT_ADDRESS", "")

# EsportsOracle ABI - paste from Remix after compilation
ESPORTS_ORACLE_ABI = json.loads(r'''[
  {"inputs":[],"stateMutability":"nonpayable","type":"constructor"},
  {"anonymous":false,"inputs":[
    {"indexed":true,"internalType":"uint256","name":"id","type":"uint256"},
    {"indexed":true,"internalType":"bytes32","name":"eventId","type":"bytes32"},
    {"indexed":false,"internalType":"string","name":"eventName","type":"string"},
    {"indexed":false,"internalType":"uint256","name":"endTime","type":"uint256"},
    {"indexed":false,"internalType":"address","name":"creator","type":"address"}],
   "name":"MarketCreated","type":"event"},
  {"anonymous":false,"inputs":[
    {"indexed":true,"internalType":"uint256","name":"id","type":"uint256"},
    {"indexed":false,"internalType":"bool","name":"outcome","type":"bool"},
    {"indexed":false,"internalType":"address","name":"resolver","type":"address"},
    {"indexed":false,"internalType":"uint256","name":"resolvedAt","type":"uint256"}],
   "name":"MarketResolved","type":"event"},
  {"inputs":[],"name":"marketCount","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"name":"marketIdByEventId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"bytes32","name":"eventId","type":"bytes32"},{"internalType":"string","name":"eventName","type":"string"},{"internalType":"uint256","name":"endTime","type":"uint256"}],"name":"createMarket","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"id","type":"uint256"},{"internalType":"bool","name":"outcome","type":"bool"}],"name":"resolveMarket","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"internalType":"bytes32","name":"eventId","type":"bytes32"}],"name":"getMarketByEvent","outputs":[{"internalType":"bool","name":"exists","type":"bool"},{"internalType":"uint256","name":"id","type":"uint256"},{"internalType":"bytes32","name":"_eventId","type":"bytes32"},{"internalType":"string","name":"eventName","type":"string"},{"internalType":"uint256","name":"endTime","type":"uint256"},{"internalType":"bool","name":"resolved","type":"bool"},{"internalType":"bool","name":"outcome","type":"bool"},{"internalType":"address","name":"creator","type":"address"},{"internalType":"uint256","name":"createdAt","type":"uint256"},{"internalType":"uint256","name":"resolvedAt","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"resolver","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"address","name":"_resolver","type":"address"}],"name":"setResolver","outputs":[],"stateMutability":"nonpayable","type":"function"}
]''')

def keccak_text(text: str) -> bytes:
    """Generate event ID from text using keccak256"""
    return Web3.keccak(text=text)

def ts_to_str(ts: float) -> str:
    """Convert timestamp to readable UTC string"""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def connect_web3():
    """Connect to BNB Testnet and return web3, account, and contract instances"""
    w3 = Web3(Web3.HTTPProvider(BNB_RPC_URL))
    
    if not w3.is_connected():
        raise ConnectionError("Failed to connect to BNB Testnet")
    
    logging.info(f"Connected to BNB Testnet: {BNB_RPC_URL}")
    
    acct = Account.from_key(PRIVATE_KEY)
    logging.info(f"Using account: {acct.address}")
    
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS), 
        abi=ESPORTS_ORACLE_ABI
    )
    
    return w3, acct, contract

def ensure_market(contract, w3, acct, event_id_bytes: bytes, event_name: str, end_time: int) -> int:
    """Create market if doesn't exist, return market ID"""
    # Check if market exists
    exists, id_, *_ = contract.functions.getMarketByEvent(event_id_bytes).call()
    
    if exists and id_ != 0:
        logging.info(f"Market already exists with ID: {id_}")
        return id_
    
    # Create new market
    logging.info(f"Creating new market: {event_name[:50]}...")
    
    tx = contract.functions.createMarket(event_id_bytes, event_name, end_time).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 400000,
        "maxFeePerGas": w3.to_wei("2", "gwei"),
        "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        "chainId": 97
    })
    
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    
    logging.info(f"Transaction sent: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    logging.info(f"Market created! Gas used: {receipt['gasUsed']}")
    
    # Query ID again
    exists2, id2, *_ = contract.functions.getMarketByEvent(event_id_bytes).call()
    return id2 if exists2 else 0

def resolve_market(contract, w3, acct, id_: int, outcome_yes: bool):
    """Resolve a market with YES or NO outcome"""
    logging.info(f"Resolving market ID {id_} with outcome: {'YES' if outcome_yes else 'NO'}")
    
    tx = contract.functions.resolveMarket(id_, outcome_yes).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 250000,
        "maxFeePerGas": w3.to_wei("2", "gwei"),
        "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        "chainId": 97
    })
    
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    
    logging.info(f"Resolution transaction sent: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    logging.info(f"Market resolved! Gas used: {receipt['gasUsed']}")
    
    return tx_hash.hex()

def run_bridge_for_sharky():
    """Main bridge function - fetch Sharky's positions and bridge to BNB"""
    # Filters (same as main bot)
    time_threshold = 72 * 60 * 60  # 72 hours
    value_threshold = 300.0  # $300 minimum

    SHARKY_USERNAME = "Sharky6999"
    SHARKY_WALLET = "0x751a2b86cab503496efd325c8344e10159349ea1"

    print("\n" + "="*80)
    print("  BNB TESTNET ORACLE BRIDGE - SHARKY POSITIONS")
    print("="*80 + "\n")

    # Connect to BNB Testnet
    w3, acct, contract = connect_web3()
    
    # Get contract info
    owner = contract.functions.owner().call()
    market_count = contract.functions.marketCount().call()
    logging.info(f"Contract owner: {owner}")
    logging.info(f"Total markets created: {market_count}\n")

    # Fetch Sharky's positions
    logging.info("Fetching Sharky's positions from Polymarket...")
    positions = fetch_trader_positions(SHARKY_WALLET)
    
    if not positions:
        logging.error("No positions found")
        return
    
    logging.info(f"Found {len(positions)} total positions\n")

    now_ts = time.time()
    valid = []
    
    # Filter positions
    for p in positions:
        parsed = parse_position(p, SHARKY_USERNAME)
        if not parsed:
            continue
        
        # Check timestamp and freshness (72h)
        entry_ts = parsed.get("entry_timestamp", 0)
        if not entry_ts or (now_ts - entry_ts) > time_threshold:
            continue
        
        # Check minimum value ($300)
        if float(parsed.get("current_value", 0)) < value_threshold:
            continue
        
        valid.append(parsed)

    if not valid:
        logging.warning("No positions match criteria (≤72h, ≥$300)")
        return

    logging.info(f"Found {len(valid)} positions matching criteria")
    
    # Sort by newest first, take top 3 for demo
    valid.sort(key=lambda x: x.get("entry_timestamp", 0), reverse=True)
    top = valid[:3]
    
    logging.info(f"Processing top {len(top)} positions\n")

    # Process each position
    for i, pos in enumerate(top, 1):
        print("-" * 80)
        market_slug = pos.get("market_slug") or pos.get("event_slug") or pos.get("market_title", "Unknown")
        event_id = keccak_text(str(market_slug))
        event_name = pos.get("market_title", "Unknown Market")
        
        # Set end_time to now + 24h for demo purposes
        end_time = int(now_ts + 86400)

        logging.info(f"[{i}/{len(top)}] {event_name}")
        logging.info(f"    Outcome: {pos.get('outcome')}")
        logging.info(f"    Entry Time: {ts_to_str(pos.get('entry_timestamp', now_ts))}")
        logging.info(f"    Current Value: ${pos.get('current_value', 0):,.2f}")
        logging.info(f"    P&L: ${pos.get('cash_pnl', 0):,.2f}")

        # Create/get market on BNB
        market_id = ensure_market(contract, w3, acct, event_id, event_name, end_time)
        logging.info(f"    ✅ On-chain Market ID: {market_id}")

        # Resolve with trader's outcome
        outcome_yes = str(pos.get("outcome", "")).upper() == "YES"
        tx_hash = resolve_market(contract, w3, acct, market_id, outcome_yes)
        
        bscscan_url = f"https://testnet.bscscan.com/tx/{tx_hash}"
        logging.info(f"    ✅ Resolved on BNB Testnet!")
        logging.info(f"    🔗 View on BscScan: {bscscan_url}\n")

    print("=" * 80)
    logging.info(f"✅ Bridge complete! {len(top)} positions bridged to BNB Testnet")
    print("=" * 80)

if __name__ == "__main__":
    # Safety checks
    if not PRIVATE_KEY or PRIVATE_KEY == "":
        print("\n❌ Error: BNB_PRIVATE_KEY not set in .env file")
        print("\nSet up your .env file with:")
        print("BNB_RPC_URL=https://bsc-testnet.bnbchain.org")
        print("BNB_PRIVATE_KEY=your_testnet_private_key")
        print("BNB_CONTRACT_ADDRESS=deployed_contract_address")
        raise SystemExit(1)
    
    if not CONTRACT_ADDRESS or CONTRACT_ADDRESS == "":
        print("\n❌ Error: BNB_CONTRACT_ADDRESS not set in .env file")
        print("\nDeploy the EsportsOracle.sol contract on BNB Testnet first!")
        print("Then add the address to your .env file")
        raise SystemExit(1)
    
    run_bridge_for_sharky()
