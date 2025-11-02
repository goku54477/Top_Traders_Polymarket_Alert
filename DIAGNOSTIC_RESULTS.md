# Diagnostic Results Analysis

## Key Findings

### Market Distribution
- **Counter-Strike**: 20 markets found
- **Dota 2**: 2 markets found  
- **League of Legends**: 2 markets found (LoL T1 vs TES)
- **Valorant**: 1 market found
- **Total Esports**: 25 markets found in sample

### Problems Identified

1. **False Positives**: Filter is letting through NON-esports markets:
   - Marathons (Joe Klecker, Alexander Mutiso)
   - Horse Racing (Breeders Cup Classic)
   - College Football (Cincinnati vs Utah)

2. **Keyword Issues**:
   - "tes" matches 26 markets - could be "Top Esports" (LoL team) OR false matches
   - "ti" matches 46 markets - likely "The International" (Dota tournament)
   - Many esports markets categorized as "Unknown" (975 out of 1000)

3. **Filter Too Permissive**:
   - 22 markets passed filter but some are non-esports
   - Need better exclusion logic

### Positive Findings

1. **Tags Field Available**: Markets have a `tags` array that could help filtering
2. **Esports Markets Exist**: Found markets for CS, Dota, LoL, Valorant
3. **Volume Data**: Can use `volume_total` for filtering

## Recommendations

### Immediate Fixes Needed

1. **Fix NON_ESPORTS_KEYWORDS**:
   - Add: "marathon", "breeders cup", "college football", "cfb", "ncaa"
   - Add more sports: "horse racing", "racing"

2. **Improve Keyword Matching**:
   - "tes" is too broad - use "top esports" or check context
   - "ti" needs context checking (Dota 2 International)
   - Add more specific team names and tournaments

3. **Use Tags Field**:
   - Check if tags contain esports-related terms
   - Exclude tags like "Crypto", "Up or Down", "Recurring" for non-esports

4. **Better Game Detection**:
   - Check slug patterns: "cs2-", "dota2-", "lol-"
   - Check title patterns more carefully

## Next Steps

1. Update filtering logic with better exclusions
2. Add tags-based filtering
3. Improve keyword matching for LoL markets
4. Test with updated filters


