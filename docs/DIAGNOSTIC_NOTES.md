# Diagnostic Investigation: Why Only CS Markets Are Showing

## What We've Done

1. ✅ Created `diagnose_markets.py` - A comprehensive diagnostic script that will:
   - Fetch markets from Dome API
   - Show the exact data structure returned
   - Test the filtering logic step-by-step
   - Categorize markets by game type (CS, LoL, Dota, Valorant, etc.)
   - Show which markets pass/fail filters and why
   - Provide recommendations for fixes

## Current Filtering Logic Analysis

From `app/esports_alert_bot.py`, the filtering works as follows:

1. **Fetches from**: `/polymarket/markets` endpoint
2. **Filtering Process**:
   - Checks title and slug (lowercase) against keywords
   - Uses `ESPORTS_KEYWORDS` and `ESPORTS_SPECIFIC_KEYWORDS`
   - Excludes markets matching `NON_ESPORTS_KEYWORDS`
   - Only includes markets with `is_esports=True` and `is_non_esports=False`

3. **Current Keywords**:
   - General: "esports", "dota", "valorant", "league of legends", "counter-strike", "cs2", "csgo", etc.
   - Specific: "lol", team names like "t1", "g2", "fnatic", etc.

## Possible Issues

1. **Keyword Matching**: CS keywords ("cs", "cs2", "csgo", "counter-strike") might be more common in market titles
2. **Title Format**: Other esports might use different naming conventions
3. **Case Sensitivity**: Already handled (converting to lowercase)
4. **NON_ESPORTS_KEYWORDS**: Might be too aggressive and excluding valid esports markets
5. **Market Volume**: The bot also filters by volume > $1000, which might exclude smaller esports

## Next Steps

To run the diagnostic and see what's actually happening:

```powershell
# Set your API key
$env:DOME_API_KEY="your_dome_api_key_here"

# Run the diagnostic
python diagnose_markets.py
```

The diagnostic will show:
- What markets are actually in the API response
- Which keywords match which markets
- How many markets pass/fail the filter
- Breakdown by game type
- Specific examples of why markets fail

## What the Diagnostic Will Reveal

1. **Market Structure**: What fields Dome API returns (title, slug, category, tags, etc.)
2. **Keyword Effectiveness**: Which keywords actually match markets
3. **Game Distribution**: How many markets exist for each game type
4. **Filter Performance**: Why markets pass or fail
5. **Recommendations**: Specific fixes needed

## After Running Diagnostic

Once we see the results, we can:
1. Adjust keywords if needed
2. Fix any filtering logic issues
3. Add missing game-specific terms
4. Relax or tighten NON_ESPORTS_KEYWORDS
5. Potentially use category/tags fields if Dome API provides them

## Files Ready

- ✅ `diagnose_markets.py` - Ready to run (needs API key)
- ✅ `app/esports_alert_bot.py` - Current bot code (to be fixed based on findings)


