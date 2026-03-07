# Build and deploy to physical iPhone

Build the iOS app locally and install+launch on the connected physical device for development testing.

## Steps

1. Regenerate the Xcode project from project.yml:
```bash
cd /Users/wouter/dev/snow/ios && xcodegen generate
```

2. Build for the physical device:
```bash
xcodebuild -project /Users/wouter/dev/snow/ios/PowderChaser.xcodeproj \
  -scheme PowderChaser \
  -destination 'id=00008150-001625E20AE2401C' \
  -configuration Debug \
  build \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM=N324UX8D9M \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstoreconnect/AuthKey_GA9T4G84AU.p8 \
  -authenticationKeyID GA9T4G84AU \
  -authenticationKeyIssuerID 39f22957-9a03-421a-ada6-86471b32ee9f
```

3. Find the built app and install it:
```bash
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/PowderChaser-*/Build/Products/Debug-iphoneos -name "Powder Chaser.app" -maxdepth 1 2>/dev/null | head -1)
xcrun devicectl device install app --device 00008150-001625E20AE2401C "$APP_PATH"
```

4. Launch the app:
```bash
xcrun devicectl device process launch --device 00008150-001625E20AE2401C com.wouterdevriendt.snowtracker
```

5. Report success or failure to the user.

## Notes
- Device: iPhone (ID: `00008150-001625E20AE2401C`)
- Team ID: `N324UX8D9M`
- Bundle ID: `com.wouterdevriendt.snowtracker`
- ASC API key at `~/.appstoreconnect/AuthKey_GA9T4G84AU.p8`
- If signing fails, may need to create a fresh dev cert (see MEMORY.md for steps)
- The app name on disk is "Powder Chaser.app" (with space)
