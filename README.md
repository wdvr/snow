# Powder Chaser

<p align="center">
  <img src="https://powderchaserapp.com/snowflake.svg" alt="Powder Chaser" width="120" />
</p>

<p align="center">
  <strong>ML-powered snow quality tracking for ski resorts worldwide</strong>
</p>

<p align="center">
  <a href="https://powderchaserapp.com">Website</a> &bull;
  <a href="https://apps.apple.com/app/powder-chaser">App Store</a> &bull;
  <a href="https://buymeacoffee.com/wdvr">Buy Me a Coffee</a>
</p>

---

Powder Chaser is an iOS app and serverless backend that tracks real-time snow conditions at 1,040+ ski resorts across 25 countries. A neural network ensemble (v15), trained on ~12,000 real-world observations from 134 resorts, scores snow quality at three elevations per resort -- helping you find fresh powder instead of icy slopes. Weather data is aggregated from 4 independent sources with outlier detection for high-confidence readings.

<p align="center">
  <img src="https://powderchaserapp.com/screenshot-iphone.png" alt="Powder Chaser Screenshot" width="300" />
</p>

## Features

### Core

- **1,040+ ski resorts across 25 countries** -- US, Canada, France, Japan, New Zealand, Austria, Australia, Chile, Switzerland, Italy, Argentina, Norway, Sweden, Finland, Germany, Spain, Andorra, Slovenia, and more
- **Multi-source weather at 3 elevations** -- Base, mid, and top conditions per resort from 4 independent data sources with outlier detection
- **ML-powered snow quality scoring** -- 0-100 scale with natural language explanations
- **Quality categories** -- Champagne Powder, Powder Day, Excellent, Great, Good, Decent, Mediocre, Poor, Bad, Horrible
- **7-day forecast timeline** -- ML-predicted quality for each day ahead
- **Snow history & season totals** -- Daily snowfall chart data with cumulative season summaries
- **Favorites with groups** -- Organize resorts by region, trip, or custom groups
- **Resort comparison** -- Compare up to 5 resorts side by side on key metrics
- **Region filtering & nearby search** -- Browse by region or find resorts near your location
- **Interactive resort map** -- Quality-colored markers with clustering
- **Push notifications** -- Powder alerts with custom snowfall thresholds per resort
- **Weekly snow digest** -- Summary of best conditions across your favorites
- **Apple Sign In authentication** -- Secure sign-in with guest mode fallback
- **Offline mode** -- Cached conditions for use on the mountain with stale-data indicators

### Recent Additions

- **Multi-source weather data** -- Aggregates 4 independent sources (Open-Meteo, OnTheSnow, Snow-Forecast.com, Apple WeatherKit) with outlier detection and confidence levels
- **Data source transparency** -- Shows which sources contributed to each reading and confidence level (HIGH/MEDIUM/LOW)
- **AI Chat Assistant** -- "Ask AI" tab for natural language questions about snow conditions, powered by Claude Sonnet 4.6 on AWS Bedrock with tool use
- **User Condition Reports** -- Submit and browse real-time reports from other skiers (8 condition types, 1-10 scoring)
- **Elevation profile visualization** -- Visual cross-section showing conditions at each elevation band
- **Shareable conditions cards** -- Beautiful branded cards for sharing to social media
- **Card-based UI** -- Modernized design system with consistent card styling

---

## Snow Quality Algorithm

The quality scoring system uses a **neural network ensemble** (v15) trained on ~12,000 real-world observations from 134 resorts. It produces a raw score (1.0-6.0) that maps to a 0-100 quality scale and a human-readable category.

### How It Works

```
Multi-source weather data (Open-Meteo, OnTheSnow, Snow-Forecast, WeatherKit)
        |
        v
  MultiSourceMerger (outlier detection, weighted consensus)
        |
        v
  Feature extraction (40 engineered features)
        |
        v
  Neural network ensemble (10 models, averaged)
        |
        v
  Quality score (1.0-6.0) --> 0-100 scale + category + explanation
```

### Feature Engineering

The model takes raw hourly weather data and computes 40 engineered features across 7 categories:

| Category | Features | What They Capture |
|----------|----------|-------------------|
| **Temperature** | `cur_temp`, `max_temp_24h`, `min_temp_24h`, `temp_trend_48h` | Current conditions and warming/cooling trends |
| **Freeze-thaw** | `freeze_thaw_days_ago`, `warmest_thaw`, `thaw_intensity_recency` | When snow last refroze and how severe the thaw was |
| **Snowfall** | `snow_since_freeze_cm`, `snowfall_24h_cm`, `snowfall_72h_cm`, `older_snow_accum`, `hours_since_last_snowfall` | Fresh snow at multiple time windows and recency |
| **Snow depth** | `snow_depth_m`, `fresh_to_total_ratio` | Base depth and proportion of new snow |
| **Warm hours** | Hours above 0/3/6 C since freeze-thaw + current warm spell | Cumulative heat exposure that degrades snow |
| **Wind & visibility** | `avg_wind_24h`, `max_wind_24h`, `max_wind_gust_norm`, `visibility_km`, `min_visibility_24h_km`, `calm_powder_indicator` | Wind crust, gusts, and visibility conditions |
| **Interactions** | `fresh_powder_indicator`, `warm_degradation`, `summer_flag`, and more | Non-linear combinations capturing key condition patterns |

### Model Architecture

- **Type**: 2-layer neural network (input -> hidden -> sigmoid-scaled output)
- **Ensemble**: 10 models with varying hidden sizes (16-64 neurons), averaged for predictions
- **Training**: Mini-batch gradient descent with He initialization, L2 regularization, class-balanced loss weights
- **No framework dependencies**: Pure NumPy training, pure Python inference (no PyTorch/TensorFlow in Lambda)

### Elevation Weighting

The overall resort quality is a weighted average across elevations:

| Elevation | Weight | Rationale |
|-----------|--------|-----------|
| Top | 50% | Summit conditions matter most for quality skiing |
| Mid | 35% | Where most runs and lifts operate |
| Base | 15% | Lower elevations degrade first |

### Quality Categories

| Category | Raw Score | 0-100 Scale | Description |
|----------|-----------|-------------|-------------|
| Champagne Powder | >= 5.9 | ~98-100 | Lightest, driest powder -- the holy grail |
| Powder Day | >= 5.5 | ~90-98 | Deep fresh powder, cold temps, low wind |
| Excellent | >= 5.0 | ~80-90 | Abundant recent snow, well-preserved conditions |
| Great | >= 4.5 | ~70-80 | Fresh snow with good coverage and cold temps |
| Good | >= 4.0 | ~60-70 | Soft rideable surface, some fresh snow |
| Decent | >= 3.5 | ~50-60 | Acceptable conditions, firm in spots |
| Mediocre | >= 3.0 | ~40-50 | Firm base with limited fresh, or mild warming |
| Poor | >= 2.5 | ~30-40 | Hard packed, minimal snow since last thaw-freeze |
| Bad | >= 1.5 | ~10-30 | Refrozen surface, no fresh snow |
| Horrible | < 1.5 | ~0-10 | Insufficient cover or actively melting |

### Natural Language Explanations

Every quality score comes with a generated explanation that describes surface conditions, fresh snow context, temperature impact, base depth, and forecast outlook. For example:

> *"Fresh powder: 18cm in the last 24 hours. Cold (-12 C) -- good preservation. Deep 185cm base. Outlook: 12cm expected in 48 hours."*

### Model Performance

| Metric | Value |
|--------|-------|
| MAE | 0.225 (on 1-6 scale) |
| R-squared | 0.937 |
| Exact quality match | 81.1% |
| Within 1 quality level | 100% |
| Training samples | ~12,000 real observations |
| Engineered features | 40 |
| Resorts covered | 134 |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **iOS App** | Swift 6, SwiftUI, Xcode 26 |
| **Backend** | Python, FastAPI, AWS Lambda (via Mangum) |
| **Database** | Amazon DynamoDB (9 tables) |
| **Infrastructure** | Pulumi (Python), AWS |
| **ML Training** | NumPy (custom neural network, no framework dependencies) |
| **ML Inference** | Pure Python (runs in Lambda with no ML library overhead) |
| **AI Chat** | Claude Sonnet 4.6 via AWS Bedrock Converse API with tool_use |
| **Weather Data** | [Open-Meteo](https://open-meteo.com/) (primary), [OnTheSnow](https://www.onthesnow.com/), [Snow-Forecast.com](https://www.snow-forecast.com/), [Apple WeatherKit](https://developer.apple.com/weatherkit/) |
| **Auth** | Sign in with Apple, guest auth |
| **Push Notifications** | APNs via Amazon SNS |
| **CI/CD** | GitHub Actions (deploy, TestFlight, weather triggers) |
| **Monitoring** | CloudWatch |

---

## Architecture

```
                                    +------------------+
                                    |   iOS App        |
                                    |   (SwiftUI)      |
                                    +--------+---------+
                                             |
                                    HTTPS (REST API)
                                             |
                              +--------------v--------------+
                              |       API Gateway           |
                              |    (Custom domain)          |
                              +--------------+--------------+
                                             |
                              +--------------v--------------+
                              |     Lambda (Mangum/FastAPI)  |
                              |                              |
                              |  +--- API Handler ----------+|
                              |  |  Resort, conditions,     ||
                              |  |  quality, timeline,      ||
                              |  |  chat, reports, auth     ||
                              |  +--------------------------+|
                              |                              |
                              |  +--- ML Scorer ------------+|
                              |  |  Neural net ensemble     ||
                              |  |  40-feature inference    ||
                              |  +--------------------------+|
                              +-----------+---+--------------+
                                          |   |
                        +-----------------+   +------------------+
                        |                                        |
               +--------v---------+                    +---------v--------+
               |    DynamoDB      |                    |     S3           |
               |  (9 tables)      |                    |  Static JSON     |
               +------------------+                    +------------------+

  +-------------------+          +-------------------+          +-------------------+
  | Weather Processor |          | Static JSON Gen   |          | Notification      |
  | (Scheduled Lambda)|          | (Scheduled Lambda) |          | Processor         |
  |                   |          |                   |          | (Scheduled Lambda) |
  | Fetches from 4    |          | Pre-computes batch|          | Sends powder      |
  | weather sources,  |          | quality to S3 for |          | alerts via SNS    |
  | merges with       |          | fast API responses|          | to APNs           |
  | outlier detection,|          |                   |          |                   |
  | runs ML scoring,  |          |                   |          |                   |
  | stores to DynamoDB|          |                   |          |                   |
  +-------------------+          +-------------------+          +-------------------+
```

### Data Flow

1. **Weather Processor** runs on a schedule, fetching hourly weather data from 4 independent sources (Open-Meteo, OnTheSnow, Snow-Forecast.com, Apple WeatherKit) for all resorts at 3 elevations. The MultiSourceMerger applies weighted consensus (Open-Meteo 0.50, OnTheSnow 0.25, Snow-Forecast 0.15, WeatherKit 0.10) with outlier detection (drops values >50% from median). It computes ML-based snow quality scores and stores conditions in DynamoDB with confidence levels (HIGH = 3+ sources, MEDIUM = 2, LOW = 1).

2. **Static JSON Generator** runs after the weather processor and pre-computes batch snow quality data to S3 as static JSON. The batch API endpoint reads from S3 for fast responses, falling back to DynamoDB if S3 is unavailable.

3. **API Handler** serves the iOS app via API Gateway. It reads conditions from DynamoDB (or S3 for batch endpoints), runs ML inference for real-time requests, and generates natural language explanations.

4. **AI Chat** uses AWS Bedrock (Claude Sonnet 4.6) with tool_use. The model has tool definitions for fetching live conditions, quality scores, timelines, and recommendations -- grounding its responses in real-time data.

5. **Notification Processor** checks conditions against user-configured thresholds and sends powder alerts via SNS/APNs. Weekly digest notifications summarize the best conditions across the user's favorites.

### DynamoDB Tables

| Table | Purpose | TTL |
|-------|---------|-----|
| `resorts` | Resort master data (coordinates, elevations, region) | -- |
| `weather-conditions` | Hourly conditions per resort per elevation | 60 days |
| `snow-summary` | Season snowfall totals | -- |
| `daily-history` | Daily snow history snapshots for charts | -- |
| `user-preferences` | Notification settings, favorites | -- |
| `device-tokens` | APNs push tokens | 90 days |
| `feedback` | User feedback submissions | -- |
| `chat` | AI chat conversation history | 30 days |
| `condition-reports` | User-submitted condition reports | 90 days |

---

## Project Structure

```
snow/
+-- ios/                          # iOS app (Swift 6, SwiftUI)
|   +-- SnowTracker/              # Main app target
|   |   +-- Sources/
|   |   |   +-- Models/           # Data models (Resort, WeatherCondition, etc.)
|   |   |   +-- Views/            # SwiftUI views
|   |   |   +-- ViewModels/       # View models (MVVM)
|   |   |   +-- Services/         # API client, auth, cache, push notifications
|   |   |   +-- SnowTrackerApp.swift
|   |   +-- Resources/            # Assets, localization
|   +-- SnowTrackerWidget/        # Home screen widgets
|   +-- SnowTrackerTests/         # Unit tests
|   +-- fastlane/                 # App Store automation
+-- android/                      # Android app (Kotlin, Jetpack Compose)
+-- backend/                      # Python backend
|   +-- src/
|   |   +-- handlers/             # Lambda entry points
|   |   |   +-- api_handler.py    # FastAPI routes (main API)
|   |   |   +-- weather_processor.py   # Scheduled weather fetching
|   |   |   +-- weather_worker.py      # Parallel weather processing
|   |   |   +-- static_json_handler.py # S3 static JSON generation
|   |   |   +-- notification_processor.py  # Push notification delivery
|   |   +-- services/             # Business logic
|   |   |   +-- ml_scorer.py      # ML inference (neural net ensemble)
|   |   |   +-- snow_quality_service.py    # Quality assessment orchestration
|   |   |   +-- quality_explanation_service.py  # NL explanation generation
|   |   |   +-- openmeteo_service.py       # Open-Meteo API client
|   |   |   +-- multi_source_merger.py    # Multi-source weather aggregation
|   |   |   +-- chat_service.py            # AI chat via Bedrock
|   |   |   +-- daily_history_service.py   # Snow history aggregation
|   |   +-- models/               # Pydantic data models
|   |   +-- ml_model/             # Model weights (JSON)
|   +-- tests/                    # pytest test suite (1550+ tests)
+-- ml/                           # ML training pipeline
|   +-- train_v2.py               # Neural network training script
|   +-- collect_data.py           # Feature collection from Open-Meteo
|   +-- model_weights_v2.json     # Trained model weights
|   +-- scores/                   # Ground truth quality scores
+-- infrastructure/               # Pulumi IaC (AWS)
+-- website/                      # Marketing site
+-- .github/workflows/            # CI/CD pipelines
+-- CLAUDE.md                     # Agent development instructions
+-- FEATURES.md                   # Feature roadmap
```

---

## Getting Started

### Prerequisites

- macOS with Xcode 26+
- Python 3.12+ (for backend)
- AWS CLI configured (for deployment)

### iOS App

```bash
cd ios
open SnowTracker.xcodeproj
```

The app requires `GoogleService-Info.plist` for Firebase Analytics (not included in the repo). See [Firebase setup](#firebase-configuration) below. Build and run on simulator or device -- the app connects to the production API by default.

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests (1550+ tests)
PYTHONPATH=src python3 -m pytest tests/ -x -q

# Run locally
uvicorn src.main:app --reload
```

### ML Training

```bash
# Collect features from Open-Meteo (requires training_features.json)
python3 ml/collect_data.py

# Train model (historical_weight=0.0 for best results with 12000+ real samples)
python3 ml/train_v2.py 0.0
```

Training outputs model weights to `ml/model_weights_v2.json`. Copy to `backend/src/ml_model/model_weights_v2.json` for deployment.

---

## Firebase Configuration

The app uses Firebase Analytics. The `GoogleService-Info.plist` file is not included for security reasons.

**Option A: Create your own Firebase project**
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project and add an iOS app with bundle ID `com.wouterdevriendt.snowtracker`
3. Download `GoogleService-Info.plist` and place it in `ios/SnowTracker/SnowTracker/Resources/`

**Option B: Use environment variables**
```bash
export FIREBASE_API_KEY="your-api-key"
export FIREBASE_GCM_SENDER_ID="your-sender-id"
export FIREBASE_GOOGLE_APP_ID="your-app-id"
cd ios && ./scripts/generate-google-service-info.sh
```

---

## API Reference

**Production:** `https://api.powderchaserapp.com`
**Staging:** `https://staging.api.powderchaserapp.com`

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/regions` | List regions with resort counts |
| GET | `/api/v1/resorts` | List all resorts (filter: `?region=alps`, `?country=CA`) |
| GET | `/api/v1/resorts/nearby?lat=X&lon=Y` | Find resorts near location |
| GET | `/api/v1/resorts/{id}` | Resort details |
| GET | `/api/v1/resorts/{id}/conditions` | Weather conditions (all elevations) |
| GET | `/api/v1/resorts/{id}/snow-quality` | Snow quality summary + explanation |
| GET | `/api/v1/resorts/{id}/timeline` | 7-day forecast timeline |
| GET | `/api/v1/resorts/{id}/history` | Snow history + season totals |
| GET | `/api/v1/resorts/{id}/condition-reports` | User-submitted condition reports |
| GET | `/api/v1/snow-quality/batch?resort_ids=a,b,c` | Batch snow quality |
| GET | `/api/v1/conditions/batch?resort_ids=a,b,c` | Batch conditions |
| GET | `/api/v1/recommendations/best` | Best conditions globally |
| POST | `/api/v1/chat` | AI chat (Bedrock Claude, tool_use) |
| POST | `/api/v1/auth/apple` | Apple Sign In |
| POST | `/api/v1/resorts/{id}/condition-reports` | Submit condition report |

### Example

```bash
curl https://api.powderchaserapp.com/api/v1/resorts/whistler-blackcomb/snow-quality
```

```json
{
  "resort_id": "whistler-blackcomb",
  "elevations": {
    "top": {
      "quality": "excellent",
      "snow_score": 92,
      "explanation": "Fresh powder: 18cm in the last 24 hours. Cold (-12\u00b0C) \u2014 good preservation."
    },
    "mid": { "quality": "great", "snow_score": 74 },
    "base": { "quality": "decent", "snow_score": 55 }
  },
  "overall_quality": "great",
  "overall_snow_score": 78,
  "overall_explanation": "Fresh powder at summit (18cm in 24h), but firmer conditions at lower elevations. Cool (-4\u00b0C). Solid 142cm base."
}
```

---

## Deployment

### Backend (AWS Lambda)

Push to `main` auto-deploys to **staging**. Production requires a manual workflow dispatch:

```bash
# Deploy to staging (automatic on push to main)
gh workflow run deploy.yml -f environment=staging

# Deploy to production
gh workflow run deploy.yml -f environment=prod
```

All Lambda functions share the same code package -- a deploy updates the API handler, weather processor, static JSON generator, and notification processor simultaneously.

### iOS App (TestFlight)

```bash
# Internal TestFlight build
gh workflow run "iOS TestFlight Internal"
```

### Weather Processing

```bash
# Trigger weather data refresh
gh workflow run trigger-weather.yml -f environment=prod
```

---

## Testing

```bash
# Backend (1550+ tests)
cd backend && PYTHONPATH=src python3 -m pytest tests/ -x -q

# iOS (119 tests)
xcodebuild test -project ios/SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:SnowTrackerTests
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for your changes
4. Commit with clear messages
5. Open a Pull Request

### Development Guidelines

- Follow existing code style (SwiftLint for iOS, Ruff for Python)
- Add tests for new features
- iOS: Use `.foregroundStyle` (not `.foregroundColor`), `.clipShape(RoundedRectangle(...))` (not `.cornerRadius`)
- Backend: Use Pydantic for validation, proper error handling for CloudWatch
- ML: Keep inference dependency-free (pure Python, no NumPy in Lambda)

---

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You can use, modify, and distribute the code for noncommercial purposes.

## Acknowledgments

- [Open-Meteo](https://open-meteo.com/) for free weather data (primary source)
- [OnTheSnow](https://www.onthesnow.com/) for resort conditions data
- [Snow-Forecast.com](https://www.snow-forecast.com/) for mountain weather forecasts
- [Apple WeatherKit](https://developer.apple.com/weatherkit/) for supplementary weather data
- [skiresort.info](https://www.skiresort.info/) for resort information
- [Anthropic](https://www.anthropic.com/) for Claude (AI chat and development assistance)
- All the skiers and snowboarders who provided quality scores for ML training

---

<p align="center">
  Made with &#10052;&#65039; by <a href="https://github.com/wdvr">@wdvr</a>
</p>
