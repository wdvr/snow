# Snow Quality Tracker - Progress

## Status: LIVE IN PRODUCTION
**Last Updated**: 2026-01-24
**API**: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

---

## GitHub Issues = Source of Truth

All tasks tracked at: https://github.com/wdvr/snow/issues

```bash
# View issues by workflow label
gh issue list --label "agent-friendly"     # Ready for autonomous work
gh issue list --label "needs-user-input"   # Requires user decisions
gh issue list --label "complex"            # Multi-component features
```

### Agent-Friendly Issues (Ready to Work)
| Issue | Title | Component | Status |
|-------|-------|-----------|--------|
| [#12](https://github.com/wdvr/snow/issues/12) | Implement 60-second API caching | Backend | Done |
| [#15](https://github.com/wdvr/snow/issues/15) | Add offline caching for iOS app (SwiftData) | iOS | ✅ Done (PR #28) |
| [#18](https://github.com/wdvr/snow/issues/18) | Add more ski resorts to database | Backend | ✅ Done (PR #28) |
| [#21](https://github.com/wdvr/snow/issues/21) | Add pretty splash screen / launch screen | iOS | ✅ Done (PR #28) |

### Needs User Input
| Issue | Title | What's Needed |
|-------|-------|---------------|
| [#11](https://github.com/wdvr/snow/issues/11) | Widget not showing data | Device testing/logs |
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources | Decision on data source |
| [#16](https://github.com/wdvr/snow/issues/16) | Push notifications for snow alerts | APNs certificates |
| [#17](https://github.com/wdvr/snow/issues/17) | App Store preparation and TestFlight | App Store account |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App | Watch for testing |

### Complex Features (May Need Breakdown)
| Issue | Title | Components |
|-------|-------|------------|
| [#36](https://github.com/wdvr/snow/issues/36) | Proximity-based resort discovery with map | iOS + Backend |
| [#14](https://github.com/wdvr/snow/issues/14) | Sign in with Apple backend | iOS + Backend |
| [#22](https://github.com/wdvr/snow/issues/22) | Best Snow This Week - Location Recommendations | iOS + Backend |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode | iOS + Backend |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration | iOS + Backend + Research |

---

## Completed Features

| Feature | Date |
|---------|------|
| Production deployment | 2026-01 |
| 60-second API caching (21x faster) | 2026-01-24 |
| Unified Grafana monitoring | 2026-01-24 |
| 28+ ski resorts across 8 regions | 2026-01-24 |
| Region-based filtering (iOS + API) | 2026-01-24 |
| Animated splash screen | 2026-01-24 |
| Offline caching (SwiftData) | 2026-01-24 |
| iOS app with SwiftUI | 2026-01 |
| Snow predictions (24/48/72h) | 2026-01 |
| iOS Widgets (Favorites + Best Snow) | 2026-01 |
| Feedback & Share buttons | 2026-01 |
| Open-Meteo weather integration | 2026-01 |
| CloudWatch monitoring | 2026-01 |
| GitHub Actions CI/CD | 2026-01 |
| 94 backend tests, 46 iOS tests | 2026-01 |

---

## DynamoDB Tables
- `snow-tracker-resorts-prod`
- `snow-tracker-weather-conditions-prod` (TTL: 7 days)
- `snow-tracker-user-preferences-prod`
- `snow-tracker-feedback-prod`

---

## Quick Commands

```bash
# Test API
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts

# Run backend tests
cd backend && python -m pytest tests/ -v

# Deploy
gh workflow run deploy.yml -f environment=prod

# Seed resorts
AWS_PROFILE=personal python -m src.utils.resort_seeder --env prod
```

---

## Notes

### 2026-01-25
- Implemented region-based filtering for ski resorts (PR #28)
  - 8 regions: NA West, Rockies, East, Alps, Scandinavia, Japan, Oceania, South America
  - New `/api/v1/regions` endpoint
  - iOS filter chips with region icons
- Added animated splash screen with snow effects (PR #28)
- Implemented offline caching with SwiftData (PR #28)
- Expanded to 28+ resorts including Southern Hemisphere
- Fixed Pydantic V2 deprecation warnings
- Created resorts.json data management system

### 2026-01-24
- Deployed snow predictions, share button, iOS widgets
- Widget URL fixed (was pointing to old API)
- Weather data shows 0cm for Silver Star but user reports 1cm actual
- Switched from weatherapi.com to Open-Meteo for better elevation data
- Created workflow labels for hybrid agent/dev workflow
- Created issues #22-25 for planned features
