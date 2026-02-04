fastlane documentation
----

# Installation

Make sure you have the latest version of the Xcode command line tools installed:

```sh
xcode-select --install
```

For _fastlane_ installation instructions, see [Installing _fastlane_](https://docs.fastlane.tools/#installing-fastlane)

# Available Actions

## iOS

### ios beta

```sh
[bundle exec] fastlane ios beta
```

Build and upload to TestFlight

### ios beta_quick

```sh
[bundle exec] fastlane ios beta_quick
```

Build and upload to TestFlight (quick - skip processing wait)

### ios release

```sh
[bundle exec] fastlane ios release
```

Full release: build, upload to TestFlight, upload metadata, submit for review

### ios release_no_screenshots

```sh
[bundle exec] fastlane ios release_no_screenshots
```

Release without screenshots (faster)

### ios submit_for_review

```sh
[bundle exec] fastlane ios submit_for_review
```

Submit existing build for review (metadata only)

### ios screenshots

```sh
[bundle exec] fastlane ios screenshots
```

Generate App Store screenshots on all required device sizes

### ios screenshots_iphone

```sh
[bundle exec] fastlane ios screenshots_iphone
```

Generate screenshots for iPhone only (faster)

### ios deliver_metadata

```sh
[bundle exec] fastlane ios deliver_metadata
```

Upload metadata, screenshots, and app icon to App Store Connect

### ios upload_screenshots

```sh
[bundle exec] fastlane ios upload_screenshots
```

Upload only screenshots

### ios upload_icon

```sh
[bundle exec] fastlane ios upload_icon
```

Upload only the app icon

### ios upload_metadata_only

```sh
[bundle exec] fastlane ios upload_metadata_only
```

Upload only metadata (no screenshots)

### ios download_metadata

```sh
[bundle exec] fastlane ios download_metadata
```

Download existing metadata from App Store Connect

### ios bump_version

```sh
[bundle exec] fastlane ios bump_version
```

Bump version number (major, minor, or patch)

### ios set_version

```sh
[bundle exec] fastlane ios set_version
```

Set specific version number

### ios prepare_and_upload

```sh
[bundle exec] fastlane ios prepare_and_upload
```

Generate screenshots and upload everything

### ios full_app_store_prep

```sh
[bundle exec] fastlane ios full_app_store_prep
```

Full App Store preparation: icons, screenshots, metadata

----

This README.md is auto-generated and will be re-generated every time [_fastlane_](https://fastlane.tools) is run.

More information about _fastlane_ can be found on [fastlane.tools](https://fastlane.tools).

The documentation of _fastlane_ can be found on [docs.fastlane.tools](https://docs.fastlane.tools).
