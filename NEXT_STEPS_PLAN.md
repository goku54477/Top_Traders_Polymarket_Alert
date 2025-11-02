# Next Steps Plan - Esports Odds Alert Bot

## ✅ Completed (Current Session)

### Phase 1: ROI Calculations & Enhanced Alert Logic ✅
- ✅ ROI calculation function implemented
- ✅ Multiplier display (4.0x format) 
- ✅ Removed ROI percentage from display
- ✅ Enhanced analysis messages with variety
- ✅ Potential Return highlighted with emojis
- ✅ HTML parse mode for better formatting

### Phase 4: API Stability & Performance (Partially Complete) ✅
- ✅ Caching layer added (10 min TTL for markets, 1 min for prices)
- ✅ Enhanced error handling (404s as DEBUG, 429 with exponential backoff)
- ✅ Metrics tracking (API calls, cache hits/misses, errors)
- ✅ Enhanced logging with cycle summaries
- ✅ Rate limiting improvements (delays between calls)
- ✅ Price cache cleanup (auto-expires old entries)

### Alert Improvements ✅
- ✅ Separate alerts (one per message)
- ✅ Analysis message variety (different templates based on price/volume)
- ✅ Slug-based randomization for consistent variety per market

### Current Status
- ✅ Dota links working: `https://polymarket.com/event/{slug}`
- ✅ LoL links fix implemented: Conditional URL logic with multiple fallback options

---

## ✅ Fix LoL Links (COMPLETED)

### Issue
LoL market links use the same format as Dota (`https://polymarket.com/event/{slug}`) but don't work. Dota links work fine.

### Solution Implemented ✅
Implemented conditional URL logic that:
1. Checks for direct URL fields (`polymarket_url`, `url`, `market_url`)
2. For LoL markets: tries `/market/{condition_id}` format first
3. Falls back to `/market/{token_id}` if condition_id not available
4. Final fallback to `/event/{slug}` format
5. For Dota/other games: continues using `/event/{slug}` format (known to work)
6. Added comprehensive logging for debugging URL construction

### Investigation Steps

1. **Compare Slug Formats**
   - Check if LoL slugs have different structure than Dota slugs
   - Dota example: `dota2-team-falcons-team-liquid-...`
   - LoL example: `lol-t1-tes-2025-11-02-total-games-3pt5`
   - Look for differences in formatting, encoding, or special characters

2. **Test Different URL Formats**
   - Try `/market/{condition_id}` format for LoL specifically
   - Check if Polymarket uses different URL structure for LoL markets
   - Verify if markets exist on Polymarket (may not be created yet)

3. **Check API Response**
   - Inspect full market object for LoL markets
   - Look for `url`, `polymarket_url`, or `link` fields
   - Check if `condition_id` format works for LoL: `/market/{condition_id}`

4. **Potential Solutions**
   - Use conditional URL format: Dota uses `/event/{slug}`, LoL uses `/market/{condition_id}`
   - Or: Check if slug needs URL encoding
   - Or: Markets may not exist yet on Polymarket (need to wait)

### Implementation Approach
```python
# Pseudo-code for conditional URL format
if game_type == "League of Legends":
    if condition_id:
        polymarket_url = f"https://polymarket.com/market/{condition_id}"
    else:
        polymarket_url = f"https://polymarket.com/event/{slug}"
else:
    polymarket_url = f"https://polymarket.com/event/{slug}"
```

---

## 📋 Remaining Phase 4 Tasks

### 1. Complete Rate Limiting (Partially Done)
- ✅ Small delays between price API calls (0.05s)
- ✅ Delay between market pagination (0.1s)
- ⚠️ May need to adjust delays based on 429 error frequency
- ⚠️ Consider implementing adaptive rate limiting

### 2. Near-Miss Logging (Optional)
- Log markets that meet volume but not price threshold
- Useful for debugging and analysis
- Track markets that were close but didn't trigger alerts

### 3. Performance Monitoring
- Track slow operations (>1 second)
- Monitor cache hit rates
- Alert on high error rates (>10% API errors)

---

## 🚀 Future Enhancements

### Phase 5: Database & User Management (Deferred)
- SQLite database for alert history
- User preference storage
- Alert history tracking across restarts
- **Status**: Not needed currently, can add later

### Kalshi Integration
- Add Kalshi market monitoring
- Cross-platform price comparison
- Arbitrage opportunity detection
- **Status**: On hold until Polymarket is stable

### Additional Features
- Telegram commands (start/stop alerts, preferences)
- Market favorites/watchlist
- Price change alerts (not just extremes)
- Historical performance tracking

---

## 🐛 Known Issues

1. **LoL Links Not Working** (FIXED ✅)
   - Previous: Using `/event/{slug}` format only
   - Fixed: Implemented conditional URL logic with multiple fallback options
   - Status: Ready for testing - will try `/market/{condition_id}` or `/market/{token_id}` for LoL markets

2. **Analysis Variety** (FIXED)
   - ✅ Now using slug-based randomization
   - ✅ Different templates per price/volume range
   - Status: Working correctly

---

## 📝 Testing Checklist

Before deploying:
- [ ] Test Dota links (should work)
- [ ] Test LoL links (fix implemented, needs verification)
- [ ] Check logs to see which URL format is used for LoL markets
- [ ] Verify alerts are sent separately
- [ ] Check analysis messages vary between alerts
- [ ] Monitor cache hit rates
- [ ] Check error logs for 429/404 patterns
- [ ] Verify metrics logging is working

---

## 🔐 Security Notes

- ✅ All API keys use environment variables
- ✅ `.env` file in `.gitignore`
- ✅ Test files cleaned of hardcoded keys
- ✅ Repository is private
- ⚠️ No keys should be in git history (already cleaned)

---

## 📊 Metrics to Monitor

- **API Calls**: Should decrease with caching
- **Cache Hit Rate**: Target >50% after first cycle
- **Error Rate**: Should be <5%
- **Alert Generation**: Track per cycle
- **Cycle Time**: Should be faster with caching

---

## 🎯 Immediate Next Steps

1. **Test LoL Links Fix** (Priority 1)
   - Run bot and test LoL market links
   - Verify URLs work correctly
   - Check logs to see which URL format is being used

2. **Test Complete Flow** (Priority 2)
   - Run full test cycle
   - Verify all features working
   - Check Telegram alerts format

3. **Complete Phase 4** (Priority 3)
   - Finish remaining performance improvements
   - Add near-miss logging if desired
   - Optimize based on metrics

---

## 📚 Code Structure

### Key Files
- `app/esports_alert_bot.py` - Main bot logic
- `test_complete_flow.py` - Integration tests
- `.env` - Environment variables (not in git)
- `.gitignore` - Excludes .env and test files

### Key Functions
- `fetch_all_esports_markets()` - Fetches and filters markets (with caching)
- `fetch_price()` - Gets market price (with caching)
- `analyze_and_prepare_alerts()` - Generates alerts with variety
- `send_telegram_alerts()` - Sends one alert per message
- `format_event_info()` - Parses market data for display

### Configuration
- `CACHE_TTL_MINUTES` - Market cache TTL (default: 10 min)
- `VALUE_THRESHOLD` - Minimum ROI threshold (default: 0.04)
- `POLL_INTERVAL_MIN` - Check interval (default: 5 min)

---

## 💡 Tips for Debugging

1. **Check Logs**: Look for "LoL market" log entries to see URL construction
2. **Test URLs Manually**: Copy URLs from logs and test in browser
3. **Compare Slugs**: Check if LoL slugs differ from Dota slugs
4. **API Response**: Inspect full market object for URL fields
5. **Telegram Links**: Ensure HTML formatting is correct for links

---

**Last Updated**: 2025-11-02
**Status**: Phase 4 partially complete, LoL links fix implemented (ready for testing)


