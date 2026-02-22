# Powder Chaser - Progress

## Status: LIVE
**Last Updated**: 2026-02-22

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Current Issues (Priority Order)

### 🔴 Critical
| Issue | Description | Status |
|-------|-------------|--------|
| (none) | | |

### 🟡 Medium
| Issue | Description | Status |
|-------|-------------|--------|
| App Store Release | Need provisioning profile with Push Notifications | User action needed |

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
| Improve share text with snow score, depth, and forecast | 2026-02-22 |
| Add storm badge to Favorites tab when significant snow predicted | 2026-02-22 |
| Improve resort search to match country codes and pass types | 2026-02-22 |
| Add storms incoming section to favorites summary card | 2026-02-22 |
| Add Snow Depth and Predicted Snow sort options to resort list | 2026-02-22 |
| Add snow depth and forecast data to batch quality endpoint | 2026-02-22 |
| Add forecast badge to resort list when significant snow is expected | 2026-02-22 |
| Add forecast badge to favorites when significant snow is expected | 2026-02-22 |
| Add markdown rendering for AI chat responses (headers, lists, code blocks) | 2026-02-22 |
| Improve chat AI system prompt for markdown-formatted responses | 2026-02-22 |
| Add snow history + resort comparison tools to AI chat (9 tools total) | 2026-02-22 |
| Add Fresh Snow and Temperature sort options to resort list | 2026-02-22 |
| Add small widget size for Favorites and Best Snow widgets | 2026-02-22 |
| Add condition reports tool to AI chat for on-the-ground context | 2026-02-22 |
| Add Epic/Ikon pass filter to resort list with persistence | 2026-02-22 |
| Add conditions summary card to favorites view | 2026-02-22 |
| Fix recommendation falsy value bug, add error logging to 32 endpoints | 2026-02-22 |
| Remove 6 duplicate resorts, add Fortress Mountain, clean up DynamoDB orphans | 2026-02-22 |
| Update About view to show dynamic resort count, fix all branding references | 2026-02-22 |
| Enhance chat AI system prompt with quality definitions + 20 new aliases | 2026-02-22 |
| Add chat retry button, accessibility labels, fix diacritics search | 2026-02-22 |
| Fix global recommendations favoring tiny resorts (vertical drop weight) | 2026-02-22 |
| Add Epic/Ikon pass badges to resort list and favorites views | 2026-02-22 |
| Add chat auto-suggest: pre-detect resort mentions for faster responses | 2026-02-22 |
| Fix elevation consistency: explanation temperature matches temperature_c | 2026-02-22 |
| Replace silent exception handlers with warning-level logging | 2026-02-22 |
| Retrain ML model with 127 new samples (2181 total, MAE=0.176) | 2026-02-22 |
| Fix elevation profile shape (mountain not Christmas tree) | 2026-02-22 |
| Fix NavigationLink eager view creation causing list view hang | 2026-02-22 |
| Fix Bedrock IAM policy for cross-region inference profiles | 2026-02-22 |
| Fix trail map populate script missing new fields | 2026-02-22 |
| Fix chat Bedrock model ID and IAM permissions | 2026-02-22 |
| App Store Release | 2026-02-22 |
| Add trail map links + run difficulty bars (green/blue/black %) to detail view | 2026-02-21 |
| Add run breakdown data for 26 core resorts | 2026-02-21 |
| Fix chat Bedrock model ID (us.anthropic.claude-sonnet-4-6) | 2026-02-21 |
| Fix main thread blocking: batch @Published conditions updates | 2026-02-21 |
| Add weather comfort features to ML model v12 (wind chill, solar) | 2026-02-21 |
| Add simulated streaming UX for AI chat responses | 2026-02-21 |
| Add gradient backgrounds + weather overlays (snow/sun/wind) | 2026-02-21 |
| Fix retry button loading feedback | 2026-02-21 |
| Soften dark mode gradient colors | 2026-02-21 |
| Fix environment switch requiring app restart | 2026-02-21 |
| Rename app to "Powder Chaser" across iOS + 13 languages | 2026-02-21 |
| Rewrite App Store metadata (description, subtitle, keywords) | 2026-02-21 |
| Fix "soft" quality explanation at cold temps (<-5°C) | 2026-02-21 |
| Fix map cluster tap showing empty screen (no loading state) | 2026-02-21 |
| Fix map cluster/detail not showing snow quality from summaries | 2026-02-21 |
| Add 63 new production training samples to ML dataset (1740 total) | 2026-02-21 |
| Add 213 tests: scraper_worker, version_consolidator, weather_worker | 2026-02-21 |
| Add 205 tests for api_handler, cache, resort_loader | 2026-02-21 |
| Remove unused non-prefs-aware formatting methods from iOS | 2026-02-21 |
| Lower timeline smoothing rate to 2cm/h (fix production drops) | 2026-02-21 |
| Add 39 snow_summary_service tests | 2026-02-21 |
| Fix conditions endpoint returning 50 entries instead of 3 | 2026-02-21 |
| Fix batch API resort_count reporting requested vs returned count | 2026-02-21 |
| Add timeline snow depth smoothing (prevent impossible forecast drops) | 2026-02-21 |
| Add retry button to resort detail no-data state | 2026-02-21 |
| Add 60 notification_service tests, fix thaw alert timezone bug | 2026-02-21 |
| Remove duplicate resorts (silverstar, northstar-california-resort) | 2026-02-21 |
| Fix batch API snowfall_fresh_cm returning wrong field | 2026-02-21 |
| Add 43 weather_processor tests | 2026-02-21 |
| Add 58 openmeteo_service tests | 2026-02-21 |
| Cap fresh_snow_cm at snow_depth_cm to prevent contradictory explanations | 2026-02-21 |
| Add 65 ml_scorer tests | 2026-02-21 |
| ML model v9: snow_depth feature, MAE 0.180, 83.5% exact | 2026-02-21 |
| Fix all remaining iOS hardcoded unit calls | 2026-02-21 |
| Update quality info sheet and descriptions to match ML model approach | 2026-02-21 |
| Fix notification threshold display to respect unit preference | 2026-02-21 |
| Fix ForecastBadge hardcoding cm instead of respecting unit preference | 2026-02-21 |
| Synthesize mixed-elevation explanations when no elevation matches overall | 2026-02-21 |
| ML model v8: MAE 0.299, within-1 100%, R² 0.870 | 2026-02-21 |
| Fix recommendation reason text to match quality labels | 2026-02-21 |
| Match overall explanation to weighted quality level | 2026-02-21 |
| Use weighted elevation quality in recommendations (consistency fix) | 2026-02-21 |
| Improve cold accumulation boost and explanation text for deep snow | 2026-02-21 |
| Fix all resorts missing from recommendations (GSI pagination + ProjectionExpression) | 2026-02-21 |
| Increase API Lambda memory to 512MB | 2026-02-21 |
| Fix recommendation scoring plateau (log scale for fresh snow) | 2026-02-21 |
| Optimize iOS sort performance (pre-compute lookups) | 2026-02-21 |
| Reduce DynamoDB queries 3x (single-query per resort) | 2026-02-21 |
| Add structured logging and request timing middleware | 2026-02-21 |
| iOS: API retry logic with exponential backoff | 2026-02-21 |
| iOS: Replace 62 debug prints with os.Logger | 2026-02-21 |
| Fix recommendation reason text formatting | 2026-02-21 |
| Fix DynamoDB Limit+Filter bug for multi-elevation queries | 2026-02-21 |
| Add missing API Gateway routes (regions, auth, trips, snow-quality) | 2026-02-21 |
| Use ML model for timeline quality predictions | 2026-02-21 |
| Replace deprecated datetime.utcnow() with datetime.now(UTC) | 2026-02-21 |
| ML model v7: retrained on corrected elevation data | 2026-02-21 |
| Notification deep linking to resort detail | 2026-02-20 |
| Thaw-freeze info popover in resort detail | 2026-02-20 |
| Fix 12 more na_east resort elevations | 2026-02-20 |
| Add 3 missing resorts (Bretton Woods, Jay Peak, Loon Mountain) | 2026-02-20 |
| Protect elevation data from scraper overwrites | 2026-02-20 |
| Fix elevation data for 94+ resorts (critical weather accuracy) | 2026-02-20 |
| Populate workflow: source and update_existing inputs | 2026-02-20 |
| ML model v6: 10-model ensemble, 93.6% exact accuracy | 2026-02-20 |
| Optimized quality thresholds (v5.1): 87.4% → 92.7% | 2026-02-20 |
| ML model v5: deterministic labels, 87.4% exact accuracy | 2026-02-20 |
| Map view date selector for nearby resorts | 2026-02-20 |
| Map markers use top elevation for snow quality (not base) | 2026-02-04 |
| Core resorts protected from false removal notifications | 2026-02-04 |
| Support page with contact form | 2026-02-04 |
| Buy Me a Coffee link on website | 2026-02-04 |
| Removed Privacy Policy/Terms from iOS (not needed yet) | 2026-02-04 |
| Simplified tab bar (5 tabs, Trips hidden) | 2026-02-04 |
| DKIM email verification for powderchaserapp.com | 2026-02-04 |
| Snow accumulation delta tracking fix | 2026-02-04 |
| iOS notification sync fix | 2026-02-03 |
| Resort database versioning system | 2026-02-03 |
| 13 language translations | 2026-02-03 |
| S3 → DynamoDB pipeline for scraped resorts | 2026-02-03 |
| SNS notifications for new resorts | 2026-02-03 |
| East Coast resorts (VT, NH, ME) | 2026-02-03 |
| Parallel resort scraper (23 countries) | 2026-02-03 |
| Parallel weather processing | 2026-02-03 |
| Best Snow Recommendations | 2026-02-03 |
| Push Notifications | 2026-02-03 |
| Firebase Analytics & Crashlytics | 2026-02-02 |
| Daily resort scraper | 2026-02-02 |
| Push notification infrastructure (APNS) | 2026-02-01 |
| Proximity-based resort discovery | 2026-01-27 |
| Freeze-thaw detection (14-day lookback) | 2026-01-25 |
| Snow quality ratings | 2026-01-25 |
| CloudWatch metrics + Grafana | 2026-01-25 |
| 60-second API caching | 2026-01-24 |
| 900+ ski resorts across 23 countries | 2026-01-24 |
| iOS Widgets | 2026-01 |

---

## Architecture

### Snow Quality Algorithm
ML model v11: ensemble of 10 neural networks (29 features incl. snow_depth → quality score 1-6).
Val MAE 0.176, R² 0.955, 83.5% exact, 100% within-1. Trained on 2181 samples across 134 resorts. See `ml/ALGORITHM.md` for details.

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
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts/big-white/conditions

# Run tests
cd backend && python -m pytest tests/ -v

# Deploy (auto on push to main)
git push origin main

# Trigger weather processor
gh workflow run trigger-weather.yml -f environment=staging

# View issues
gh issue list --state open
```
