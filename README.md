# jumpstart

## Data refresh

- Refresh all known set data: `python3 scripts/refresh_data.py`
- Refresh one set: `python3 scripts/refresh_data.py fmsc`
- If `<set>-owned.txt` exists, generated data keeps the full set and marks unowned packs with `excludedFromRandomizer: true`
- Owned-list entries are validated against the set's Scryfall pack names during refresh
- Owned files can use `Name#Number` to target a specific collector number when a set has duplicate pack names