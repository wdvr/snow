# Powder Chaser

<p align="center">
  <img src="https://powderchaserapp.com/snowflake.svg" alt="Powder Chaser" width="120" />
</p>

<p align="center">
  <strong>Find the best snow conditions at ski resorts worldwide</strong>
</p>

<p align="center">
  <a href="https://powderchaserapp.com">Website</a> •
  <a href="https://apps.apple.com/app/powder-chaser">App Store</a> •
  <a href="https://buymeacoffee.com/wdvr">Buy Me a Coffee</a>
</p>

---

Powder Chaser is an open-source iOS app and backend that tracks snow conditions at 900+ ski resorts across 23 countries. It uses weather data and a custom algorithm to estimate snow quality - helping you find fresh powder instead of icy slopes.

<p align="center">
  <img src="https://powderchaserapp.com/screenshot-iphone.png" alt="Powder Chaser Screenshot" width="300" />
</p>

## Features

- **Snow Quality Ratings** - Excellent, Good, Fair, Poor, Icy based on fresh snow since last thaw-freeze
- **900+ Resorts** - North America, Europe, Japan, Oceania, South America
- **Multi-Elevation Tracking** - Base, mid, and summit conditions
- **Smart Recommendations** - "Best Snow Near You" based on location
- **Push Notifications** - Get alerts when conditions improve at favorite resorts
- **Offline Support** - Cached data for use on the mountain
- **iOS Widgets** - Glanceable conditions on your home screen
- **Map View** - Visual exploration with clustered markers

## How It Works

### Snow Quality Algorithm

The app tracks **fresh snow accumulation since the last ice-forming event**:

| Quality | Fresh Snow | Description |
|---------|------------|-------------|
| Excellent | 3+ inches (7.6+ cm) | Fresh powder, perfect conditions |
| Good | 2-3 inches (5-7.6 cm) | Soft surface, enjoyable skiing |
| Fair | 1-2 inches (2.5-5 cm) | Some fresh snow on older base |
| Poor | <1 inch (<2.5 cm) | Thin cover, harder surface |
| Icy | None | Refrozen surface, no fresh snow |
| Not Skiable | N/A | Warm temps, no snow cover |

**Ice forms when:** 3 hours at +3°C, 6 hours at +2°C, or 8 hours at +1°C

### Data Sources

- **[Open-Meteo](https://open-meteo.com/)** - Free weather API for temperature, snowfall, predictions
- **Resort Scraping** - Automated discovery of new resorts from skiresort.info

## Tech Stack

| Component | Technology |
|-----------|------------|
| iOS App | Swift 6, SwiftUI, SwiftData, Xcode 26 |
| Backend | Python 3.14, FastAPI, AWS Lambda |
| Database | Amazon DynamoDB |
| Infrastructure | Pulumi (Python), AWS |
| Auth | Sign in with Apple, Google Sign-In |
| Push Notifications | APNs via Amazon SNS |
| CI/CD | GitHub Actions |
| Analytics | Firebase Analytics & Crashlytics |

## Project Structure

```
snow/
├── ios/                      # iOS app (SwiftUI)
│   ├── SnowTracker/          # Main app target
│   ├── SnowTrackerWidget/    # Home screen widgets
│   └── fastlane/             # App Store automation
├── backend/                  # Python backend
│   ├── src/
│   │   ├── handlers/         # Lambda handlers
│   │   ├── services/         # Business logic
│   │   └── models/           # Pydantic models
│   ├── scripts/              # Resort scraper, utilities
│   └── tests/                # pytest tests
├── infrastructure/           # Pulumi IaC
├── website/                  # Marketing site (React)
└── .github/workflows/        # CI/CD pipelines
```

## Building the App

### Prerequisites

- macOS with Xcode 26+
- Python 3.12+ (for backend)
- AWS CLI configured (for deployment)
- Node.js 18+ (for website)

### iOS App

```bash
cd ios
open SnowTracker.xcodeproj
```

Build and run on simulator or device. The app connects to the production API by default.

**For development with local backend:**
1. Enable Debug mode in Settings
2. Enter your local API URL (e.g., `http://localhost:8000`)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run locally (requires DynamoDB local or AWS credentials)
uvicorn src.main:app --reload
```

### Website

```bash
cd website
npm install
npm run dev
```

## Authentication Setup

### Sign in with Apple

1. Create an App ID with "Sign in with Apple" capability in Apple Developer Portal
2. Create a Service ID for web authentication (optional)
3. Configure the iOS app's entitlements

The app uses Apple's authentication framework - no additional server setup required for basic sign-in.

### Google Sign-In

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Sign-In API
3. Create OAuth 2.0 credentials (iOS client)
4. Add your `GoogleService-Info.plist` to the iOS project
5. Configure URL schemes in Info.plist

```xml
<key>GIDClientID</key>
<string>YOUR_CLIENT_ID.apps.googleusercontent.com</string>

<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.googleusercontent.apps.YOUR_CLIENT_ID</string>
    </array>
  </dict>
</array>
```

## API Reference

**Base URL:** `https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod`

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/regions` | List regions with resort counts |
| GET | `/api/v1/resorts` | List all resorts |
| GET | `/api/v1/resorts?region={region}` | Filter by region |
| GET | `/api/v1/resorts?country={code}` | Filter by country (e.g., `CA`, `US`) |
| GET | `/api/v1/resorts/nearby?lat={lat}&lon={lon}` | Find nearby resorts |
| GET | `/api/v1/resorts/{id}` | Resort details |
| GET | `/api/v1/resorts/{id}/conditions` | Current weather conditions |
| GET | `/api/v1/conditions/batch?resort_ids={ids}` | Batch conditions |
| GET | `/api/v1/snow-quality/batch?resort_ids={ids}` | Batch snow quality |
| POST | `/api/v1/feedback` | Submit feedback |

### Example Response

```bash
curl https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod/api/v1/resorts/big-white/conditions
```

```json
{
  "conditions": [
    {
      "resort_id": "big-white",
      "elevation_level": "top",
      "current_temp_celsius": -8.5,
      "snowfall_24h_cm": 15.0,
      "snow_quality": "excellent",
      "fresh_snow_cm": 22.5,
      "last_freeze_thaw_hours_ago": 168
    }
  ]
}
```

## Deployment

### Backend (AWS Lambda)

Deployments are automated via GitHub Actions on push to `main`:

```bash
# Manual deploy
gh workflow run deploy.yml -f environment=staging
```

### iOS App (TestFlight)

```bash
cd ios/fastlane
fastlane beta
```

## Environment Variables

### Backend (AWS Lambda)

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `staging` or `prod` |
| `RESORTS_TABLE` | DynamoDB table name |
| `WEATHER_CONDITIONS_TABLE` | DynamoDB table name |
| `AWS_REGION_NAME` | AWS region (us-west-2) |

### iOS App

Configuration is in `Configuration.swift` - no environment variables needed. API URLs are hardcoded per environment.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow existing code style (SwiftLint for iOS, Ruff for Python)
- Add tests for new features
- Update documentation as needed

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You can use, modify, and distribute the code for noncommercial purposes.

## Acknowledgments

- [Open-Meteo](https://open-meteo.com/) for free weather data
- [skiresort.info](https://www.skiresort.info/) for resort information
- All the skiers and snowboarders who provided feedback

---

<p align="center">
  Made with ❄️ by <a href="https://github.com/wdvr">@wdvr</a>
</p>
