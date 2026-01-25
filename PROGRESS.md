# Snow Quality Tracker - Progress

## Status: LIVE IN PRODUCTION
**Last Updated**: 2026-01-25
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

### Open Issues

#### Needs User Input
| Issue | Title | What's Needed |
|-------|-------|---------------|
| [#13](https://github.com/wdvr/snow/issues/13) | Research alternative snow data sources | Decision on data source |
| [#16](https://github.com/wdvr/snow/issues/16) | Push notifications for snow alerts | APNs certificates |
| [#17](https://github.com/wdvr/snow/issues/17) | App Store preparation and TestFlight | App Store account |
| [#25](https://github.com/wdvr/snow/issues/25) | Apple Watch App | Watch for testing |

#### Complex Features (May Need Breakdown)
| Issue | Title | Components |
|-------|-------|------------|
| [#14](https://github.com/wdvr/snow/issues/14) | Sign in with Apple backend | iOS + Backend |
| [#22](https://github.com/wdvr/snow/issues/22) | Best Snow This Week - Location Recommendations | iOS + Backend |
| [#23](https://github.com/wdvr/snow/issues/23) | Trip Planning Mode | iOS + Backend |
| [#24](https://github.com/wdvr/snow/issues/24) | Webcam Integration | iOS + Backend + Research |

### Recently Closed Issues
| Issue | Title | Closed |
|-------|-------|--------|
| [#21](https://github.com/wdvr/snow/issues/21) | Add pretty splash screen / launch screen | 2026-01-25 |
| [#18](https://github.com/wdvr/snow/issues/18) | Add more ski resorts to database | 2026-01-25 |
| [#15](https://github.com/wdvr/snow/issues/15) | Add offline caching for iOS app (SwiftData) | 2026-01-25 |
| [#12](https://github.com/wdvr/snow/issues/12) | Implement 60-second API caching | 2026-01-24 |
| [#11](https://github.com/wdvr/snow/issues/11) | Widget not showing data | 2026-01-24 |

---

## Completed Features

| Feature | Date |
|---------|------|
| Region-based filtering (iOS + API) | 2026-01-25 |
| Animated splash screen | 2026-01-25 |
| Offline caching (SwiftData) | 2026-01-25 |
| 28+ ski resorts across 8 regions | 2026-01-25 |
| 60-second API caching | 2026-01-24 |
| Production deployment | 2026-01 |
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

# Test regions endpoint
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/regions

# Filter by region
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts?region=alps

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
- **PR #28 merged** - Major feature update:
  - Animated splash screen with snowflake effects (#21)
  - Offline caching with SwiftData (#15)
  - Expanded to 28+ resorts across 8 regions (#18)
  - Region-based filtering (new feature)
- New `/api/v1/regions` endpoint with resort counts
- iOS region filter chips with icons
- Fixed Pydantic V2 deprecation warnings
- Created resorts.json data management system

### 2026-01-24
- Deployed snow predictions, share button, iOS widgets
- Widget URL fixed (was pointing to old API)
- Weather data shows 0cm for Silver Star but user reports 1cm actual
- Switched from weatherapi.com to Open-Meteo for better elevation data
- Created workflow labels for hybrid agent/dev workflow
- Created issues #22-25 for planned features
