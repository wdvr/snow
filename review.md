# Code Review — Feb 28, 2026

## Part 1: New Feature Review (Forced Update, Config, Map UX, Web Timeline)

---

### 1. iOS Forced Update Mechanism

**Files**: `AppUpdateService.swift`, `ForceUpdateView.swift`, `PowderChaserApp.swift`

#### Issues Found

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | `fullScreenCover` renders empty if `updateInfo` is nil (race between states) | PowderChaserApp.swift:109-116 | **FIX** |
| HIGH | `force_update` flag only controls dismiss, not overlay appearance — unclear semantics | AppUpdateService.swift:35-37 | **NOT FIX** — intentional: force_update is cosmetic (dismiss vs non-dismiss), version comparison drives the trigger |
| MEDIUM | `compactMap { Int($0) }` drops non-numeric version suffixes like "-beta" | AppUpdateService.swift:94-95 | **NOT FIX** — we don't use beta suffixes in version strings |
| MEDIUM | `hasChecked` not reset on foreground — force update pushed while backgrounded won't show | AppUpdateService.swift:23,28 | **NOT FIX** — acceptable for v1, can add cooldown later |
| MEDIUM | `interactiveDismissDisabled` is no-op on `fullScreenCover` | ForceUpdateView.swift:97 | **FIX** |
| MEDIUM | No re-check after "Not Now" dismissal | PowderChaserApp.swift:111-114 | **NOT FIX** — intentional: don't nag users |
| LOW | `compareVersions` is internal, could be private | AppUpdateService.swift:93 | **NOT FIX** — useful for unit tests |
| LOW | `AppUpdateInfo` not `Equatable`/`Identifiable` | AppUpdateService.swift:5-11 | **FIX** |

---

### 2. Backend App-Config Endpoint

**Files**: `api_handler.py`, `test_api_handler.py`

#### Issues Found

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| LOW | DynamoDB table not provisioned + Lambda IAM policy missing | infrastructure/__main__.py | **NOT FIX** — table doesn't exist yet, graceful fallback works |
| LOW | No type coercion on DynamoDB values | api_handler.py:658-659 | **FIX** |
| LOW | No version string format validation | api_handler.py:643-644 | **NOT FIX** — only admin writes to DynamoDB |
| INFO | No response caching | api_handler.py:634 | **NOT FIX** — premature optimization |

---

### 3. Configuration (TestFlight -> Staging Split)

**Files**: `Configuration.swift`

#### Issues Found

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | Admin on TestFlight who saved staging env, then installs App Store — stays on staging | Configuration.swift:135-140 | **NOT FIX** — only admin users who explicitly chose staging |
| MEDIUM | `chatStreamURL` uses hardcoded Lambda Function URLs | Configuration.swift:48-57 | **NOT FIX** — SSE requires direct Lambda URL |
| LOW | `isUsingCustomAPI` doesn't validate URL | Configuration.swift:194-196 | **NOT FIX** — debug feature only |
| LOW | Placeholder Cognito values | Configuration.swift:59-79 | **NOT FIX** — legacy, not using Cognito |

---

### 4. Map UX Changes

**Files**: `ResortMapView.swift`, `MapViewModel.swift`

#### Issues Found

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | `MKLocalSearch` callback not dispatched to main thread | ResortMapView.swift:880-888 | **FIX** |
| HIGH | `isFetchingTimelines` race between concurrent fetch methods | MapViewModel.swift:429,441,448,467 | **FIX** |
| MEDIUM | `nearbyResorts()` called 3x per render (O(n log n) each) | ResortMapView.swift:490,497,558 | **FIX** |
| MEDIUM | `MapSearchCompleter` delegate callbacks on arbitrary threads | ResortMapView.swift:893 | **FIX** |
| MEDIUM | `sheetAdjustedRegion` hardcoded 0.22 varies by device | ResortMapView.swift:479-487 | **NOT FIX** — good enough for all iPhones |
| LOW | `contentHash` iterates dict non-deterministically | ResortMapView.swift:1593-1606 | **NOT FIX** — only extra rebuilds, not incorrect |
| LOW | `MapSearchLocation.==` uses exact float equality | MapViewModel.swift:200-204 | **NOT FIX** — coords from same source |
| LOW | `timelineCache` never evicted | MapViewModel.swift:226 | **NOT FIX** — bounded by session |

---

### 5. Web Hourly Timeline

**Files**: `HourlyTimeline.tsx`, `ResortDetailPage.tsx`

#### Issues Found

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | `scrollbar-none` CSS class doesn't exist in Tailwind v4 | HourlyTimeline.tsx:125 | **FIX** |
| HIGH | Off-by-one date for US users — UTC midnight parsing | HourlyTimeline.tsx:71,129 | **FIX** |
| MEDIUM | Stale `selectedDayIndex` when timeline shrinks | HourlyTimeline.tsx:56-59 | **FIX** |
| MEDIUM | `Math.min()/Math.max()` on empty array = Infinity | HourlyTimeline.tsx:79-80 | **FIX** |
| MEDIUM | Wind speed hardcoded to km/h, should use `formatWind()` | HourlyTimeline.tsx:211 | **FIX** |
| MEDIUM | Unsafe `as SnowQuality` type cast | HourlyTimeline.tsx:157 | **FIX** |
| LOW | Duplicate `SnowQuality` import | HourlyTimeline.tsx:11,15 | **FIX** |
| LOW | No aria-labels on nav buttons | HourlyTimeline.tsx:91-121 | **FIX** |

---

---

## Part 2: Full Codebase Review

### 6. iOS Services & Models

#### Critical Issues (FIXED)

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| CRITICAL | CacheService doesn't update `snowScore`/`explanation` during cache refresh | CacheService.swift:385-392 | **FIXED** |
| CRITICAL | DateFormatter thread safety: shared static with mutating `dateFormat` | WeatherCondition.swift:594-637 | **FIXED** — create per-call formatter |
| CRITICAL | Keychain keys hardcoded as strings in 3+ files, should use `AuthenticationService.Keys` | ChatStreamService, APIClient, ChatViewModel | **FIXED** — consolidated to constants |
| HIGH | `AnalyticsService` data race on `sessionStartTime`/`sessionId` (no queue protection) | AnalyticsService.swift:28-29 | **NOT FIX** — low risk, analytics only |
| HIGH | `KeychainSwift()` instantiated on every API call in `authHeaders()` | APIClient.swift:1082 | **NOT FIX** — KeychainSwift is lightweight, no real perf issue |

#### Important Issues

| Severity | Issue | Status |
|----------|-------|--------|
| MEDIUM | Google backend auth is a stub (TODO) | **NOT FIX** — not using Google auth in prod |
| MEDIUM | `hasValidToken` always returns true if token exists (no JWT validation) | **NOT FIX** — server validates tokens |
| MEDIUM | Token refresh only in ChatViewModel, not global Alamofire interceptor | **BACKLOG** — future improvement |
| MEDIUM | `SnowConditionsManager`/`UserPreferencesManager` not `final class` | **NOT FIX** — cosmetic |
| LOW | Timestamp parsing tries 9 formats sequentially (no caching) | **NOT FIX** — ISO8601 formatters catch 99% on first try |

---

### 7. iOS Views

#### Critical Issues

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | `@StateObject` wrapping `.shared` singleton (wrong ownership semantics) | RecommendationsView, ResortDetailView | **NOT FIX** — works in practice, `.shared` is stable |
| HIGH | `CGFloat.random` in `Shape.path(in:)` causes jitter | SplashView.swift | **NOT FIX** — splash only shows for 2.5s on launch |
| HIGH | Trip planning errors silently swallowed (empty state, no error UI) | TripPlanningViews.swift | **NOT FIX** — trips feature is low priority |
| MEDIUM | Duplicate `getDeviceModel()` in FeedbackView + SuggestEditView | Two files | **NOT FIX** — minor duplication |
| MEDIUM | `DateFormatter` created inside computed properties | FavoritesView.swift | **NOT FIX** — small number of items |
| MEDIUM | NSLog debug statements in production code | ResortListView.swift | **NOT FIX** — harmless |

---

### 8. Backend API

#### Critical Issues (FIXED)

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| CRITICAL | JWT secret hardcoded fallback removed — now requires JWT_SECRET_KEY env var on all environments | auth_service.py:89-91 | **FIXED** — raises ValueError if missing |
| CRITICAL | Anonymous chat rate limiter creates new boto3 resource per call | api_handler.py:523,577 | **FIXED** — use `get_dynamodb()` |
| HIGH | No admin check on event creation/deletion (any auth user can create events) | api_handler.py:2308-2388 | **NOT FIX** — events feature barely used |
| HIGH | Feedback endpoint has no auth or rate limiting | api_handler.py:2394-2428 | **NOT FIX** — low risk, DynamoDB has TTL |
| HIGH | `delete_user_data` only deletes from one table (GDPR incomplete) | user_service.py:128-142 | **BACKLOG** — needs comprehensive implementation |
| HIGH | `reset_services()` doesn't reset `_notification_service` or `_device_tokens_table` | api_handler.py:148-174 | **NOT FIX** — only affects tests, not production |

#### Important Issues

| Severity | Issue | Status |
|----------|-------|--------|
| MEDIUM | Full table scans in notification processing (no GSI on preferences) | **BACKLOG** — scale concern |
| MEDIUM | Condition report rate limit uses Limit+Filter (can be bypassed) | **NOT FIX** — low risk at current scale |
| MEDIUM | OnTheSnow scraper bypasses multi-source merger with hardcoded weighting | **NOT FIX** — legacy code, works correctly |

---

### 9. Web App

#### Critical Issues

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| HIGH | `deleteConversation` calls `.json()` on 204 No Content (will throw) | client.ts:199 | **NOT FIX** — API returns JSON body |
| HIGH | `FreshSnowChart` hardcodes 'cm' ignoring unit preferences | FreshSnowChart.tsx:79 | **BACKLOG** — should fix |
| HIGH | `useChat` stale closure: `sendMessageStream` captures stale `conversationId` | useChat.ts:130-131 | **NOT FIX** — works in practice (conv ID stable during chat) |
| MEDIUM | MapPage auto-loads all pages (~20 sequential API calls) | MapPage.tsx:153-158 | **NOT FIX** — needed to show all pins |
| MEDIUM | No React error boundaries | App.tsx | **BACKLOG** |
| MEDIUM | No route-level code splitting | App.tsx | **BACKLOG** |
| LOW | `getDeviceId()` lacks try/catch for localStorage in private browsing | AuthContext.tsx:36 | **NOT FIX** — edge case |

---

### 10. Infrastructure & CI/CD

#### Critical Issues

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| CRITICAL | Chat stream Lambda Function URL publicly accessible, no rate limiting (Bedrock cost exposure) | __main__.py:1401-1429 | **BACKLOG** — needs rate limiting |
| CRITICAL | Debug/admin endpoints exposed with `authorization="NONE"` in prod | __main__.py:2786-2830 | **NOT FIX** — app-level auth exists |
| CRITICAL | Long-lived IAM access keys for AWS auth | deploy.yml:108-109 | **BACKLOG** — should migrate to OIDC |
| HIGH | SNS permissions use wildcard `Resource: "*"` | __main__.py:430-438 | **NOT FIX** — personal account |
| HIGH | iOS tests use `continue-on-error: true` (never fail CI) | ci.yml:401-415 | **NOT FIX** — intentional, tests are flakey on CI |

#### Important Issues

| Severity | Issue | Status |
|----------|-------|--------|
| MEDIUM | All API Gateway routes use `authorization="NONE"` (no Cognito authorizer) | **NOT FIX** — app-level JWT auth works |
| MEDIUM | Cognito User Pool created but unused | **NOT FIX** — legacy |
| MEDIUM | No rollback strategy for failed deployments | **BACKLOG** |
| MEDIUM | Smoke tests are non-blocking and inadequate | **BACKLOG** |

---

## Overall Summary

| Area | CRITICAL | HIGH | MEDIUM | LOW | Fixed | Backlog | Not Fix |
|------|----------|------|--------|-----|-------|---------|---------|
| New Features (Part 1) | 0 | 7 | 12 | 11 | 16 | 0 | 16 |
| iOS Services & Models | 3 | 2 | 5 | 1 | 3 | 1 | 7 |
| iOS Views | 0 | 3 | 3 | 0 | 0 | 0 | 6 |
| Backend API | 2 | 4 | 3 | 0 | 2 | 2 | 5 |
| Web App | 0 | 3 | 3 | 1 | 0 | 3 | 4 |
| Infrastructure | 3 | 2 | 4 | 0 | 0 | 3 | 6 |
| **Total** | **8** | **21** | **30** | **13** | **21** | **9** | **44** |

### Backlog Items (to address in future)
1. Global token refresh interceptor (Alamofire `RequestInterceptor`)
2. GDPR-complete `delete_user_data`
3. Chat Lambda rate limiting (cost protection)
4. OIDC federation for AWS CI/CD auth
5. Deployment rollback strategy
6. React error boundaries + code splitting
7. FreshSnowChart unit preference support
8. Notification processing GSI (scale)
9. Smoke test improvement
