# Claude Working Instructions - Snow Quality Tracker

## Project Overview
This is a snow quality tracking application for ski resorts, focusing on Canada and US initially. The app tracks snow conditions by analyzing weather data at different elevations (base, mid, top) and estimates fresh powder that hasn't turned to ice based on temperature patterns.

## Tech Stack

### Frontend (iOS)
- **Language**: Swift 6
- **UI Framework**: SwiftUI
- **IDE**: Xcode 26
- **Target**: iOS app compatible with Mac and iPhone
- **Authentication**: Sign in with Apple

### Backend (AWS)
- **Language**: Python
- **Infrastructure**: AWS (API Gateway, Lambda, DynamoDB)
- **Deployment**: Lambda OR EKS/Fargate (TBD)
- **Infrastructure as Code**: Pulumi
- **Database**: DynamoDB

### Development Workflow
- **Version Control**: Git with GitHub (private repository)
- **Workflow**: Pull Request based development with frequent commits
- **Permissions**: Use dangerously disable sandbox after initial setup
- **Testing**: Comprehensive automated testing for all components

## iOS Development Tools & Setup (2026)

### Modern iOS Development Stack
- **Xcode 26**: 35% faster build times, AI-powered code assistance, instant SwiftUI previews
- **Swift 6**: Enhanced performance, reduced boilerplate with macros, better type checking
- **SwiftUI**: Declarative UI with live previews, new container views, material-aware animations
- **Core ML**: For potential AI/ML features
- **Combine**: Reactive programming for handling asynchronous events
- **SwiftData**: Modern replacement for CoreData

### Key Features in Xcode 26
- Instant SwiftUI previews that behave like real app
- Timeline view for tracing async operations
- AI code assistant integration
- Enhanced debugging tools
- Live render previews

### Best Practices
- Use native Swift/SwiftUI for maximum performance
- Implement proper testing (unit, integration, UI tests)
- Follow accessibility guidelines (VoiceOver, Dynamic Type, high contrast)
- Leverage async/await for API calls
- Use MVVM or similar architecture pattern

## Environment Setup

### Required Files
- `.env` - AWS credentials and configuration
- `.gitignore` - Standard Swift/Python ignores plus AWS secrets
- `Pulumi.yaml` - Infrastructure configuration

### AWS Services
- **API Gateway**: REST API endpoints
- **Lambda**: Serverless functions for weather data processing
- **DynamoDB**: NoSQL database for storing snow conditions
- **CloudWatch**: Monitoring and logging

### Weather Data Sources
Research needed for:
- Primary API (weatherapi.com, Apple Weather API)
- Snow report integration (snow-report.com for elevation data)
- User-generated data (apps like Slopes)

## Development Workflow

### Git Workflow - COMMIT FREQUENTLY
1. **Frequent Commits**: Commit every logical change, don't batch work
2. **Feature Branches**: Create branches from main for each feature/fix
3. **Clear Messages**: Use descriptive commit messages explaining the "why"
4. **Pull Requests**: ALL changes must go through PR review process
5. **PR Requirements**:
   - All tests must pass
   - Code review approval required
   - No direct pushes to main
6. **Merge Strategy**: Squash and merge for clean history

### Testing Strategy - TEST EVERYTHING (CRITICAL)

**IMPORTANT: Add tests for EVERY change.** We need comprehensive test coverage to catch issues early. When making changes:
1. Add unit tests for new/modified logic
2. Add integration tests for API changes
3. Add UI tests for any UI changes
4. Run tests locally before pushing

#### Backend Testing (Python)
- **Unit Tests**: Test all services, models, and utilities (`pytest`)
- **Integration Tests**: Test Lambda functions end-to-end
- **API Tests**: Test all REST endpoints with various inputs
- **Database Tests**: Test DynamoDB operations with mocked tables
- **Local Lambda Testing**: Use SAM CLI or localstack for local testing
- **Coverage**: Aim for >90% code coverage

#### Frontend Testing (iOS/Swift) - HEAVILY TEST UI
- **Unit Tests**: Test ViewModels, services, and business logic (`XCTest`)
- **UI Tests**: Test ALL user flows and states:
  - Loading states
  - Error states (API unavailable, network errors)
  - Empty states
  - Data display states
  - Navigation flows
  - Pull to refresh
  - Tab switching
- **API Integration Tests**: Test iOS can decode real API responses (catches model mismatches)
- **Snapshot Tests**: Verify UI layout consistency
- **Network Tests**: Mock API calls and test error handling
- **Device Tests**: Test on multiple iOS versions and devices

#### Infrastructure Testing
- **Pulumi Tests**: Validate infrastructure configuration
- **Security Tests**: Scan for IAM policy issues and vulnerabilities
- **Performance Tests**: Load testing for API endpoints
- **Deployment Tests**: Verify infrastructure deploys correctly

#### Automated Testing Pipeline
- **GitHub Actions**: Run tests on every PR and push
- **Local Testing**: Commands to run all tests locally before push
- **Pre-commit Hooks**: Run linting and quick tests before commits
- **Test Environments**: Separate dev/staging/prod with test data

#### Local Development Testing Commands
```bash
# Backend testing
cd backend
python -m pytest tests/ -v --cov=src --cov-report=html

# Lambda local testing
sam local start-api
sam local invoke WeatherProcessorFunction

# Infrastructure testing
cd infrastructure
pulumi preview --diff

# iOS testing (from Xcode or command line)
xcodebuild test -scheme SnowTracker -destination 'platform=iOS Simulator,name=iPhone 15'
```

#### Deploy iOS App to Physical Device (i17pw)
When user says "push to phone" or "push to device", run all three commands:
```bash
# Build, install, and launch on i17pw (iPhone 17 Pro Max)
cd /Users/wouter/dev/snow/ios
xcodebuild -project SnowTracker.xcodeproj -scheme SnowTracker -destination 'id=00008150-001625E20AE2401C' -configuration Debug build
xcrun devicectl device install app --device 00008150-001625E20AE2401C ~/Library/Developer/Xcode/DerivedData/SnowTracker-edzwkquvfqbwjccdxrgtoywgkbwj/Build/Products/Debug-iphoneos/SnowTracker.app
xcrun devicectl device process launch --device 00008150-001625E20AE2401C com.snowtracker.app
```

### Initial Ski Resorts
- Big White (BC, Canada)
- Lake Louise (AB, Canada)
- Silver Star (BC, Canada)

### Project Structure
```
snow/
├── ios/              # SwiftUI iOS app
├── backend/          # Python Lambda functions
├── infrastructure/   # Pulumi AWS setup
├── .env             # Environment variables
├── README.md        # Project overview
├── CLAUDE.md        # This file
└── PROGRESS.md      # Task tracking and status
```

## Key Features to Implement

### Core Functionality
1. **Snow Quality Algorithm**: Track fresh snow vs iced conditions based on temperature
2. **Multi-Elevation Tracking**: Base, mid, top elevation conditions per resort
3. **Real-time Weather Data**: Daily updates from weather APIs
4. **User Preferences**: Save favorite resorts, personalized alerts

### Technical Implementation
1. **Backend Lambda**: Scheduled function to fetch and process weather data
2. **API Design**: REST endpoints for resort data, conditions, user preferences
3. **iOS App**: Resort selector, condition display, user authentication
4. **Database Schema**: Design for efficient querying by resort/elevation/date

## Research Tasks
- [ ] Weather API comparison and selection
- [ ] Ski resort data source for comprehensive list
- [ ] iOS app store requirements and guidelines
- [ ] AWS cost optimization strategies
- [ ] User-generated snow condition integration possibilities

## Development Phases
See `PROGRESS.md` for detailed task breakdown and current status.

---

**Sources for iOS Development Research:**
- [Getting Started with iOS Programming in 2026](https://www.davydovconsulting.com/post/getting-started-with-ios-programming-in-2026-tools-languages-and-setup)
- [iOS Development Masterclass 2026 – SwiftUI, SwiftData, AI](https://www.udemy.com/course/swiftui-masterclass-course-ios-development-with-swift/)
- [iOS 26 Explained: Apple's Biggest Update for Developers](https://www.index.dev/blog/ios-26-developer-guide)
- [Best iOS App Development Tools to Use in 2026](https://webandcrafts.com/blog/best-ios-development-tools)
- [iOS App Development Essentials: Best Practices](https://solidappmaker.com/ios-app-development-essentials-best-practices-for-modern-developers/)
