# Deploy to TestFlight via CI

Trigger iOS build and upload to TestFlight Internal via GitHub Actions. Use this to ship a new build for testing.

## Steps

1. Trigger the iOS Build workflow and wait for it to complete:
```bash
gh workflow run "iOS Build" --repo wdvr/snow
```

2. Monitor the build until it completes:
```bash
gh run list --workflow=ios-build.yml --repo wdvr/snow --limit=1
gh run view <run_id> --repo wdvr/snow
```

3. Once the build succeeds, trigger TestFlight Internal upload:
```bash
gh workflow run "iOS TestFlight Internal" --repo wdvr/snow
```

4. Monitor the upload:
```bash
gh run list --workflow=ios-testflight-internal.yml --repo wdvr/snow --limit=1
gh run view <run_id> --repo wdvr/snow
```

5. Report the final status to the user, including the build number.

## Notes
- The build workflow archives and exports the IPA as a GitHub artifact
- The TestFlight Internal workflow downloads the artifact and uploads to App Store Connect
- Both run on the self-hosted Mac runner — only one job at a time
- If a CI Pipeline job is running, it may block the build; cancel it if needed
- Build numbers are auto-calculated from git commit count
