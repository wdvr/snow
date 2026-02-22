# Claude Working Instructions - Snow Quality Tracker

## Quick Start for Agents

### Environment Setup Check
Before starting work, verify these are available:

```bash
# Check GitHub CLI
which gh || echo "gh CLI not installed - see setup below"

# Check GitHub token
echo "GITHUB_TOKEN is ${GITHUB_TOKEN:+set (length: ${#GITHUB_TOKEN})}"

# Check AWS credentials (if doing backend work)
echo "AWS_PROFILE: ${AWS_PROFILE:-not set}"
```

### Installing gh CLI (if needed)
If running in a sandboxed environment without sudo:
```bash
mkdir -p ~/bin && cd /tmp && \
  curl -L https://github.com/cli/cli/releases/latest/download/gh_2.63.2_linux_amd64.tar.gz -o gh.tar.gz && \
  tar -xzf gh.tar.gz && \
  mv gh_*/bin/gh ~/bin/ && \
  rm -rf gh.tar.gz gh_* && \
  export PATH="$HOME/bin:$PATH"
```

The `GITHUB_TOKEN` environment variable will be used automatically for authentication.

### Parallel Subagent Execution
You have permission to spawn multiple subagents in parallel for faster task completion:
```bash
# Spawn parallel agents with full permissions
claude -p --dangerously-skip-permissions "task description here" &
claude -p --dangerously-skip-permissions "another task" &
wait
```
Use this for independent tasks that can run concurrently (e.g., investigating different issues, running tests while making changes).

### No Shortcuts Policy
**We don't take shortcuts.** If you encounter issues during your work - even if they're unrelated to your current task - fix them. This includes:
- Pre-existing test failures
- Compilation warnings
- Outdated dependencies
- Code style inconsistencies
- Documentation that's out of sync

Spawn subagents to handle parallel fixes if needed:
```bash
claude -p --dangerously-skip-permissions "Fix the failing tests in SnowTrackerTests.swift" &
```

A clean codebase is everyone's responsibility. Leave things better than you found them.

### iOS Code Signing - Auto-Cleanup of Certificates
The iOS build workflow uses App Store Connect API for automatic signing. Xcode creates a new
development certificate on each CI build (ephemeral runners have no keychain certs). A
**cert cleanup step** in `ios-build.yml` runs before each archive to revoke excess certs
via the ASC API, keeping 1 dev cert and 2 distribution certs. This prevents hitting Apple's limit.

**NEVER**:
- Remove the cert cleanup step from `ios-build.yml`
- Set `skip_automatic_signing: false` in shared workflows (creates unmanaged certs)

The signing approach (in `ios-build.yml`):
- **Cert cleanup**: Python script uses ASC API to revoke excess dev certs before archive
- **Archive**: `-allowProvisioningUpdates` with ASC API auth for automatic signing
- **Export**: `app-store-connect` method with automatic signing style
- **PRs**: `CODE_SIGNING_ALLOWED=NO` (no signing needed)

### Always Test on Real Device
When working on iOS changes, **always build and deploy to the physical device** if it's available. Don't just build for simulator - real device testing catches issues that simulators miss. After deploying, launch the app to verify the fix works.

The device ID for the iPhone is `00008150-001625E20AE2401C`.

---

## Hybrid Agent/Developer Workflow

### Issue Labels for Workflow
| Label | Meaning |
|-------|---------|
| `agent-friendly` | Can be completed autonomously by AI agent |
| `needs-user-input` | Requires user decisions, credentials, or device access |
| `needs-clarification` | Requirements unclear, ask before starting |
| `complex` | Multi-component feature, may need breakdown |
| `ios` | iOS/Swift work |
| `backend` | Python/AWS work |
| `research` | Investigation task, no code changes |

### Finding Work
```bash
# Agent-friendly issues (start here!)
gh issue list --label "agent-friendly"

# Issues needing user input (flag to user)
gh issue list --label "needs-user-input"

# All open issues
gh issue list --state open
```

### Development Flow
1. **Pick an issue** - Prefer `agent-friendly` issues for autonomous work
2. **Create branch**: `git checkout -b feature/issue-123-description`
3. **Implement with tests** - Always add tests for changes
4. **Commit frequently** with clear messages
5. **Push branch**: `git push -u origin feature/issue-123-description`
6. **Create DRAFT PR**: `gh pr create --draft --title "Title" --body "Closes #123"`
7. **Add progress comments** on PR for audit trail
8. **Mark ready when complete**: `gh pr ready` (triggers auto-merge if CI passes)

> **IMPORTANT**: Always create PRs as drafts (`--draft`). This prevents auto-merge from merging
> half-baked work. Only mark ready (`gh pr ready`) when implementation is complete and tested.

### When Blocked
- If `needs-user-input`: Flag to user and explain what's needed
- If `needs-clarification`: Ask specific questions before proceeding
- If device/credentials needed: Document what's required, move on to other work

---

## Project Overview

Snow quality tracking app for ski resorts. Tracks conditions at different elevations and estimates fresh powder vs. icy conditions.

### Tech Stack
| Component | Technology |
|-----------|------------|
| iOS App | Swift 6, SwiftUI, Xcode 26 |
| Backend | Python, FastAPI, AWS Lambda |
| Database | DynamoDB |
| Infrastructure | Pulumi (Python) |
| CI/CD | GitHub Actions |
| Weather Data | Open-Meteo API |

### Project Structure
```
snow/
├── ios/              # SwiftUI iOS app
├── backend/          # Python Lambda functions
├── infrastructure/   # Pulumi AWS setup
├── .github/          # GitHub Actions workflows
├── CLAUDE.md         # This file (agent instructions)
└── PROGRESS.md       # Status tracking
```

### AWS Account
All infrastructure runs on the **personal** AWS account (`us-west-2` region).

### API Endpoints
```
Custom domains (used by iOS app):
  Production: https://api.powderchaserapp.com
  Staging:    https://staging.api.powderchaserapp.com
  Dev:        https://dev.api.powderchaserapp.com

API Gateway URLs (direct):
  Staging:    https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging
  Production: https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod

GET  /health                           - Health check
GET  /api/v1/regions                   - List ski regions with resort counts
GET  /api/v1/resorts                   - List all resorts
GET  /api/v1/resorts?region=alps       - Filter by region (na_west, na_rockies, na_east, alps, scandinavia, japan, oceania, south_america)
GET  /api/v1/resorts?country=CA        - Filter by country code
GET  /api/v1/resorts/nearby?lat=X&lon=Y&radius=200&limit=20 - Find resorts near location
GET  /api/v1/resorts/{id}              - Resort details
GET  /api/v1/resorts/{id}/conditions   - Weather conditions (all elevations)
GET  /api/v1/resorts/{id}/conditions/{level} - Conditions for specific elevation (base/mid/top)
GET  /api/v1/resorts/{id}/snow-quality - Snow quality summary (all elevations + overall)
GET  /api/v1/resorts/{id}/timeline     - 7-day forecast timeline
GET  /api/v1/resorts/{id}/events       - Resort events
GET  /api/v1/snow-quality/batch?resort_ids=a,b,c - Batch snow quality
GET  /api/v1/conditions/batch?resort_ids=a,b,c   - Batch conditions
GET  /api/v1/quality-explanations      - Quality level descriptions
GET  /api/v1/recommendations?lat=X&lon=Y - Nearby recommendations
GET  /api/v1/recommendations/best      - Best conditions globally
POST /api/v1/auth/apple                - Apple Sign In
POST /api/v1/auth/guest                - Guest authentication
POST /api/v1/auth/refresh              - Refresh auth token
GET  /api/v1/auth/me                   - Current user info
POST /api/v1/trips                     - Create trip
GET  /api/v1/trips                     - List trips
GET  /api/v1/trips/{id}               - Get trip details
PUT  /api/v1/trips/{id}               - Update trip
DELETE /api/v1/trips/{id}             - Delete trip
POST /api/v1/feedback                  - Submit feedback
POST /api/v1/chat                      - AI conditions chat (Bedrock Claude Sonnet 4.6)
GET  /api/v1/chat/conversations        - List chat conversations
GET  /api/v1/chat/conversations/{id}   - Get conversation messages
DELETE /api/v1/chat/conversations/{id} - Delete conversation
POST /api/v1/resorts/{id}/condition-reports - Submit user condition report
GET  /api/v1/resorts/{id}/condition-reports - List condition reports for resort
GET  /api/v1/user/condition-reports    - List user's own condition reports
DELETE /api/v1/resorts/{id}/condition-reports/{report_id} - Delete condition report
GET  /api/v1/resorts/{id}/history      - Snow history (daily snowfall chart data + season summary)
```

### DynamoDB Tables
```
snow-tracker-resorts-{env}                 - Resort master data
snow-tracker-weather-conditions-{env}      - Hourly weather conditions (60d TTL)
snow-tracker-snow-summary-{env}            - Season snowfall totals (no TTL)
snow-tracker-daily-history-{env}           - Daily snow history snapshots (no TTL)
snow-tracker-user-preferences-{env}        - User preferences & notification settings
snow-tracker-device-tokens-{env}           - APNs device tokens (90d TTL)
snow-tracker-resort-events-{env}           - Resort events
snow-tracker-feedback-{env}                - User feedback
snow-tracker-chat-{env}                    - AI chat conversations (30d TTL)
snow-tracker-condition-reports-{env}       - User condition reports (90d TTL)
```

### Bedrock Configuration
- Model: Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6-20250514`) via Amazon Bedrock Converse API with tool_use
- Region: `us-west-2`
- Chat history table: `snow-tracker-chat-{env}`
- Condition reports table: `snow-tracker-condition-reports-{env}`

---

## GitHub Workflow

### Branch Naming
- `feature/issue-123-description` - New features
- `fix/issue-123-description` - Bug fixes
- `chore/description` - Maintenance (no issue required)

### Common Commands
```bash
# Issues
gh issue list --state open
gh issue create --title "Title" --body "Description" --label "enhancement"
gh issue view 123

# Pull Requests (always use --draft, mark ready when done)
gh pr create --draft --title "Add feature" --body "Closes #123"
gh pr ready           # Mark PR ready for review/merge
gh pr list
gh pr merge 123 --squash --auto  # Auto-merge when CI passes

# Deployments & Weather Processing
gh run list --workflow=deploy.yml
gh workflow run trigger-weather.yml -f environment=staging -f wait_for_completion=true
```

### Pull Request Requirements
- Link to GitHub issue (use "Closes #123")
- All tests must pass
- Add progress comments for audit trail
- **Never push directly to main**

---

## Testing Commands

### Backend (Python)
```bash
cd backend
python -m pytest tests/ -v --cov=src --cov-report=html
```

### iOS (requires Mac with Xcode)
```bash
cd ios

# Unit tests
xcodebuild test -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:SnowTrackerTests

# UI tests
xcodebuild test -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:SnowTrackerUITests
```

### Infrastructure
```bash
cd infrastructure
pulumi preview --diff
```

---

## Key Guidelines

### Code Quality
- **Always add tests** for new/modified code
- **Never skip tests** - CI will catch issues
- **Follow existing patterns** in the codebase
- **Keep changes focused** - one issue per PR

### Security
- Never commit secrets (.env, credentials)
- Validate user input
- Use parameterized queries for DynamoDB

### iOS Specific
- Use SwiftUI and async/await
- Follow MVVM architecture
- Support accessibility (VoiceOver, Dynamic Type)
- Test on multiple device sizes

### Backend Specific
- Use Pydantic for validation
- Add proper error handling
- Log appropriately for CloudWatch
- Keep Lambda functions focused

---

## Current Resorts (28+ across 8 regions)
**NA West Coast**: Whistler Blackcomb, Mammoth, Palisades Tahoe, Big White, Silver Star, Sun Peaks
**NA Rockies**: Lake Louise, Revelstoke, Vail, Park City, Jackson Hole, Aspen, Telluride, Steamboat, Breckenridge
**Alps**: Chamonix, Zermatt, St. Anton, Verbier, Val d'Isère, Courchevel, Kitzbühel, Cortina d'Ampezzo
**Japan**: Niseko, Hakuba
**Oceania**: The Remarkables (NZ), Thredbo (AU)
**South America**: Portillo (CL)

---

## Deploy to Physical Device (Mac only)
```bash
# Build, install, and launch on iPhone 17 Pro Max (i17pw)
cd ios
xcodebuild -project SnowTracker.xcodeproj -scheme SnowTracker \
  -destination 'id=00008150-001625E20AE2401C' -configuration Debug build
xcrun devicectl device install app --device 00008150-001625E20AE2401C \
  ~/Library/Developer/Xcode/DerivedData/SnowTracker-*/Build/Products/Debug-iphoneos/SnowTracker.app
xcrun devicectl device process launch --device 00008150-001625E20AE2401C com.snowtracker.app
```

## Available Skills

Detailed instructions in `.claude/commands/`:

- **`/build-test`** — Build iOS app and run tests, run backend pytest
- **`/deploy-testflight`** — Deploy to TestFlight (via GH Actions or manual xcodebuild)
- **`/deploy-backend`** — Deploy backend to AWS Lambda via Pulumi or GH Actions
