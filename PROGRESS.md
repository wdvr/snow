# Powder Chaser - Progress

## Status: LIVE
**Last Updated**: 2026-02-23

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Active Work (Feb 23)

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

#### Backend: ML Scorer Bug
- [x] Fix extract_features_from_condition() missing visibility_m, min_visibility_24h_m, max_wind_gust_24h
- [x] Deploy to prod, trigger weather processor to recompute scores

#### Backend: Chat Streaming
- [x] Fix chat stream Lambda crash: `ModuleNotFoundError: No module named 'jwt'` — changed to `from jose import jwt`
- [x] Deploy fix to staging + prod

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

#### UI Verification Tests
- [x] Add VerificationTests.swift with list/map/detail/chat tests
- [x] Add UI_TESTING to auto-auth bypass in SnowTrackerApp.swift
- [x] All verification tests passing on simulator

### 🔴 Critical
| Issue | Description | Status |
|-------|-------------|--------|
| Chat broken | jwt import crash in chat_stream_handler.py | FIXED |
| ML scorer bug | Missing wind/visibility features in extract_features_from_condition | FIXED |
| S3 static JSON missing | Batch quality endpoint falling back to slow DynamoDB | FIXED |
| Snow history empty | DAILY_HISTORY_TABLE env var missing from API Lambda | FIXED |
| List view slow | S3 JSON never generated (Lambda OOM/timeout) → sequential processing | FIXED |

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
ML model v13: ensemble of 10 neural networks (37 features incl. visibility, wind gusts → quality score 1-6).
Val MAE 0.265, R² 0.880, 74.7% exact, 99% within-1. Trained on 11,960 samples from 134 resorts. See `ml/ALGORITHM.md` for details.

Quality levels: EXCELLENT (6) → GOOD (5) → FAIR (4) → POOR (3) → BAD (2) → HORRIBLE (1)

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
