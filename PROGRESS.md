# Powder Chaser - Progress

## Status: LIVE
**Last Updated**: 2026-03-01

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Active Work (Week of Mar 1) — Data Quality & Cross-Platform Consistency

### In Progress
- [ ] Fix review.md HIGH items: `MKLocalSearch` not on main thread, `isFetchingTimelines` race condition
- [ ] Fix review.md Web items: scrollbar CSS, UTC date parsing, stale selectedDayIndex, empty array Math
- [ ] Operational status proposal: how to surface lifts/runs/surface data without polluting ML score

### Completed (Mar 1)
- [x] Fix BUG-004: Jackson Hole mid scores "great" with 0.1cm fresh — now scores 2.99 mediocre
- [x] Fix BUG-005: "Not skiable" explanation with None depth — added icy/degraded handling
- [x] Fix BUG-008: Timeline phantom champagne powder — tightened cap thresholds (<0.1/72h→3.5, <1.0/72h→4.0)
- [x] Fix BUG-009: 22 Nordic resorts with NULL elevation — fixed resorts.json + runtime sanity checks
- [x] Fix BUG-017: Chat test flaky in full suite — autouse fixture resets DynamoDB cache
- [x] Fix BUG-019: "Thin cover" explanation despite measurable fresh snow — reordered POOR logic
- [x] Feature 2.11: Authenticated chat rate limiting (100 msgs/day per user)
- [x] Firebase chat analytics: 7 events in AnalyticsService + wired in ChatViewModel
- [x] Code cleanup: duplicate haversine → geo_utils import, unused type imports removed
- [x] Fix `snowfall_after_freeze_cm` stuck at 0 when Open-Meteo underreports (BUG-014)
- [x] Fix cross-view elevation inconsistency — standardize mid > top > base (BUG-015)
- [x] Raise ML fresh-snow floors: 8cm+/≤0°C → 3.5, 8cm+/≤-3°C → 4.0 (BUG-016)
- [x] Fix explanation text: "Limited fresh snow" → "Fresh snow (Xcm/24h) on a warming base"
- [x] Fix map popup "New Snow" showing 0 (use `formattedFreshSnowWithPrefs`)
- [x] Fix chart header "0cm accumulated" when there was recent snow
- [x] Fix forecast arrow text on wrong side of dashed line
- [x] Weather worker: reconcile `snowfall_after_freeze_cm` with merged multi-source data
- [x] ML scorer: override `snow_since_freeze_cm` feature from conditions
- [x] Timeline uses resort-local timezone instead of UTC
- [x] Recommendations endpoint S3 fast path (cold start <1s)
- [x] Best conditions endpoint S3 fast path (19s → 0.15s)
- [x] Compact map overlays — merge filter + day selector into single row
- [x] OnTheSnow scraper rewrite — JSON extraction from `__NEXT_DATA__` (16 → 95 resorts)
- [x] Enable Snow-Forecast as secondary data source
- [x] 10-resort validation: Whistler, Jackson Hole, Mammoth, Revelstoke, Mt. Baker, Chamonix, St. Anton, Niseko, Vail, Kicking Horse — all PASS
- [x] Backend tests: 1705 passing (0 flaky), iOS tests: 119 passing

### Completed (Feb 28)
- [x] Remove Live Activity / Dynamic Island feature (doesn't change fast enough)
- [x] Fix list view → map zoom (NavigationCoordinator 100ms delay)
- [x] Rethink fresh snow metric: settling factor + "New Snow" terminology (15+ iOS files)
- [x] Add settling factor to backend (time-based 1.0/0.85/0.70/0.55 multiplier)
- [x] Update marketing text (40 data points, compaction-aware language)
- [x] Physics eval: 4 new Breckenridge/Tahoe test cases (126/126 checks pass)
- [x] Run difficulty display + ticket price display
- [x] Enable Snow-Forecast in infrastructure config (ENABLE_SNOWFORECAST → "true")

### Queued
- [ ] App Store screenshots for v2.1 (Powder Chaser branding, new features)
- [ ] Trip Planning Mode (#23) — multi-component feature
- [ ] Web: Trail map viewer fix (page URLs instead of DZI thumbnails) (#187)
- [ ] Web: Timeline/hourly forecast cards
- [ ] Annual snowfall data for 594 missing resorts
- [ ] Apple Watch companion app (#25)
- [ ] Android: Google Sign-In (#190), piste overlay (#188), trail maps (#187), suggest edit (#189)

### GitHub Issues (Open — 5 remaining)
| # | Title | Labels |
|---|-------|--------|
| 25 | Apple Watch App | enhancement, ios, needs-user-input |
| 187 | Android: Trail map viewer (DZI thumbnails) | enhancement, android |
| 188 | Android: Piste overlay on map | enhancement, android |
| 189 | Android: Suggest an Edit button | enhancement, android |
| 190 | Android: Google Sign-In placeholder | bug, android |

*Issue #13 (multi-source data research) closed Mar 1 — completed.*

## Completed (Feb 27-28) — Polish & Launch

### Just Completed (Feb 27)
- [x] Resort list card redesign (iOS) — ScrollView+LazyVStack matching Best Snow tab
- [x] Chat forecast fix — replaced broken S3 with Open-Meteo API (8 new tests)
- [x] Alternate app icons — 9 variants + picker in Settings > Appearance
- [x] Quality score consistency — batch endpoint now uses weighted avg (50/35/15)
- [x] Widget region display — human-readable names instead of raw IDs
- [x] Card background fix — secondarySystemBackground for visible cards
- [x] App display name → "Powder Chaser" (was "Snow Tracker" in icon change dialog)
- [x] Backend tests: 1693 passing
- [x] iOS tests: 119 passing
- [x] TestFlight build 745 uploaded

### Just Completed (Feb 27 — continued)
- [x] Favorites view: card layout with logo, pass badges, quality badge, stats, explanation
- [x] Favorites view: 10-day date selector with timeline forecast per resort
- [x] Marketing website: update screenshot (map view)
- [x] Marketing website: link to real App Store entry (id6758333173)
- [x] Marketing website: update quality levels (old 6-level → new 10-level scale)
- [x] Web app: iOS Smart App Banner (`<meta name="apple-itunes-app">`)
- [x] Map view: simplify filter chips (5 → 3: All, Good+, Below Good)
- [x] Piste overlay: min zoom 13, alpha 0.7 for lighter appearance
- [x] Nearby resorts section: collapsible with chevron toggle
- [x] iOS tests: 119 passing
- [x] TestFlight build triggered

### Just Completed (Feb 27 — bug fixes & data)
- [x] BUG-003 fixed: fresh snow floor constraint in ml_scorer (21cm@-7.5°C now scores EXCELLENT, not 26/100)
- [x] BUG-011 fixed: 2-source outlier detection (>50% disagreement → outlier, not weighted avg)
- [x] SVG→PNG logo conversion: 354 SVG logos converted to PNG via CairoSVG, uploaded to S3
- [x] Backend tests: 1620 passing
- [x] Backend deployed to prod + static JSON regenerated
- [x] Resorts database updated (PNG logo URLs pushed to DynamoDB)

### Just Completed (Feb 28)
- [x] Nearby resort tap crash fix (race condition, 0.5s delay)
- [x] "Show on Map" navigation (NavigationCoordinator, cross-tab zoom)
- [x] Full rename SnowTracker → PowderChaser (dirs, targets, module, workflows, docs)
- [x] Debug "Send Test Notification" for admin users in production
- [x] Snow depth fix: ERA5 re-enable + 14d snowfall floor (Kimberly 1cm→100cm, 529 resorts)
- [x] Fresh snow cap fix: don't cap at unreliable snow_depth values
- [x] Timeline card background: .cardStyle() for consistency
- [x] Map filters: 3→6 options (Excellent+/Good+/Decent+/Mediocre+/Below Good)
- [x] Chat keyboard dismiss + conversation history auth (token refresh on 401)
- [x] Translations: 79 new strings across 13 languages (113→192 per file)
- [x] Backend deployed to prod + TestFlight triggered

### Just Completed (Feb 27 — v2.0 release)
- [x] Map zoom refresh: fetch conditions on zoom using visibleResortIds() viewport filter
- [x] Webcam card: prominent card in map detail sheet (replaces small "Cams" button)
- [x] Version bump to 2.0.0 (project.yml + project.pbxproj + App Store metadata)
- [x] App Store release notes + description updated (1040+ resorts, 25 countries)
- [x] Fixed App Store release workflow (boolean input passing, fastlane precheck)
- [x] TestFlight build 758 (v2.0.0)
- [x] v2.0.0 submitted to App Store review via fastlane deliver

### Just Completed (Feb 27 — v2.1 polish)
- [x] Extract 19 hardcoded English strings → Localizable.strings + translate to all 17 languages (211 strings per file)
- [x] Add 4 new languages: Russian (ru), Finnish (fi), Czech (cs), Traditional Chinese (zh-Hant)
- [x] Merge 15 logo results from background agents (818→833 logos, 81.7%)
- [x] Piste overlay: boosted alpha (0.7→0.85), lowered min zoom (13→12), CIFilter saturation/contrast enhancement
- [x] BUG-194 fix: fresh snow display now shows 24h snowfall preferentially instead of misleading accumulated-since-thaw
- [x] Closed GitHub issues: #193 (map zoom), #194 (fresh snow display), #195 (outlier detection), #24 (webcam)
- [x] DynamoDB updated with 15 new resort logos (Populate workflow)

### Just Completed (Feb 27 — vector piste overlay)
- [x] Vector piste overlay replacing OpenSnowMap raster tiles (fully native MKPolyline)
- [x] Piste lines colored by difficulty (green/blue/red/black), lifts as dashed gray lines
- [x] Piste + lift name labels at high zoom (latDelta < 0.04°) with difficulty-colored text
- [x] S3 pre-cache: fetch from powderchaserapp.com/data/pistes/{id}.json, fallback to Overpass
- [x] precache_pistes.py: batch script uploading all 1019 resorts to S3 (running)
- [x] PisteOverlayService: actor with LRU cache, S3-first with Overpass fallback
- [x] Verified: Big Sky 589 runs, Vail 211, Zermatt 181, Whistler 65
- [x] iOS tests: 119 passing, TestFlight triggered (v2.1.0)

### Completed: Piste Overlay Polish (Feb 28)
- [x] Remove piste name labels entirely (black background looks bad)
- [x] Fix trails not disappearing on zoom-out — added zoom check in renderer (0.5° max span)
- [x] Show trails at wider zoom level (fetch threshold 0.3→0.5)
- [x] Toggle button verified removed in code (commit 51d1ee9)
- [x] Pre-cache: 809/1019 done, rest have no OSM data or encoding issues

### Data Coverage (current)
| Data | Coverage |
|------|----------|
| Trail maps | 957/1019 (93.9%) |
| Logos | 834/1019 (81.8%) — 354 SVG→PNG converted |
| Webcams | 1019/1019 (100%) — auto-generated skiresort.info pages |
| Websites | 884/1019 (86.7%) |

---

## Completed Features (Feb 26)

### Trail Maps
- [x] Scrape trail map URLs for all 1019 resorts → 957/1019 (93.9%)
- [x] Sources: skiresort.info DZI, snow-forecast.com, resort websites, skimap.org
- [x] iOS: full-screen zoomable TrailMapView (image URLs) + SFSafariViewController (page URLs)
- [x] Fix: DZI level-8 tiles were 218x180px thumbnails → converted to interactive page URLs
- [x] 29 parallel subagents for mass trail map discovery

### Resort Logos
- [x] 818/1019 logos (80.3%) — SVG, PNG, JPG from official sites + CDNs
- [x] logo_url field in resorts.json, DynamoDB, iOS, Android, Web
- [x] Smart merge: only upgrades, never downgrades. Quality scoring (SVG=7 → favicon=1)
- [x] 10+5 parallel subagents for logo discovery

### Ski Trail/Piste Overlay on Map
- [x] OpenSnowMap raster tiles (tiles.opensnowmap.org/pistes/{z}/{x}/{y}.png)
- [x] iOS: MKTileOverlay at z12-18, toggle button (skiing icon), attribution banner
- [x] Web: Leaflet TileLayer with zoom-aware rendering (z12+)

### Data Source Transparency
- [x] Backend: source_details in merger output (consensus vs outlier per source)
- [x] iOS: DataSourcesCard (collapsible, per-source snowfall + status)
- [x] Web: Data Sources Card

### Other Completed
- [x] Indy Pass support (iOS + Web + Android) — 43 resorts tagged
- [x] Suggest an Edit (iOS + Web)
- [x] Dynamic chat suggestions (iOS fetches from API)
- [x] Community reports fix (TTL=90d, secondary color timestamp)
- [x] Chat ellipsis bug fix
- [x] Cost optimization: exclude raw_data from DynamoDB writes (~$71/mo savings)
- [x] Resort logos in detail views + map popups (iOS + Web + Android)
- [x] Map popup enhancements: webcam + trail map + logo buttons

---

## Known Bugs

See `BUGS.md` for full details. Summary:

| Status | Count | Bugs |
|--------|-------|------|
| **Fixed** | 8 | BUG-003, 007, 011, 012, 013, 014, 015, 016 |
| **Backlog** | 5 | BUG-008 (timeline phantom), 009 (Finnish elevation), 017 (chat test flaky), 018 (label-score boundary), 019 (explanation edge case) |
| **Stale** | 2 | BUG-004, 005 — need re-verification |

---

## Backlog — iOS

- [x] Map forecast refresh on zoom (fetches on pan but not zoom change) — **v2.0**
- [x] Webcam card in map detail sheet — **v2.0**

## Backlog — Android (not blocking release)

- [ ] Google Sign-In (button exists, onClick placeholder)
- [ ] Trip Creation (FAB stub)
- [ ] Comparison View (stub screen)
- [ ] Suggest an Edit button
- [ ] Trail map fix (page URLs instead of DZI thumbnails)
- [ ] Piste overlay on map
- [ ] Many iOS features pending parity (see DIARY.md for full list)
- [ ] Google Play internal testing setup

## Backlog — Web

- [ ] Trail map viewer fix (page URLs instead of DZI thumbnails)
- [ ] Timeline/hourly forecast cards (lower priority)

## Backlog — Backend/Data

- [ ] Weather Unlocked integration ($220-420/mo) — best multi-source option
- [ ] Annual snowfall: 594 resorts still missing
- [ ] 47 resorts not found on skiresort.info (Chinese, heli-ski, indoor)
- [ ] Dynamic chat suggestions: seed table + update Android/Web

---

## Cross-Platform Feature Parity

Reference platform: **iOS** (most complete).

### Web — Near Complete
All HIGH priority items done (W1-W10). Only W6 (Timeline/Hourly) remains as medium priority.

### Android — Functional but Behind
HIGH priority items done (A1-A5: Data Sources, Clustering, Regions, Streaming Chat, Map Forecast). Medium items A6-A8 (Google Sign-In, Trips, Comparison) are stubs. ~50 iOS features still pending parity — see DIARY.md.

---

## Architecture

### Snow Quality Algorithm
ML model v15: ensemble of 10 neural networks (40 features incl. visibility, wind gusts, hours_since_last_snowfall → quality score 1-6).
Val MAE 0.225, R² 0.937, 81.1% exact, 100% within-1. Trained on ~12,000 samples from 134 resorts.

Quality levels (10): CHAMPAGNE POWDER → POWDER DAY → EXCELLENT → GREAT → GOOD → DECENT → MEDIOCRE → POOR → BAD → HORRIBLE

### DynamoDB Tables
- `snow-tracker-resorts-{env}`
- `snow-tracker-weather-conditions-{env}` (TTL: 60 days)
- `snow-tracker-snow-summary-{env}`
- `snow-tracker-daily-history-{env}`
- `snow-tracker-user-preferences-{env}`
- `snow-tracker-feedback-{env}`
- `snow-tracker-device-tokens-{env}` (TTL: 90 days)
- `snow-tracker-chat-{env}` (TTL: 30 days)
- `snow-tracker-condition-reports-{env}` (TTL: 90 days)
- `snow-tracker-resort-events-{env}`

---

## Quick Commands

```bash
# Test API
curl https://api.powderchaserapp.com/api/v1/resorts/big-white/conditions

# Run tests
cd backend && python3 -m pytest tests/ -x -q
xcodebuild test -project ios/PowderChaser.xcodeproj -scheme PowderChaser -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:PowderChaserTests

# Deploy (auto on push to main)
git push origin main

# Trigger weather processor
gh workflow run trigger-weather.yml -f environment=staging

# Static JSON Lambda (async)
aws lambda invoke --function-name "snow-tracker-static-json-prod" --invocation-type Event --region us-west-2 /tmp/out.json
```
