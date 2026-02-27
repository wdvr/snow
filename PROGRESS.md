# Powder Chaser - Progress

## Status: LIVE
**Last Updated**: 2026-02-26

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Active Work (Feb 27) — Polish & Launch

### Just Completed (Feb 27)
- [x] Resort list card redesign (iOS) — ScrollView+LazyVStack matching Best Snow tab
- [x] Chat forecast fix — replaced broken S3 with Open-Meteo API (8 new tests)
- [x] Alternate app icons — 9 variants + picker in Settings > Appearance
- [x] Quality score consistency — batch endpoint now uses weighted avg (50/35/15)
- [x] Widget region display — human-readable names instead of raw IDs
- [x] Card background fix — secondarySystemBackground for visible cards
- [x] App display name → "Powder Chaser" (was "Snow Tracker" in icon change dialog)
- [x] Backend tests: 1599 passing
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

| Bug | Description | Status |
|-----|-------------|--------|
| BUG-003 | Scores too low for fresh snow (Lake Louise 21cm=−7.5°C scored 26) | **Fixed** — fresh snow floor constraint |
| BUG-006 | Breckenridge depth mismatch (static JSON vs live) | Self-resolves on Lambda run |
| BUG-011 | Source disagreement not triggering outlier detection | **Fixed** — 2-source outlier detection |

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
xcodebuild test -project ios/SnowTracker.xcodeproj -scheme SnowTracker -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:SnowTrackerTests

# Deploy (auto on push to main)
git push origin main

# Trigger weather processor
gh workflow run trigger-weather.yml -f environment=staging

# Static JSON Lambda (async)
aws lambda invoke --function-name "snow-tracker-static-json-prod" --invocation-type Event --region us-west-2 /tmp/out.json
```
