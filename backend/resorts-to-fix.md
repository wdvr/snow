# Resorts Needing Manual Review

Generated: 2026-02-19

These resorts were excluded from the automated validation pass and need manual review before being added to production.

## Excluded Resorts

| Resort ID | Name | Reason |
|-----------|------|--------|
| `canada-olympic-park-calgary` | Canada Olympic Park (WinSport) | Training facility, not a destination ski resort |
| `craigleith-ski-club` | Craigleith Ski Club | Private members-only ski club |
| `osler-bluff-ski-club` | Osler Bluff Ski Club | Private members-only ski club |
| `fortress-mountain` | Fortress Mountain | Closed since 2004 (potential reopening TBD) |

## Notes

- **Private clubs**: Craigleith and Osler Bluff are private clubs near Collingwood, ON. They don't publish public snow reports, so our weather validation pipeline can't verify them. Could be added later if they become relevant.
- **WinSport/COP**: Canada Olympic Park in Calgary is primarily a training facility with a small ski hill. It's more of a local park than a destination resort.
- **Fortress Mountain**: Closed since 2004. A development group has announced plans to reopen, but no timeline confirmed. Re-evaluate when/if it reopens.

## Data Quality Notes for Added Resorts

The following issues were observed during validation and should be monitored:

### Elevation Data
The scraped `elevation_base_m` values from skiresort.info appear to represent **vertical drop** rather than actual base elevation for many resorts. For example:
- Alta shows base 200m (actual: ~2600m)
- Vail shows base 300m (actual: ~2475m)

This doesn't affect snow quality calculations since we use coordinates + Open-Meteo elevation-aware API, but the displayed elevation ranges will be incorrect until corrected.

### Coordinates Fixed During Validation
These resorts had clearly wrong coordinates in the scraped data that were manually corrected:
- Aspen Highlands (was in Portland, OR area)
- Beaver Creek (was near Denver instead of Vail)
- Brighton (was near Denver instead of Cottonwood Canyons, UT)
- Buttermilk Mountain (was in Alabama)
- Mont-Sainte-Anne (was in Montreal area instead of Quebec City)
- Solitude (was in eastern UT instead of Cottonwood Canyons)
- Sugarloaf (was in southern NY instead of Maine)
- Wolf Creek (was in western NY instead of southern CO)
