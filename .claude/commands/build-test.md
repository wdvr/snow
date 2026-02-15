# Build and Test Snow

## iOS

```bash
# Generate project
cd ios && xcodegen generate

# Build
xcodebuild -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build

# Unit tests
xcodebuild test -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:SnowTrackerTests -quiet

# Deploy to physical device
xcodebuild -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'id=00008150-001625E20AE2401C' -configuration Debug build
xcrun devicectl device install app --device 00008150-001625E20AE2401C \
  ~/Library/Developer/Xcode/DerivedData/SnowTracker-*/Build/Products/Debug-iphoneos/SnowTracker.app
```

## Backend

```bash
cd backend
source venv/bin/activate  # or: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v --cov=src

# Linting
ruff check src/ tests/
ruff format --check src/ tests/

# Local dev server
uvicorn src.main:app --reload
```

## Notes
- iOS: XcodeGen-based (regenerate after project.yml changes)
- Backend: Python 3.12, FastAPI
- Device ID: `00008150-001625E20AE2401C`
