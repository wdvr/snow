# Powder Chaser — Dev Diary

Cross-platform fix/feature tracker. Each item shows status across platforms.
Status: done | pending | n/a (not applicable) | backlog

---

## Feb 28, 2026

### Fix: Nearby resort card tap crash
Race condition when tapping nearby resort card on map — setting pendingRegion and selectedResort simultaneously caused SwiftUI to fight between map animation and sheet presentation. Fixed by delaying selectedResort by 0.5s.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: "Show on Map" navigation
Added cross-tab navigation via NavigationCoordinator. "Show on Map" button in resort detail toolbar (map.fill icon) + context menus on Resorts, Favorites, and Best Snow tabs. Switches to Map tab, zooms to resort, shows detail sheet.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Fix: Spotlight app name
Set PRODUCT_NAME to "Powder Chaser" (was defaulting to "PowderChaser" from TARGET_NAME). Added PRODUCT_MODULE_NAME override to keep Swift module name as PowderChaser. Updated TEST_HOST for test targets.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Chore: Full rename SnowTracker → PowderChaser
Renamed all directories, targets, scheme, tests, widget, module name from SnowTracker to PowderChaser. Updated all source files, workflows, docs, backend user-agent strings, Grafana dashboards. Bundle IDs unchanged (com.wouterdevriendt.snowtracker) to preserve App Store identity.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Fix: Debug "Send Test Notification" visible for admin in production
Debug section in NotificationSettingsView was gated by `isDebugOrTestFlight` only. Now also shows for admin users (via `AppConfiguration.shared.showDeveloperSettings`) in production builds, matching the staging API button pattern.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Fix: Test push notification works for any authenticated user
Backend `test-push-notification` endpoint was admin-only in production (403 for regular users). Changed to require any authenticated user — it only sends to the requesting user's own devices, so there's no security concern. Trigger-notifications endpoint remains admin-only.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Fix: Map UX improvements
- "Show on Map" from resort list now properly zooms (not just pans) + offsets resort to upper half above detail sheet
- Nearby card taps offset resort to upper half above detail sheet
- Map detail sheet has "Zoom to Resort" button
- Search for location updates "Nearby" label to "Near {place}" with distance-sorted resorts
- X button to clear search location and return to user's current location
- "Near current location" option in search sheet
- All features work without location permissions when search location is set
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

## Feb 27, 2026

### Feature: Map search — search for locations from bottom bar
Added magnifying glass + "Search" button in the bottom nearby bar. Opens sheet with MKLocalSearchCompleter autocomplete. Selecting a result pans map to that location. Works independently of location services.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Fix: Piste overlay colors for NA resorts
Colors used EU convention (green/blue/red/black) everywhere. NA resorts (US/CA) use green/blue/black. Added PisteColorScheme enum derived from resort country. Novice+easy→green, intermediate→blue for NA. EU stays green/blue/red/black.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Nearby resort card → zoom to resort
Tapping a nearby resort card now zooms the map to that resort (0.08° span) before showing the detail sheet, instead of just opening the sheet at the current zoom level.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Change: Piste overlay always enabled, toggle removed
Ski trail overlay now enabled by default and the toolbar toggle was removed. Trails only render when zoomed in (latDelta < 0.3) so no clutter at wide zoom. Fetches trigger on appear and region change.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Change: App display name — "Snow Tracker" → "Powder Chaser"
Updated CFBundleDisplayName and CFBundleName in project.yml and Info.plist. Home screen and Spotlight now show "Powder Chaser". Widget renamed too.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Feature: Vector piste overlay POC — Overpass API + native MKPolyline
Queries OpenStreetMap via Overpass API for downhill piste ways (`piste:type=downhill`) and aerial lifts (`aerialway`) within a bounding box around visible resorts. Renders pistes as colored MKPolyline overlays (green=novice, blue=easy, red=intermediate, black=advanced) and lifts as dashed gray lines. PisteOverlayService is an actor with LRU cache (50 entries), deduped in-flight requests. Auto-fetches when piste toggle is enabled and map is zoomed in (latDelta < 0.15°). Coexists with existing OpenSnowMap raster tiles. Coverage: good for NA/Europe (Vail: 211, Zermatt: 131, Chamonix: 105), sparse for Japan (Niseko: ~8 ways in broad area).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Piste overlay enhancement — brighter colors, lower min zoom, CIFilter processing
Alpha increased from 0.7 to 0.85 for more visible trails. Min zoom lowered from 13 to 12 for earlier trail visibility. Custom `SaturatedPisteTileOverlay` subclass applies CIColorControls filter (saturation 1.6, contrast 1.2) to OpenSnowMap raster tiles via `loadTile` override with static GPU-backed CIContext. Graceful fallback to unprocessed tiles if filter fails.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Bugfix: BUG-194 — Fresh snow display showed accumulated-since-thaw, not recent snowfall
Users saw "21cm fresh" with a POOR score — misleading because `freshSnowCm` = accumulated snow since last thaw-freeze event (up to 14+ days). Now all views (resort list, detail quick stats, favorites, chat, elevation profile) prefer `snowfall24hCm` when >= 0.5cm. Shows "Xcm/24h" with cloud.snow icon for recent snow, falls back to "Xcm fresh" with snowflake icon for accumulated. Labels switch dynamically ("24h" vs "Fresh").
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | n/a |

### Feature: Translation expansion — 19 new strings + 4 new languages (17 total)
Extracted 19 hardcoded English strings (buttons, alerts, actions). All 17 language files now have 211 strings. Added Russian (ru), Finnish (fi), Czech (cs), Traditional Chinese (zh-Hant) with complete coverage.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Data: Logo merge — 15 new logos (833/1019, 81.7%)
Merged logo search results from background agents. Smart quality scoring (SVG > PNG > WebP > JPG). DynamoDB updated via Populate Resorts workflow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

---

## Feb 26, 2026

### Feature: v2.0 — Map zoom refresh + webcam card + version bump
Map now fetches conditions on zoom (not just pan) using `visibleResortIds()` viewport filter. Webcam button in map detail sheet replaced with prominent card opening in-app SFSafariViewController. Version bumped to 2.0.0 with updated App Store release notes and description (1040+ resorts, 25 countries).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

## Feb 28, 2026

### Bugfix: Snow depth systematic underestimation (Kimberly 1cm→100cm, 529 resorts affected)
Open-Meteo's `snow_depth` forecast model (~9km grid) wildly underestimates mountain snow depth: Kimberly showed 1cm (should be 100cm), Fernie 0cm, Sun Peaks 0cm. 529/1019 resorts (52%) affected — those without resort-reported data from onthesnow.com. Three fixes: (1) Re-enabled ERA5 historical archive conditionally when modeled depth < 30cm at elevation > 1000m, (2) Added accumulated 14-day snowfall × 0.6 settling ratio as floor, (3) Fixed fresh_snow_cm cap to not cap at unreliable snow_depth values.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Bugfix: Timeline card background color mismatch
Conditions timeline card had `.systemBackground` instead of `.secondarySystemBackground`. Replaced manual styling with `.cardStyle()` modifier for consistency.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Expanded map quality filter chips (3→6 options)
Map filter chips expanded from 3 (All/Good+/Below Good) to 6 granular options: All, Excellent+, Good+, Decent+, Mediocre+, Below Good. Each with appropriate quality arrays and color.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | n/a |

### Bugfix: Chat keyboard dismiss + conversation history auth
Added `.scrollDismissesKeyboard(.interactively)` to chat message list. Added token refresh on 401 in `loadConversations()` (matching `sendWithAutoRefresh` pattern).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Translations — 79 new strings across 13 languages
Added missing translations for all new UI (quality ratings, favorites, resort list, settings, recommendations, map, detail view, chat, chat suggestions, map filters). Now 192 strings per language.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Data: SVG→PNG logo conversion for iOS compatibility
iOS AsyncImage can't render SVG files. Identified 395 resorts with SVG logo_urls (39% of all logos). Built CairoSVG batch conversion script: downloads SVG, converts to 256x256 PNG, uploads to S3 webapp bucket. Successfully converted 354/395 (41 failed: 404s, SSL errors, HTML responses). Updated resorts.json with new S3 PNG URLs. DynamoDB updated via Populate workflow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Bugfix: BUG-003 — Fresh snow scored too low (Lake Louise 21cm@-7.5°C scored 26/100)
ML model freeze-thaw detection reset `snow_since_freeze_cm` even with genuinely fresh snow. Added `_apply_fresh_snow_floor` physics constraint (symmetric counterpart to `_apply_no_snowfall_cap`): heavy snow ≥15cm@≤-5°C floors at 4.5 (EXCELLENT), moderate ≥8cm@≤-3°C at 3.5 (DECENT), light ≥3cm@≤0°C at 2.5 (MEDIOCRE). Only applies with hours_since_last_snowfall ≤ 12. 14 new tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Bugfix: BUG-011 — Source disagreement not triggering outlier detection in 2-source case
When only 2 sources disagreed by >30%, the multi-source merger fell back to weighted averaging and marked both as "included" — even with 97% disagreement. Now: >50% disagreement triggers outlier detection (lower value marked as outlier, higher trusted — weather stations under-report snow more often than they hallucinate it). 30-50% disagreement still uses weighted average. <30% uses simple average (consensus). Both-near-zero (<1cm) always uses consensus. Added 7 new tests, updated 6 existing tests. All 1620 backend tests pass.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 27, 2026

### Feature: Resort list card redesign (iOS)
Transformed the main Resorts tab from flat `List`+`PlainListStyle` rows to `ScrollView`+`LazyVStack` with card-styled rows matching the `RecommendationCard` from the Best Snow tab. Each card now shows: ResortLogoView (40px), resort name + pass badges + QualityBadge, location, StatItem row (temp/fresh snow/forecast/distance), and quality explanation. Reuses existing shared components (ResortLogoView, PassBadge, QualityBadge, StatItem, .cardStyle()). All existing functionality preserved: search, filters, sort, pull-to-refresh, context menu, deep links, analytics, lazy loading.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Bugfix: Chat forecast tool returned "Not available" instead of real forecasts
The `get_resort_forecast` tool in `chat_stream_handler.py` tried to read a per-resort JSON from S3 (`static-json/{env}/resort-{id}.json`) that doesn't exist, so AI chat could never give next-week predictions. Replaced with a working Open-Meteo API call: looks up resort from DynamoDB for coordinates, calls `OpenMeteoService.get_timeline_data()`, summarizes hourly data into 7-day daily forecasts (min/max temp + total snowfall). 8 new tests added.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Alternate app icons (iOS)
Added 9 app icon variants selectable from Settings > Appearance > App Icon. Icons generated with Pillow: Classic (default), Mountain, Minimal, Gradient, Dark, Neon, Warm, Forest, Bold ("PC"). Each has 1024x1024 PNG in its own .appiconset + preview imageset. AppIconPickerView shows a grid with selection highlight and haptic feedback. Build settings: ASSETCATALOG_COMPILER_ALTERNATE_APPICON_NAMES + INCLUDE_ALL_APPICON_ASSETS.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Bugfix: Quality score mismatch between app (60s) and widget (97)
Batch endpoint (`_get_snow_quality_for_resort`) used a single representative elevation's quality score, while the recommendations endpoint used weighted average (50% top + 35% mid + 15% base). Per design rules, `overall_quality` should always use weighted average. Fixed both `api_handler.py` and `static_json_generator.py` to compute weighted average across all elevation levels. Now app and widget show consistent scores.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Bugfix: Widget showed raw region IDs (e.g. "na_rockies_Alberta")
Both FavoriteResortsWidget and BestResortsWidget displayed raw `region` strings from the API instead of human-readable names. Added `RegionDisplayHelper` to widget extension that parses compound region keys (e.g. "na_rockies_AB" → "Alberta, Canada") with US state, Canadian province, and country name mappings. Applied to both recommendations and batch fetch paths in WidgetDataService.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Feature: Favorites view card redesign + 10-day date selector
Completely redesigned FavoritesView: replaced flat list with card layout matching the main Resorts tab (ResortLogoView, pass badges, QualityBadge, StatItem row, quality explanation text). Added 10-day date selector that fetches timeline data for all favorite resorts and shows predicted quality/weather for each future day. Cards switch between current conditions and forecast data based on selected day.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Feature: Map view UX polish
Simplified map filter chips from 5 options (All, Excellent+, Good+, Below Good, Poor) to 3 clearer options (All, Good+, Below Good). Made nearby resorts section collapsible with chevron toggle animation. Piste overlay improvements: increased minimum zoom from 12→13 (saves memory), added 0.7 alpha for lighter/less obtrusive appearance. OpenSnowMap raster tiles can't be further customized (line thickness, colors are baked into tiles).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Marketing website updates
Updated quality levels from old 6-level to new 10-level scale (Champagne Powder through Horrible). Replaced screenshot with map view (was showing wrong app). Updated all App Store links to include ID (id6758333173). Added iOS Smart App Banner to both marketing site and web app.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | n/a |

### Bugfix: Card background invisible (white on white)
CardStyleModifier used `Color(.systemBackground)` which matched the scroll view background, making cards invisible. Changed to `Color(.secondarySystemBackground)` for visible card distinction.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Bugfix: App name "Snow Tracker" in icon change dialog
iOS icon change confirmation dialog showed "Snow Tracker" instead of "Powder Chaser". Fixed by setting `CFBundleDisplayName` and `CFBundleName` to "Powder Chaser" in Info.plist.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Feb 26, 2026

### Bugfix: Trail map viewer showed 218x180 DZI thumbnails instead of interactive maps
Trail map URLs from skiresort.info were DZI level-8 tile URLs (`trailmap_XXXXX_files/8/0_0.jpg`) — only 218x180px thumbnails. Full-screen TrailMapView (AsyncImage) tried to show these tiny images on a phone screen, making trail maps essentially useless. Fix: converted 699 DZI tile URLs to skiresort.info trail map page URLs (interactive DeepZoom viewer). iOS code now detects URL type: direct image URLs (.jpg/.png from snow-forecast) open in native TrailMapView with pinch-to-zoom; page URLs open in SFSafariViewController with skiresort.info's interactive deep zoom viewer. Logo coverage also bumped to 818/1019 (80.3%).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | done |

### Feature: Massive trail map + logo enrichment via parallel subagents
Enriched resorts.json with trail maps and high-quality logos for 1019 resorts using parallel AI subagent approach. Trail maps: 29 subagents (10 resorts each) searched web for missing trail maps — coverage went from 72.2% to 93.9% (957/1019). Sources: skiresort.info DZI tiles, snow-forecast.com pistemaps, resort websites, skimap.org. Also fixed DZI zoom level bug (level 0 = 1px blue square → level 8 = usable thumbnails). Logos: 10 subagents (100 resorts each) searched for SVG/PNG logos on official resort websites. Added logo_url field to backend model, iOS Resort.swift, Android Models.kt, web types.ts. All platforms prefer server logo_url over Google Favicon fallback. Final: 813/1019 logos (79.8%), 379 SVG + 379 PNG + 55 other. Smart merge script only upgrades, never downgrades existing good logos.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Cost Optimization: Exclude raw_data from DynamoDB writes (~$71/mo savings)
Discovered `raw_data` field (57KB raw Open-Meteo API response) was being written to `weather-conditions` table but never read back — all reads use ProjectionExpression excluding it. ML scorer only uses raw_data from in-memory objects during weather processing. Excluded it from `save_weather_condition()` in both `weather_worker.py` and `weather_processor.py` via `model_dump(exclude={"raw_data"})`. Reduces each write from ~59 WCU to ~2 WCU (~96% reduction). Also confirmed CloudWatch custom metrics ($52.71/mo) were already removed on Feb 19 (commit 15ccb7a). Combined March savings: ~$124/mo.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Ski trail/piste overlay on map view (iOS + web)
Added OpenSnowMap piste tile overlay to the map view. Uses `tiles.opensnowmap.org/pistes/{z}/{x}/{y}.png` — transparent PNG tiles showing color-coded ski trails from OpenStreetMap data. iOS: `MKTileOverlay` added to `ClusteredMapView` at `.aboveRoads` level, toggle button with `figure.skiing.downhill` icon in toolbar, attribution banner. Web: Leaflet `TileLayer` with zoom-aware rendering (only at z12+), toggle button with Mountain icon. Tiles verified at Whistler (15.5KB), Chamonix (9.7KB), Vail (1.4KB) — good coverage worldwide.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | n/a |

### Feature: Resort logos in detail views + map popups
Added resort logos across all platforms using Google Favicon API. Extracts hostname from `officialWebsite` field and constructs favicon URL client-side (`https://t3.gstatic.com/faviconV2?...&url=http://{hostname}&size=128`). Shows initials fallback (gradient blue-cyan box) when logo unavailable. iOS: `ResortLogoView` component (44px detail, 36px map popup). Web: `ResortLogo` component (48px detail, 36px cards, 28px map popup). Android: `ResortLogo` composable (44dp detail header, 36dp list cards) using Coil `AsyncImage`. Also enhanced iOS map popup with webcam + trail map quick-action buttons alongside the existing website button.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Feature: Indy Pass filter + badges (Android)
Added Indy Pass filter chip (green) to Android resort list, matching iOS behavior. Indy badges shown in resort detail (AssistChip), resort cards, and chat suggestions. Updated `Models.kt` with `indyPass` field, `Color.kt` with `IndyGreen`, 13 locale string files with `pass_indy` string. All 55 Android tests passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Feature: Suggest an Edit (iOS + web)
Added "Suggest an Edit" functionality to resort detail views on both iOS and web. Users can select a section (elevation data, lift/trail count, location, pass info, website/webcam, trail map, other) and submit a correction. iOS uses `FeedbackSubmission` model via `APIClient`; web uses `SuggestEditModal` component via `api.submitFeedback()`. Unauthenticated web users are auto-signed in as guest. Submissions stored in DynamoDB feedback table.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | done |

### Fix: Web feedback API schema mismatch
Web `SuggestEditModal` was sending `type`/`resort_id` fields but backend expects `subject`/`message`/`app_version`/`build_number`. Web also expected response `feedback_id` but backend returns `id`. Fixed `client.ts` `submitFeedback` signature and `SuggestEditModal.tsx` to match backend `FeedbackSubmission` model. iOS was already correct.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | n/a |

### Fix: iOS chat text truncation in bullet/numbered lists
Chat AI responses with bullet points were showing truncated text with "..." (e.g., "and not from recent..."). Root cause: SwiftUI HStack layout negotiation in `MarkdownTextView` — bullet/number labels competed with text for horizontal space. Fixed by adding `.layoutPriority(1)` on text views, `.fixedSize()` on bullet labels, and `.lineLimit(nil)` + `.fixedSize(horizontal: false, vertical: true)` on `inlineMarkdown` helper.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Data: Indy Pass resort matching (41 resorts)
Compiled 248 Indy Pass resorts from multiple sources and matched 41 to our 1019-resort database using fuzzy name matching with country cross-reference. Covers resorts across 12 countries (US, CA, AT, JP, CH, SE, CL, CZ, ES, IT, NO, SI). Added `indy_pass` field to `resorts.json` and pushed to DynamoDB via populate workflow. Backend model and iOS model already supported the field; chat service already displays Indy Pass info.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Feature: Trail map images (736 resorts) + zoomable iOS viewer
Scraped trail map URLs for all 1019 resorts: 697 from skiresort.info (DZI tiles), 39 from snow-forecast.com (JPEG piste maps). Fixed 13 notable resort slug overrides (Mammoth, Heavenly, Steamboat, Telluride, Val d'Isere, St. Anton, Kitzbuhel, Hakuba, etc.). 736/1019 (72.2%) now have `trail_map_url` in resorts.json. iOS: Added full-screen `TrailMapView` with pinch-to-zoom, double-tap zoom, drag-to-pan, share button. Resort detail opens native viewer instead of Safari. Integrated trail map + webcam scraping into `enrich_resorts.py` for future enrichment runs.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | done |

### QA Round 2: Scoring physics, API hardening, chat crash, infrastructure fixes
Comprehensive QA audit with 6 parallel agents found and fixed: (1) **ML scorer**: `hours_since_last_snowfall=0.0` was treated as falsy via `or 336.0`, defaulting to 14 days without snow — fixed with explicit None check. Also applied `_apply_no_snowfall_cap()` to `predict_quality()` (real-time endpoint), not just timeline. (2) **API hardening**: Added `_validate_resource_id()` regex validation to all path-parameter endpoints, sanitized error messages to not echo user input or AWS internals, added DynamoDB scan pagination to `get_all_resorts()`. (3) **Chat Float→Decimal crash**: Location queries with lat/lon floats crashed DynamoDB PutItem — fixed with `json.loads(json.dumps(tool_calls), parse_float=Decimal)`. (4) **UserPreferences validation**: Old DynamoDB records missing `updated_at` caused Pydantic validation errors — made fields optional with defaults. (5) **IAM fix**: `chat_suggestions_table` ARN added to Lambda policy in Pulumi. (6) **OpenMeteo threshold**: Aligned snowfall threshold to >0.1cm to ignore sensor noise. All 1592 backend tests passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Timeline forecasts "champagne powder" with zero snowfall (BUG-008)
Added physics constraint to ML scorer: high snow quality ratings (powder day, champagne powder) are physically impossible without fresh snowfall. The ML model could hallucinate scores of 5.0-6.0 for forecast time slots when other features (cold temps, deep snow depth) looked favorable but snowfall was zero. New `_apply_no_snowfall_cap()` function in `ml_scorer.py` enforces: (1) No snowfall in 72h -> cap at 4.0 (GREAT max). (2) No snowfall in 24h with < 5cm in 72h -> cap at 4.5 (EXCELLENT max). Applied as post-scoring guard in `predict_quality_at_hour()`. Added 12 unit tests. All 1592 backend tests pass.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: DynamoDB sync — delete removed resorts + fix bogus elevations (BUG-009b)
Synced DynamoDB prod table with cleaned resorts.json. The populate workflow only adds/updates — it never deletes. Three actions: (1) Ran populate workflow with `update_existing=true` to push corrected data for 845 valid-elevation resorts. (2) Deleted 22 removed resorts directly from DynamoDB (heli-ski, backcountry, planned, indoor, duplicates). (3) Fixed 136 resorts with null elevations directly in DynamoDB — set mid/top to base elevation for flat-terrain resorts (e.g., MeriTeijo top went from bogus 2869m to correct 71m). (4) Regenerated static S3 JSON via Lambda to refresh API cache. Verified: API total_count=1019, MeriTeijo top=71m, deleted resorts return 404.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Resort data cleanup — bogus elevations, duplicates, non-resorts (BUG-009)
Critical data quality fix for `backend/data/resorts.json`. Finnish bunny hills were scoring as "powder day" because fake 2800m+ elevations caused Open-Meteo temperature lapse rate to make temps artificially cold. Changes: (1) Removed 20 non-downhill entries (heli-ski, backcountry, planned/unbuilt, indoor, summer-only). (2) Removed 2 duplicates (northstar-california, silverstar with wrong Ontario coordinates). (3) Fixed 7 resorts with known-wrong elevations (Espace San Bernardo base=7m, Buttermilk swapped base/VD, Aspen Mountain base=400m, Aspen Snowmass base=813m, Diavolezza base=600m, Myoko Akakura top=3029m, Espace Lumiere base=54m). (4) Nulled bogus elevations for 26 resorts across NO/SE/PL/RO/SK (Oslo Tryvann at 2000m, Kungsberget at 2033m, etc.). (5) Fixed coordinates for Hafjell (was in Voss, now Lillehammer) and Nesfjellet (was in Narvik, now Hallingdal). (6) Nulled 21 local-currency prices for RO/PL resorts (>$100 threshold). Resort count: 1040 -> 1018. All 1569 backend tests pass.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Dynamic chat suggestions
Replaced 16 hardcoded AI chat suggestion queries with a DynamoDB-backed dynamic system. New `snow-tracker-chat-suggestions-{env}` table stores suggestions with interpolation tokens (`{resort_name}`, `{nearby_city}`, `{region}`, `{resort_name_2}`). Backend `GET /api/v1/chat/suggestions` returns active suggestions sorted by priority, with hardcoded fallback on error. iOS interpolates tokens using user's favorites, nearby resorts, and location context. Includes seed script (`scripts/seed_chat_suggestions.py`), Pulumi infrastructure, API Gateway route, 6 backend tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | done |

### Fix: Remove duplicate spinner on iOS splash screen
SplashView had two loading indicators: a rotating snowflake (fancy, on-brand) and a standard `ProgressView` at the bottom. Removed the bottom `ProgressView` since the rotating snowflake already serves as loading indicator. Also updated App Store screenshot tests to include AI chat screenshots (phone + iPad), added iPad Pro devices to Fastlane screenshot config, and updated release notes for v1.1.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Inclusive map quality filter + Show on Map button
Web map quality filter rewritten to use full quality scale with inclusive filtering. Previously only showed a few tiers; now supports all levels (Mediocre+ includes everything from mediocre through champagne_powder). Added "Show on Map" button to web resort detail page that navigates to `/map?resort=X&lat=Y&lon=Z&zoom=12` for deep linking. Map page now accepts URL query params to center on a specific resort.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | n/a |

### Feature: iOS App Store release preparation
Created comprehensive `/ios-release` skill at `../.claude/commands/ios-release.md` documenting the complete App Store release workflow: version management, screenshot generation, metadata upload, submission, and 10 lessons learned. Updated release notes with all v1.1 features (AI chat, new map, 1040 resorts, condition reports, etc.). Generated new screenshots including AI chat, map view, resort detail for iPhone + iPad.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Android Fresh Snow Chart (A10 — feature parity)
Added FreshSnowChart composable to Android resort detail screen. Renders a 7-day per-day snowfall bar chart using Compose Canvas (no external chart library). Aggregates hourly timeline points into daily totals, shows cm/in values above bars, date labels on x-axis, distinguishes actual vs forecast data with different opacity bars. Includes "Fresh Powder" header with total snowfall since last thaw. Placed between Snow Details card and Predictions card in resort detail layout. Matches iOS FreshSnowChartView functionality.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Feature: Web cross-platform parity — Map View
Full interactive map page using Leaflet.js + react-leaflet with MarkerClusterGroup for resort clustering. Quality-colored circle markers, 8 region preset buttons (NA West, Rockies, NA East, Alps, Scandinavia, Japan, Oceania, S. America), quality filter tiers (All/Powder+/Excellent+/Good+/Mediocre+), tile layer switching (Standard/Satellite/Terrain), nearby resort carousel with geolocation, resort popup with quality badge on click. New files: MapPage.tsx, QualityFilter.tsx, RegionPresets.tsx, ResortPopup.tsx, NearbyCarousel.tsx.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Feature: Web cross-platform parity — Resort detail enhancements
Comprehensive resort detail overhaul: (1) **ElevationPicker** — segmented Summit/Mid/Base control with elevation meters. (2) **SnowDetailsCard** — fresh snow, 24h/48h/72h snowfall, warming indicator, freeze/thaw time, snow since freeze, base depth warning, weather description. (3) **WeatherDetailsCard** — min/max temp, humidity, wind speed, gust, max gust 24h, visibility with severity colors, min visibility 24h. (4) **SnowForecastCard** — 24h/48h/72h predictions with storm badges. (5) **DataSourcesCard** — collapsible card showing merge method, per-source snowfall with consensus/outlier status. (6) **AllElevationsSummary** — side-by-side base/mid/top cards. (7) **FreshSnowChart** — 7-day daily snowfall bar chart. (8) **Webcam link** in header.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Feature: Web cross-platform parity — Settings, reports, share, units
(1) **SettingsPage** — unit preferences (°C/°F, cm/inches), account management (guest sign in/out), about section. Routed at /settings with nav link. (2) **UnitProvider** context — localStorage-backed unit preferences with formatTemp/formatSnow/formatSnowInt helpers used in history tab. (3) **ConditionReportForm** — modal with condition type dropdown, score slider, elevation picker, comment textarea, POST to API. Submit Report button on reports tab. (4) **Share button** — Web Share API with clipboard fallback + toast notification. (5) **Pass filter** — Epic/Ikon filter buttons on home page. (6) **Distance sorting** — haversine distance + sort-by-distance option.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | n/a |

### Feature: Android cross-platform parity — Data sources, clustering, streaming, forecast
(1) **DataSourcesCard** — expandable card in resort detail showing per-source snowfall, consensus/outlier status with color coding, merge method display. Added SourceDetails/SourceInfo models. (2) **Map Clustering** — Google Maps Compose clustering via maps-compose-utils with ResortClusterItem wrapper, custom marker rendering (quality-colored badges with score), custom cluster badges with count. (3) **Region Presets** — 9 region FilterChips with lat/lng/zoom presets. (4) **SSE Streaming Chat** — ChatStreamService using OkHttp with 120s read timeout, parses SSE events (status/tool_start/tool_done/text_delta/done/error), integrated in ChatRepository with REST fallback. (5) **Map Forecast Mode** — date selector chips, forecast loading per-resort timeline, forecast banner with loading state, forecast quality overlay on markers. (6) **Onboarding Flow** — multi-step: welcome screen with 3 feature highlights (Snow Quality Scores, Interactive Map, AI-Powered Chat), region selection grid with 8 regions + descriptions, saves hidden regions to UserPreferencesRepository.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Deploy workflow wiping Lambda env vars (CRITICAL)
Root cause of recurring snow history/chat/condition reports breakage after each deploy. The GitHub Actions deploy workflow (`deploy.yml`) had hardcoded `update-function-configuration` calls for each Lambda that OVERWROTE whatever Pulumi set. The API handler was missing: `DAILY_HISTORY_TABLE`, `SNOW_SUMMARY_TABLE`, `CHAT_TABLE`, `CONDITION_REPORTS_TABLE`, `CHAT_RATE_LIMIT_TABLE_NAME`. Weather processor and worker were missing `DAILY_HISTORY_TABLE`. Every deploy silently reverted these to defaults (non-existent dev tables), breaking history writes and chat persistence. Fixed all three Lambda configurations in deploy.yml.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Web history page API response mismatch
Web `HistoryResponse` type expected `days[]` + `season_total_cm` but API returns `history[]` + `season_summary`. Web `HistoryDay` used `snowfall_cm`/`min_temp_c`/`max_temp_c` but API uses `snowfall_24h_cm`/`temp_min_c`/`temp_max_c`. Fixed types.ts, ResortDetailPage.tsx, and ForecastChart.tsx to match actual API response. Web history tab was completely broken before this fix.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | n/a |

### Feature: Android & Web cross-platform feature parity batch
Major cross-platform update implementing 20+ pending features:
**Android (Models.kt, Color.kt, CountryFlags.kt, ResortMapScreen.kt, ResortDetailScreen.kt, ChatScreen.kt):**
- Expanded SnowQuality enum from 6 to 13 values (champagne_powder through unknown) with distinct colors
- Compound region key display ("na_west_BC" -> "NA West Coast (British Columbia)")
- Asia (KR, CN) and Eastern Europe (PL, CZ, SK, RO, BG) region support
- Map style switching (Standard/Satellite/Terrain) with dropdown toggle
- Map initial zoom defaults to NA Rockies instead of Alps
- Trail map link card in resort detail (opens browser)
- Elevation range display in resort header (base - top with unit prefs)
- Enhanced ElevationPicker showing elevation values per level
- Enhanced share text with conditions data (temp, fresh, depth, forecast)
- 16 randomized chat suggestions (pool of 16, shows 4 per visit)
- Markdown rendering in chat (bold, italic, headers, lists)
- Tool call XML stripping in chat messages
- Country name lookup for 25 countries including new regions
- Updated all map marker hues for 10-level quality scale
- 12 new unit tests for compound keys and regions
**Web (types.ts, colors.ts, format.ts, ResortDetailPage.tsx, QualityBadge.tsx, ConditionsTable.tsx, ResortCard.tsx):**
- 13-level SnowQuality type with distinct color palette
- formatQuality labels for all 13 quality levels
- Compound region key display in resort cards and detail page
- Trail map link in resort header
- TrailDistribution component with stacked bar chart
- Predicted snowfall (48h forecast) column in ConditionsTable
- Enhanced QualityBadge with prominent score in lg size
- Region display uses regionDisplayName everywhere
All 187 Android tasks passing, web TypeScript clean.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | done | done | n/a |

### Feature: Resort data enrichment — city, webcam URLs, price audit
Four-part resort data enrichment: (1) **Price audit**: Verified and corrected day ticket prices for 65+ resorts (e.g., Whistler was $66, now $175-260 USD; Vail $189-356). Created `enrich_resort_data.py` with 90+ manually verified 2025/26 prices. (2) **City geocoding**: Added `city` and `state_province` fields to 955/1040 resorts (91%) via Nominatim reverse geocoding + 90 manual overrides. iOS `displayLocation` now shows "Big White, Kelowna, BC, Canada" instead of "British Columbia, Canada". (3) **Webcam URLs**: Added `webcam_url` to all 1040 resorts (skiresort.info webcam pages). iOS detail view shows "Webcams" link opening in-app Safari overlay. (4) **Safari overlay**: Added `IdentifiableURL`, `SafariView`, and `.safariOverlay()` modifier so website, trail map, and webcam links open in embedded SFSafariViewController instead of leaving the app. Backend model, populate script, iOS model/cache/demo data all updated. 1563 backend + 119 iOS tests passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | done |

### Fix: Table column alignment in AI chat markdown renderer
Tables with alternating row colors had misaligned columns because each row's HStack was laid out independently in a VStack. Fixed by: (1) computing an explicit `totalWidth` from column widths + separator widths, (2) applying `.frame(width: totalWidth)` to every row HStack and the container VStack, (3) extracting a shared `tableRow()` builder so header and data rows use identical layout code, (4) adding explicit widths to inter-row separator lines. All columns now align perfectly across all rows.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Chat history not loading end-to-end in iOS app
Backend was fixed (Float->Decimal), but iOS app had multiple UX issues preventing history from working properly: (1) ConversationListView swallowed errors silently — if loading failed, user just saw "No Conversations" with no retry option. Added dedicated `isLoadingConversations` and `conversationListError` states with error display and retry button. (2) Tapping a conversation dismissed the sheet immediately before the load completed, so messages appeared with no feedback. Now waits for the API call to finish (with per-row spinner) before dismissing. (3) Main chat view showed empty suggestions when `isLoading` was true during conversation load. Now shows a centered "Loading conversation..." spinner. (4) Added cleanup of streaming state before loading historical conversations to prevent stale data.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Verified: 16 diverse chat suggestions already in place
Confirmed 16 ChatSuggestion entries covering: proximity-based, budget, resort comparisons, regional (Rockies/Alps/Japan), family-friendly, pass-based (Ikon/Epic), forecasts, hidden gems, snowpack, and temperature queries. No changes needed.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Snow history empty — DAILY_HISTORY_TABLE env var missing from Lambda functions
Root cause (again): `DAILY_HISTORY_TABLE` env var was not present on the weather worker, weather processor, or API handler Lambda functions in prod and staging. Despite being defined in Pulumi infrastructure code, the infra was never deployed after adding it. Weather worker defaulted to `snow-tracker-daily-history-dev` (which doesn't exist), so all history writes silently failed. Also missing: `SNOW_SUMMARY_TABLE` on API handler, `SNOW_SUMMARY_TABLE` on weather processor Pulumi config. Fixed: set env vars on all 6 Lambda functions (3 prod + 3 staging) via AWS CLI, updated Pulumi infra to include `SNOW_SUMMARY_TABLE` for weather processor, weather worker, and API handler. Triggered weather processor to backfill data. Table went from 122 to 1066+ records.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Debug notification testing returns "debug features not available" on TestFlight
Debug endpoints (`/api/v1/debug/test-push-notification` and `/api/v1/debug/trigger-notifications`) blocked ALL production requests with HTTP 403. TestFlight builds use the production API (not staging), so admin users testing via TestFlight always got blocked. Fix: added admin user identification via SHA256 email hash check (same hash list as iOS `Configuration.swift`). Admin users can now access debug endpoints in production. Also fixed test notification using `APNS_SANDBOX` in prod (should be `APNS` for production push certificates). Added 7 new tests for debug endpoint access control. Total: 1563 backend tests passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Data sources moved to bottom, shows excluded sources with reasons
Data sources card moved from inline (between conditions cards) to the very bottom of resort detail view. Backend now includes all 4 known sources (Open-Meteo, OnTheSnow, Snow-Forecast, WeatherKit) in `source_details` even when a source has no data for the resort (status: `no_data`). Sources sorted by status: consensus first, then included, outlier, unavailable. Excluded outlier values shown with strikethrough and orange reason text. Unavailable sources shown as greyed "N/A".
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | backlog | n/a | done |

---

## Feb 25, 2026

### Fix: Chat messages not persisting (Float→Decimal DynamoDB error)
Chat stream handler was saving tool_calls data containing Python floats (resort coordinates, temperatures, snowfall amounts) directly to DynamoDB, which rejects float types. Added `_convert_floats()` to recursively convert floats to Decimal before `put_item()`. This was the actual root cause of chat history appearing empty — assistant messages with tool results silently failed to save.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Randomized chat suggestion rotation (4 of 16)
Expanded AI chat from 4 hardcoded suggestion chips to a pool of 16 diverse prompts (compare resorts, find powder, budget trips, regional conditions, pass comparisons). Shows 4 randomly selected on each visit. Suggestions include specific resort comparisons, Ikon/Epic pass queries, Japan conditions, hidden gems, and budget filters.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Markdown table column widths content-based
Tables used uniform column widths, making wide tables poorly formatted. Changed to per-column content-based width calculation: `max(60, min(220, charCount * 7 + 20))` per column. Headers and data cells are measured independently. Results in compact columns for short data and wider columns for long text.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Feature: Per-source reason text in data source transparency
Added `reason` field to source details showing why each source was included/excluded (e.g., "Reported 5cm, 67% from median 3cm — excluded as outlier (>50%)" or "Within 12% of each other (threshold: 30%)"). Backend includes human-readable reasons with median values, deviation percentages, and thresholds. iOS displays reason text below each source row.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | backlog | n/a | done |

### Fix: Map style switching broken — always shows satellite
`String(describing: MapStyle)` no longer produces reliable output for comparison in newer Xcode. Replaced with custom `MapDisplayStyle` enum that maps directly to `MKMapType` values. Standard/Satellite/Hybrid toggle now works correctly. Android: added `MapDisplayStyle` enum with Standard/Satellite/Terrain options and Layers dropdown toggle.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Forecast mode on map spins forever / loads very slowly
Timeline data was fetched one-resort-at-a-time in sequential batches of 10. For 1000+ resorts, this meant 100+ sequential API batches. Fixed: batch size increased from 10→30 parallel requests, limited to 150 resorts max, and map pins update progressively after each batch instead of waiting for all to complete.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Feature: Data source transparency — show which sources contributed to each score
Users can now see which of the 4 weather sources (Open-Meteo, OnTheSnow, Snow-Forecast, WeatherKit) contributed to each snowfall reading, which were in consensus, and which were dropped as outliers. Backend `merge()` returns `source_details` with per-source snowfall values, status (consensus/outlier), merge method, and source count. iOS shows collapsible "Data Sources" card in resort detail with color-coded status per source. 8 new backend tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | backlog | n/a | done |

### Fix: Community report TTL 365→90 days
Reports were kept for a full year; reduced to 90 days to keep community data fresh and relevant.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Community report timestamp nearly invisible
Report timestamps used `.tertiary` foreground style (nearly invisible on light backgrounds). Changed to `.secondary` for better readability.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Chat history always empty on iOS
`list_conversations()` queried non-existent DynamoDB GSI "UserIndex" — the actual index name is "user_id-index". One-line fix.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feature: Markdown table rendering in AI chat
AI chat responses now render markdown tables with proper header styling, column dividers, and horizontal scrolling for wide tables. Added full table parsing to MarkdownTextView (pipe-delimited `| col | col |` syntax). Android: added MarkdownText composable with bold/italic/header/list/table-separator support via AnnotatedString.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Feature: Interactive resort card carousel in AI chat
When the AI recommends specific resorts, it embeds `[[resort:resort-id]]` markers that iOS renders as tappable resort cards in a horizontal carousel. Cards show quality badge (color-coded), resort name, fresh snow, temperature, snow depth, and country. Tapping opens the full resort detail sheet. Backend system prompt updated to instruct AI to use card markers.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Fix: Viewport-based forecast loading on map
Removed arbitrary 150-resort limit for forecast fetching. Now tracks the current visible map region and only fetches timelines for resorts visible in the viewport. Re-fetches when user pans/zooms to a new area.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Feature: Updated AI chat prompt suggestions
Replaced generic chat suggestions with practical examples: "Best snow within 500 miles", "Cheap resorts within 6h drive", "Non-Epic resorts under $150/day", "Compare Whistler vs Jackson Hole".
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Fix: Raw JSON tool calls visible in AI chat
AI sometimes hallucinated `<tool_call>`/`<tool_response>` XML blocks in text responses instead of using native tool_use. Fixed: (1) iOS strips these blocks before rendering, (2) backend system prompt now explicitly forbids raw JSON in responses, (3) intermediate "thinking" messages hidden from display. Android: added `stripToolCalls()` regex to remove XML blocks before rendering.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | done |

### Feature: Rich resort cards in AI chat carousel
Overhauled resort cards from basic name+stats to visually rich cards: quality gradient header with snow score (0-100), SF Symbol quality icon, trail difficulty bar (green/blue/black/double-black proportional), lift ticket price range, pass badges (Epic/Ikon/Indy), temperature/snow/depth stats, country/region display. Cards expand to full resort detail on tap.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Fix: Improved markdown table rendering
Better column sizing (auto-calculated based on column count), alternating row backgrounds, cleaner dividers, proper padding. Tables are horizontally scrollable with rounded corners.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Feature: Enriched nearby resorts data in chat
`get_nearby_resorts` tool in stream handler now returns pricing, pass affiliations, and current conditions inline — avoids needing a second `get_resort_details_batch` call. Faster responses for "resorts near me" queries.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

## Feb 26, 2026

### Fix: Replace weighted-average merge with outlier detection + majority consensus
Open-Meteo=0cm + OTS=3cm + SF=3cm used to produce 1.3cm (weighted avg). Now: outlier detection via median — Open-Meteo's 0 is >50% from median 3, gets dropped, consensus {3,3} averages to 3.0cm. Two-source disagreements still fall back to weighted average. 33 tests (8 new for outlier scenarios).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Timeline explanations — "gusts increase score" and "warming to -11°C worsens"
Two bugs in `generate_score_change_reason()`: (1) When no factor aligned with score direction, fallback picked dominant factor regardless, creating nonsensical explanations like "gusts up to 48km/h improves conditions". Fixed by falling through to generic message when no aligned factor exists. (2) Sub-zero warming (e.g. -15→-11°C) blamed for score drops via `temp_delta > 2 and not improving`. Added `cur_temp > -3` guard — only attribute warming when near/above freezing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix: Timeline popover text overflow
Explanation text in conditions timeline popover was cut off due to narrow `maxWidth: 260`. Widened to 320pt.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Fix: WeatherKit 401 "NOT_ENABLED" → all 4 sources working
Root cause: JWT `sub` claim used App ID (`com.wouterdevriendt.snowtracker`) instead of Services ID. WeatherKit REST API requires a registered Services ID. Fix: created Services ID `com.wouterdevriendt.snowtracker.weatherkit` in Apple Developer Portal, updated `WEATHERKIT_SERVICE_ID` GitHub secret. Now all 4 sources merge: `onthesnow.com + open-meteo.com + snowforecast.com + weatherkit.apple.com`. Created `/weatherkit-debug` skill with full troubleshooting guide.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 25, 2026

### iOS: UI test framework with accessibility identifiers
Added `AccessibilityIdentifiers.swift` — centralized enum of stable test IDs shared between app and UI tests. Added `.accessibilityIdentifier()` to key views (WelcomeView, MainTabView chat FAB, ChatView inputs/buttons, ResortDetailView toolbar). Created `UITestHelpers.swift` with `TestID` mirrored constants, `XCUIApplication`/`XCUIElement` extensions (`waitToExist`, `waitAndTap`, `navigateToTab`, `openChat`, `takeScreenshot`). New `SmokeTests.swift` — 8 quick tests covering resort list, detail, all tabs, map, chat send, settings, regressions, data source. Created `/test-ui` skill for easy invocation. All 8 smoke tests passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Feature: Multi-source weather data (Snow-Forecast + WeatherKit + MultiSourceMerger)
Open-Meteo missed 3cm snowfall at Big White on Feb 24 (all 4 models showed 0.0cm). Added 3 supplementary data sources with weighted averaging to catch what grid models miss:
- **Snow-Forecast scraper** (`snowforecast_scraper.py`): Scrapes snow-forecast.com for 3300+ resorts. Auto-generates URL slugs with override file. Runs as prefetch Lambda every 6 hours, writes cache to S3.
- **Apple WeatherKit** (`weatherkit_service.py`): ES256 JWT auth, fetches currentWeather + forecastHourly, converts SWE to snowfall. Called inline (~200ms) per resort.
- **MultiSourceMerger** (`multi_source_merger.py`): Replaces inline 70/30 OnTheSnow merge. Normalized weighted average (Open-Meteo 0.50, OnTheSnow 0.25, Snow-Forecast 0.15, WeatherKit 0.10). Priority-based snow depth (resort-reported > model). Confidence: 3+ sources = HIGH.
- Infrastructure: Prefetch Lambda (512MB/900s) + CloudWatch 6hr schedule. Feature flags: `ENABLE_SNOWFORECAST`, `ENABLE_WEATHERKIT` (both default off).
- 149 new tests (1539 total), all passing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Score: Fix list/detail vs timeline score mismatch
Batch/summary scores used weighted average across all elevations (50% top + 35% mid + 15% base) while timeline showed single mid-elevation score. Changed batch/summary to use representative elevation (mid > top > base), matching timeline default and explanation text. Big White went from showing 61 in list but 66 in timeline to consistent scores.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Timeline: Improve score change reason explanations
Many timeline entries showed generic "Conditions declining (-7 pts)" without explaining the specific cause. Rewrote `generate_score_change_reason()` with: lowered thresholds (wind delta 5km/h, temp 2C, snowfall 0.5cm, depth -5cm), new patterns (snow aging, daytime warming, overnight cooling, absolute high wind), smart fallback that identifies the largest changing factor instead of generic message. Fixed contradictory messages (e.g., "Visibility improving worsens conditions") by tracking factor directionality and preferring aligned factors. Added minimum wind thresholds so calm wind isn't cited. Added 9 new tests (74 total).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Map: Fix clustering breaking when panning between regions
Clustering broke when zooming out, panning to Europe, zooming in/out, going to Asia. Root cause: individual removeAnnotation/addAnnotation calls during quality updates confused MKMapView's clustering engine. Fixed by batching all add/remove operations into single calls and re-setting clusteringIdentifier on configure() to survive view reuse.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Fix: Southern hemisphere resorts showing score 10 in summer
Resorts like La Hoya (AR) showed score 10 "Bad" at 17°C with 0 snow depth — should be score 0 "Not Skiable". Added summer override: when temp >= 10°C with no snow depth and no fresh snowfall, both ML and heuristic scorers now return HORRIBLE (score 0). Affects all southern hemisphere resorts (AR, CL, NZ, AU) during off-season.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Map: Forecast time slider updates all annotation pins
When selecting a future day in the date selector, all map pins now update to show predicted quality for that day — not just the 5 nearby resort cards. Moved date selector above nearby carousel so it's always visible. Added forecast banner and loading indicator. Timeline fetches batched (10 concurrent) with session caching. Region changes also fetch timelines when in forecast mode.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Timeline: Temperature-aware snow depth smoothing
Open-Meteo's forecast snow depth model predicted unrealistic snowpack collapse (e.g. 144cm → 11cm in 4 days at sub-zero temps). Replaced flat max-drop-per-hour with temperature-aware melt rates: 3cm/day sub-zero, 15cm/day above-zero. Three-pass smoothing: find last observed, consecutive pair smoothing with temperature, forecast floor clamping. 13 new tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Timeline: Score change delta explanations
When viewing the 7-day forecast timeline, each point now shows WHY the score changed vs the previous period. E.g., "Fresh snow +5cm", "Warming to 3°C softens snow", "Refreezing creates icy conditions". Uses `generate_score_change_reason()` comparing consecutive timeline points. Shows colored delta arrows (green up, red down) with compact keyword, full reason in popover.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### List View: Fix region display showing internal keys
Resort list showed raw internal region keys like "na_west_BC" instead of human-readable names. Root cause: `regionDisplayName` only matched exact internal keys ("na_west") but API returns compound keys ("na_west_BC"). Fixed by parsing compound keys: extract suffix after known prefix, look up in US state / Canadian province dictionaries. Non-NA compound keys (alps_FR) return empty (show country only). Added comprehensive test coverage for all compound key patterns.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Timeline: Smooth ML score jumps from snow depth artifacts
Open-Meteo snow depth can make unrealistic jumps (e.g., +8cm overnight with 0.1cm snowfall), causing ML score jumps of +19 points. Added pre-ML hourly snow depth smoothing that caps increases at snowfall*1.5+0.5cm/hr and decreases at temperature-aware melt rates. Also added post-scoring smoothing to cap step-to-step score changes. 10 new tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Weather Processor: Fix 576 grey resorts
876 non-NA resorts had empty `region` in DynamoDB because `populate_resorts.py` used `state_province` (only set for NA). Weather processor grouped all 876 into a single Lambda worker that timed out at 600s. Fixed: use `region` from resorts.json (alps, scandinavia, etc.) with `state_province` suffix for NA. Added chunking in weather processor (max 100 per worker). Re-populated DynamoDB, triggered weather processor.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Map: Add Asia and Eastern Europe regions
iOS was missing Asia (KR, CN) and Eastern Europe (PL, CZ, SK, RO, BG) from SkiRegion enum, map presets, filter settings, and onboarding. Backend had 66 + 222 resorts in these regions. Also fixed Alps countries to include SI, ES, AD. Android: added asia/eastern_europe to inferRegion, regionDisplayName, and country name lookups with tests. Web: added asia/eastern_europe to regionDisplayName and format.ts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Map: Auto-refresh quality on region change
Map only fetched conditions once on appear. Panning/zooming to new areas showed grey pins. Added debounced (1.5s) auto-fetch on viewport change, plus manual reload button (arrow.clockwise) in toolbar. Only fetches uncached resorts in batches of 30.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Research: Alternative weather data sources
Comprehensive evaluation of 10 weather APIs. Top recommendations:
- **Weather Unlocked** ($220-420/mo): per-elevation (base/mid/top) forecasts for 850+ resorts
- **Synoptic Data / SNOTEL** (FREE): actual station snow depth observations for US resorts
- **Tomorrow.io** (FREE tier): worth testing their snow depth model
- Apple WeatherKit: marginal value (no snow depth, no per-elevation)
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | backlog |

---

## Feb 24, 2026

### Map: Add Region menu accessibility label
Globe menu button in map toolbar had no accessibility label, making it invisible to XCUI tests. Added `.accessibilityLabel("Region")`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Map: Region switching UI test
Added `testMapView_RegionSwitching` that navigates Alps → Japan → Rockies via the Region menu, taking screenshots at each stop. Previous zoom test failed because XCUI pinch gesture on MKMapView extends into tab bar area.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Chat: Add get_resort_details_batch to streaming handler
The `get_resort_details_batch` tool was defined in `chat_service.py` but missing from `chat_stream_handler.py`. AI streaming would hit "Unknown tool" errors when trying batch lookups.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Split thinking messages into separate bubbles
When AI uses tools, intermediate text ("Now let me check...") was concatenated with the final response into one giant message. Now split at tool boundaries into separate italic bubbles.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Chat: Fix conversation history not loading
Backend returns ISO 8601 date strings but iOS JSONDecoder expected Double, causing decode failures. Added custom `init(from:)` with ISO 8601 parsing for ChatMessage and ChatConversation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Map: Proactive condition fetching for visible resorts
Map annotations showed stale quality data from S3 batch JSON. Only updated when individually tapped. Now fetches full conditions for all visible resorts in background on map appear.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Map: Add yellow segment to cluster pie chart
"Decent" quality (yellow) was grouped with mediocre/poor (orange) in cluster pie charts. Added 5th segment for yellow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Fresh Powder Chart: Fix axes and freeze line
- Removed confusing combined "°C / cm" Y-axis label, added proper legend with color-coded items
- Renamed "Last freeze" annotation to "Crust formed" (matches actual semantics of `lastFreezeThawHoursAgo`)
- Subtitle now says "since last thaw" not "since last freeze"
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Quality Labels: Expand from 6 to 10 levels
New scale: Horrible, Bad, Poor, Mediocre, Decent, Good, Great, Excellent, Powder Day, Champagne Powder. With distinct colors and icons. Android: expanded SnowQuality enum with all 13 values, updated Color.kt with distinct colors, map markers, and tests. Web: expanded SnowQuality type, qualityColors, and formatQuality labels.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Trail Distribution: Fix missing data for Big White and others
Trail percentages (green/blue/black runs) weren't passed through the API transform. Fixed `_transform_resort()` passthrough. Web: added TrailDistribution component with stacked bar and labels on resort detail page.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### ML Model v14-v15: Physics-based scoring overhaul
v14 added `hours_since_last_snowfall` feature, removed manual hacks (aging penalty, cold boost, smoothing). v15 added physics-based audit of training data, expanded eval suite (64 edge cases, 14 constraints), targeted synthetic data. Cold+dry now correctly scores POOR not FAIR.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Pull-to-refresh: Fix hang and slow refresh
DynamoDB `Limit=1` was too small with filter expressions. Changed to `Limit=15` with parallel fetch. Then further optimized to only refresh summaries (not full conditions). Fixed spinner stuck by preventing re-render during refresh with explicit yield.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Score Recalibration: Piecewise-linear mapping
`score_to_100` was non-linear and unfair at boundaries. Replaced with piecewise-linear mapping for more intuitive 0-100 scores.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Condition Reports: Backend/iOS model mismatch
Backend response fields didn't match iOS Codable model. Aligned response format.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Chat: Fix IAM streaming permissions, batch tools, guest auth
Chat stream Lambda lacked `lambda:InvokeFunction` permission. Added `get_resort_details_batch` tool. Fixed guest auth for anonymous chat. Fixed empty bubbles appearing on tool calls.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | done |

### Forecast Score Stability
Forecast scores were jittering due to freeze-thaw state changes. Added freeze-thaw guard, aging penalty damping, and score smoothing across timeline days.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 23, 2026

### Map: Grey screen on first annotation tap
`sheet(isPresented:)` race condition caused empty sheet on first tap. Changed to `sheet(item:)` pattern.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Map: Initial zoom showing entire world
1040 resorts scattered globally looked bad. Default to NA Rockies region, user location when available. Android: changed default camera to LatLng(40.6, -111.5) zoom 5f (Rockies area).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Chat: JWT import crash in streaming Lambda
`ModuleNotFoundError: No module named 'jwt'` — changed to `from jose import jwt`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Ignoring "best powder" questions
System prompt didn't instruct to use `get_best_conditions` tool. AI asked for location instead of answering.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### ML Scorer: Missing wind/visibility features
`extract_features_from_condition()` missing visibility_m, min_visibility_24h_m, max_wind_gust_24h. Scores were wrong.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Static JSON Generator: Connection pool exhaustion
Parallel workers (20) exhausted DynamoDB connection pool. Changed to sequential processing. 1040 resorts in 266s.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow History: Empty data
DAILY_HISTORY_TABLE env var missing from prod API Lambda (defaulted to dev table).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### List View: Slow loading
Quality fetch limited to 300 resorts. Increased to 2000 (all resorts). Added progressive batch loading.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Map: Batch quality chunking
Android sent all 1040 resort IDs in one request. Split into chunks.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | done | n/a | n/a |

### Wind/Visibility: Explanation text improvement
"Windy (30 km/h)" → "30 km/h wind decreases the score" with actual impact shown.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Big White: Incorrect Epic Pass badge
Incorrectly tagged as Epic Pass resort. Removed.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Resort Data: 862 resorts with (0,0) coordinates
Geocoded all resorts. Fixed 4 country misattributions (2 Austrian→US, 2 Italian→FR).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Wind Gust & Visibility UI
Added wind gust, max gust 24h, visibility with color-coded severity to resort detail.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### ML Model v13: Wind gust and visibility features
Retrained with 37 features (up from 34) including visibility_km, min_visibility_24h_km, max_wind_gust_norm. 11,960 samples from 134 resorts. MAE=0.265, R²=0.880.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Resort Database: Expand from 138 to 1040 resorts
Added resorts across 25 countries via enrichment scripts. Scraped prices, pass affiliations, and labels from skiresort.info.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Data Quality: Massive enrichment pass
Enriched run percentages (2.8%→93.8%), website URLs (13.2%→85.4%), annual snowfall (446 resorts), base elevations (95.6%), top elevations (86.8%). Fixed 459 corrupted elevation values from scraper artifacts. Nulled 252 bad elevations exceeding country maximums.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS Certificate Cleanup
Added automatic certificate cleanup step to iOS build workflow. Revokes excess dev certs via ASC API before archive to prevent hitting Apple's cert limit.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Parallel Batch Quality Fetch
Map quality fetch parallelized for faster loading. Fixed map clustering bugs. Added chat location awareness.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

---

## Feb 22, 2026

### Live Activities & Dynamic Island
Real-time resort conditions on lock screen.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Chat: compare_resorts crash
Tool crashed on missing data. Added error handling and missing API fields.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Weekly Digest: Double-counting forecast snow
Cumulative forecast snowfall was double-counted in digest calculation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### VoiceOver Accessibility
Added accessibility labels to condition reports, elevation profiles, quality badges, season stats, snow history chart.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Batch Endpoint Timeouts
Fixed timeout and None safety in recommendations and batch quality endpoints.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Streaming Chat with SSE
Added Server-Sent Events streaming for AI chat via Lambda Function URL + Web Adapter. Tool tracing shows what AI is doing in real-time. Required multiple Lambda permission and wrapper fixes.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | done | done |

### Android App: Initial release
Full Android app in Kotlin + Jetpack Compose. Resort list, map, favorites, detail view, conditions. Material 3, Room database, Hilt DI.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | done | n/a | n/a |

### React Web App
Built web app at app.powderchaserapp.com with resort browsing, geolocation nearby resorts, favorites, and anonymous AI chat.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | n/a |

### Chat: Harden API with retry and validation
Added retry with exponential backoff for Bedrock calls, input length validation, larger conversation context window.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Fix timeouts with pre-fetched data
Chat was timing out because Bedrock tool_use calls were slow. Pre-fetch resort data before calling Bedrock, skip redundant tool invocations. Increased Lambda timeout.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow Scores in Widgets
Added ML snow scores (0-100) to home screen widgets. Large widget now shows 5 resorts instead of 3.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Favorites: Conditions summary card
Added summary card to favorites view showing best conditions, storms incoming section, and forecast badges for upcoming snow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Storm Badge on Favorites Tab
Tab icon shows storm badge when significant snowfall (10+ cm) is predicted for any favorited resort.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Resort Search: Country codes and pass types
Search now matches "CA" for Canada, "Epic" for Epic Pass resorts, etc.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Share Text: Snow score, depth, and forecast
Share card now includes snow score, current depth, and forecast data instead of just resort name. Android: enhanced share text to include temperature, fresh snow, depth, 48h forecast alongside quality and score.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### Batch Quality: Snow depth and forecast data
Added snow_depth_cm, forecast_snowfall_cm to batch quality response so list/map views show depth and forecast without individual API calls.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Sort Options: Snow Depth and Predicted Snow
Added new sort options to resort list for sorting by current snow depth or predicted incoming snowfall.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Chat: Markdown rendering
AI chat responses now render markdown (bold, italic, lists, links, code) instead of plain text. Android: added MarkdownText composable with bold (**), italic (*), headers (#), bullet lists, and table separator handling via AnnotatedString.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Chat: Snow history and comparison tools
Added `get_snow_history` and `compare_resorts` tools so AI can answer historical questions and compare resorts side-by-side.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Condition reports tool
AI chat can now access user-submitted condition reports for on-the-ground context when answering questions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Epic/Ikon Pass Filter
Added pass type filter to resort list. Pass badges shown on list and favorites views.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Elevation Display: Unit preferences
Elevation displays now respect user unit preferences (meters vs feet) everywhere in the app. Android: added elevation range to resort header card using formatElevation, enhanced ElevationPicker to show elevation values alongside level names.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | n/a | n/a |

### DynamoDB Backups and Missing API Routes
Enabled point-in-time recovery on all DynamoDB tables. Added missing API Gateway routes for regions, auth, trips, snow-quality, events, and notification endpoints.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Auth fix and 16 new resorts
Fixed chat authentication bug. Added 16 Scandinavian and Alps resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Extract shared ELEVATION_WEIGHTS constant
Elevation weighting (50% top + 35% mid + 15% base) was defined in multiple files with risk of drift. Extracted to shared constant.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Branding: Rename to Powder Chaser
App renamed from "Snow Tracker" to "Powder Chaser" with updated marketing materials, About view, and documentation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

---

## Feb 21, 2026

### AI Chat, Condition Reports, Offline Mode, Weekly Digest
Major feature drop: AI chat with Claude Sonnet 4.6 via Bedrock (with tool use for resort lookups, comparisons), user-submitted condition reports, offline mode with aggressive caching, weekly snow digest, floating chat bubble, gradient weather backgrounds.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | backlog | backlog | done |

### Production Crash: Missing python-ulid
Lambda crashed on first condition report submission — `python-ulid` not in requirements.txt.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Bedrock model ID issues
Wrong model ID format caused Bedrock access errors. Tried Claude 3.5 Sonnet v2, Sonnet 4, then back to Sonnet 4.6 after user fixed Bedrock access. Must use inference profile IDs like `us.anthropic.claude-sonnet-4-6`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### List View Hang
List view hung on main thread due to synchronous DynamoDB batch calls during scroll. Fixed with async dispatch and reduced API calls from 21 to 2 per refresh.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Trail Maps and Run Difficulty
Added trail map links and run difficulty percentage breakdown (green/blue/black) to resort detail view. Required populating trail data for all resorts. Android: added trail map link card (opens in browser) and RunDifficultyCard already existed. Web: added trail map link in header, TrailDistribution bar component.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Elevation Profile Redesign
Redesigned elevation profile visualization to look like a mountain shape instead of flat bars.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Epic/Ikon Pass Badges
Added Epic and Ikon pass badges to resort detail, list, and favorites views. Fixed Apple Sign In email preservation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Elevation Consistency Bug
Explanation text temperature didn't match the `temperature_c` field because they used different elevation preferences. Fixed to use same elevation (prefer mid > top > base).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Recommendations: Tiny resorts favored over major ones
Global recommendations scoring favored tiny resorts with marginally higher scores. Added size weighting to prefer well-known resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Chat: Auto-suggest resort detection
Chat now detects resort names in user messages and offers quick-tap suggestions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Batch Quality: Elevation mismatch
Batch endpoint used different elevation than detail endpoint for overall quality. Aligned to weighted average (50/35/15).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### ML Model v10-v11: Real data only
Dropped historical data from training, using only real-world scored data + synthetic edge cases. v11: 2181 samples, improved accuracy.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Explanation Text: Wrong elevation temperature
Explanation text was using top-elevation temperature instead of mid-elevation (which is what `temperature_c` shows). Fixed in `quality_explanation_service.py`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Unit Preferences: Multiple hardcoded spots
ForecastBadge hardcoded "cm", notification thresholds showed cm regardless of preference, skeleton loader used wrong units, timeline wind speed was hardcoded. Fixed all to respect user preferences.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Overall Quality: Weighted raw scores
Overall quality was computing from quality labels (discrete) instead of raw scores (continuous), causing information loss. Fixed to use weighted raw score averaging. Applied same fix to static JSON generator and recommendations.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### ML Model v8-v9: Deep snow and aging
v8: retrained with accumulated snow and cold temperature scenarios. v9: added snow_depth as ML feature. Post-ML aging penalty for old snow. Improved heuristic scorer for deep unrefrozen snow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Quality Explanation: User-friendly language
Replaced technical jargon ("freeze-thaw cycle", "accumulation") with plain English. Made explanations more conversational.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Conditions Endpoint: Returning 50 entries
Conditions query was returning too many entries per resort due to missing elevation filter. Added proper elevation-specific query.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Duplicate Resorts
Found and removed duplicate resort entries in the database. Added chat aliases so queries for old names still work.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Backend: Falsy value check bug
`if not value` was treating `0` and `0.0` as missing data, causing incorrect fallbacks. Changed to `if value is None`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### 483 new tests
Added comprehensive test coverage: 65 ml_scorer tests, 60 notification_service tests, 39 snow_summary_service tests, 205 api_handler/cache/resort_loader tests, 213 scraper/consolidator/weather tests.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS Certificate Management
Replaced cert revocation approach with stored signing certificate import from GitHub Secrets. Prevents hitting Apple's cert creation limits on CI.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Snowfall Consistency Check
Open-Meteo cumulative snowfall window was inconsistent between processor and worker. Added consistency check that runs after scraper data merge.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS Code Quality: Zero warnings build
Replaced all deprecated `.foregroundColor` with `.foregroundStyle`, `.cornerRadius` with `.clipShape(RoundedRectangle)`. Extracted `.cardStyle()` modifier. Made all DateFormatters static. Added haptic feedback. Zero compiler warnings achieved.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Rename to Powder Chaser v1.1
App renamed from "Snow Tracker" to "Powder Chaser". Updated all marketing materials, website, and About view.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | n/a |

### Map Cluster: Snow quality display fix
Map cluster pie charts showed wrong quality distribution. Temperature-aware explanations were using wrong elevation. Fixed both.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Auto-bypass auth in screenshot mode
Screenshot and demo modes now auto-bypass authentication and onboarding for automated testing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Timeline: Snow depth smoothing
Timeline snow depth was dropping too fast (10cm/h melt rate). Lowered to 2cm/h for more realistic visualization.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow Score (0-100) and Quality Explanations
Added human-readable 0-100 snow score alongside quality label. Explanations describe what's driving the score (fresh snow, temperature, wind, etc.). Added to static JSON generator. Web: enhanced QualityBadge lg size with prominent score display above label.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | done | done | done |

### Cap fresh_snow_cm at snow_depth_cm
API could return `fresh_snow_cm: 20, snow_depth_cm: 5` — contradictory. Capped fresh snow at depth.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 20, 2026

### Snow Conditions Timeline View
7-day forecast timeline showing snow quality, temperature, snowfall, and wind for each day at each elevation. With explanations and score info popovers.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | pending | done |

### ML-based Snow Quality Scoring (v2-v7)
Replaced heuristic scoring with neural network ensemble. v2: initial neural net. v3: synthetic edge cases. v5: ensemble of 5 models + deterministic labels (87.4% exact). v6: 10-model ensemble (93.6% exact). v7: retrained on corrected elevation data.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Fix Snow Quality Algorithm: Source confidence bias
Heuristic scorer had a bias based on data source (scraped vs. API). Scores varied depending on where the data came from rather than actual conditions. Removed the bias.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Batch Endpoint: Thread contention
ML model inference with 10-model ensemble caused thread contention in batch endpoint. Optimized with pre-loaded models and reduced lock contention.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Elevation Data: Fix 94 resorts
Critical weather accuracy fix — 94 resorts had wrong elevation data causing Open-Meteo to apply incorrect temperature lapse rates (~6.5 deg C per 1000m). Protected elevation data from future scraper overwrites.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### East Coast Resorts
Added 3 missing NA East resorts (Bretton Woods, Jay Peak, Loon Mountain). Fixed 12 wrong top elevations for existing na_east resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Notification Deep Linking and Thaw-Freeze Info
Push notification taps now deep link to the relevant resort. Added thaw-freeze info popover explaining how quality is calculated.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### ML Model for Timeline Predictions
Timeline quality predictions now use the ML model instead of heuristic scoring, matching what the current conditions endpoint uses.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Missing API Gateway Routes
Regions, auth, trips, snow-quality endpoints were returning "Missing Authentication Token" because API Gateway routes were not configured in Pulumi.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow-quality Endpoint Crash
Endpoint crashed when DynamoDB enum fields were stored as strings instead of enum values. Added `hasattr` guard for `.value` access.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Recommendations: Lambda OOM
Recommendations endpoint crashed with OOM on 512MB Lambda. Root cause: unpaginated GSI query loading all weather data. Fixed with ProjectionExpression and proper pagination. Had to alias reserved word `ttl`.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Recommendations: Scoring plateau
Logarithmic fresh snow scale caused scores to plateau after 10cm. Switched to linear scale for more differentiation between moderate and heavy snowfall.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Server-side Timeline Cache
Added 30-minute TTL cache for timeline endpoint. Prevents redundant weather calculations for frequently-requested resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS: Structured Logging
Replaced all `print()` statements with `os.Logger` in the iOS service layer. Backend also got structured logging with consistent format.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Map Detail Sheet: Missing data and pull-to-refresh
Map detail sheet showed no data on first open. Pull-to-refresh didn't actually refresh conditions. Added loading spinner.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Retrain ML Model: 1677 real-world samples
First major retrain with 13 days of real-world scored data. Improved accuracy on edge cases.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 19, 2026

### Add 80 Validated Resorts
Added 80 new resorts validated with correct coordinates and elevations. Fixed iOS batch performance. Removed daily scrape schedule (using manual trigger instead).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Remove CloudWatch Custom Metrics
Custom metrics were costing ~$50/month. Removed in favor of log-based monitoring.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS Build: Certificate management overhaul
Multiple attempts to fix iOS build certificate issues. Tried manual distribution signing, automatic signing with cert cleanup, inline ASC API signing. Final solution: stop creating new certs, reuse existing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Feb 17, 2026

### App Startup Performance
Instant cache loading for near-zero startup time. Snow quality display made consistent between list and detail views.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### iOS Build: Automatic provisioning profile download
Build archive was failing because provisioning profiles weren't being auto-downloaded. Enabled `-allowProvisioningUpdates` with ASC API auth.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Feb 15, 2026

### Snow Quality Cap: 1-2 inch fresh snow in cold temps
Quality was capped too aggressively for resorts with 1-2 inches of fresh snow in cold temperatures. Adjusted threshold.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 14, 2026

### API Custom Domain DNS Fix
Certificate validation DNS record conflicted with existing records. Added `allow_overwrite` to Pulumi cert validation record. Fixed pending Pulumi operations with stack export/import workaround.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Deployment Skills for Claude Agents
Added `/deploy-testflight` and `/deploy-backend` Claude agent skills for easier deployments.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | n/a |

---

## Feb 8, 2026

### Snow Quality: Smooth gradient for thin snow
Cliff-edge at 2.54cm (1 inch) caused quality to jump dramatically. Replaced with smooth gradient up to 5.08cm (2 inches).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 7, 2026

### Snow Quality: Icy label showing for fresh powder
Resorts with fresh snow were incorrectly labeled "Icy" because freeze-thaw detection thresholds were too aggressive. Fixed detection logic: "Icy" only when actually frozen, "Soft" when thawing.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Scraper: Regex parsing wrong numbers as snow depth
Snow depth scraper regex matched unrelated numbers on the page (e.g., trail counts) as snow depth. Fixed regex to target correct elements.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 5, 2026

### Static JSON API: Pre-computed resort data
Added Lambda that generates static JSON file (~325KB) with all resort data + snow quality. Batch endpoint reads from S3 instead of DynamoDB — 200 resorts in 130ms (was 5+ seconds). Multiple Pulumi fixes for bucket configuration.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Resort Data Validation: Multi-batch audit
5-batch validation audit fixing resort elevations, coordinates, and data quality issues across the database. Fixed Sugar Bowl coordinates. Fixed Snoqualmie elevation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow Quality Labels: "Icy" only when frozen
Quality label was showing "Icy" for cold but not actually frozen conditions. Fixed to only show "Icy" when freeze-thaw cycle has occurred.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow Depth in API and Quality Calculation
Added `snow_depth_cm` to API response. Incorporated snow depth into quality calculation. Added display in iOS resort detail.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Fernie: Showing as non-skiable
Fernie was missing from the database or had bad data, showing as non-skiable in list view. Added resort and updated seeder.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### HORRIBLE Quality Threshold
Made HORRIBLE threshold more conservative — was triggering too easily for marginal conditions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 4, 2026

### API List Loading: Optimize for 10K+ resorts
List endpoint was slow with growing resort database. Added pagination, reduced response payload size, optimized DynamoDB queries.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### PolyForm Noncommercial License
Added open source license. Created comprehensive README. Set up Buy Me a Coffee. Removed GoogleService-Info.plist from repo (use template).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Feb 3, 2026

### Parallel Weather Processing
Implemented fan-out Lambda architecture: orchestrator invokes per-resort workers in parallel. Scaled from sequential (slow for 100+ resorts) to parallel processing of 1000+ resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Parallel Resort Scraper
Implemented orchestrator/worker pattern for resort scraping. Workers run per-country, results aggregated in S3. Added SNS notifications for newly discovered resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### East Coast Resorts (VT, NH, ME)
Added Vermont, New Hampshire, and Maine ski resorts to the database.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Localization: 13 languages
Added translations for French, German, Spanish, Italian, Japanese, Korean, Chinese (Simplified/Traditional), Portuguese, Dutch, Swedish, Norwegian, Finnish.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Marketing Website
Launched powderchaserapp.com with iPhone screenshots, proprietary algorithm marketing, and support page with contact form.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | n/a |

### Map: Pie chart clusters and warm temp fix
Added pie chart visualization to map resort clusters. Fixed warm temperature quality override logic. Fixed "Not Skiable" in batch endpoint.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Region Filter and Onboarding
Added region filter to iOS app. Region selection in onboarding flow. Fixed DynamoDB Decimal/float conversion issue.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Geo Indexing and Snow Summary
Added geohash indexing for location-based queries. Persistent snow summary tracking across weather updates.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Firebase Analytics
Comprehensive event tracking across iOS app: resort views, map interactions, favorites, chat, search, condition reports.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### App Store Preparation: v4.0.0
Fastlane automation for App Store submission. App icon generation. Review information. Automated Claude release notes. Export compliance. Hid Trips tab. Removed staging/prod selector from release UI.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Snow Accumulation Bug: 24h snowfall delta tracking
24h snowfall was using cumulative values instead of deltas, causing massive overreporting of fresh snow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Map Markers: Wrong elevation for snow quality
Map markers were using base elevation quality instead of the representative elevation (mid > top > base).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Push Notifications: False "removed" alerts
Core resorts were triggering "resort removed" SNS notifications when scraper temporarily couldn't find them. Added protection for core resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Feb 2, 2026

### Push Notifications Fix
Notifications weren't delivering. Fixed APNs configuration, EventTarget target_id length limit (max 64 chars), and resort versioning system.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Apple Sign In: Email preservation
Apple Sign In email was lost on fallback auth path. Fixed to preserve email throughout the auth flow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Map View: Snow quality icons not rendering
Map marker icons for snow quality were not displaying. Fixed rendering pipeline.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Near You: Increase search radius
Default "Near You" search radius was too small (200km). Increased to 1000km.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

---

## Feb 1, 2026

### Login UI Fixes
Fixed Google logo display, email display in profile, debug error handling. Removed auth requirement from notification endpoints. Fixed feedback API route validation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

---

## Jan 31, 2026

### Push Notifications and Fresh Snow Alerts
Added resort event notifications and fresh snow alerts via APNs. Required multiple infra fixes: SNS PlatformApplication attributes, API Gateway routes for events/notifications, missing Lambda env vars, APNs credential configuration, multiline private key handling.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### iOS Build Errors: Duplicate types and concurrency
iOS build broke due to duplicate type declarations and Swift 6 concurrency issues from notification feature additions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Jan 30, 2026

### Recommendations: API and caching fixes
Recommendations endpoint had multiple issues: batch query optimization, caching TTL too short, parallel DynamoDB queries, iOS decoding mismatches. Multiple rounds of fixes.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Firebase Analytics and Crashlytics
Integrated Firebase Analytics for usage tracking and Crashlytics for crash reporting.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### CI: Shared ios-infra workflows
Migrated iOS CI/CD workflows to shared `ios-infra` repository for reuse across projects. Added intelligent runner strategy with self-hosted fallback.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Jan 29, 2026

### Scraper Data Quality and DB Population Workflow
Fixed scraper data quality issues. Added GitHub Actions workflow to populate DynamoDB from resorts.json. Fixed duplicate ACM DNS validation records.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Recommendations API Routes
Added recommendations endpoints to API Gateway. Fixed iOS app issues with recommendations display. Optimized with batch query and 1-hour cache. Fixed batch conditions scan to parse all fields.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

---

## Jan 28, 2026

### Auth, Recommendations, and Trip Planning
Major backend feature drop: Apple/Google/Guest authentication with JWT, personalized recommendations based on location and preferences, trip planning CRUD with multi-resort itineraries.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | backlog | backlog | done |

### Release Workflow Restructure
Separated build from upload in CI/CD. Restructured into 3-step release process. Version bump to 1.1.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Region Filtering in Widget
Best Snow widget now supports region filtering (NA West, NA Rockies, Alps, etc.).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### API Timeout: 5s to 30s
iOS app was timing out on slow API calls. Increased client timeout from 5s to 30s.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Dead Code Cleanup
Removed dead code, fixed silent error handlers, improved test reliability across the codebase.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

---

## Jan 27, 2026

### TestFlight Automated Deployment
Set up automated TestFlight deployment pipeline. Required extensive debugging: Info.plist path, JWT generation for ASC API (multiple Python/YAML/heredoc fixes), PyJWT install issues, bundle ID, export compliance, beta group assignment, runner fallback strategy.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Marketing Website and Custom Domains
Launched powderchaserapp.com. Set up custom API subdomains (api.powderchaserapp.com, staging.api.powderchaserapp.com). Automated website deployment to S3.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | done | done |

### Map Clustering and Geocoding
Added clustered map view. Improved resort geocoding with multi-source approach (Apple, Google, OSM). Fixed certificate creation to import from secrets.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Batch Conditions: Parallel fetching
Batch conditions endpoint was sequential (slow). Changed to parallel DynamoDB fetching with ThreadPoolExecutor.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Resort Scraping and Population
Added scraping scripts for ski resort data. Population scripts with SNS notifications for new/removed resorts. Parallel scraping with delta mode. URL filtering to skip non-resort pages.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Lambda SnapStart
Enabled Lambda SnapStart for faster cold starts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS SDK Update to 26.0
Updated to iOS SDK 26.0 and Swift 6.0. Added location privacy description string. Fixed Xcode version selection in CI.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Data Loading Optimization
Lazy fetch conditions (don't load until resort tapped). Aggressive caching. Reduced API response size by excluding raw_data field.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### App Store Assets and Fastlane
App Store screenshots, app icon, metadata management via Fastlane. Multiple fixes for App Store upload requirements (emojis rejected, phone format, review info).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Proximity-based Resort Discovery
Find resorts near your location with distance and quality sorting.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

---

## Jan 26, 2026

### Google Sign-In
Added Google Sign-In alongside Apple authentication.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Interactive Map View
Location-based resort filtering on a full map view with annotations.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Offline Mode
Fixed API offline mode and data display issues. App now works with cached data when offline.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### Bundle ID Update
Updated bundle ID for new Apple Developer account. Fixed app group identifier in entitlements.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Jan 25, 2026

### Snow Quality Batch Endpoint
Added batch API endpoint for fetching snow quality of multiple resorts at once. Fixed quality calculation bugs and added test coverage.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Parallel API Loading
Fixed slow API loading by fetching conditions for multiple resorts in parallel instead of sequentially.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### HORRIBLE Snow Quality Level
Added HORRIBLE (1) quality level. Updated iOS launch screen. Adjusted quality thresholds.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Freeze-Thaw Detection: Extended to 14 days
Weather processor only looked back 7 days for freeze-thaw events. Extended to 14 days for more accurate detection in stable cold weather.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### API Lambda: Wrong table environment
API Lambda environment variables were pointing to dev table instead of the correct environment table. Fixed configuration.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Historical Data Backfill
Added script and deployment step for backfilling historical weather data. Later removed from automatic deploy, added manual trigger workflow.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

---

## Jan 24, 2026

### Switch to Open-Meteo
Replaced weatherapi.com with Open-Meteo for weather data. Free, no API key needed, better elevation support with lapse rate adjustments.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Snow Quality Rating: Fresh powder since thaw-freeze
Implemented first snow quality algorithm based on fresh powder accumulation since last thaw-freeze cycle. Quality levels: EXCELLENT, GOOD, FAIR, POOR, BAD.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### OnTheSnow Scraper
Integrated OnTheSnow for real snow depth data to supplement Open-Meteo weather data.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### 60-second API Caching
Added 60-second response caching to reduce API load and improve response times.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Splash Screen and Region Filtering
Added splash/loading screen. Offline data caching. More resorts added. Region filtering (Alps, Rockies, etc.).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | n/a |

### CloudWatch Metrics and Grafana Dashboards
Added custom CloudWatch metrics for API latency, weather processing, and resort coverage. Created Grafana dashboards for monitoring.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS Conditions: Response format mismatch
iOS model expected different JSON structure than what the API returned. Multiple rounds of fixes to align the two.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Lambda Timeout: Open-Meteo
Lambda was timing out when Open-Meteo API was slow. Reduced API timeouts to fail fast.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Widget Reliability
Fixed widget data service decoding issues. Added debugging logs. Improved reliability.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Conditional CI: Path-based job execution
CI jobs now only run when relevant files change (iOS jobs skip when only backend changes, etc.).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

---

## Jan 23, 2026

### First Deployment: iOS app talking to live API
Connected iOS app to deployed staging API. Multiple rounds of fixes: Lambda handler, API Gateway configuration, Python imports, response format parsing, DynamoDB queries. Weather processor producing real data.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### API Error Handling
Replaced fake data fallback with proper error messages when API fails. Added error message UI.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Weather Processor: Multiple fixes
Convert floats to Decimal for DynamoDB. Remove redundant enum-to-string conversion. Fix handler and elevation formatting. Fix logging for both enum and string values.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Lambda: Large package deployment
Lambda deployment failed for packages over 50MB. Fixed deployment pipeline.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### US, European, and Japanese Resorts
Expanded from initial Canadian resorts to include major US (Vail, Park City, etc.), European (Chamonix, Zermatt, etc.), and Japanese (Niseko, Hakuba) resorts.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### Feedback Feature
Added in-app feedback submission with backend endpoint.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | pending | n/a | done |

### Snow Predictions, Share Button, and Widgets
Added 7-day snow predictions. Share button for resort conditions. iOS home screen widgets showing best snow conditions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### iOS CI: XcodeGen and Screenshots
Added XcodeGen to CI for generating Xcode project. Set up screenshot capture automation.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Fix iOS: WeatherCondition rawData decoding
Complex nested JSON in weather response caused decoding failures. Fixed with custom decoder.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

---

## Jan 20, 2026

### Project Inception
Initial project setup for Snow Quality Tracker. Project scaffolding with comprehensive testing strategy. Resort data seeder. CI/CD pipeline with GitHub Actions.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | done |

### Infrastructure: Pulumi AWS setup
S3 state backend, multi-environment Pulumi deployment (dev/staging/prod). API Gateway, Lambda functions, DynamoDB tables. EKS with Grafana/Prometheus (later disabled to reduce costs).
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### iOS App: Initial features
API client, SwiftUI views for resort list and detail, Sign in with Apple authentication. Silver Star resort added, favorites persistence.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| done | n/a | n/a | n/a |

### Scheduled Weather Processing Lambda
Lambda function to periodically fetch and process weather data from external APIs. Fix config namespace issues.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |

### EKS: Version upgrade fiasco
Attempted upgrade to EKS 1.34 failed because Kubernetes requires incremental version upgrades. Had to destroy and redeploy staging cluster. Eventually disabled EKS entirely to reduce costs.
| iOS | Android | Web | API |
|-----|---------|-----|-----|
| n/a | n/a | n/a | done |
