# Snow Quality Tracker - Progress

## Status: LIVE (Ready for Open Source)
**Last Updated**: 2026-02-04

### Endpoints & Website
- **Staging API**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
- **Marketing Website**: https://powderchaserapp.com
- **Support**: https://powderchaserapp.com/support

---

## Current Issues (Priority Order)

### 🔴 Critical
*None*

### 🟡 Medium
| Issue | Description | Status |
|-------|-------------|--------|
| Apple Sign In Email | Shows "Apple ID (000495...)" instead of email | Backlog |
| App Store Release | Need provisioning profile with Push Notifications | User action needed |

### 🟢 Future Features
| Issue | Description |
|-------|-------------|
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode (Trips tab hidden for now) |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources |

---

## Completed Features

| Feature | Date |
|---------|------|
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
Quality is based on **fresh powder since last thaw-freeze event**:
- **Excellent**: 3+ inches (7.6+ cm) of fresh snow
- **Good**: 2-3 inches (5-7.6 cm)
- **Fair**: 1-2 inches (2.5-5 cm)
- **Poor**: <1 inch (<2.5 cm)
- **Bad/Icy**: No fresh snow, cold temps
- **Horrible**: No snow, warm temps (not skiable)

**Ice forms when**: 3h @ +3°C, 6h @ +2°C, or 8h @ +1°C

### DynamoDB Tables
- `snow-tracker-resorts-{env}`
- `snow-tracker-weather-conditions-{env}` (TTL: 7 days)
- `snow-tracker-snow-summary-{env}`
- `snow-tracker-user-preferences-{env}`
- `snow-tracker-feedback-{env}`
- `snow-tracker-device-tokens-{env}`

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
