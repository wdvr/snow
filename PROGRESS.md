# Powder Chaser - Progress

## Status: LIVE
**Last Updated**: 2026-02-26

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Active Work (Feb 26)

### Pre-Release Audit & Final Polish

#### App Store Release
- [x] Remove duplicate splash screen spinner (iOS)
- [x] Update App Store screenshot tests (add AI chat, iPad)
- [x] Update release notes for v1.1
- [x] TestFlight build uploaded (build 717, v1.1.0)
- [x] Generate final screenshots (iPhone 17 Pro Max + iPhone 17)
- [ ] Generate iPad screenshots (iPad Pro 13" + 11")
- [ ] Upload metadata + screenshots to App Store Connect
- [ ] Submit for App Store review
- [x] Create `/ios-release` skill with lessons learned

#### Web App Fixes (Feb 26)
- [x] **W-BUG-001: Quality shows "Unknown" for all resorts** — batch quality call sends all 1019 IDs at once, exceeds 200 limit → chunked to ≤200 per request
- [x] **W-BUG-002: No pagination** — switched to useInfiniteQuery, 50 per page, "Load more" button
- [x] **W-BUG-003: Server-side sort_by param** — Added sort_by (name/quality_score/snowfall/elevation) + sort_order to GET /api/v1/resorts
- [x] Web: chunk batch quality requests into ≤200 ID batches
- [x] Web: add limit/offset/sort_by to getResorts() API client
- [x] Web: infinite scroll or "Load more" pagination in resort list
- [x] Backend: add sort_by query param to GET /api/v1/resorts

#### Dynamic Chat Suggestions
- [x] Create DynamoDB table for chat suggestions (in Pulumi)
- [x] Add API endpoint `GET /api/v1/chat/suggestions` (no auth required)
- [x] Make 12/16 suggestions location/favorites-aware with interpolation tokens
- [x] Default to embedded 16 if table empty
- [x] Update iOS to fetch from API with token interpolation
- [ ] Update Android, Web to fetch from API
- [ ] Seed chat suggestions table (after infrastructure deploys)

#### Resort Logos
- [x] Research logo availability — Google Favicon API covers 74%
- [x] Generated `backend/data/resort_logos.json` with URLs
- [ ] Add logo_url to resorts.json
- [ ] Display in resort detail view top cell (iOS, Android, Web)

#### Resort Data Deep Audit — COMPLETED
- [x] Cross-country only resort check → Removed 22 non-downhill resorts (1040→1018)
- [x] Duplicate resort detection → 2 exact + ~14 combined-area identified
- [x] Coordinate accuracy verification → Fixed Hafjell, Nesfjellet, Dollar Mountain
- [x] Elevation data validation → Nulled 26 bogus, fixed 7 specific errors
- [x] Ticket price sanity check → Nulled 21 local-currency-as-USD prices
- [x] Pass affiliation accuracy → Added Ikon/Epic for 6 resorts
- [x] Added missing Alyeska Resort (biggest AK, Ikon full)
- [x] Report in BUGS.md

#### Snow Quality & Prediction Audit — COMPLETED
- [x] BUG-008 FIXED: Timeline phantom champagne powder → no-snowfall-cap in ML scorer
- [x] BUG-001 FIXED: Limit/offset pagination on /api/v1/resorts
- [x] BUG-005 FIXED: "Not skiable" explanation with 81cm base → depth-aware logic
- [x] BUG-009 FIXED: Finnish bogus elevations corrupting recommendations
- [x] CQA-001 FIXED: iOS SSE UTF-8 corruption
- [x] CQA-002/006 FIXED: React Query cache mutations from .sort()
- [x] CQA-003 FIXED: setState during render in useChat
- [x] CQA-007 FIXED: Web fetch timeout (30s AbortController)
- [x] API response validation — 17/17 endpoints healthy
- [x] Backend tests: 1592 passing
- [x] QA Round 2: hours_since_last_snowfall=0.0 falsy bug fixed
- [x] QA Round 2: No-snowfall cap applied to real-time endpoint (was timeline-only)
- [x] QA Round 2: _validate_resource_id() on all path-parameter endpoints
- [x] QA Round 2: Float→Decimal chat DynamoDB crash fixed
- [x] QA Round 2: chat_suggestions_table IAM permission added
- [x] QA Round 2: DynamoDB scan pagination for get_all_resorts()
- [x] QA Round 2: Error messages sanitized (no user input echo)
- [ ] BUG-003: Scores too low for fresh snow (Lake Louise 21cm=-7.5C=26) — data issue
- [ ] BUG-006: Breckenridge depth mismatch (static JSON vs live) — resolves on Lambda run
- [ ] BUG-011: Source disagreement not triggering outlier detection — tuning needed

### TODO: iOS / Backend / Cross-platform

1. [x] **Chat table column alignment** — Fixed: explicit `totalWidth` on all rows, shared `tableRow()` builder for header and data rows. All columns now align.
2. [x] **16 chat suggestion examples with random rotation** — Verified: 16 diverse suggestions covering proximity, budget, comparisons, regional, family, pass-based, forecasts, hidden gems. Shows random 4 each visit.
3. [x] **Resort day ticket prices seem off** — Verified and corrected prices for 65+ resorts. Whistler $175-260, Vail $189-356, etc. Created `enrich_resort_data.py` with 90+ manually verified 2025/26 prices.
4. [x] **Chat history still doesn't work** — Fixed: Float→Decimal DynamoDB error in chat_stream_handler.py. iOS UX improved: error display, loading states, retry button.
5. [x] **Add city to resort titles** — Added city and state_province fields to 955/1040 resorts via Nominatim reverse geocoding + manual overrides. iOS displays "Big White, Kelowna, BC, Canada" style titles.
6. [ ] **Resort logo in detail view** — Deferred: logos not readily available as URLs from skiresort.info. Infrastructure prepared but needs logo source.
7. [x] **Snow history still empty** — Fixed: DAILY_HISTORY_TABLE env var missing from Lambda functions. Note: deploys may wipe env vars — always re-verify after deploy.
8. [x] **Website opens in new tab** — Website, trail map, and webcam links now open in embedded SFSafariViewController overlay instead of leaving the app.
9. [x] **Webcam pages / main webcam on detail view** — Added webcam_url to all 1040 resorts (skiresort.info webcam pages). iOS detail view shows "Webcams" link in header links row.
10. [x] **Map: default to hybrid, remember selection** — Map defaults to hybrid, persisted via @AppStorage. (Forecast refresh on zoom still TODO.)
11. [x] **Clarify or remove pin icon** — Changed to antenna/broadcast icon with "Live" label for Live Activities.
12. [x] **Re-launch onboarding from settings** — "Restart Tutorial" button in settings, pre-populates current preferences.
13. [x] **Push notifications don't work** — Fixed: Debug endpoints blocked all prod requests. Added admin email hash check. Fixed APNS_SANDBOX→APNS for prod.
14. [x] **App still called "Snow Tracker" in places** — Renamed to "Powder Chaser" in Info.plist, project.yml, all 13 Localizable.strings.

### New Features (Feb 26 — Pre-Release)

#### Downloadable Resort Trail Map (iOS + Web + Android)
- [x] **Research**: trail map image sources (skiresort.info DZI, snow-forecast.com JPEG, official resort CDNs)
- [x] **Scrape trail map URLs** for all 1019 resorts (skiresort.info trailmap IDs + snow-forecast slugs) — running now
- [ ] Add trail_map_image_url to resorts.json + DynamoDB
- [ ] iOS: full-screen zoomable image viewer in resort detail
- [ ] Web: full-screen image modal in resort detail
- [ ] Android: full-screen image viewer in resort detail
- Sources found: skiresort.info DZI tiles (5472×3639px, zoomable), snow-forecast.com JPEG (~400-500 resorts), official resort CDNs (annual URL changes)

#### Ski Trail Overlay on Main Map (POST-RELEASE)
- [x] **Research completed**: 3 viable options identified
- Option A (easiest): OpenSnowMap raster overlay `tiles.opensnowmap.org/pistes/{z}/{x}/{y}.png` — transparent piste tiles, 1-2 days work
- Option B (best): OpenSkiMap vector PBF tiles `tiles.openskimap.org/tiles/openskimap/{z}/{x}/{y}.pbf` — difficulty-colored, clickable trails, ~1 week
- Option C (richest): On-demand Overpass API per resort (Whistler = 827 piste ways in 1.3MB GeoJSON)
- [ ] Choose approach and implement (post-release feature)

#### Suggest an Edit (iOS + Web + Android)
- [x] **"Suggest an Edit" button** on every resort detail view
- [x] Opens pre-filled feedback form with resort name + section
- [x] Submits to existing /api/v1/feedback endpoint with type="resort_edit"
- [x] iOS: add SuggestEditView.swift + button on ResortDetailView
- [x] Web: add SuggestEditModal component + button on ResortDetailPage
- [ ] Android: add button to resort detail screen
- [x] Verify feedback submissions persist to DynamoDB — web schema mismatch fixed

#### Indy Pass Support
- [x] **Research**: 271 Indy Pass resorts (2025-26), estimated 60-100 overlap with our 1019
- [x] Scrape indyskipass.com/resorts/ for full resort list + fuzzy match → 248 resorts, 41 matched
- [x] Update resorts.json with Indy Pass data (full/base tiers) → 43 total (41 new + 2 existing)
- [x] Populate DynamoDB with updated pass data (both staging + prod)
- [x] iOS: add Indy filter chip to resort list + badges in all views
- [x] Web: add Indy filter button to resort list + badges in cards/detail/map
- [ ] Android: add Indy filter chip to resort list

#### iOS Chat Ellipsis Bug — FIXED
- [x] **BUG**: Chat output truncates text with "..." in bullet points
- [x] Example: "not from recent snowfall" shows as "not from recent..."
- [x] Fix: `.layoutPriority(1)` on text, `.fixedSize()` on bullet labels, `.lineLimit(nil)` on inlineMarkdown
- [x] Deployed via TestFlight

#### Community Reports Fix — ALREADY DONE
- [x] Condition report TTL already 90 days (was already correct)
- [x] Timestamp already uses `.secondary` color (was already fixed)

#### Data Source Transparency — ALREADY DONE
- [x] Backend: expose source_details in merger output (which sources contributed, consensus vs outlier)
- [x] iOS: add DataSourcesCard showing per-source info (collapsible, shows consensus/outlier per source)
- [x] Web: Data Sources Card already implemented

### TODO: Cross-platform (Web + Android)

- [x] Review DIARY.md for all features/fixes marked `pending` on Android and Web
- [x] Implement pending Android features/fixes from diary — 13 quality levels, chat improvements, map layers, compound regions, trail map links
- [x] Implement pending Web features/fixes from diary — 13 quality levels, trail distribution, 48h forecast column, compound regions

### Remaining Issues
- [ ] Resort logo source needed (deferred)
- [ ] Map forecast refresh on zoom (not yet implemented)
- [x] Deploy wipes DAILY_HISTORY_TABLE env var from API handler — FIXED: added all missing env vars to deploy.yml hardcoded configs
- [x] Populate Resorts Database workflow triggered — DONE: city/webcam/prices now in prod DynamoDB

---

## Cross-Platform Feature Parity (Feb 26)

Reference platform: **iOS** (most complete). Goal: Web + Android at 100% parity.

### Web Parity Gaps (vs iOS)

#### HIGH PRIORITY
- [x] **W1: Map View** — Leaflet.js interactive map with clustering, quality-colored markers, region presets (8 regions), quality filter tiers, tile layer switch (Standard/Satellite/Terrain), nearby carousel, resort popup on click
- [x] **W2: Data Sources Card** — Collapsible card showing merge method, source count, per-source snowfall with consensus/outlier status color-coding
- [x] **W3: Elevation Picker** — Segmented control (Summit/Mid/Base) with elevation meters, auto-selects available level
- [x] **W4: Expanded Conditions** — SnowDetailsCard with fresh snow, 24h/48h/72h snowfall, warming indicator, freeze/thaw time, snow since freeze, base depth warning, weather description
- [x] **W5: Weather Details** — WeatherDetailsCard with min/max temp, humidity, wind speed, wind gust, max gust 24h, visibility with severity colors, min visibility 24h, weather description
- [ ] **W6: Timeline/Hourly Forecast** — Hourly conditions cards (lower priority, forecast chart covers daily view)
- [x] **W7: Condition Report Submission** — ConditionReportForm modal with condition type, score slider, elevation, comment
- [x] **W8: Unit Preferences** — UnitProvider context with °C/°F and cm/inches toggle, localStorage persistence, formatTemp/formatSnow/formatSnowInt helpers
- [x] **W9: Pass Filter** — Epic/Ikon filter buttons on home page resort list
- [x] **W10: Distance Sorting** — Haversine distance calculation, sort-by-distance with geolocation

#### MEDIUM PRIORITY
- [x] **W11: Settings Page** — Full settings page with unit preferences (temp + snow), account management, about section
- [x] **W12: All Elevations Summary** — Side-by-side base/mid/top cards showing quality, temp, fresh snow, depth, 24h snowfall
- [x] **W13: Share Button** — Web Share API with clipboard fallback, toast notification
- [x] **W14: Snow Forecast Card** — 24h/48h/72h predicted snowfall with storm badges
- [x] **W15: Fresh Snow Chart** — 7-day daily snowfall bar chart using Recharts
- [x] **W16: Webcam Link** — Camera icon + webcam link in resort detail header

### Android Parity Gaps (vs iOS)

#### HIGH PRIORITY
- [x] **A1: Data Sources Card** — Expandable card in resort detail showing per-source snowfall, consensus/outlier status, merge method
- [x] **A2: Map Clustering** — Google Maps Compose clustering with custom marker/cluster rendering, quality-colored badges
- [x] **A3: Map Region Presets** — 9 region FilterChips (Show All, NA West, Rockies, NA East, Alps, Scandinavia, Japan, Oceania, S. America)
- [x] **A4: Streaming Chat** — SSE streaming via ChatStreamService with OkHttp, integrated in ChatRepository with fallback to REST
- [x] **A5: Map Forecast Mode** — Date selector chips, forecast loading per-resort, forecast banner with loading state

#### MEDIUM PRIORITY
- [ ] **A6: Google Sign-In** — Button exists but onClick is placeholder (not functional)
- [ ] **A7: Trip Creation** — FAB button has TODO comment, not implemented
- [ ] **A8: Comparison View** — Stub screen with placeholder text
- [x] **A9: Onboarding Flow** — Multi-step: Welcome screen with feature highlights, region selection grid (8 regions), saves hidden regions to preferences
- [x] **A10: Fresh Snow Chart** — Compose Canvas 7-day snowfall bar chart with per-elevation breakdown, unit-aware formatting

---

## Previous Work (Feb 25)

### Workstream 6: Weather Data & Grey Resorts Fix

#### Timeline Depth Fix
- [x] Fix unrealistic snow depth forecast collapse (144cm→11cm in 4 days at sub-zero)
- [x] Temperature-aware melt rates: 3cm/day sub-zero, 15cm/day above-zero
- [x] Add 13 new tests for smoothing edge cases
- [x] Deploy to prod

#### Grey Resorts Fix (576 resorts showing question marks)
- [x] Root cause analysis: 876 non-NA resorts had empty region in DynamoDB
- [x] Fix populate_resorts.py to use proper region from resorts.json
- [x] Add weather processor chunking (max 100 per worker)
- [x] Re-populate DynamoDB (staging + prod)
- [x] Trigger weather processor to fetch data for all resorts
- [x] Verify grey count drops — confirmed: Pamporovo, Ruka, Hakuba, Zermatt all have scores

#### Weather API Research (completed)
- [x] Evaluate 10 alternative weather data sources
- [ ] Weather Unlocked: per-elevation forecasts ($220-420/mo) — best fit, needs signup
- [ ] Synoptic Data/SNOTEL: free US station observations — needs integration
- [ ] Tomorrow.io: test free tier snow depth quality

---

## Previous Active Work (Feb 24)

### Workstream 5: Chat UX Improvements

#### iOS Chat Fixes
- [x] Split streaming messages into separate bubbles at tool boundaries (thinking vs final response)
- [x] Fix conversation history not loading (ISO 8601 date parsing in ChatMessage/ChatConversation)
- [x] Style intermediate "thinking" messages: italic, muted color, lighter background
- [x] Deploy to TestFlight
- [x] Test chat: verified streaming, tool status, and response display on simulator
- [x] Verify conversation history: backend returns ISO 8601 dates, iOS parser handles them
- [x] Fix map Region menu accessibility label for UI test
- [x] Add map region switching UI test (Alps, Japan, Rockies)

#### Completed Earlier (Feb 24)
- [x] Fix fresh powder chart: axes legend, "Crust formed" label, "since last thaw" subtitle
- [x] Fix map: proactive condition fetching for all visible resorts
- [x] Fix map: add yellow segment to cluster pie chart for "decent" quality
- [x] Expand quality labels from 6 to 10 levels (backend + iOS)
- [x] Fix trail distribution passthrough for Big White and others
- [x] Add 9 new unit tests (DailySnowData, crust date regression)
- [x] Add Fresh Powder Chart UI test

---

## Previous Active Work (Feb 23)

### Workstream 1: Wind & Visibility Features (ML + UI)

#### Investigation
- [x] Investigate Big White scoring (borderline 4.3 threshold, snowfall_24h=1.8cm not 16.7cm)
- [x] Check what weather data Open-Meteo provides for wind/visibility (wind_gusts_10m, visibility)
- [x] Audit current ML features for wind/visibility gaps (missing: gusts, visibility)

#### ML Model Updates
- [x] Add wind gust and visibility to Open-Meteo API calls (openmeteo_service.py)
- [x] Add visibility_km, min_visibility_24h_km, max_wind_gust_norm features (ml_scorer.py)
- [x] Update collect_data.py with new features
- [x] Re-collect training features (11,960 samples from 134 resorts)
- [x] Retrain model v13 with 37 features (MAE=0.265, R²=0.880, 99% within-1)
- [x] Deploy updated model weights to prod

#### Backend Updates
- [x] Add wind_gust_kmh, max_wind_gust_24h, visibility_m, min_visibility_24h_m to API response
- [x] Update quality explanation to mention wind/visibility when significant
- [x] Trigger weather processor to populate new fields in DynamoDB

#### iOS UI
- [x] Show wind gust, max gust 24h in resort detail view (PR #183)
- [x] Show visibility with color-coded severity when < 5km
- [x] Add VoiceOver accessibility for wind/visibility
- [x] Deploy to TestFlight

#### Android
- [x] Add wind gust and visibility fields to Android weather models
- [x] Show wind/visibility in resort detail and timeline views
- [ ] Deploy to internal testing (pending Google Play setup)

#### Web
- [x] Web: show wind gust & visibility in conditions table with color-coded severity

### Workstream 2: Resort Data Audit (1040 resorts)

#### Critical: Coordinate Fix
- [x] Geocode 862 resorts with (0,0) coordinates (all 1040 now have valid coords)
- [x] Fix 2 Austrian resorts misattributed as US/CA, 2 Italian resorts as FR
- [x] Commit updated resorts.json with coordinates
- [x] Re-populate DynamoDB (staging + prod)
- [x] Trigger weather processor for newly-geocoded resorts

#### Data Quality Audit & Fixes
- [x] Run comprehensive data quality audit (1237 issues found)
- [x] Null out corrupted elevations for 252 resorts (exceeded country max)
- [x] Normalize pass affiliations ("Unlimited" -> "full", "5 days" -> "local/base")
- [x] Recalculate large_resort based on vertical drop >= 800m
- [x] Clean zero-width spaces from 119 resort names
- [x] Add DE, SI, ES, AD to alps region definition
- [x] Run percentages: enriched from 2.8% to 93.8% coverage (948 resorts scraped)
- [x] Website URLs: enriched from 13.2% to 85.4% coverage (751 resorts)
- [x] Annual snowfall: enriched 446/1040 resorts (42.9%) via Open-Meteo historical API
- [x] Base elevations: enriched 994/1040 (95.6%) from DEM + skiresort.info
- [x] Top elevations: enriched 903/1040 (86.8%) from skiresort.info (fixed scraper bug)
- [x] Fixed 459 corrupted elevation values (scraper artifacts from "Similar Resorts")
- [x] Computed family_friendly (976), expert_terrain (983), vertical_drop (870) from data
- [x] Fix 6 data quality issues: 3 elevation swaps, 3 trail percentage scrape errors
- [ ] Annual snowfall: 594 resorts still missing (Open-Meteo daily rate limit, retry tomorrow)
- [ ] 47 resorts not found on skiresort.info (Chinese, heli-ski, indoor)

### Workstream 3: List & Map Performance Fixes

#### iOS
- [x] Increase batch quality fetch from 300 to 2000 (all resorts get quality data)
- [x] Add snow quality score to map detail sheet badge
- [x] Add summary data fallback in map detail when conditions unavailable
- [x] Deploy to TestFlight

#### Android
- [x] Fix map view: add chunked batch quality fetching (was sending all 1040 IDs at once)
- [x] Fix favorites view: add chunked batch quality fetching
- [ ] Deploy to internal testing (pending Google Play setup)

---

## Current Issues (Priority Order)

### Workstream 4: Critical Bug Fixes (Feb 23 evening)

#### iOS List View
- [x] Progressive batch loading (update UI per batch, not all-at-once)
- [x] S3 static JSON was missing — fixed generator (sequential processing, larger connection pool). 1040 resorts in 266s.
- [x] List/detail data discrepancy resolved — synthesizeSummary() syncs detail→list, S3 static JSON now fresh

#### iOS Map View
- [x] Map detail sheet: show summary data immediately while full conditions load
- [x] Cluster view verified working — "0 resorts" was transient (stale data, no S3 JSON)
- [x] Fix grey screen on first annotation tap — changed `.sheet(isPresented:)` to `.sheet(item:)` pattern
- [x] Fix initial zoom showing entire world — default to NA Rockies region, user location when available
- [x] Fix region presets not applying — added `pendingRegion` coordination with MKMapView

#### Backend: ML Scorer Bug
- [x] Fix extract_features_from_condition() missing visibility_m, min_visibility_24h_m, max_wind_gust_24h
- [x] Deploy to prod, trigger weather processor to recompute scores

#### Backend: Chat Streaming
- [x] Fix chat stream Lambda crash: `ModuleNotFoundError: No module named 'jwt'` — changed to `from jose import jwt`
- [x] Deploy fix to staging + prod
- [x] Fix chat not answering "best powder" questions — system prompt now instructs to use `get_best_conditions` tool

#### Backend: Snow History
- [x] Fix: DAILY_HISTORY_TABLE env var missing from prod API Lambda (defaulted to dev table)
- [x] Set env var on prod + staging API Lambdas — history now working

#### iOS: App Store Connect
- [ ] Upload metadata and screenshots to App Store Connect
- [ ] Submit for review

#### Backend: Static JSON Generator
- [x] Fix connection pool exhaustion — changed from 20 parallel workers to sequential processing
- [x] Increase connection pool to 25, add retry config
- [x] Increase Lambda memory 512→1024MB, timeout 600→900s (both infra + runtime)
- [x] Generate static JSON for prod (1040 resorts, 325KB, 266s)
- [x] Batch endpoint now reads from S3: 200 resorts in 130ms (was 5+ seconds)

#### Backend: Quality Explanations
- [x] Wind/visibility text now mentions score impact: "30 km/h wind decreases the score" (was "Windy (30 km/h)")
- [x] Same fix applied to timeline explanations
- [x] 10 regression tests for wind/visibility score impact text

#### Data Quality: Big White
- [x] Remove incorrect `epic_pass:"local"` — Big White is not an Epic Pass resort
- [x] Updated in resorts.json, pushed to DynamoDB, static JSON regenerated

#### UI Verification Tests
- [x] Add VerificationTests.swift with list/map/detail/chat tests
- [x] Add UI_TESTING to auto-auth bypass in SnowTrackerApp.swift
- [x] All verification tests passing on simulator
- [x] Add map detail sheet regression test (verifies no grey/empty screen)

### 🔴 Critical
| Issue | Description | Status |
|-------|-------------|--------|
| Chat broken | jwt import crash in chat_stream_handler.py | FIXED |
| ML scorer bug | Missing wind/visibility features in extract_features_from_condition | FIXED |
| S3 static JSON missing | Batch quality endpoint falling back to slow DynamoDB | FIXED |
| Snow history empty | DAILY_HISTORY_TABLE env var missing from API Lambda | FIXED |
| List view slow | S3 JSON never generated (Lambda OOM/timeout) → sequential processing | FIXED |
| Map grey screen | First annotation tap shows empty sheet (sheet(isPresented:) race) | FIXED |
| Map ugly zoom | Initial view shows entire world with 1040 resorts | FIXED |
| Chat ignoring questions | "Best powder?" returned location prompt instead of answer | FIXED |
| Wind/vis explanation | "Windy (30 km/h)" → "30 km/h wind decreases the score" | FIXED |
| Big White Epic badge | Incorrectly tagged as Epic Pass resort | FIXED |

### 🟡 Medium
| Issue | Description | Status |
|-------|-------------|--------|
| App Store Release | Need to upload metadata + screenshots | Pending |

### 🟢 Future Features
| Issue | Description |
|-------|-------------|
| Resort similarity engine | "Resorts like X with lots of green runs" — needs resort metadata |
| MCP distance search | Find best resorts within X km / Y hours drive |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode (Trips tab hidden for now) |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources |

---

## Completed Features

| Feature | Date |
|---------|------|
| Fix chat: split thinking bubbles, conversation history, intermediate message styling | 2026-02-24 |
| Fix map: proactive condition fetching, yellow pie segment | 2026-02-24 |
| Fix fresh powder chart: legend, crust formed label, 9 new tests | 2026-02-24 |
| Expand quality labels from 6 to 10 levels (backend + iOS) | 2026-02-24 |
| Fix trail distribution passthrough for Big White and others | 2026-02-24 |
| Fix map grey screen, wind/vis explanations, chat, Big White data (5 bug fixes) | 2026-02-24 |
| Fix static JSON generator: sequential processing, 1040 resorts in 266s | 2026-02-24 |
| Fix chat streaming: jwt→jose import, snow history: DAILY_HISTORY_TABLE env var | 2026-02-24 |
| Fix ML scorer: add wind/visibility features to extract_features_from_condition | 2026-02-24 |
| Add UI verification tests + auto-auth for UI_TESTING mode | 2026-02-24 |
| Fix 6 resort data quality issues: elevation swaps, trail pct scrape errors | 2026-02-23 |
| Android: fix batch quality chunking in map and favorites views | 2026-02-23 |
| iOS: fix list loading (quality fetch 300→2000), map score display, summary fallback | 2026-02-23 |
| Add wind gust and visibility to web conditions table with color-coded severity | 2026-02-23 |
| Enrich top elevations 903/1040 (86.8%) via skiresort.info, fix scraper elevation bug | 2026-02-23 |
| Enrich annual snowfall (446/1040), base elevations (994/1040), fix 459 corrupted elevations | 2026-02-23 |
| Compute family_friendly, expert_terrain, large_resort labels from existing data | 2026-02-23 |
| Fix Android stale data: sync quality updates from detail to list view | 2026-02-23 |
| Fix iOS list: slow refresh (21→2 API calls), stale data sync, filter scroll | 2026-02-23 |
| Enrich run percentages (93.8%) and website URLs (85.4%) from skiresort.info | 2026-02-23 |
| Fix resort data quality: elevations, pass values, labels, names (252 elevations, 73 passes) | 2026-02-23 |
| Geocode all 862 resorts with (0,0) coordinates, fix 4 country misattributions | 2026-02-23 |
| Add wind gust and visibility UI to Android app | 2026-02-23 |
| Retrain ML model v13 with wind gust and visibility features (37 features, 11960 samples) | 2026-02-23 |
| Add wind gust and visibility UI to iOS app (PR #183) | 2026-02-23 |
| Add wind gust and visibility to weather pipeline (backend + ML) | 2026-02-23 |
| Parallelize static JSON generator (ThreadPoolExecutor, 20 workers) | 2026-02-23 |
| Expand resort database from 138 to 1040 resorts across 25 countries | 2026-02-23 |
| Enrich resort data with prices, pass affiliations, and labels | 2026-02-23 |
| Increase static JSON Lambda to 10min/512MB for 1040 resorts | 2026-02-23 |
| Implement Live Activities & Dynamic Island for resort conditions | 2026-02-22 |
| Improve AI chat system prompt with interpretation guidance | 2026-02-22 |
| Fix chat compare_resorts crash, add missing API fields, optimize DynamoDB queries | 2026-02-22 |
| Add error handling to chat conversation endpoints | 2026-02-22 |
| Fix weekly digest double-counting cumulative forecast snow | 2026-02-22 |
| Extract shared ELEVATION_WEIGHTS constant, fix condition report query and confidence calc | 2026-02-22 |
| Fix chat service: parallelize resort auto-detect, re-raise save errors | 2026-02-22 |
| Add VoiceOver accessibility to condition report section | 2026-02-22 |
| Add timeline retry button and snow history chart accessibility | 2026-02-22 |
| Add error handling for Bedrock API calls in chat service | 2026-02-22 |
| Add VoiceOver accessibility to elevation profile bands | 2026-02-22 |
| Update quality info sheet to reflect current ML model stats | 2026-02-22 |
| Add VoiceOver labels to quality count badges and season stats | 2026-02-22 |
| Fix batch endpoint timeouts and None safety in recommendations | 2026-02-22 |
| Add retry button to map cluster view when data fails to load | 2026-02-22 |
| Retrain ML model with 127 new samples (2181 total, MAE=0.176) | 2026-02-22 |

---

## Architecture

### Snow Quality Algorithm
ML model v15: ensemble of 10 neural networks (40 features incl. visibility, wind gusts, hours_since_last_snowfall → quality score 1-6).
Val MAE 0.225, R² 0.937, 81.1% exact, 100% within-1. Trained on ~12,000 samples from 134 resorts. See `ml/ALGORITHM.md` for details.

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

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Weather Processor | Every 1 hour | Updates weather conditions via Open-Meteo API |
| Notification Processor | Every 1 hour | Sends push notifications |
| Scraper Orchestrator | Daily 06:00 UTC | Fans out to 23 country-specific workers |
| Version Consolidator | Daily 07:00 UTC | Aggregates scraper results |

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
