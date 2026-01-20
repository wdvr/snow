# Snow Quality Tracker

A smart snow conditions tracking app for ski resorts that predicts fresh powder quality by analyzing weather patterns at different mountain elevations.

## Overview

Snow Quality Tracker helps skiers and snowboarders find the best powder conditions by monitoring weather data across multiple elevation points (base, mid, top) at ski resorts. The app uses intelligent algorithms to estimate how much fresh snow remains powder versus what has turned to ice based on temperature patterns and snowfall data.

## Key Features

### 🏔️ Multi-Elevation Tracking
- Monitor conditions at base, mid, and top elevations
- Real-time weather data integration
- Historical condition trends

### ❄️ Intelligent Snow Quality Algorithm
- Tracks fresh snowfall amounts
- Estimates ice formation based on temperature exposure
- Identifies optimal skiing conditions

### 🎿 Resort Coverage
**Initial Focus**: Canada & United States
- Big White (BC, Canada)
- Lake Louise (AB, Canada)
- Silver Star (BC, Canada)
- *Expanding to additional resorts*

### 📱 Native iOS Experience
- SwiftUI interface optimized for iPhone and Mac
- Sign in with Apple authentication
- Personalized favorite resorts
- Offline condition caching

## Technology Stack

### Frontend
- **iOS**: Swift 6 + SwiftUI
- **Platform**: iOS/iPadOS/macOS (Catalyst)
- **Authentication**: Sign in with Apple

### Backend
- **API**: Python on AWS Lambda
- **Database**: DynamoDB
- **Infrastructure**: AWS (API Gateway, Lambda, CloudWatch)
- **IaC**: Pulumi for AWS deployment

### Data Sources
- Weather APIs for real-time conditions
- Snow report integration
- Potential user-generated condition reports

## Project Structure

```
snow/
├── ios/              # SwiftUI iOS application
├── backend/          # Python Lambda functions
├── infrastructure/   # Pulumi AWS configuration
├── docs/             # Additional documentation
├── .env.example      # Environment variables template
└── README.md         # This file
```

## Getting Started

### Prerequisites
- Xcode 26+ (for iOS development)
- Python 3.12+ (for backend)
- AWS CLI configured
- Pulumi CLI installed

### Setup
1. Clone the repository
2. Copy `.env.example` to `.env` and configure AWS credentials
3. Follow setup instructions in `claude.md`

## Development Workflow

This project follows a Pull Request based workflow:
1. Create feature branches from `main`
2. Develop and test changes locally
3. Submit Pull Requests for review
4. Merge to `main` after approval

## Documentation

- **`claude.md`**: Detailed development instructions and tooling guide
- **`progress.md`**: Current task status and development progress
- **`docs/`**: Additional technical documentation

## Contributing

Please read the development guidelines in `claude.md` before contributing. Key points:
- Use SwiftUI for iOS development
- Follow Swift 6 best practices
- Write tests for new functionality
- Update documentation as needed

## License

Private repository - All rights reserved.

## Roadmap

### Phase 1: Core Functionality
- Basic weather data integration
- iOS app with resort selection
- Snow quality algorithm implementation

### Phase 2: Enhanced Features
- User preferences and favorites
- Historical data analysis
- Performance optimizations

### Phase 3: Expansion
- Additional resort coverage
- User-generated condition reports
- Advanced predictive algorithms

## Support

For development questions and technical guidance, see `claude.md` for detailed instructions and best practices.