# Powder Chaser Bug Tracker

## API Stability & Backend Tests

**Audit Date:** 2026-02-26
**Auditor:** Stability audit agent

### Backend Tests

**Result: ALL 1563 TESTS PASSING**
- Platform: Python 3.14.2, pytest 9.0.2
- Runtime: 11.90s
- Test files: 42 test modules
- Zero failures, zero errors, zero warnings

### Production API Endpoints (api.powderchaserapp.com)

| # | Endpoint | Status | Notes |
|---|----------|--------|-------|
| 1 | `GET /health` | OK | `healthy`, env=`prod` |
| 2 | `GET /api/v1/regions` | OK | 8 regions returned (na_west, na_rockies, na_east, alps, scandinavia, japan, oceania, south_america) |
| 3 | `GET /api/v1/resorts?limit=5` | **BUG** | `limit` param ignored -- returns ALL 1040 resorts regardless of limit value |
| 4 | `GET /api/v1/resorts?region=alps&limit=5` | **BUG** | `limit` param ignored with region filter too -- returns all 633 alps resorts |
| 5 | `GET /api/v1/resorts/nearby` | OK | 4 resorts returned for lat=46.8, lon=6.9, radius=100 |
| 6 | `GET /api/v1/resorts/:id` | OK | Returns full resort detail (Whistler Blackcomb) |
| 7 | `GET /api/v1/resorts/:id/conditions` | OK | Returns list of 3 elevation conditions (mid, top, base) |
| 8 | `GET /api/v1/resorts/:id/conditions/mid` | OK | 36 fields returned, snow_depth=241.3cm |
| 9 | `GET /api/v1/resorts/:id/snow-quality` | OK | quality=mediocre, score=56 |
| 10 | `GET /api/v1/resorts/:id/timeline` | OK | 63 entries with hourly forecast data |
| 11 | `GET /api/v1/resorts/:id/history` | OK | 2 history entries + season_summary |
| 12 | `GET /api/v1/snow-quality/batch` | OK | 3 resorts returned with quality ratings |
| 13 | `GET /api/v1/conditions/batch` | OK | 2 resorts returned |
| 14 | `GET /api/v1/quality-explanations` | OK | 2 keys: `explanations` + `algorithm_info` |
| 15 | `GET /api/v1/recommendations/best` | OK | 10 recommendations returned |
| 16 | `GET /api/v1/resorts/:id/condition-reports` | OK | 1 report returned with summary |
| 17 | `POST /api/v1/auth/guest` | OK | Returns `access_token`, `refresh_token`, `user`, `expires_in` |

### Staging API (staging.api.powderchaserapp.com)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /health` | OK | `healthy`, env=`staging` |
| `GET /api/v1/resorts/whistler-blackcomb/snow-quality` | OK | quality=decent, score=57 |
| `GET /api/v1/resorts?limit=1` | OK | Returns resorts (same limit bug present) |

### Staging vs Production Parity

| Resort | Prod Quality | Staging Quality | Prod Score | Staging Score | Delta |
|--------|-------------|-----------------|-----------|--------------|-------|
| Whistler Blackcomb | mediocre | decent | 56 | 57 | 1 point |
| Vail | bad | bad | 13 | 14 | 1 point |

**Assessment:** Scores are within 1-2 points between staging and prod. The minor differences are expected due to slightly different weather data refresh times. Quality labels can differ when a score is on a boundary (56 vs 57 crossing mediocre/decent threshold). No significant parity issues.

### Error Handling

| Test Case | HTTP Code | Response | Assessment |
|-----------|-----------|----------|------------|
| Non-existent resort | 404 | `{"detail":"Resort nonexistent-resort-12345 not found"}` | OK -- proper error |
| Invalid region | 400 | `{"detail":"Invalid region. Must be one of: [...]"}` | OK -- helpful error with valid options |
| Empty batch resort_ids | 400 | `{"detail":"No resort IDs provided"}` | OK -- proper validation |
| Very long resort ID (500 chars) | 404 | `{"detail":"Resort xxx...xxx not found"}` | MINOR -- echoes the full 500-char input back. Should truncate or reject oversized input for security (potential log injection/DoS vector). |

### Bugs Found

#### BUG-001: `limit` parameter ignored on `/api/v1/resorts` endpoint (CONFIRMED)
- **Severity:** Medium
- **Impact:** Every call to `/api/v1/resorts` returns ALL 1040 resorts (~1.4MB payload) regardless of `limit` param
- **Reproduction:** `curl "https://api.powderchaserapp.com/api/v1/resorts?limit=1"` returns 1040 resorts
- **Also affects:** Region-filtered queries (`?region=alps&limit=5` returns all 633 alps resorts)
- **Note:** The `nearby` endpoint correctly limits results, so the bug is specific to the main resorts list
- **Performance impact:** Clients always download the full resort catalog. Mobile clients on slow connections will experience unnecessary latency and data usage.
- **Present on:** Both prod and staging

#### BUG-002: Very long resort ID echoed in error response (LOW)
- **Severity:** Low
- **Impact:** A 500-character resort ID is fully echoed in the 404 error response. Should truncate or validate input length.
- **Risk:** Minor log pollution / potential abuse vector. Not a critical security issue but violates input validation best practices.

### Summary

- **Backend tests:** 1563/1563 passing (100%)
- **API endpoints:** 17/17 responding correctly
- **Bugs found:** 1 medium (limit ignored), 1 low (input not truncated)
- **Staging/prod parity:** Good (scores within 1-2 points)
- **Error handling:** Good (proper HTTP codes, helpful messages)
- **Overall stability:** GOOD -- all endpoints functional, no 500 errors, no timeouts

---

## Snow Quality & Prediction Audit

**Audit Date:** 2026-02-26
**Auditor:** Quality verification agent
**Data Source:** Production API (api.powderchaserapp.com)

### 1. Batch Quality Response Validation

Requested 20 resorts, received 18. **2 resorts missing from static JSON:**

| Missing Resort | Notes |
|----------------|-------|
| `niseko-united` | Resort exists as `niseko` but batch uses `niseko-united` which is not in static JSON |
| `big-sky` | Not present in static JSON at all |

**Also missing from batch endpoint (European/other):**
- `cortina-dampezzo`, `kitzbuhel`, `val-thorens`, `laax`, `cervinia`, `mayrhofen` -- all returned empty from batch
- Only 3 of 10 requested European resorts returned data (courchevel, st-anton, verbier)

### 2. Quality Score Sanity Check Failures

#### BUG-003: Scores too low for resorts with significant fresh snow and cold temps (HIGH)

The rule "fresh > 10cm AND temp < 0C should score >= 60" fails for multiple resorts:

| Resort | Fresh Snow | Temp | Score | Expected | Issue |
|--------|-----------|------|-------|----------|-------|
| whistler-blackcomb | 19.5cm | -2.8C | 56 | 60+ | Borderline -- wind gusts (75 km/h) and low visibility are dragging it down |
| big-white | 16.1cm | -6.2C | 53 | 60+ | 16cm fresh at -6C should be decent at minimum |
| lake-louise | 21.0cm | -7.5C | 26 | 60+ | **Most egregious.** 21cm fresh at -7.5C scored as "poor" (26). Wind gusts (76 km/h) tank the score but 21cm fresh powder should not be "poor" |

**Root cause for Lake Louise:** `hours_since_last_snowfall` is `None` for all elevations. This missing feature may cause the ML model to produce lower scores. Additionally, `snowfall_after_freeze_cm=20.97` at mid (meaning 21cm fell after the last freeze), yet the batch explanation says "Hard packed surface with 21cm of aged snow" -- this is contradictory. The snow is NOT aged if it fell after the freeze.

#### BUG-004: Jackson Hole mid-elevation scores "great" (4.39) with only 0.1cm fresh snow (MEDIUM)

- **Mid elevation:** score=4.39 (great), fresh=0.1cm, temp=-7.5C, depth=40.64cm, `last_freeze_thaw_hours_ago=16h`, `max_consecutive_warm_hours=4h`
- **Top elevation:** score=4.40 (great), fresh=40.6cm, temp=-12.6C -- this makes sense
- **Issue:** Mid has nearly zero fresh snow and a recent thaw-freeze cycle. The ML model gives it "great" quality purely based on cold temperature. A score of 4.39 with 0.1cm of fresh snow and a 16h-old freeze-thaw is unrealistic. This is a "firm groomed" surface at best, not "great."
- **Batch uses mid elevation** so the app shows Jackson Hole as "great" (score=79) which is misleading.

#### BUG-005: Aspen-Snowmass explanation says "Not skiable: insufficient snow cover" but has 81cm base (MEDIUM)

- **Mid elevation:** depth=81.28cm, temp=2.4C, score=1.33 (bad)
- **Explanation in batch:** "Not skiable: insufficient snow cover"
- **Reality:** 81cm is a perfectly skiable base depth. The issue is warm temps (12.1C at base) and freeze-thaw, not insufficient snow cover. The explanation text is wrong/misleading.

#### BUG-006: Breckenridge depth mismatch between static JSON and conditions endpoint (HIGH)

- **Static JSON (batch):** `snow_depth_cm=9.0` -- explanation says "Thin 9cm base"
- **Conditions endpoint (live):** mid=64.0cm, top=78.0cm, base=50.0cm
- **None of the condition elevations show 9cm.** The static JSON has stale or corrupted depth data for Breckenridge.
- Same issue potentially affects Telluride: batch shows 9.0cm but conditions show mid=9.0cm, base=1.0cm, top=33.0cm. In this case mid=9cm matches, but `base=1.0cm` in late February is concerning.

### 3. Zero/Extremely Low Snow Depth Issues

#### BUG-007: Sun Peaks shows 0.0cm snow depth at all elevations (HIGH)

- **All elevations:** depth=0.0cm, quality=bad (score=16 in batch)
- **Reality:** Sun Peaks is a major BC resort that typically has 200+ cm base in late February
- **Source data:** Only 2 sources (open-meteo + weatherkit), both show 0cm 24h snowfall. The depth reading is clearly wrong -- Open-Meteo likely doesn't have snow depth for this resort.
- **Impact:** Users see Sun Peaks as having zero snow, which is objectively false.

| Resort | Batch Depth | Notes |
|--------|------------|-------|
| sun-peaks | 0.0cm | Major BC resort, should have 200+ cm |
| breckenridge | 9.0cm (batch) vs 64cm (live) | Static JSON stale/corrupted |
| telluride | 9.0cm (mid) / 1.0cm (base) | Extremely thin for late Feb |
| jackson-hole | 40.64cm | Low for late Feb |
| alta | 46.0cm | Low for late Feb |

### 4. Timeline Prediction Stability Issues

#### BUG-008: Champagne powder forecast with zero snowfall (CRITICAL)

**Whistler timeline:**
```
Mar 1 afternoon: score=3.6 (good),     depth=163cm, snowfall=0.0cm
Mar 2 morning:   score=6.0 (champagne), depth=161cm, snowfall=0.0cm  <-- IMPOSSIBLE
Mar 2 midday:    score=5.9 (champagne), depth=161cm, snowfall=0.0cm
Mar 2 afternoon: score=4.7 (excellent), depth=160cm, snowfall=0.0cm
Mar 3 morning:   score=2.4 (poor),      depth=158cm, snowfall=0.0cm  <-- 2.3 point drop
```

- Score jumps from 3.6 to 6.0 overnight with ZERO snowfall and DECREASING depth
- "Champagne powder" requires actual fresh dry snow. This is physically impossible without snowfall.
- The score then crashes from 4.7 to 2.4 the next morning -- a 2.3-point swing with no weather event

**Niseko timeline (same bug):**
```
Feb 22 afternoon: score=3.2 (mediocre), depth=78cm, snowfall=0.0cm
Feb 23 morning:   score=6.0 (champagne), depth=76cm, snowfall=0.0cm  <-- IMPOSSIBLE
Feb 23 midday:    score=6.0 (champagne), depth=75cm, snowfall=0.0cm
Feb 23 afternoon: score=5.0 (powder_day), depth=75cm, snowfall=0.0cm
Feb 24 morning:   score=3.5 (decent),   depth=73cm, snowfall=0.0cm
Feb 24 midday:    score=1.6 (bad),       depth=72cm, snowfall=0.0cm  <-- 3.4 point drop in 6h
```

- The `score_change_reason` for the Niseko jump says "Cooling to -5C firms up snow" -- this does NOT justify a jump to champagne powder (6.0).
- The subsequent crash from 5.0 to 1.6 in 6 hours is unrealistic.

**Root cause hypothesis:** The timeline forecast may be using a different code path or model that doesn't properly constrain quality labels to require fresh snowfall. The `quality_score` and `snow_score` are also diverging wildly (snow_score=48 but quality_score=6.0 on Niseko Feb 23).

### 5. Best Conditions Recommendations Issues

#### BUG-009: Best recommendations dominated by resorts with bogus elevation data (CRITICAL)

All 10 "best conditions" recommendations are Scandinavian/Finnish resorts with wildly inflated elevation data:

| Resort | Country | Claimed Top Elev | Real Top Elev | Inflation |
|--------|---------|-----------------|---------------|-----------|
| MeriTeijo Ski | FI | 2,869m | ~160m | +2,700m |
| Påminne | FI | 2,407m | ~100m | +2,300m |
| Serena | FI | 2,510m | ~50m | +2,460m |
| Hafjell | NO | 2,090m | ~1,050m | +1,040m |
| Sauda Skisenter | NO | 2,050m | ~700m | +1,350m |
| Haukelifjell | NO | 2,090m | ~1,000m | +1,090m |

- **Finland's highest point is 1,324m (Halti mountain).** MeriTeijo claiming 2,869m is impossible.
- **Impact:** Inflated elevations cause Open-Meteo to apply large lapse-rate temperature corrections (approx -6.5C per 1000m). A resort at fake 2,869m gets temperatures ~17C colder than reality.
- **This makes these tiny resorts appear to have epic cold-weather powder conditions**, pushing them to the top of the "best conditions" list globally.
- **User impact:** Users see unknown Finnish bunny hills as having "powder day" conditions (score 90+) while major world-class resorts like Whistler (score 56) and Vail (score 13) show mediocre/bad.
- **Data source:** These resorts were scraped from skiresort.info on 2026-02-23. The mid/top elevations appear to be auto-calculated (evenly spaced) from bogus base+top values.

#### BUG-010: Recommendations lack conditions data in response (LOW)

All 10 best recommendations have `conditions: {}` (empty) in the nested recommendation object. The conditions data exists at the top level of each recommendation (`snow_quality`, `snow_score`, `fresh_snow_cm`, etc.) but the `conditions` sub-object (typically containing per-source details) is missing.

### 6. Source Data Consistency Issues

#### BUG-011: High source disagreement not flagged as outlier (MEDIUM)

Sources frequently disagree by 97-99% but are all marked as "included" with weighted average:

**Vail (all elevations):**
- onthesnow.com: 20.32cm
- weatherkit.apple.com: ~2cm
- open-meteo.com: 0.28-0.56cm
- Spread: 97-99% disagreement
- Method: `weighted_average` (not outlier detection)
- **OnTheSnow reports 36-72x more snow than Open-Meteo.** One of them is clearly wrong, but neither is marked as outlier.

**Whistler (all elevations):**
- weatherkit.apple.com: 6.2-6.4cm
- open-meteo.com: 0.14-0.21cm
- onthesnow.com: 2.54cm
- Spread: 97-98% disagreement
- Method: `weighted_average`

**Issue:** When sources disagree by >90%, the system should flag outliers rather than blending them. The current fallback to weighted average when there's "no clear consensus" may be producing inaccurate snowfall values.

#### BUG-012: `hours_since_last_snowfall` is None for Lake Louise (LOW)

All three elevation levels for Lake Louise return `hours_since_last_snowfall: null`. This is an ML model input feature -- missing values may cause undefined behavior or fallback to a default that produces incorrect scores.

### 7. History Data Coverage

#### BUG-013: Only 2 days of history tracked for all resorts (LOW)

Every resort checked (Whistler, Vail, Jackson Hole, Revelstoke, Chamonix, Big White) has only 2 history entries (Feb 22 and Feb 26). This suggests:
- History tracking started recently (around Feb 22)
- Or the daily history job only runs every 4 days
- Season summary shows `total_snowfall_cm` based on only 2 data points, which is not representative

### 8. Batch Endpoint Coverage

- **Requested 20 resorts, received 18** (niseko-united and big-sky missing)
- **The `niseko-united` ID used in the batch request does not exist** -- the correct ID is `niseko`
- **Many major European resorts missing from static JSON** (cortina-dampezzo, kitzbuhel, val-thorens, laax, cervinia, mayrhofen)
- **Static JSON returns 0 results with no resort_ids filter** -- the unfiltered batch endpoint is non-functional

### Summary of Findings

| Bug ID | Severity | Description |
|--------|----------|-------------|
| BUG-003 | HIGH | Scores too low for fresh snow + cold conditions (Lake Louise 21cm at -7.5C = score 26) |
| BUG-004 | MEDIUM | Jackson Hole mid scores "great" with 0.1cm fresh snow |
| BUG-005 | MEDIUM | Aspen explanation says "not skiable" with 81cm base |
| BUG-006 | HIGH | Breckenridge depth: 9cm in static JSON vs 64cm in live conditions |
| BUG-007 | HIGH | Sun Peaks shows 0cm depth (should be 200+ cm) |
| BUG-008 | CRITICAL | Timeline forecasts "champagne powder" with zero snowfall (Whistler, Niseko) |
| BUG-009 | CRITICAL | Best recommendations dominated by resorts with impossible elevation data (Finnish resorts at 2,800m) |
| BUG-010 | LOW | Recommendations response missing nested conditions data |
| BUG-011 | MEDIUM | 97%+ source disagreement not triggering outlier detection |
| BUG-012 | LOW | hours_since_last_snowfall is None for Lake Louise |
| BUG-013 | LOW | Only 2 days of history for all resorts |

**Critical issues (2):** Timeline phantom champagne powder and bogus elevation data corrupting recommendations.
**High issues (3):** Score/depth data inconsistencies between endpoints and inaccurate snow depth readings.
**Medium issues (3):** ML model scoring anomalies and source disagreement handling.
**Low issues (3):** Missing data fields, limited history, empty nested objects.

---

## Resort Data Audit (`backend/data/resorts.json`)

**Audit Date:** 2026-02-26
**Total Resorts:** 1,040

---

### Category A: NON-DOWNHILL RESORTS (Remove from dataset)

These are heli-ski operations, cat-ski operations, backcountry-only, planned/unbuilt, indoor/dry-slope, and summer-only operations that should not be tracked as regular ski resorts.

#### Heli-Ski / Cat-Ski Operations (7)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `alpine-heliski` | Alpine Heliski | NZ | Heli-skiing only, no lifts |
| `ben-ohau-heli-skiing` | Ben Ohau Heli Skiing | NZ | Heli-skiing only, no data at all |
| `methven-heliski` | Methven Heliski | NZ | Heli-skiing only |
| `queenstown-heliski` | Queenstown Heliski | NZ | Heli-skiing only |
| `powder-south-heliski` | Powder South Heliski | CL | Heli-skiing only |
| `pyrenees-heliski-vielha` | Pyrenees Heliski - Vielha | ES | Heli-skiing only |
| `arpa-snowcats-los-andes` | Arpa Snowcats - Los Andes | CL | Cat-skiing operation, not a resort |

#### Planned / Not Yet Built (3)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `cerro-punta-negra-planned` | Cerro Punta Negra (planned) | AR | Not yet built, no data |
| `winter-sports-world-western-sidney-planned` | Winter Sports World - Western Sidney (planned) | AU | Indoor snow facility, not yet built |
| `roaring-meg-resort-planned` | Roaring Meg Resort (planned) | NZ | Not yet built, no data |

#### Indoor / Dry Slope / Artificial (2)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `indoor` | Indoor | DE | Name is literally "Indoor" - likely a scraping error where the category name was captured as a resort. Located in Triberg (Black Forest). No runs, no website, $89 ticket for a 1380m VD makes no sense. |
| `dry-slopes-urban-xtreme-brisbane` | Dry slopes Urban Xtreme - Brisbane | AU | Indoor dry-slope facility in Brisbane, base 91m, no top elevation. Not a real ski resort. |

#### Backcountry / Glacier Operations - No Resort Infrastructure (7)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `fox-glacier` | Fox Glacier | NZ | Glacier heli-ski area, no elevation data, no lifts |
| `harris-mountains` | Harris Mountains | NZ | Heli-ski area, no elevation data |
| `mount-cook` | Mount Cook | NZ | Heli-ski area near Wellington(?), no elevation data, $183 price |
| `southern-lakes` | Southern Lakes | NZ | Heli-ski area, no elevation data |
| `central-north` | Central North | NZ | No data at all, coords near Palmerston North (no ski area there) |
| `tasman-glacier` | Tasman Glacier | NZ | Glacier skiing only, no lifts |
| `wilderness` | Wilderness | NZ | Backcountry area, no lifts |

#### Summer-Only Operation (1)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `galdh-piggen-sommerskisenter-juvass` | Galdhopiggen Sommerskisenter - Juvass | NO | Summer-only glacier ski centre (May-October). No base elevation. Will never show winter snow quality. |

**Total non-downhill: 20 resorts to remove**

---

### Category B: DUPLICATE RESORTS (Consolidate)

#### Exact Duplicates

| Resort ID 1 | Resort ID 2 | Issue |
|-------------|-------------|-------|
| `northstar` | `northstar-california` | Exact same coordinates and elevation data. Remove `northstar-california`. |
| `silver-star` | `silverstar` | Same resort with different IDs. `silverstar` has WRONG coordinates (43.08N, -79.15W = Ontario, not BC). Remove `silverstar`. |

#### Combined Area vs Individual Resort (weather data overlap)

These are cases where both the individual resort AND the combined ski area are listed. They will generate duplicate weather/quality data since they share coordinates.

| Individual | Combined Area | Recommendation |
|------------|---------------|----------------|
| `zermatt` | `zermatt-breuil-cervinia-valtournenche-matterhorn` | Same coords. Keep `zermatt`, remove combined. |
| `verbier` | `4-vallees-verbier-la-tzoumaz-nendaz-veysonnaz-thyon` | Near-same coords. Keep `verbier`, remove combined. |
| `tignes` + `val-disere` | `tignes-val-disere` | Keep individuals, remove combined. |
| `la-plagne` | `la-plagne-paradiski` | Near-same coords. Keep `la-plagne`, remove `la-plagne-paradiski`. |
| `les-arcs` | `les-arcs-peisey-vallandry-paradiski` | Keep `les-arcs`, remove combined. |
| `lech-zuers` + `st-anton` | `st-anton-st-christoph-stuben-lech-zurs-warth-schrocken-ski-arlberg` | Keep individuals, remove combined Ski Arlberg entry. |
| `ischgl` | `ischgl-samnaun-silvretta-arena` | Keep `ischgl`, remove combined. |
| `saalbach-hinterglemm` | `saalbach` (Skicircus) | Same VD. Keep one, remove other. |
| `courchevel` | `les-3-vallees-val-thorens-les-menuires-meribel-courchevel` | Keep individual, remove combined. |
| `chamonix` | 4 sub-areas (`aiguille-du-midi-chamonix`, `brevent-flegere-chamonix`, `grands-montets-argentiere-chamonix`, `les-houches-saint-gervais-prarion-bellevue-chamonix`) | All share same coords. Keep `chamonix` only, remove 4 sub-areas. |
| `hakuba-valley` | 3 sub-areas (`hakuba-47-goryu`, `hakuba-cortina`, `hakuba-iwatake-mountain-resort`) | All same coords. Keep `hakuba-valley` + `hakuba` (Happo-One), remove 3 sub-areas. |

#### Same-Location Sub-Areas with Identical Coordinates (fix coords or merge)

These sub-areas share exact same coordinates, causing duplicate weather fetches and identical quality scores:

| Location | Resorts | Issue |
|----------|---------|-------|
| Davos Klosters | `jakobshorn-davos-klosters`, `madrisa-davos-klosters`, `parsenn-davos-klosters`, `rinerhorn-davos-klosters` | 4 resorts, same coords (46.80, 9.84). All are genuinely separate ski areas but coords should differ. |
| Garmisch-Partenkirchen | `garmisch-classic-garmisch-partenkirchen`, `eckbauer-garmisch-partenkirchen` | Same coords (47.50, 11.08). Separate areas, fix coords. |
| San Isidro | `san-isidro-zona-cebolledo`, `san-isidro-zona-salencias` | Same coords (43.06, -5.37). Two zones of same resort. Could merge. |
| Praděd | `prad-d-figura`, `prad-d-my-ak-mala-moravka-ski-karlov` | Same coords (50.08, 17.23). |
| Zadov | `zadov-chura-ov-u-horej`, `zadov-kobyla` | Same coords (49.08, 13.63). |

---

### Category C: INCORRECT COORDINATES

| Resort ID | Name | Current Coords | Issue | Correct Coords (approx) |
|-----------|------|---------------|-------|--------------------------|
| `silverstar` | SilverStar (British Columbia) | 43.08N, -79.15W | Points to Ontario, not BC | Remove this duplicate (keep `silver-star`) |
| `hafjell` | Hafjell | 60.59N, 6.65E | Points to Voss area. Hafjell is near Lillehammer. City also wrong ("Voss"). | 61.23N, 10.45E |
| `nesfjellet-nesbyen` | Nesfjellet - Nesbyen | 68.08N, 16.47E | Points to Narvik area. Nesfjellet is in Hallingdal. City also listed as "Narvik" (wrong). | 60.57N, 9.11E |
| `olimpica-bor-a` | Olimpica - Borsa | 47.55N, 25.90E | Points to Gura Humorului, not Borsa. City also wrong ("Gura Humorului"). | 47.66N, 24.67E |

---

### Category D: ELEVATION DATA ERRORS

#### Wrong Base Elevations (major errors, often 1000m+ off)

| Resort ID | Name | Current Base | Real Base (approx) | Issue |
|-----------|------|-------------|-------------------|-------|
| `espace-san-bernardo-la-rosiere-la-thuile` | Espace San Bernardo | 7m | ~1850m | Base 7m for an Alpine resort is absurd |
| `espace-lumiere-pra-loup-val-d-allos` | Espace Lumiere - Pra Loup | 54m | ~1500m | Base 54m in the Alps is wrong |
| `buttermilk-mountain` | Buttermilk Mountain | 619m | ~2399m | Base and VD are SWAPPED (base=619, VD=2399; should be base=2399, VD=619) |
| `aspen-mountain` | Aspen Mountain | 400m | ~2422m | Base wildly wrong. Real VD is ~996m, not 3018m |
| `aspen-snowmass` | Snowmass | 813m | ~2473m | Base wrong. Real VD is ~1340m, not 3000m |
| `diavolezza-lagalb` | Diavolezza/Lagalb | 600m | ~2093m | Base wrong |
| `myoko-akakura` | Myoko Akakura | 454m (ok) | 454m | Top is wrong: 3029m (no 3000m peaks in Myoko). Real top ~1500m |

#### Systematic Wrong Base Elevations in South America

Many South American resorts have base elevations that appear to be the elevation of the nearest town/city rather than the ski area base. This is a systematic scraping issue.

| Resort ID | Name | Current Base | Real Base (approx) |
|-----------|------|-------------|-------------------|
| `caviahue` | Caviahue | 200m | ~1600m |
| `cerro-castor` | Cerro Castor | 195m | ~1025m |
| `cerro-perito-moreno-el-bolson-laderas` | Cerro Perito Moreno | 200m | ~1100m |
| `los-penitentes` | Los Penitentes | 194m | ~2580m |
| `cerro-mirador-punta-arenas` | Cerro Mirador | 190m | ~600m |
| `la-parva` | La Parva | 300m | ~2650m |
| `el-colorado-farellones` | El Colorado/Farellones | 460m | ~2430m |
| `vallecitos` | Vallecitos | 500m | ~2900m |
| `antuco` | Antuco | 450m | ~1400m |
| `los-puquios` | Los Puquios | 315m | ~2600m |

#### Missing Both Base AND Top Elevation (16 resorts)

Most of these are NZ heli/backcountry ops that should be removed anyway. The remaining ones that are real resorts:

| Resort ID | Country |
|-----------|---------|
| `malselv-fjellandsby` | NO |
| `t-roa-mt-ruapehu` | NZ |
| `bia-ka-tatrza-ska-kotelnica-kaniowka-bania` | PL |
| `bia-y-jar-karpacz` | PL |
| `biezczadski-wa-kowa` | PL |
| `czarny-gro` | PL |
| `gromadzy-ustrzyki-dolne` | PL |
| `gora-ar-miedzybrodzie-zywieckie` | PL |
| `pricop-b-ile-bor-a` | RO |

#### Missing Top Elevation (~130 resorts)

Major gap affecting: Czech Republic (~25), Poland (~20), Romania (~20), Slovakia (~15), Slovenia (~15), Finland (~10), Bulgaria (~5). This affects weather quality calculations since we use top elevation for snow quality scoring.

#### Wengen-Jungfrau Missing Data

`wengen`: Major Swiss resort missing top elevation (real: ~2971m), vertical drop (real: ~1697m), and all run percentages. This is a well-known resort that should have complete data.

---

### Category E: TICKET PRICE ISSUES

#### Likely Local Currency (NOT USD) - Systematic Issue

Prices for many Eastern European resorts appear to be in local currency, not converted to USD:

| Resort ID | Name | Listed "USD" | Likely Currency | Real USD (approx) |
|-----------|------|-------------|-----------------|-------------------|
| `sveti-konstantin` | Sveti Konstantin (BG) | $495 | 495 BGN | ~$272 |
| `rusi-ski-bukowina-tatrza-ska` | Rusin-Ski (PL) | $238 | 238 PLN | ~$60 |
| `sucha-dolina-kosarzyska-piwniczna-zdroj` | Sucha Dolina (PL) | $205 | 205 PLN | ~$51 |
| `borsec` | Borsec (RO) | $206 | 206 RON | ~$45 |
| `icoana-cavnic` | Icoana - Cavnic (RO) | $211 | 211 RON | ~$46 |
| `jina` | Jina (RO) | $209 | 209 RON | ~$46 |
| `sovata` | Sovata (RO) | $207 | 207 RON | ~$46 |
| `wolfsberg-g-rana` | Wolfsberg - Garana (RO) | $218 | 218 RON | ~$48 |
| `vartop` | Vartop (RO) | $198 | 198 RON | ~$44 |
| `liangcheng` | Liangcheng (CN) | $420 | 420 CNY | ~$58 |
| Plus ~12 more Romanian resorts with prices $130-$220 | | | All likely RON | |

---

### Category F: PASS AFFILIATION ERRORS

#### Missing Pass Affiliations

| Resort ID | Name | Missing Pass | Details |
|-----------|------|-------------|---------|
| `palisades-tahoe` | Palisades Tahoe | Ikon | Should have `ikon_pass: "full"`. Currently only has Mountain Collective. |
| `big-sky-resort` | Big Sky Resort | Ikon | Should have `ikon_pass: "full"` |
| `crystal-mountain-wa` | Crystal Mountain WA | Ikon | Should have `ikon_pass: "base"` (Ikon partner) |
| `mt-bachelor` | Mt. Bachelor | Ikon | Should have `ikon_pass: "base"` (in addition to Indy) |
| `bald-mountain-sun-valley` | Bald Mountain - Sun Valley | Epic | Should have `epic_pass: "full"` (Sun Valley joined Epic) |
| `dollar-mountain-sun-valley` | Dollar Mountain - Sun Valley | Epic | Should have `epic_pass: "full"` |

#### Verify These

| Resort ID | Name | Current | Question |
|-----------|------|---------|----------|
| `snowbasin` | Snowbasin | `epic_pass: "local"` | Verify 25/26 status - Snowbasin's Epic partnership may have changed |

---

### Category G: MISSING CRITICAL DATA

#### Resorts with No Run Percentages (25 resorts)

Includes combined-area duplicates (`aspen`, `hakuba-valley`, `big-bear`), heli/backcountry ops (to be removed), and these real resorts with missing data:

| Resort ID | Name | Country |
|-----------|------|---------|
| `wengen` | Wengen-Jungfrau | CH |
| `centro-francisco-jerman` | Centro Francisco Jerman | AR |
| `gela` | Gela | BG |
| `kulinoto` | Kulinoto | BG |
| `sucha-dolina-kosarzyska-piwniczna-zdroj` | Sucha Dolina | PL |
| 8 Chinese resorts | Various | CN |

---

### Category H: CHINESE SEA-LEVEL "RESORTS" (Likely indoor/artificial)

| Resort ID | Name | Base Elev | Issue |
|-----------|------|-----------|-------|
| `jinxiangshan` | Jinxiangshan | 6m | Sea level, no top elevation, no runs. Likely indoor snow park. |
| `liangcheng` | Liangcheng | 14m | Sea level, $420 price (CNY?), no runs. Likely indoor. |
| `yulongwan` | Yulongwan | 15m | Sea level, no top elevation. Likely indoor. |

---

### Category I: OLYMPIC / COMPETITION VENUES (Review needed)

| Resort ID | Name | Country | Issue |
|-----------|------|---------|-------|
| `yanqing-national-alpine-ski-centre` | Yanqing National Alpine Ski Centre | CN | 2022 Beijing Olympics. Base 171m is suspicious (real ~900m). Top 2357m may be wrong (real ~2198m). Check public access. |
| `jeongseon-alpine-centre` | Jeongseon Alpine Centre | KR | 2018 PyeongChang Olympics downhill. Missing base elevation. Limited public access. |
| `alpensia-pyeongchangs-winter-olympic-park` | Alpensia | KR | 2018 Olympics. VD only 195m. |
| `canada-olympic-park-calgary` | Canada Olympic Park - Calgary | CA | 1988 Olympics. VD only 120m. Urban ski hill. |

---

### Category J: VERY SMALL RESORTS (VD < 50m)

| Resort ID | Name | VD | Notes |
|-----------|------|-----|-------|
| `sveti-konstantin` | Sveti Konstantin (BG) | 20m | Tiny slope, $495 price tag (currency error?) |
| `winter-park-bariloche-piedras-blancas` | Winter Park Bariloche (AR) | 20m | Snow play area, not a ski resort |
| `primeros-pinos` | Primeros Pinos (AR) | 22m | Tiny slope |
| `corin-forest` | Corin Forest (AU) | 12m | Toboggan/tubing area near Canberra |
| `pungrat-besnica` | Pungrat - Besnica (SI) | 15m | Tiny local slope |
| `pokljuka-goreljek` | Pokljuka - Goreljek (SI) | 47m | Known biathlon/Nordic venue, minimal alpine |
| `taivalvaara` | Taivalvaara (FI) | 43m | Very small Finnish hill |

---

### Category K: NOTABLE MISSING RESORTS

| Resort | Country | Region | Notes |
|--------|---------|--------|-------|
| **Alyeska Resort** | US (AK) | na_west | Biggest Alaska resort. Zero AK resorts in dataset. |
| **Meribel** (standalone) | FR | alps | Only appears as part of Les 3 Vallees combined entry |
| **Val Thorens** (standalone) | FR | alps | Only in combined Les 3 Vallees entry |
| **Les Menuires** (standalone) | FR | alps | Only in combined Les 3 Vallees entry |
| **Crans-Montana** | CH | alps | Major Swiss resort, missing entirely |
| **Saas-Fee** | CH | alps | Major Swiss glacier resort, missing entirely |

---

### Category L: REGION DISTRIBUTION (no na_midwest resorts)

The `na_midwest` region is defined in the regions config but contains **zero resorts**. Either populate it or remove the region definition.

---

### DATA QUALITY SUMMARY

#### By Priority

**P0 - Remove (20 resorts):**
- 7 heli-ski / cat-ski operations
- 7 backcountry/glacier with no resort infrastructure
- 3 planned/unbuilt resorts
- 2 indoor/dry-slope facilities
- 1 summer-only operation

**P1 - Fix Data (critical errors affecting quality calculations):**
- 2 exact duplicate resorts to remove
- ~14 combined-area duplicates to consolidate
- 4 wrong coordinates (Hafjell, Nesfjellet, Olimpica Borsa, silverstar duplicate)
- 7+ wrong base/top elevations (Espace San Bernardo 7m base, Buttermilk swapped base/VD, Aspen Mountain 400m base, etc.)
- 10+ South American base elevations systematically wrong
- 6 missing pass affiliations (Ikon/Epic)
- 20+ Eastern European prices likely in wrong currency

**P2 - Fill Gaps:**
- ~130 resorts missing top elevation
- 25 resorts missing run percentages
- 9 real resorts missing both elevations

**P3 - Consider:**
- 7 very small resorts (VD < 50m)
- 3 Chinese sea-level resorts (likely indoor)
- 4 Olympic venues with limited public access
- 6 missing major resorts (Alyeska, Meribel, Val Thorens, Les Menuires, Crans-Montana, Saas-Fee)
- Empty na_midwest region

#### Resort Count After Cleanup

- Current: 1,040
- Remove non-downhill: -20
- Remove exact duplicates: -2
- Remove combined-area duplicates: ~-14
- **Expected final count: ~1,004**

---

## Code Quality Audit (iOS + Web)

**Audit Date:** 2026-02-26
**Auditor:** Code quality audit agent
**iOS Tests:** 119/119 passing
**Web TypeScript Check:** Passed (no errors)

---

### CRITICAL

#### CQA-001: iOS SSE stream service corrupts multi-byte UTF-8 characters
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/Services/ChatStreamService.swift` (line 124-126)
- **Issue:** The SSE byte stream is read one byte at a time and each byte is immediately cast to a `Character` via `Character(UnicodeScalar(byte))`. This is fundamentally broken for multi-byte UTF-8 characters (accents, emoji, non-ASCII resort names like "Kitzbuhel", CJK characters). A multi-byte character will be split into multiple invalid characters, corrupting the chat response text.
- **Code:**
  ```swift
  for try await byte in bytes {
      let char = Character(UnicodeScalar(byte))
      buffer.append(char)
  ```
- **Impact:** Chat responses containing accented characters (common in European resort names like Chamonix, Zermatt, Val d'Isere, Kitzbuhel) will display garbled text. Emoji in AI responses will also be corrupted.
- **Fix:** Accumulate bytes into a `Data` buffer and decode with `String(data:encoding:.utf8)` when processing lines, or use `URLSession.AsyncBytes` line-based iteration via `.lines`.

#### CQA-002: Web `useSnowQualityBatch` mutates input array via `.sort()` in query key
- **Platform:** Web
- **File:** `web/src/hooks/useResorts.ts` (line 32)
- **Issue:** `resortIds.sort().join(',')` calls `.sort()` on the input array, which mutates it in-place. Since `resortIds` comes from a `useMemo` in parent components, this mutates the memoized value, potentially causing React Query cache key instability, unexpected re-renders, and stale data.
- **Code:**
  ```ts
  queryKey: ['snow-quality-batch', resortIds.sort().join(',')],
  ```
- **Impact:** Intermittent stale data or unnecessary re-fetches in the resort list and map views. Could also cause infinite re-render loops in edge cases where the mutated array triggers a new memo value which triggers a new sort.
- **Fix:** Use `[...resortIds].sort().join(',')` to sort a copy.

#### CQA-003: Web `useChat` sets state during render (React anti-pattern)
- **Platform:** Web
- **File:** `web/src/hooks/useChat.ts` (lines 64-72)
- **Issue:** The `useChatSession` hook calls `setMessages(serverMessages)` directly in the render body (not inside a `useEffect`). Calling `setState` during render can cause infinite re-render loops and is explicitly warned against in React's documentation.
- **Code:**
  ```ts
  const serverMessages = conversationQuery.data
  if (serverMessages && serverMessages.length > 0 && messages.length === 0 && conversationId) {
    setMessages(serverMessages)
  }
  ```
- **Impact:** Potential infinite render loop when loading a conversation from the server. In practice, the `messages.length === 0` guard limits the damage, but this still causes a double-render on every conversation load and violates React's rendering contract.
- **Fix:** Move this logic into a `useEffect` with `[serverMessages, conversationId]` dependencies.

---

### HIGH

#### CQA-004: iOS `@ObservedObject` used with inline/shared initialization (should be `@StateObject`)
- **Platform:** iOS
- **Files:** Multiple files (11 occurrences across 7 files)
  - `ios/PowderChaser/PowderChaser/Sources/PowderChaserApp.swift` (lines 39, 40, 130-132, 136)
  - `ios/PowderChaser/PowderChaser/Sources/Views/AuthenticationViews.swift` (line 6)
  - `ios/PowderChaser/PowderChaser/Sources/Views/ResortMapView.swift` (line 8)
  - `ios/PowderChaser/PowderChaser/Sources/Views/ResortListView.swift` (line 51)
  - `ios/PowderChaser/PowderChaser/Sources/Views/ChatView.swift` (line 6)
  - `ios/PowderChaser/PowderChaser/Sources/Views/SettingsView.swift` (line 4)
- **Issue:** `@ObservedObject` is used with inline initialization (`= SomeClass.shared`) in views that own the lifecycle of the observed object. `@ObservedObject` does not own the object and SwiftUI may re-create the wrapper on each view update. For singleton `.shared` instances this means SwiftUI could create a new subscription each re-render, causing performance degradation and potentially missed state updates.
- **Impact:** In practice, since these are all singletons (`.shared`), the object itself is not recreated, but the `@ObservedObject` wrapper is. This can lead to missed observation updates during rapid view refreshes and subtle UI state bugs (e.g., network banner not appearing/disappearing reliably).
- **Fix:** Use `@StateObject` for the first view that introduces the object, or better yet, pass singletons via `.environmentObject()` from the root and use `@EnvironmentObject` in child views.

#### CQA-005: Web ResortDetailPage uses non-null assertion on `resortId` from URL params
- **Platform:** Web
- **File:** `web/src/pages/ResortDetailPage.tsx` (lines 66-71)
- **Issue:** `resortId!` (TypeScript non-null assertion) is used on `useParams()` result, which can be `undefined` if the component is rendered outside its route context (e.g., during testing, or if routing configuration changes).
- **Code:**
  ```tsx
  const { data: resort, isLoading: resortLoading } = useResort(resortId!)
  const { data: conditions, isLoading: conditionsLoading } = useResortConditions(resortId!)
  const { data: timeline } = useResortTimeline(resortId!)
  const { data: history } = useResortHistory(resortId!)
  const { data: snowQuality } = useResortSnowQuality(resortId!)
  const { data: reports } = useConditionReports(resortId!)
  ```
- **Impact:** Runtime crash if `resortId` is undefined. All 6 API hooks would be called with `undefined`, potentially fetching `/api/v1/resorts/undefined/conditions`.
- **Fix:** Add an early return guard: `if (!resortId) return <NotFoundPage />` before the hooks, or use a default value.

#### CQA-006: Web ResortDetailPage mutates React Query cache data with `.sort()`
- **Platform:** Web
- **File:** `web/src/pages/ResortDetailPage.tsx` (line 245-248)
- **Issue:** `resort.elevation_points.sort(...)` mutates the `resort` object that lives in React Query's cache. This means subsequent reads from the cache may return data in a different order than what the API returned.
- **Code:**
  ```tsx
  {resort.elevation_points
    .sort((a, b) => a.elevation_meters - b.elevation_meters)
    .map((ep) => `${ep.elevation_meters}m`)
    .join(' - ')}
  ```
- **Impact:** Mutating cached data can cause inconsistent rendering across components that share the same cache entry. May cause subtle ordering bugs if other components expect the original API order.
- **Fix:** Use `[...resort.elevation_points].sort(...)` or `resort.elevation_points.toSorted(...)`.

#### CQA-007: Web API client has no request timeout
- **Platform:** Web
- **File:** `web/src/api/client.ts` (line 42)
- **Issue:** The `fetch()` call in `ApiClient.fetch()` has no `AbortSignal.timeout()` or equivalent. If the API server hangs, the request will wait indefinitely.
- **Code:**
  ```ts
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  })
  ```
- **Impact:** Users may see infinite loading spinners if the API is slow or unresponsive. No way to recover without refreshing the page.
- **Fix:** Add `signal: AbortSignal.timeout(30000)` (or a configurable timeout) to the fetch options.

#### CQA-008: Web API client has no retry logic for transient failures
- **Platform:** Web
- **File:** `web/src/api/client.ts`
- **Issue:** Unlike the iOS `APIClient` which has a retry policy for 408/500/502/503/504, the web API client makes a single attempt and gives up on any failure. The iOS app retries once for transient server errors.
- **Impact:** Transient network errors (502/503 from API Gateway, brief connectivity drops) cause immediate failure in the web app, while the same scenario would be silently retried on iOS.
- **Fix:** Add a simple retry wrapper (1 retry with backoff) for 5xx status codes and network errors.

---

### MEDIUM

#### CQA-009: Web MapPage has no error state for failed data loads
- **Platform:** Web
- **File:** `web/src/pages/MapPage.tsx`
- **Issue:** The `MapPage` only checks `isLoading` from `useResorts()` but never checks the `error` state. If the resort data fetch fails, the page shows the loading spinner indefinitely (since `isLoading` becomes false but there is no error UI).
- **Impact:** Users see an empty map with no explanation if the API is down or returns an error. No way to retry without refreshing.
- **Fix:** Add error state handling: `const { data: resorts, isLoading, error } = useResorts()` and render an error banner with retry button.

#### CQA-010: Web app has no React Error Boundary
- **Platform:** Web
- **File:** `web/src/App.tsx` and all pages
- **Issue:** No `ErrorBoundary` component exists anywhere in the web app. An uncaught exception in any component's render will crash the entire app with a blank white screen.
- **Impact:** Any runtime error (e.g., accessing property of undefined in a resort card, unexpected API response shape) will crash the entire app. Users must manually refresh.
- **Fix:** Add a root `ErrorBoundary` in `App.tsx` that catches render errors and displays a "Something went wrong" fallback with a reload button.

#### CQA-011: iOS `ChatStreamService` creates new KeychainSwift instance per call
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/Services/ChatStreamService.swift` (line 92)
- **Issue:** `KeychainSwift()` is instantiated inline every time `performStream()` is called. While not a bug per se, this creates a new keychain access group wrapper each time, which is unnecessary overhead.
- **Code:**
  ```swift
  let token = KeychainSwift().get("com.snowtracker.authToken")
  ```
- **Impact:** Minor performance overhead. Consistent with `APIClient.authHeaders()` which does the same. Both should share a single instance.
- **Fix:** Use a shared `KeychainSwift` instance, or access the token through `AuthenticationService.shared`.

#### CQA-012: Web ChatPage `loginAsGuest` in useEffect dependency may cause re-renders
- **Platform:** Web
- **File:** `web/src/pages/ChatPage.tsx` (lines 42-48)
- **Issue:** `loginAsGuest` is included in the `useEffect` dependency array. If this function is recreated on each render (not wrapped in `useCallback` in the auth hook), it will cause the effect to re-fire, potentially triggering multiple guest auth requests.
- **Code:**
  ```tsx
  useEffect(() => {
    if (!isAuthenticated) {
      loginAsGuest().catch(() => {})
    }
  }, [isAuthenticated, loginAsGuest])
  ```
- **Impact:** Potential multiple guest auth API calls on page load, though the `.catch(() => {})` silences any errors. Could cause token overwrites if multiple auth responses arrive out of order.
- **Fix:** Verify that `loginAsGuest` is memoized in the `useAuth` hook, or remove it from the dependency array with an ESLint disable comment explaining why.

#### CQA-013: iOS `DispatchQueue.main.asyncAfter` for UI transitions in ResortMapView
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/Views/ResortMapView.swift` (around line 155)
- **Issue:** Uses `DispatchQueue.main.asyncAfter` with hardcoded delays to sequence sheet dismiss/present transitions. This is fragile and can fail on slower devices or during heavy load.
- **Impact:** On slower devices, the delay may not be sufficient and sheets could fail to present, or on fast devices, there may be an unnecessary visual delay. This pattern is a common source of intermittent UI bugs.
- **Fix:** Use SwiftUI's `onChange` or `task` modifiers to react to state changes rather than relying on timed delays.

#### CQA-014: Web app has no dark mode support
- **Platform:** Web
- **File:** All web pages and components
- **Issue:** All colors are hardcoded to light mode values (white backgrounds, gray text). The `index.css` file has no `prefers-color-scheme: dark` media queries. Users who prefer dark mode see a bright white app.
- **Impact:** Poor user experience for dark mode users. Most modern web apps respect the OS/browser dark mode preference.
- **Fix:** Add Tailwind's `dark:` variant classes and a `prefers-color-scheme` media query, or add a manual theme toggle.

#### CQA-015: Web SSE stream in `useChat` does not handle abort/cleanup on unmount
- **Platform:** Web
- **File:** `web/src/hooks/useChat.ts` (lines 131-244)
- **Issue:** While `abortRef` is set up with an `AbortController`, there is no cleanup function that aborts the stream when the component unmounts. If the user navigates away from the chat page while a message is streaming, the stream continues in the background.
- **Code:** `abortRef.current = controller` is set but never cleaned up on unmount.
- **Impact:** Background streams consume memory and bandwidth after navigation. The `setMessages` and `setIsLoading` calls after unmount will trigger React's "setState on unmounted component" warning (or silently fail in React 18+).
- **Fix:** Return a cleanup function from the `sendMessage` callback or add a `useEffect` cleanup that calls `abortRef.current?.abort()`.

---

### LOW

#### CQA-016: iOS hardcoded Google Client ID
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/Services/AuthenticationService.swift` (line 32)
- **Issue:** The Google Sign-In client ID is hardcoded as a string literal. While not a security vulnerability (client IDs are public), it should be in a configuration file for consistency with other environment-specific values.
- **Impact:** Requires code change to update the client ID. Minor maintainability concern.
- **Fix:** Move to `Info.plist` or `AppConfiguration`.

#### CQA-017: iOS force-unwrapped URLs in Configuration
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/Services/Configuration.swift` (lines 37-38, 53-55)
- **Issue:** `URL(string: "...")!` force-unwraps are used for constant URL strings. While these are safe (the strings are valid URLs), force unwraps are generally discouraged.
- **Impact:** No runtime impact since the strings are valid. Purely a code style concern.
- **Fix:** Use `guard let` with a `fatalError("Invalid URL constant")` for clearer intent, or keep as-is with a comment.

#### CQA-018: Web `utils/format.ts` mutates array with `.sort()` on `knownBaseRegions`
- **Platform:** Web
- **File:** `web/src/utils/format.ts` (line 164)
- **Issue:** `knownBaseRegions.sort(...)` mutates a module-level array. Since this is called during formatting, it runs on every render that uses region formatting.
- **Impact:** Minimal since the sort is by length (deterministic), but it is still an unnecessary mutation of shared state on every call.
- **Fix:** Sort the array once at module initialization, or use `.toSorted()`.

#### CQA-019: Web API client token management split between class and localStorage
- **Platform:** Web
- **File:** `web/src/api/client.ts` (line 29-33) and `web/src/hooks/useChat.ts` (line 136)
- **Issue:** The `ApiClient` class stores the token in `this.accessToken` (set via `setToken()`), but the SSE streaming code in `useChat.ts` reads directly from `localStorage.getItem('snow_access_token')`. If these two sources get out of sync, streaming auth could fail.
- **Code (useChat.ts):**
  ```ts
  const token = localStorage.getItem('snow_access_token')
  ```
- **Impact:** Token inconsistency between REST and streaming API calls. If `setToken()` is called but localStorage is not updated (or vice versa), one path may use a stale token.
- **Fix:** Centralize token storage in the `ApiClient` class and expose a getter for the SSE code to use.

#### CQA-020: Web conversations list shows no loading state
- **Platform:** Web
- **File:** `web/src/pages/ChatPage.tsx` (lines 133-164)
- **Issue:** The conversations sidebar does not show a loading indicator while the conversation list is being fetched. It jumps from empty to populated.
- **Impact:** Minor UX issue. Users may briefly see "No conversations yet" before their conversations load.
- **Fix:** Add a loading skeleton or spinner while `conversations` is loading.

#### CQA-021: iOS `PowderChaserApp` uses `DispatchQueue.main.asyncAfter` for splash screen timing
- **Platform:** iOS
- **File:** `ios/PowderChaser/PowderChaser/Sources/PowderChaserApp.swift` (line 92)
- **Issue:** The splash screen is shown for a fixed 2.5 seconds regardless of whether data has loaded. If data loads in 500ms, the user still waits 2.5 seconds. If data takes 5 seconds, the splash disappears before content is ready.
- **Code:**
  ```swift
  DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
      withAnimation(.easeOut(duration: 0.5)) {
          showSplash = false
      }
  }
  ```
- **Impact:** Suboptimal UX -- splash screen duration is not tied to actual data readiness. Users may see a brief flash of empty content.
- **Fix:** Tie splash dismissal to data loading completion with a minimum display time (e.g., `max(dataLoadTime, 1.5s)`).

---

### Code Quality Audit Summary

| Severity | Count | Platform |
|----------|-------|----------|
| CRITICAL | 3 | iOS: 1, Web: 2 |
| HIGH | 5 | iOS: 1, Web: 4 |
| MEDIUM | 7 | iOS: 2, Web: 5 |
| LOW | 6 | iOS: 3, Web: 3 |
| **Total** | **21** | iOS: 7, Web: 14 |

**Key themes:**
- **Array mutation bugs (Web):** Multiple places where `.sort()` mutates React Query cache data or input arrays (CQA-002, CQA-006, CQA-018)
- **Missing error handling (Web):** No error boundaries, no request timeouts, no retry logic, missing error states on pages (CQA-007, CQA-008, CQA-009, CQA-010)
- **SwiftUI lifecycle misuse (iOS):** Widespread `@ObservedObject` where `@StateObject` or `@EnvironmentObject` should be used (CQA-004)
- **UTF-8 handling (iOS):** Critical byte-level SSE parsing bug that corrupts non-ASCII text (CQA-001)
- **React render contract violations (Web):** setState during render in chat hook (CQA-003)
