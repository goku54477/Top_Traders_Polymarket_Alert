# BNB Testnet Hackathon Setup Guide

## Quick Start (Hackathon Ready in <1 Hour)

### Step 1: Get BNB Testnet Ready (10 minutes)

1. **Setup MetaMask for BNB Testnet**
   - Open MetaMask
   - Add Network → Manual
   - Network Name: `BNB Smart Chain Testnet`
   - RPC URL: `https://bsc-testnet.bnbchain.org`
   - Chain ID: `97`
   - Currency Symbol: `tBNB`
   - Block Explorer: `https://testnet.bscscan.com`

2. **Get Test BNB**
   - Visit: https://testnet.bnbchain.org/faucet-smart
   - Connect your MetaMask wallet
   - Claim 1 tBNB (free, renewable every 24h)

3. **Export Your Private Key**
   - MetaMask → Account Details → Export Private Key
   - **IMPORTANT**: Only use testnet wallets! Never mainnet keys!
   - Copy the private key (starts with 0x...)

### Step 2: Deploy Smart Contract (15 minutes)

1. **Open Remix IDE**
   - Go to: https://remix.ethereum.org

2. **Create Contract File**
   - Create new file: `contracts/EsportsOracle.sol`
   - Copy contents from `contracts/EsportsOracle.sol` in this repo

3. **Compile**
   - Click "Solidity Compiler" (left sidebar)
   - Select compiler version: `0.8.20`
   - Click "Compile EsportsOracle.sol"

4. **Deploy to BNB Testnet**
   - Click "Deploy & Run Transactions" (left sidebar)
   - Environment: Select "Injected Provider - MetaMask"
   - MetaMask will prompt to switch to BNB Testnet
   - Click "Deploy"
   - Confirm transaction in MetaMask
   - Wait ~3 seconds for confirmation

5. **Copy Contract Address**
   - In Remix, under "Deployed Contracts"
   - Copy the contract address (0x...)
   - Also copy the ABI (click ABI button)

### Step 3: Configure Environment (5 minutes)

1. **Update .env file**
   ```bash
   # Add these lines to your .env file
   BNB_RPC_URL=https://bsc-testnet.bnbchain.org
   BNB_PRIVATE_KEY=0xyour_testnet_private_key_here
   BNB_CONTRACT_ADDRESS=0xcontract_address_from_remix
   ```

2. **Install Dependencies**
   ```bash
   pip install web3 eth-account
   ```

### Step 4: Run the Bridge (5 minutes)

1. **Test the Bridge**
   ```bash
   python app/bnb_oracle_bridge.py
   ```

2. **What Happens:**
   - ✅ Fetches Sharky's latest positions (≤72h, ≥$300)
   - ✅ Creates markets on BNB Testnet
   - ✅ Resolves markets with YES/NO outcomes
   - ✅ Outputs BscScan transaction URLs

3. **Verify on BscScan**
   - Visit: https://testnet.bscscan.com
   - Search for your contract address
   - See all transactions (market creations and resolutions)

## Demo Flow for Judges

### 1. Show Off-Chain Edge
- Run: `python test_sharky_telegram.py`
- Show Telegram alerts with Sharky's latest trades
- Explain: "Our bot tracks top traders on Polymarket"

### 2. Bridge to BNB
- Run: `python app/bnb_oracle_bridge.py`
- Show console output with transaction hashes
- Explain: "We bring this edge on-chain via BNB oracle"

### 3. Show On-Chain Proof
- Open BscScan testnet
- Show market creation and resolution transactions
- Explain: "Verifiable, transparent resolution on BNB"

### 4. Highlight Value Prop
- **Problem**: Centralized prediction markets, no on-chain verification
- **Solution**: Decentralized oracle on BNB bringing trader signals on-chain
- **Market**: Low-liquidity esports markets with proven edge
- **Revenue**: Oracle fees, market maker rebates (future)

## Architecture Overview

```
┌─────────────────┐
│  Polymarket API │ (Off-chain source)
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Python Bot     │ Fetch top trader positions
│  (Off-chain)    │ Filter: ≤72h, ≥$300
└────────┬────────┘
         │
         v
┌─────────────────┐
│  BNB Bridge     │ Create markets on-chain
│  (Python+Web3)  │ Resolve with trader outcomes
└────────┬────────┘
         │
         v
┌─────────────────┐
│ EsportsOracle   │ Smart contract on BNB Testnet
│ (Solidity)      │ Chain ID: 97
└─────────────────┘
```

## Key Features

✅ **Zero Gas Cost** - BNB Testnet (free tBNB from faucet)
✅ **Fast Deployment** - Remix IDE (no local setup)
✅ **Verifiable** - All resolutions on-chain (BscScan)
✅ **Fresh Signals** - Only positions ≤72 hours old
✅ **Minimum Stake** - Only positions ≥$300 (quality filter)
✅ **Top Trader** - Sharky6999 (proven track record)

## Troubleshooting

### "Transaction Failed" in MetaMask
- **Solution**: Ensure you have enough tBNB (get from faucet)

### "Contract not found"
- **Solution**: Verify BNB_CONTRACT_ADDRESS in .env is correct

### "No positions match criteria"
- **Solution**: Temporarily lower thresholds or check if Sharky has recent trades

### "Web3 connection failed"
- **Solution**: Check BNB_RPC_URL is correct: https://bsc-testnet.bnbchain.org

## Next Steps (After Hackathon)

1. **Add More Traders** - Track multiple wallets
2. **Betting Interface** - Frontend for users to bet on markets
3. **Mainnet Deployment** - Move to BNB mainnet with fees
4. **Oracle Network** - Decentralize resolution via multiple validators
5. **Revenue Model** - Market maker rebates + oracle fees

## Resources

- **BNB Testnet Faucet**: https://testnet.bnbchain.org/faucet-smart
- **BscScan Testnet**: https://testnet.bscscan.com
- **Remix IDE**: https://remix.ethereum.org
- **Web3.py Docs**: https://web3py.readthedocs.io
