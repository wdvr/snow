# Deploy Snow (Powder Chaser) to TestFlight

## Via GitHub Actions (preferred)

```bash
# Internal beta
gh workflow run "TestFlight Internal" --repo wdvr/snow

# Check status
gh run list --repo wdvr/snow --limit 5
```

## Via xcodebuild (manual)

1. Bump build number in `ios/PowderChaser/Info.plist` (CFBundleVersion)
2. Regenerate project:
```bash
cd ios && xcodegen generate
```
3. Archive:
```bash
xcodebuild archive -project ios/PowderChaser.xcodeproj -scheme PowderChaser \
  -archivePath /tmp/PowderChaser.xcarchive -destination 'generic/platform=iOS' -quiet
```
4. Export and upload:
```bash
cat > /tmp/ExportOptions.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key><string>app-store-connect</string>
    <key>teamID</key><string>N324UX8D9M</string>
    <key>destination</key><string>upload</string>
</dict>
</plist>
PLIST

xcodebuild -exportArchive -archivePath /tmp/PowderChaser.xcarchive \
  -exportOptionsPlist /tmp/ExportOptions.plist -exportPath /tmp/PowderChaser-export \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.private_keys/AuthKey_GA9T4G84AU.p8 \
  -authenticationKeyID GA9T4G84AU \
  -authenticationKeyIssuerID 39f22957-9a03-421a-ada6-86471b32ee9f
```
5. Clean up: `rm -rf /tmp/PowderChaser.xcarchive /tmp/PowderChaser-export /tmp/ExportOptions.plist`

## Notes
- Team ID: `N324UX8D9M`
- Bundle ID: `com.wouterdevriendt.snowtracker`
- App Name: Powder Chaser
- Current build: 4
