# Snow Quality Tracker - Progress

## Status: LIVE
**Last Updated**: 2026-01-27

### API Endpoints
- **Staging**: https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
- **Production**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

---

## GitHub Issues = Source of Truth

All tasks tracked at: https://github.com/wdvr/snow/issues

### Open Issues

| Issue | Title | Priority |
|-------|-------|----------|
| [#22](https://github.com/wdvr/snow/issues/22) | Best Snow This Week - Location Recommendations | High |
| [#14](https://github.com/wdvr/snow/issues/14) | Sign in with Apple backend | Medium |
| [#16](https://github.com/wdvr/snow/issues/16) | Push notifications for snow alerts | Medium |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode | Medium |
| [#17](https://github.com/wdvr/snow/issues/17) | App Store preparation and TestFlight | Low |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources | Low |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration | Low |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App | Low |

---

## Completed Features

| Feature | Date |
|---------|------|
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

Ice forms when: 3h @ +3°C, 6h @ +2°C, or 8h @ +1°C

### DynamoDB Tables
- `snow-tracker-resorts-{env}`
- `snow-tracker-weather-conditions-{env}` (TTL: 7 days)
- `snow-tracker-user-preferences-{env}`
- `snow-tracker-feedback-{env}`

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

# View issues
gh issue list --state open
```

---

## Known Technical Debt

1. **JWT authentication not implemented** - Returns hardcoded test user
2. **CORS allows all origins** - Should be configured per environment
