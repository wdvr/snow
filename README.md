# Snow Quality Tracker

A smart snow conditions tracking app for ski resorts that predicts fresh powder quality by analyzing weather patterns at different mountain elevations.

## Live API

```
https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod
```

## Features

- **Multi-Elevation Tracking** - Monitor conditions at base, mid, and top elevations
- **Snow Quality Algorithm** - Estimates fresh powder vs icy conditions based on temperature patterns
- **28+ Resorts** - Coverage across NA West, Rockies, Alps, Japan, and more
- **iOS App** - Native SwiftUI app with widgets, offline caching, and region filtering
- **Real-time Data** - Open-Meteo weather API + OnTheSnow scraping for accurate snow depths

## Tech Stack

| Component | Technology |
|-----------|------------|
| iOS App | Swift 6, SwiftUI, SwiftData |
| Backend | Python, FastAPI, AWS Lambda |
| Database | DynamoDB |
| Weather Data | Open-Meteo API, OnTheSnow scraper |
| Infrastructure | Pulumi (Python), AWS |
| CI/CD | GitHub Actions |
| Monitoring | CloudWatch, Amazon Managed Grafana |

## Project Structure

```
snow/
├── ios/                    # SwiftUI iOS app
├── backend/                # Python Lambda functions
│   ├── src/
│   │   ├── handlers/       # Lambda handlers (API, weather processor)
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities (caching, DynamoDB helpers)
│   └── tests/              # pytest tests
├── infrastructure/         # Pulumi AWS setup
│   └── grafana-dashboards/ # Grafana dashboard JSON files
└── .github/workflows/      # CI/CD pipelines
```

## Quick Start

### Prerequisites
- Python 3.12+
- AWS CLI configured
- Xcode 26+ (for iOS development)

### Backend Development
```bash
cd backend
uv pip install -r requirements.txt
python -m pytest tests/ -v
```

### Deploy
```bash
gh workflow run deploy.yml -f environment=staging
```

## API Endpoints

```
GET  /health                           - Health check
GET  /api/v1/regions                   - List ski regions
GET  /api/v1/resorts                   - List all resorts
GET  /api/v1/resorts?region={region}   - Filter by region
GET  /api/v1/resorts/{id}              - Resort details
GET  /api/v1/resorts/{id}/conditions   - Weather conditions
GET  /api/v1/resorts/{id}/snow-quality - Snow quality summary
POST /api/v1/feedback                  - Submit feedback
```

## Documentation

- **CLAUDE.md** - Development instructions and agent workflow
- **PROGRESS.md** - Current status and task tracking
- **GitHub Issues** - Source of truth for all tasks

## License

Private repository - All rights reserved.
