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

### In Progress
- [ ] Favorites view: card layout matching main list + quality explanation text
- [ ] Favorites view: 10-day date selector (forecast weather per day)
- [ ] Marketing website: update screenshot (show map view, not wrong app)
- [ ] Marketing website: link to real App Store entry
- [ ] Marketing website: update quality levels (old 6-level → new 10-level scale)
- [ ] Web app: iOS Smart App Banner (`<meta name="apple-itunes-app">`)
- [ ] Generate iPad screenshots (iPad Pro 13" + 11")
- [ ] Upload metadata + screenshots to App Store Connect
- [ ] Submit for App Store review

### Known Bugs
- [ ] Banff Sunshine icon missing (logo URLs valid — likely app-side SVG rendering issue)
- [ ] Investigate BUG-003: Scores too low for fresh snow (Lake Louise 21cm=−7.5°C=26)
- [ ] Investigate BUG-011: Source disagreement not triggering outlier detection

### Data Coverage (current)
| Data | Coverage |
|------|----------|
| Trail maps | 957/1019 (93.9%) |
| Logos | 818/1019 (80.3%) |
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
| BUG-003 | Scores too low for fresh snow (Lake Louise 21cm=−7.5°C scored 26) | Investigating |
| BUG-006 | Breckenridge depth mismatch (static JSON vs live) | Self-resolves on Lambda run |
| BUG-011 | Source disagreement not triggering outlier detection | Investigating |

---

## Backlog — iOS

- [ ] Map forecast refresh on zoom (fetches on pan but not zoom change)
- [ ] Webcam preview image in map popup (AsyncImage)

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
