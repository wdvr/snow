# Snow Quality Tracker - Progress

## Status: LIVE
**Last Updated**: 2026-02-03

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging ✅
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod ✅
- **Marketing Website**: https://powderchaserapp.com ✅

---

## Current Issues (Priority Order)

### 🔴 Critical
| Issue | Description | Status |
|-------|-------------|--------|
| Apple Sign In Email | Shows "Apple ID (000495...)" instead of email or relay email | **Needs Fix** |

### 🟡 Medium
| Issue | Description | Status |
|-------|-------------|--------|
| Near You Limit | Shows only 6 items (requests 10, limited by resorts in range) | **Fixed** (increased default radius to 1000km) |

### 🟢 Low / Monitoring
| Issue | Description | Status |
|-------|-------------|--------|
| Feedback Storage | Need to verify feedback is being saved to DynamoDB | Verify after deploy |
| Snow Accumulation | Logic verified correct - accumulates after ice events | ✅ Working |

---

## GitHub Issues = Source of Truth

All tasks tracked at: https://github.com/wdvr/snow/issues

### Open Issues

| Issue | Title | Priority |
|-------|-------|----------|
| [#88](https://github.com/wdvr/snow/issues/88) | Add missing resorts (Crystal Mountain, Stevens Pass, etc.) | High |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode | Medium |
| [#17](https://github.com/wdvr/snow/issues/17) | App Store preparation and TestFlight | Low |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources | Low |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration | Low |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App | Low |

---

## Completed Features

| Feature | Date |
|---------|------|
| Parallel resort scraper (orchestrator/worker pattern, 23 countries) | 2026-02-03 |
| Parallel weather processing architecture (#90) | 2026-02-03 |
| Map icons show correct snow quality colors (was showing "?") | 2026-02-03 |
| List view shows fresh snow (snowfall_after_freeze) for all resorts | 2026-02-03 |
| Batch snow quality API returns temp and fresh snow data | 2026-02-03 |
| iOS list view fallback to summary data when conditions unavailable | 2026-02-03 |
| Best Snow Recommendations feature (#22 closed) | 2026-02-03 |
| Push Notifications fully implemented (#16 closed) | 2026-02-03 |
| Near You default radius increased to 1000km | 2026-02-03 |
| Firebase Analytics & Crashlytics integration | 2026-02-02 |
| Daily resort scraper (was monthly) | 2026-02-02 |
| Google logo SVG fix | 2026-02-02 |
| Notification token field fix | 2026-02-02 |
| Push notification infrastructure (APNS) | 2026-02-01 |
| Notification settings UI | 2026-02-01 |
| Proximity-based resort discovery with sorting | 2026-01-27 |
| Freeze-thaw detection (14-day lookback) | 2026-01-25 |
| Snow quality ratings (Excellent→Horrible) | 2026-01-25 |
| Manual weather processor trigger workflow | 2026-01-25 |
| CloudWatch metrics + Grafana dashboards | 2026-01-25 |
| OnTheSnow scraper for real snow depth | 2026-01-25 |
| 60-second API caching (21x faster) | 2026-01-24 |
| 28+ ski resorts across 8 regions | 2026-01-24 |
| Region-based filtering | 2026-01-24 |
| Animated splash screen | 2026-01-24 |
| Offline caching (SwiftData) | 2026-01-24 |
| iOS Widgets (Favorites + Best Snow) | 2026-01 |
| Snow predictions (24/48/72h) | 2026-01 |

---

## Architecture

### Snow Quality Algorithm
Quality is based on **fresh powder since last thaw-freeze event**:
- **Excellent**: 3+ inches (7.6+ cm) of fresh snow
- **Good**: 2-3 inches (5-7.6 cm)
- **Fair**: 1-2 inches (2.5-5 cm)
- **Poor**: <1 inch (<2.5 cm)
- **Bad/Icy**: No fresh snow, cold temps
- **Horrible**: No snow, warm temps (not skiable)

**Ice forms when**: 3h @ +3°C, 6h @ +2°C, or 8h @ +1°C

### Snow Accumulation (Verified ✅)
- Tracks `snowfall_after_freeze_cm` - snow accumulated since last ice event
- Example: 5cm + 4cm + 10cm = 19cm total (as long as no thaw)
- Resets when ice formation thresholds are met
- 14-day lookback for ice detection

### DynamoDB Tables
- `snow-tracker-resorts-{env}`
- `snow-tracker-weather-conditions-{env}` (TTL: 7 days)
- `snow-tracker-user-preferences-{env}`
- `snow-tracker-feedback-{env}`
- `snow-tracker-device-tokens-{env}`

---

## Monitoring (Grafana)

### Access
```bash
# Get Grafana workspace URL
aws grafana list-workspaces --query 'workspaces[?name==`snow-tracker-grafana`].endpoint' --output text
```
Sign in via AWS SSO (IAM Identity Center)

### Available Dashboards
1. **Snow Tracker API** - Request count, latency, errors, DynamoDB metrics
2. **API Performance** - Latency gauges, error rates, Lambda metrics
3. **Scraping Monitor** - Scraper success rate, resorts processed, errors
4. **DynamoDB Metrics** - Read/write capacity, throttles, item counts
5. **Conditions Monitor** - Snow quality scores, accumulation, warming alerts

### Custom Metric Namespaces
- `SnowTracker/Scraping` - Scraper performance
- `SnowTracker/Conditions` - Snow quality metrics

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Weather Processor | Every 1 hour | Updates weather conditions via Open-Meteo API |
| Notification Processor | Every 1 hour | Processes and sends push notifications |
| Scraper Orchestrator | Daily at 06:00 UTC | Fans out to 23 country-specific worker Lambdas |
| Scraper Workers | On-demand | Scrapes resorts from skiresort.info per country |

---

## Quick Commands

```bash
# Test staging API
curl https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging/api/v1/resorts/big-white/conditions

# Run backend tests
cd backend && python -m pytest tests/ -v

# Deploy to staging
git push origin main

# Trigger weather processor manually
gh workflow run trigger-weather.yml -f environment=staging -f wait_for_completion=true

# Run scraper manually
gh workflow run daily-scrape.yml

# View issues
gh issue list --state open
```

---

## Known Technical Debt

1. **Apple Sign In email display** - Falls back to truncated ID instead of relay email
2. **CORS allows all origins** - Should be configured per environment
