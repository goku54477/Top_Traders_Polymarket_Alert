# Questions for Dome API Founder - Polymarket URL Format

## Current Issue

We're building an esports odds alert bot that uses the Dome API to fetch market data and generates Telegram alerts with direct links to Polymarket for trading.

**Problem:** For League of Legends markets, all alerts from the same match (e.g., "Game 1 Winner", "Game 3 Winner", "Totals") are currently linking to the same match page URL:
- Format: `https://polymarket.com/sports/league-of-legends/games/week/1/lol-t1-kt-2025-11-09`
- This works, but shows total match volume ($84k) rather than individual market volumes ($5k, $1.3k, etc.)

**Goal:** Each alert should link directly to its specific market's trade interface, not the general match page.

## Specific Questions

1. **Individual Market URLs:**
   - Does Polymarket provide direct URLs for individual markets (e.g., "Game 1 Winner", "Game 3 Winner") that are separate from the match page?
   - If yes, what is the URL format? (e.g., `/market/{condition_id}`, `/market/{token_id}`, or another format?)
   - Should we use `condition_id`, `token_id`, `yes_token_id`, `no_token_id`, or another field from the API response?

2. **Direct URL Fields in API:**
   - Does the Dome API response include a direct Polymarket URL field for each market? (We've checked for `polymarket_url`, `url`, `market_url` but want to confirm if these exist or if there's another field name)

3. **URL Format Verification:**
   - For LoL markets, we're currently using: `/sports/league-of-legends/games/week/1/{match-slug}`
   - Is there a way to append market-specific identifiers to this URL to jump to specific markets?
   - Do URL fragments/anchors work? (e.g., `#game1-winner`, `#moneyline`)

4. **Dota vs LoL URL Differences:**
   - We successfully use `/event/{slug}` format for Dota markets - why doesn't this work for LoL?
   - Is there a different URL structure for LoL markets vs other esports?

5. **Token ID vs Condition ID:**
   - We currently use `yes_token_id` and `no_token_id` for price fetching via `/market-price/{token_id}`
   - Should we use these same IDs for constructing market URLs, or is `condition_id` the correct field?

## Current Implementation

- **Working:** Match page URLs for LoL (e.g., `https://polymarket.com/sports/league-of-legends/games/week/1/lol-t1-kt-2025-11-09`)
- **Working:** Direct market URLs for Dota (e.g., `https://polymarket.com/event/dota2-ty-flc-2025-11-02`)
- **Not Working:** Direct market URLs for LoL using `/market/{condition_id}` or `/market/{token_id}` (returns 404)
- **Not Working:** LoL URLs using `/event/{slug}` format (returns 404)

## Example Market Data We Receive

```json
{
  "market_slug": "lol-t1-kt-2025-11-09-game1",
  "title": "LoL: T1 vs KT Rolster - Game 1 Winner",
  "condition_id": "0x7cbff757e13b49f08d302faba9f7cb6bf17586918006f182d17bdea6d2692578",
  "token_id": "...",
  "yes_token_id": "...",
  "no_token_id": "...",
  "volume_total": 5000,
  "volume_1_week": 5000
}
```

**What we need:** The correct URL format to link directly to this specific "Game 1 Winner" market, not just the match page.

## Alternative Solution (If Direct URLs Don't Exist)

If Polymarket doesn't support direct market URLs, we'll:
- Keep linking to the match page (which works)
- Enhance alert messages to clearly indicate which specific market the alert is for
- Accept that volume displayed will be match total, not individual market volume

---

**Thank you for any guidance you can provide!**

