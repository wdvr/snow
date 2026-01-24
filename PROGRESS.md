# Snow Quality Tracker - Progress & Tasks

## Project Status: LIVE IN PRODUCTION
**Last Updated**: 2026-01-24

## Current Sprint: Data Accuracy & Performance

### Completed Features (2026-01-24)
| Feature | Status | Notes |
|---------|--------|-------|
| Production deployment | ✅ COMPLETED | API live at z1f5zrp4l0.execute-api.us-west-2.amazonaws.com |
| 14 ski resorts | ✅ COMPLETED | NA (8), Europe (4), Japan (2) |
| Feedback button | ✅ COMPLETED | iOS + DynamoDB backend |
| Share button | ✅ COMPLETED | Share resort conditions |
| Snow predictions (24/48/72h) | ✅ COMPLETED | Future snowfall forecasts |
| iOS Widgets | ✅ COMPLETED | Favorite Resorts + Best Snow widgets |
| CloudWatch dashboards | ✅ COMPLETED | API monitoring in AWS Console |
| Managed Grafana infra | ✅ COMPLETED | Infrastructure code ready (not deployed) |

---

## ACTIVE SPRINT: Data Quality & Caching

### Priority 1: Widget Debugging
| Task | Status | Notes |
|------|--------|-------|
| Debug widgets not showing data | 🔴 TODO | Widgets show empty state |
| Check widget network requests | 🔴 TODO | May be failing silently |
| Verify app group data sharing | 🔴 TODO | Favorites not syncing to widget |
| Test widget timeline refresh | 🔴 TODO | Ensure data loads on schedule |

### Priority 2: Data Source Accuracy
| Task | Status | Notes |
|------|--------|-------|
| Investigate weatherapi.com accuracy | 🔴 TODO | Silver Star shows 0cm but actually 1cm |
| Compare weatherapi vs actual conditions | 🔴 TODO | Validate against resort reports |
| Check forecast API response | 🔴 TODO | Verify totalsnow_cm field accuracy |
| Research elevation-specific data | 🔴 TODO | Weather varies by elevation |
| Validate data aggregation logic | 🔴 TODO | 24h/48h/72h calculations |

### Priority 3: Alternative Data Sources
| Task | Status | Notes |
|------|--------|-------|
| Research snow-forecast.com API | 🔴 TODO | May have scraping or API options |
| Research OpenSnow API | 🔴 TODO | Popular ski weather app |
| Research resort official APIs | 🔴 TODO | Some resorts publish conditions |
| Research Slopes app integration | 🟡 PENDING | User-submitted conditions |
| Implement multi-source aggregation | 🔴 TODO | Combine multiple data sources |

### Priority 4: API Caching (Cost & Performance)
| Task | Status | Notes |
|------|--------|-------|
| Evaluate caching options | 🔴 TODO | API Gateway vs CloudFront |
| Implement 60-second cache | 🔴 TODO | All GET endpoints |
| Add cache headers to responses | 🔴 TODO | Cache-Control headers |
| Test cache invalidation | 🔴 TODO | Ensure fresh data when needed |
| Monitor cache hit rates | 🔴 TODO | CloudWatch metrics |

---

## Previous Phases (Completed)

### Phase 1: Project Foundation ✅ COMPLETED
- Git repository, CLAUDE.md, README.md, .env template, .gitignore
- GitHub private repository at wdvr/snow

### Phase 2: Architecture & Research ✅ MOSTLY COMPLETED
- Snow quality algorithm implemented
- DynamoDB schema designed
- API endpoints designed
- Weather API research ongoing

### Phase 3: Backend Infrastructure ✅ COMPLETED
- Pulumi infrastructure as code
- DynamoDB tables (resorts, weather, preferences, feedback)
- API Gateway with Lambda integration
- CloudWatch monitoring

### Phase 4: Weather Data Pipeline ✅ MOSTLY COMPLETED
- Weather service implemented (weatherapi.com)
- Snow quality algorithm implemented
- Scheduled Lambda trigger (hourly)
- Data validation with Pydantic

### Phase 5: API Development ✅ COMPLETED
- Resort endpoints (GET /resorts, GET /resorts/{id})
- Weather condition endpoints
- User preference endpoints
- Feedback endpoint
- API documentation (FastAPI auto-docs)

### Phase 6: iOS App Foundation ✅ COMPLETED
- XcodeGen project
- MVVM architecture
- Sign in with Apple (UI ready)
- Networking layer
- Data models

### Phase 7: iOS UI Development ✅ COMPLETED
- TabView navigation
- ResortListView, ConditionsView, SettingsView
- ResortDetailView with share button
- Snow predictions card
- Pull to refresh

### Phase 8: Initial Resorts Data ✅ EXPANDED
- 14 resorts: Big White, Lake Louise, Silver Star, Vail, Park City, Mammoth, Jackson Hole, Aspen, Chamonix, Zermatt, St. Anton, Verbier, Niseko, Hakuba

### Phase 9: Testing & Quality ✅ COMPLETED
- 94 backend pytest tests
- 18 integration tests with moto
- 33 iOS XCTest tests
- 13 iOS UI tests
- Pre-commit hooks (Ruff)
- Security scanning (Bandit)

### Phase 10: Deployment ✅ PRODUCTION LIVE
- GitHub Actions CI/CD
- Dev, staging, prod environments
- Lambda deployment with Linux targeting
- API health checks passing

---

## Technical Architecture

### Current Stack
- **Backend**: FastAPI + Mangum on AWS Lambda (Python 3.12)
- **Database**: DynamoDB (pay-per-request)
- **API**: API Gateway REST API
- **Weather Data**: weatherapi.com
- **iOS**: SwiftUI + Swift 6, XcodeGen
- **Infrastructure**: Pulumi (Python)
- **CI/CD**: GitHub Actions
- **Monitoring**: CloudWatch dashboards

### API Endpoints (Production)
```
Base URL: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

GET  /health                           - Health check
GET  /api/v1/resorts                   - List all resorts
GET  /api/v1/resorts/{id}              - Get resort details
GET  /api/v1/resorts/{id}/conditions   - Get weather conditions
GET  /api/v1/resorts/{id}/snow-quality - Get snow quality summary
POST /api/v1/feedback                  - Submit feedback
```

### DynamoDB Tables
- `snow-tracker-resorts-prod` - Resort data
- `snow-tracker-weather-conditions-prod` - Weather conditions (TTL: 7 days)
- `snow-tracker-user-preferences-prod` - User preferences
- `snow-tracker-feedback-prod` - User feedback

---

## Remaining Tasks (Backlog)

### High Priority
1. Fix widgets not showing data
2. Improve weather data accuracy
3. Implement API caching (60s)
4. Add snow-forecast.com or alternative data source

### Medium Priority
1. Authentication (Sign in with Apple backend)
2. Offline caching for iOS (SwiftData)
3. Push notifications for snow alerts
4. Performance testing

### Low Priority
1. App Store preparation
2. TestFlight beta
3. Additional resorts (more regions)
4. User-submitted conditions

---

## Commands Reference

```bash
# Backend
cd backend && python -m pytest tests/ -v --cov=src
AWS_PROFILE=personal python -m src.utils.resort_seeder --env prod

# iOS
cd ios && xcodegen generate --spec project.yml
xcodebuild -project SnowTracker.xcodeproj -scheme SnowTracker -destination 'id=00008150-001625E20AE2401C' build

# Deploy
gh workflow run deploy.yml -f environment=prod
gh run list --workflow=deploy.yml

# Lambda
AWS_PROFILE=personal aws lambda invoke --function-name snow-tracker-weather-processor-prod --region us-west-2 --payload '{}' /tmp/out.json

# API Test
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts
```

---

## Notes

### 2026-01-24
- Deployed snow predictions, share button, iOS widgets
- Widget URL fixed (was pointing to old API)
- Weather data shows 0cm for Silver Star but user reports 1cm actual snow
- Need to investigate weatherapi.com accuracy and consider alternative sources
- Widgets not showing data - need to debug network requests and app group sharing
