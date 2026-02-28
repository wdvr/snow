# Run UI Tests on iOS Simulator

Run the Snow Tracker UI tests on the iOS Simulator. Supports different test suites and environments.

## Arguments
- `$ARGUMENTS` — Optional: test class or method to run (e.g., `SmokeTests`, `SmokeTests/testChatOpensAndSendsMessage`, `all`)

## Steps

### 1. Regenerate Xcode project (if needed)
```bash
cd /Users/wouter/dev/snow/ios && xcodegen generate 2>&1 | tail -1
```

### 2. Run the requested tests

**Available test suites:**
- `smoke` or `SmokeTests` — Quick validation of core flows (~2 min)
- `all` — Full UI test suite including screenshots (~10 min)
- `screenshots` — App Store screenshot generation
- `verification` — Bug verification tests
- Specific test: `PowderChaserUITests/testMethodName`

Default (no argument): run `SmokeTests`

```bash
cd /Users/wouter/dev/snow/ios

# Build the UI test target
xcodebuild test \
  -project PowderChaser.xcodeproj \
  -scheme PowderChaser \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:PowderChaserUITests/<TEST_CLASS> \
  -resultBundlePath /tmp/uitest-results \
  2>&1 | tail -50
```

Where `<TEST_CLASS>` is:
- No args or `smoke` → `SmokeTests`
- `all` → omit `-only-testing` to run everything
- `screenshots` → `AppStoreScreenshotTests`
- `verification` → `VerificationTests`
- Other → use as-is (e.g., `PowderChaserUITests/testChatOpensAndSendsMessage`)

### 3. Report results

After tests complete:
- Report pass/fail count
- If any test failed, show the failure reason
- Check for screenshots in the result bundle: `find /tmp/uitest-results -name "*.png" 2>/dev/null | head -10`
- If tests passed, report success

### 4. Environment notes

The UI tests use `UI_TESTING` launch argument which:
- Auto-authenticates as guest (skips login screen)
- Skips onboarding flow
- Tests run against the environment configured in the app (default: production)

To test against staging, the app needs to be configured to use staging API before running tests.

### Test infrastructure

- **AccessibilityIdentifiers**: `Sources/AccessibilityIdentifiers.swift` — centralized IDs shared between app and tests
- **UITestHelpers**: `PowderChaserUITests/UITestHelpers.swift` — `TestID` constants, `XCUIApplication` extensions
- **SmokeTests**: Quick validation (~8 tests covering list, detail, tabs, map, chat, settings)
- **PowderChaserUITests**: Full test suite (30+ tests)
- **VerificationTests**: Bug regression tests with screenshots
- **AppStoreScreenshotTests**: Fastlane snapshot integration
