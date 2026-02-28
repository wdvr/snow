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

## Summary

| Area | HIGH | MEDIUM | LOW | Fixed | Not Fix |
|------|------|--------|-----|-------|---------|
| iOS Forced Update | 2 | 4 | 2 | 3 | 5 |
| Backend App-Config | 0 | 0 | 2 | 1 | 3 |
| Configuration | 1 | 1 | 2 | 0 | 4 |
| Map UX | 2 | 3 | 3 | 4 | 4 |
| Web Timeline | 2 | 4 | 2 | 8 | 0 |
| **Total** | **7** | **12** | **11** | **16** | **16** |
