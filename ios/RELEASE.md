# iOS App Release Guide

This document covers the complete process for releasing the Snow Tracker iOS app to the App Store using Fastlane.

## Prerequisites

### 1. App Store Connect API Key

You need an App Store Connect API key for automated uploads:

1. Go to [App Store Connect > Users and Access > Integrations > App Store Connect API](https://appstoreconnect.apple.com/access/integrations/api)
2. Create a new key with "App Manager" role
3. Download the `.p8` file and save it to `~/.appstoreconnect/AuthKey_<KEY_ID>.p8`
4. Note your **Key ID** and **Issuer ID**

### 2. Environment Setup

Copy the environment template and fill in your credentials:

```bash
cd ios/fastlane
cp .env.default .env
# Edit .env with your actual values
```

Required environment variables in `.env`:
```
APP_STORE_CONNECT_KEY_ID=YOUR_KEY_ID
APP_STORE_CONNECT_ISSUER_ID=YOUR_ISSUER_ID
APP_STORE_CONNECT_KEY_PATH=/Users/YOUR_USER/.appstoreconnect/AuthKey_YOUR_KEY_ID.p8
```

### 3. Code Signing

Ensure you have:
- **iOS Distribution certificate** installed in Keychain Access
- **Provisioning profile** with Push Notifications capability

If missing:
1. Go to [Apple Developer Portal > Certificates](https://developer.apple.com/account/resources/certificates/list)
2. Create or download the iOS Distribution certificate
3. Go to [Profiles](https://developer.apple.com/account/resources/profiles/list) and regenerate profile to include Push Notifications
4. Download and double-click to install

### 4. Ruby/Fastlane Setup

The project uses Homebrew Ruby 4 for Fastlane compatibility:

```bash
# Install Homebrew Ruby (if not installed)
brew install ruby

# Navigate to fastlane directory
cd ios/fastlane

# Set Ruby path for this session
export PATH="/opt/homebrew/opt/ruby@4/bin:$PATH"

# Install dependencies
bundle install
```

## Fastlane Lanes

### Quick Reference

| Lane | Description |
|------|-------------|
| `fastlane beta` | Build and upload to TestFlight |
| `fastlane beta_quick` | Same as beta, but skip processing wait |
| `fastlane release` | Full release: build, TestFlight, metadata, screenshots, submit for review |
| `fastlane release_no_screenshots` | Full release without screenshot generation |
| `fastlane screenshots` | Generate App Store screenshots on all devices |
| `fastlane deliver_metadata` | Upload metadata and screenshots only |
| `fastlane bump_version type:patch` | Bump version (patch/minor/major) |

### Full Release (Recommended)

```bash
cd ios/fastlane
export PATH="/opt/homebrew/opt/ruby@4/bin:$PATH"
bundle exec fastlane release
```

This will:
1. Increment build number
2. Build the app for App Store
3. Upload to TestFlight
4. Generate screenshots (all device sizes)
5. Upload metadata and screenshots
6. Submit for App Store review
7. Commit version bump and tag release

### TestFlight Only

```bash
bundle exec fastlane beta
```

### Screenshots Only

```bash
bundle exec fastlane screenshots
```

For iPhone only (faster):
```bash
bundle exec fastlane screenshots_iphone
```

## Screenshot Automation

Screenshots are captured using Fastlane's `capture_screenshots` action with UI tests.

### Devices Captured

- iPhone 16 Pro Max (6.9" - required for App Store)
- iPhone 16 Pro (6.3")
- iPhone SE 3rd gen (4.7")
- iPad Pro 13" M4

### Screenshot Test Setup

Screenshots are captured through the `ScreenshotTestPlan` test plan. The UI tests navigate through key app screens:

1. Resort list view
2. Resort detail view
3. Map view
4. Favorites
5. Recommendations
6. Settings

To add new screenshots:
1. Create UI test in `SnowTrackerUITests`
2. Navigate to the desired screen state
3. Call `snapshot("ScreenName")` to capture

Example:
```swift
func testResortList() {
    snapshot("01_ResortList")
    app.buttons["Show Map"].tap()
    snapshot("02_MapView")
}
```

### Screenshot Output

Screenshots are saved to `ios/fastlane/screenshots/` organized by device and language.

## Metadata Management

App Store metadata is stored in `ios/fastlane/metadata/en-US/`:

| File | Description |
|------|-------------|
| `name.txt` | App name (30 chars max) |
| `subtitle.txt` | Subtitle (30 chars max) |
| `description.txt` | Full description (4000 chars max) |
| `release_notes.txt` | What's new (4000 chars max) |
| `keywords.txt` | Search keywords (100 chars, comma-separated) |
| `promotional_text.txt` | Promotional text (170 chars) |
| `privacy_url.txt` | Privacy policy URL |
| `support_url.txt` | Support URL |

To update metadata without uploading:
```bash
bundle exec fastlane upload_metadata_only
```

## Common Issues & Solutions

### 1. "No signing certificate iOS Distribution found"

**Problem:** Distribution certificate not installed on this machine.

**Solution:**
1. Open Keychain Access
2. Go to [Developer Portal > Certificates](https://developer.apple.com/account/resources/certificates/list)
3. Download the iOS Distribution certificate
4. Double-click to install
5. If expired, create a new one and update provisioning profiles

### 2. "Provisioning profile doesn't include Push Notifications"

**Problem:** The provisioning profile needs to be regenerated with the Push Notifications capability.

**Solution:**
1. Go to [Developer Portal > Profiles](https://developer.apple.com/account/resources/profiles/list)
2. Edit your App Store distribution profile
3. Ensure Push Notifications is checked in capabilities
4. Download and install the new profile

### 3. "Could not retrieve response as fastlane runs in non-interactive mode"

**Problem:** Fastlane can't determine which target to use.

**Solution:** Ensure all `get_version_number` calls include `target: "SnowTracker"` parameter.

### 4. "xcodebuild -showBuildSettings timed out"

**Problem:** Xcode is slow to respond (common with large projects).

**Solution:** Set a longer timeout:
```bash
FASTLANE_XCODEBUILD_SETTINGS_TIMEOUT=120 bundle exec fastlane release
```

### 5. "Bundle version must be increased"

**Problem:** Build number already exists in App Store Connect.

**Solution:** The `release` lane automatically increments the build number. If you need to manually set it:
```bash
cd ios
agvtool new-version 100
```

### 6. Ruby/Bundler version mismatch

**Problem:** System Ruby is too old or bundler version doesn't match.

**Solution:**
```bash
# Use Homebrew Ruby
export PATH="/opt/homebrew/opt/ruby@4/bin:$PATH"

# Install correct bundler version
gem install bundler:4.0.4

# Reinstall dependencies
bundle install
```

### 7. Build fails with "type-check this expression" error

**Problem:** Swift compiler timeout on complex view bodies.

**Solution:** Break up complex SwiftUI views into smaller computed properties. The `ResortMapView.swift` file was refactored to use `ViewModifier` patterns to avoid this.

## Version Management

### Bump Version

```bash
# Patch: 4.0.0 -> 4.0.1
bundle exec fastlane bump_version type:patch

# Minor: 4.0.0 -> 4.1.0
bundle exec fastlane bump_version type:minor

# Major: 4.0.0 -> 5.0.0
bundle exec fastlane bump_version type:major

# Set specific version
bundle exec fastlane set_version version:4.0.0
```

### Build Numbers

Build numbers are auto-incremented by the release lanes. To check current:
```bash
cd ios
agvtool what-version
```

## Release Checklist

Before running `fastlane release`:

- [ ] Update `metadata/en-US/release_notes.txt` with what's new
- [ ] Review `metadata/en-US/description.txt` for accuracy
- [ ] Ensure all tests pass
- [ ] Verify Firebase/Analytics is configured correctly
- [ ] Check signing certificates are valid
- [ ] Verify provisioning profiles include all capabilities

## CI/CD Integration

For GitHub Actions, store these secrets:
- `APP_STORE_CONNECT_KEY_ID`
- `APP_STORE_CONNECT_ISSUER_ID`
- `APP_STORE_CONNECT_KEY_BASE64` (base64-encoded .p8 file)
- `MATCH_PASSWORD` (if using fastlane match for certificates)

The `.env` file is in `.gitignore` and should never be committed.

## Support

For fastlane issues: https://docs.fastlane.tools
For code signing: https://docs.fastlane.tools/codesigning/getting-started/
