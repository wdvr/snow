# Snow Quality Tracker - Progress

## Status: LIVE IN PRODUCTION
**Last Updated**: 2026-01-25
**API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

---

## GitHub Issues = Source of Truth

All tasks tracked at: https://github.com/wdvr/snow/issues

### Open Issues

| Issue | Title | Priority | Status |
|-------|-------|----------|--------|
| [#36](https://github.com/wdvr/snow/issues/36) | Proximity-based resort discovery with map | High | Ready |
| [#22](https://github.com/wdvr/snow/issues/22) | Best Snow This Week - Location Recommendations | High | Ready |
| [#14](https://github.com/wdvr/snow/issues/14) | Sign in with Apple backend | Medium | Needs planning |
| [#16](https://github.com/wdvr/snow/issues/16) | Push notifications for snow alerts | Medium | Needs APNs setup |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode | Medium | Complex |
| [#17](https://github.com/wdvr/snow/issues/17) | App Store preparation and TestFlight | Low | Needs account |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources | Low | Research |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration | Low | Research |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App | Low | Needs watch |

### Closed Issues
- #11 Widget debugging (fixed)
- #12 API caching (21x faster)
- #15 Offline caching (SwiftData)
- #18 Add more resorts (28+ resorts)
- #21 Splash screen

---

## Completed Features

| Feature | Date |
|---------|------|
| CloudWatch custom metrics + Grafana dashboards | 2026-01-25 |
| Conditional CI (skip iOS tests when not needed) | 2026-01-25 |
| OnTheSnow scraper for real snow depth | 2026-01-25 |
| 60-second API caching (21x faster) | 2026-01-24 |
| Unified Grafana monitoring | 2026-01-24 |
| 28+ ski resorts across 8 regions | 2026-01-24 |
| Region-based filtering (iOS + API) | 2026-01-24 |
| Animated splash screen | 2026-01-24 |
| Offline caching (SwiftData) | 2026-01-24 |
| iOS app with SwiftUI | 2026-01 |
| Snow predictions (24/48/72h) | 2026-01 |
| iOS Widgets (Favorites + Best Snow) | 2026-01 |
| Open-Meteo weather integration | 2026-01 |
| GitHub Actions CI/CD | 2026-01 |

---

## Architecture

### API Endpoints
```
Base URL: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

GET  /health                           - Health check
GET  /api/v1/regions                   - List ski regions
GET  /api/v1/resorts                   - List all resorts
GET  /api/v1/resorts?region={region}   - Filter by region
GET  /api/v1/resorts/{id}              - Resort details
GET  /api/v1/resorts/{id}/conditions   - Weather conditions
GET  /api/v1/resorts/{id}/snow-quality - Snow quality summary
POST /api/v1/feedback                  - Submit feedback
```

### DynamoDB Tables
- `snow-tracker-resorts-{env}`
- `snow-tracker-weather-conditions-{env}` (TTL: 7 days)
- `snow-tracker-user-preferences-{env}`
- `snow-tracker-feedback-{env}`

### CloudWatch Metrics (SnowTracker/Scraping)
- ResortsProcessed, ConditionsSaved, ProcessingDuration
- ScraperHits, ScraperMisses, ScraperSuccessRate
- ProcessingErrors

---

## Quick Commands

```bash
# Test API
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts

# Run backend tests
cd backend && python -m pytest tests/ -v

# Deploy
gh workflow run deploy.yml -f environment=staging

# View issues
gh issue list --state open
```

---

## Known Technical Debt

1. **JWT authentication not implemented** - Currently returns hardcoded test user
2. **CORS allows all origins** - Should be configured per environment
3. **ERA5 snow depth** - Deferred to background job for performance

---

## Notes

### 2026-01-25
- Added CloudWatch custom metrics to weather processor
- Created Grafana dashboard JSON files (scraping, API, DynamoDB)
- Implemented conditional CI - iOS tests skip when not needed
- Merged OnTheSnow scraper for real snow depth data
- Fixed Pydantic v2 deprecation warnings (.dict() -> .model_dump())
- Cleaned up unused code and improved CORS configuration
