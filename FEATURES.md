# Snow Quality Tracker (Powder Chaser) - Feature Roadmap

**Created**: 2026-02-20
**Last Updated**: 2026-02-20

This document outlines the feature roadmap for Powder Chaser, prioritized by user impact, feasibility, and alignment with what makes the best ski apps indispensable. It is informed by competitive analysis of OpenSnow, Slopes, OnTheSnow, Epic Mix, Ikon Pass, Ski Tracks, and others.

---

## Current State Summary

The app is live with a strong foundation:
- 900+ resorts across 23 countries with hourly weather updates
- ML-powered snow quality ratings (v7 ensemble, 88.2% accuracy)
- Push notifications (fresh snow, thaw/freeze alerts)
- 7-day forecast timeline with ML predictions
- Map view with quality-colored markers and date selector
- Best snow recommendations (proximity-based and global)
- Favorites system with notification customization
- iOS widgets, 13-language localization
- Apple Sign In / Guest auth, trip API endpoints (UI hidden)

Open issues: Trip Planning (#23), Webcam Integration (#24), Apple Watch (#25), Alternative Snow Data Sources (#13).

---

## 1. Next Up (Build Soon)

These features have the highest impact-to-effort ratio and address the most common reasons skiers open a ski app.

### 1.1 Powder Alerts with Custom Thresholds (Enhanced Notifications)

**Description**: Upgrade the notification system so users can set precise snowfall thresholds per resort (e.g., "Notify me when Whistler gets 15+ cm in 24h") and add a "Powder Day" alert type that triggers when conditions align: heavy fresh snow + cold temps + low wind. Currently the app sends fresh snow alerts at a flat 1cm threshold -- this makes alerts much more actionable.

**User Value**: The single most requested feature in ski apps. OpenSnow's custom powder alerts are a primary reason people pay for their All-Access subscription. Skiers want to know exactly when it is worth calling in sick to work. Better alerts drive daily engagement and make the app the first thing users check.

**Estimated Complexity**: S-M

**Dependencies**: Existing notification infrastructure, user preferences model (already has per-resort threshold fields). Mostly backend logic changes in notification_processor + iOS UI for threshold picker.

**Implementation Notes**:
- Backend: Add "powder day" detection logic combining fresh_snow_24h, temperature, wind speed, and snow quality score
- Backend: Allow asymmetric thresholds (e.g., 5cm for nearby resorts, 20cm for far ones)
- iOS: Add threshold slider per resort in notification settings
- iOS: Add "Powder Day" toggle as a distinct alert type
- Consider a "Powder Finder" digest notification: "Top 3 resorts with best powder right now within 200km"

---

### 1.2 Snow History & Season Totals

**Description**: Track and display cumulative snowfall over the season for each resort. Show a snow history chart (daily snowfall bars + cumulative line) and compare current season to historical averages. Display season-to-date totals prominently on resort detail pages.

**User Value**: OnTheSnow's snow history graph is one of its stickiest features. Skiers constantly compare "is this a good snow year?" Season totals help users evaluate whether a resort is worth the trip. This is purely additive -- uses data already being collected but not yet surfaced historically.

**Estimated Complexity**: M

**Dependencies**: Weather data is currently TTL'd at 7 days. Requires a new DynamoDB table or S3 archive to store daily snowfall summaries long-term. Needs a daily aggregation job.

**Implementation Notes**:
- Backend: New `snow-tracker-daily-history-{env}` table storing daily snowfall, temp range, and quality per resort
- Backend: Aggregation Lambda that runs after weather processor, computes daily summary
- Backend: New endpoint `GET /api/v1/resorts/{id}/history?season=2025-2026`
- iOS: Snow history chart in resort detail (bar chart for daily snowfall, line for cumulative)
- iOS: "Season Total" badge on resort cards and detail view
- Future: Compare season-to-date across resorts, compare to past seasons

---

### 1.3 Webcam Integration (Issue #24)

**Description**: Show live or recent webcam snapshots for resorts that have publicly available feeds. Start with a curated set of major resorts where webcams are freely embeddable, then expand.

**User Value**: "Show me what it looks like right now" is the fastest way to build trust in conditions data. Webcams are one of the top features in both OpenSnow and OnTheSnow. A single webcam image often tells a skier more than any data table. This feature directly increases time-in-app and visit frequency.

**Estimated Complexity**: M

**Dependencies**: Research needed on terms of use for webcam feeds per resort. Some resorts publish embed-friendly feeds, others require licensing. Issue #24 already captures this.

**Implementation Notes**:
- Backend: Add `webcam_urls` array field to resort schema (curated, not scraped)
- Backend: Optional image proxy Lambda to handle CORS and caching (CloudFront + S3)
- iOS: Webcam section in resort detail with horizontal scroll for multiple cameras
- iOS: Full-screen tap-to-expand with pinch-to-zoom
- Start with 20-30 major resorts (Whistler, Vail, Chamonix, etc.), expand from there
- Consider windy.com webcam API as aggregated source

---

### 1.4 Improved Resort Comparison

**Description**: Allow users to compare 2-4 resorts side-by-side on key metrics: current snow quality, fresh snow, temperature, wind, forecast, and season totals. Accessible from favorites or search.

**User Value**: The classic "where should I ski this weekend?" decision. Currently users must flip between resort detail pages to compare. A dedicated comparison view saves time and helps users make better decisions, which is the core value proposition of a conditions app.

**Estimated Complexity**: S-M

**Dependencies**: Existing conditions and quality endpoints. Batch endpoints already exist (`/conditions/batch`, `/snow-quality/batch`).

**Implementation Notes**:
- iOS: "Compare" button on favorites view, multi-select up to 4 resorts
- iOS: Side-by-side cards or table layout showing key metrics
- iOS: Highlight "winner" in each category (most snow, best quality, etc.)
- iOS: Include 3-day mini forecast for each resort in comparison
- Backend: No new endpoints needed -- use existing batch endpoints

---

### 1.5 Live Activities & Dynamic Island (iOS)

**Description**: Use iOS Live Activities to show a persistent, glanceable snow update on the Lock Screen and Dynamic Island during active storm events or on planned trip days. Show: resort name, fresh snow accumulating, current quality, temperature.

**User Value**: Live Activities are the most visible integration point on iOS. During a storm, having snowfall tick up in real-time on the Lock Screen creates a "can't put it down" experience. Slopes already uses this for active tracking -- Powder Chaser should use it for conditions monitoring.

**Estimated Complexity**: M

**Dependencies**: iOS 16.1+ (ActivityKit). Requires push-to-update token flow for server-driven updates. Existing APNS infrastructure can be extended.

**Implementation Notes**:
- iOS: Define `SnowActivityAttributes` and `SnowActivityContent` for ActivityKit
- iOS: Start Live Activity when storm is detected at a favorited resort, or on trip day
- iOS: Dynamic Island compact/expanded views showing snowfall + quality
- Backend: New push token type for ActivityKit updates, sent alongside regular APNS
- Backend: Storm detection logic to auto-trigger Live Activities
- Ties in well with trip planning (#23) -- show live conditions on trip day

---

## 2. Medium Term (Next Few Months)

These features build on the foundation and move the app toward being a daily-use companion for serious skiers.

### 2.1 Trip Planning Mode (Issue #23)

**Description**: Full implementation of the trip planning feature. Users select a resort and date range, get a countdown with evolving forecast, and receive proactive notifications as conditions change. Trip history for looking back at past adventures.

**User Value**: Converts the app from a "check conditions" tool into a planning companion. Trip anticipation drives engagement in the days/weeks before a trip. The forecast evolution ("your trip is looking better/worse") creates emotional investment.

**Estimated Complexity**: L

**Dependencies**: Backend trip endpoints exist. iOS TripPlanningViews.swift exists (hidden). Needs notification integration for trip-specific alerts.

**Implementation Notes**:
- iOS: Unhide Trips tab, polish TripPlanningViews
- iOS: Trip countdown with evolving forecast visualization
- iOS: "Conditions outlook" for trip dates showing confidence level
- Backend: Trip conditions checker Lambda (scheduled, checks upcoming trips)
- Backend: Trip-specific notification types (conditions_improved, conditions_worsened, powder_expected)
- Calendar integration (add trip to iOS Calendar)
- Share trip with friends (generate shareable link)

---

### 2.2 Resort Detail Enrichment (Terrain, Lifts, Trail Counts)

**Description**: Add static resort metadata beyond weather: number of lifts, trail counts by difficulty, vertical drop, skiable acreage, terrain parks, night skiing availability, closest airport, driving time from major cities. Source from scraper data and manual curation.

**User Value**: Users currently have to leave the app to look up basic resort info. Having everything in one place reduces friction and builds the app into a comprehensive resort guide. Essential for trip planning decisions.

**Estimated Complexity**: M

**Dependencies**: Resort model expansion. Scraper already collects some of this data. Need to verify what OnTheSnow scraper returns.

**Implementation Notes**:
- Backend: Extend Resort model with terrain fields (lifts, trails_green/blue/black, vertical_m, skiable_area_ha, etc.)
- Backend: Populate from scraper data + manual enrichment for top 50 resorts
- iOS: "Resort Info" section in detail view with iconographic stats
- iOS: Difficulty distribution bar (green/blue/black percentages)
- Data: Start with what scraper already collects, fill gaps manually for popular resorts

---

### 2.3 Snow Depth Map Overlay

**Description**: Add a map layer showing snow depth or recent snowfall as a color gradient across the map view. Toggle between "Current Quality," "Fresh Snow (24h)," "Snow Depth," and "Temperature" map modes.

**User Value**: A visual snow map is one of the most powerful decision tools -- it answers "where did the snow fall?" at a glance. OpenSnow's forecast maps are a major differentiator. This makes the existing map view dramatically more useful.

**Estimated Complexity**: M-L

**Dependencies**: Map view already exists with quality-colored markers. Needs Open-Meteo grid data or interpolation between resort points.

**Implementation Notes**:
- Backend: New endpoint returning gridded snow data (or use Open-Meteo's gridded API directly from iOS)
- iOS: MapKit overlay with color gradient (blue shades for depth, warm colors for temperature)
- iOS: Layer toggle control on map view
- iOS: Tap anywhere on map to see interpolated conditions
- Consider using Open-Meteo's "flood" API for precipitation grid data
- Start simple with marker-based heatmap, evolve to true contour overlay

---

### 2.4 Weekly Snow Summary Digest

**Description**: A push notification (or in-app digest) sent once a week summarizing: best conditions in your region, how your favorites performed, upcoming storm potential, and season-to-date snowfall leaders. The model field `weekly_summary` already exists in UserNotificationPreferences.

**User Value**: Not everyone checks the app daily. A well-crafted weekly summary re-engages casual users and serves as a "preview of the week ahead." Keeps the app top-of-mind even during dry spells.

**Estimated Complexity**: M

**Dependencies**: Notification infrastructure, snow history data (feature 1.2), recommendation engine.

**Implementation Notes**:
- Backend: Weekly digest Lambda (runs Sunday evening)
- Backend: Aggregation logic: top 3 resorts by quality, biggest snowfall, upcoming storms
- Backend: Rich notification with action buttons ("View Details", "Plan a Trip")
- iOS: In-app digest view (scrollable summary card)
- Personalized based on favorites and location

---

### 2.5 Shareable Conditions Cards

**Description**: Generate beautiful, branded image cards showing a resort's current conditions (quality rating, fresh snow, temperature, forecast preview) that users can share to Instagram Stories, iMessage, WhatsApp, etc. Include app branding and a deep link.

**User Value**: Social sharing is the number one organic growth channel for ski apps. When a user shares a "POWDER DAY at Whistler!" card, every recipient is a potential new user. Also serves trip coordination ("look at the conditions, let's go!").

**Estimated Complexity**: S-M

**Dependencies**: Resort conditions data. iOS share sheet APIs.

**Implementation Notes**:
- iOS: `UIGraphicsImageRenderer` to compose a conditions card image
- iOS: Include resort name, quality badge, key stats, mini forecast, app logo
- iOS: Share sheet integration with pre-populated text
- iOS: Optionally generate on backend (Lambda + Pillow) for push notification rich media
- Track share events in analytics to measure viral coefficient

---

### 2.6 Favorite Resort Groups / Tags

**Description**: Allow users to organize favorites into groups: "Home Mountains," "Bucket List," "Weekend Trips," "Europe Trip 2026." Groups can be reordered and color-coded.

**User Value**: Power users with 10+ favorites need organization. Groups also serve as lightweight trip planning ("compare all resorts in my Weekend Trips group"). Reduces cognitive load when the favorites list grows.

**Estimated Complexity**: S

**Dependencies**: Existing favorites system. Needs local persistence (UserDefaults or Core Data).

**Implementation Notes**:
- iOS: Add group management in favorites view (create, rename, reorder, delete groups)
- iOS: Drag-and-drop resorts between groups
- iOS: Group-level summary ("Best in this group: Whistler - EXCELLENT")
- Backend: Optionally sync groups to user preferences (for cross-device)
- Keep it simple: start with local-only, add sync later

---

### 2.7 Elevation Profile Visualization

**Description**: Show an elevation profile cross-section for each resort with conditions mapped to elevation bands. Visualize where the snow line is, where it is icy vs. powdery, and how conditions change from base to summit. The data exists (base/mid/top) but is not visualized intuitively.

**User Value**: Skiers think in terms of "is it good up top?" The current data is there but presented as numbers. A visual elevation profile makes it immediately clear where to ski. Differentiates from apps that only show summit conditions.

**Estimated Complexity**: S-M

**Dependencies**: Existing multi-elevation conditions data. Custom SwiftUI drawing.

**Implementation Notes**:
- iOS: Custom SwiftUI shape showing mountain cross-section
- iOS: Color-code elevation bands by quality (green/yellow/red gradient)
- iOS: Overlay temperature, wind, and snow depth at each elevation
- iOS: Animate transitions when switching between days in timeline
- Simple version: stacked horizontal bars. Advanced: actual mountain silhouette shape

---

### 2.8 Android App (Research Phase)

**Description**: Begin planning for an Android version, likely using Kotlin/Jetpack Compose to mirror the iOS experience. Alternatively, evaluate cross-platform options (Kotlin Multiplatform, Flutter) for shared business logic.

**User Value**: Roughly 50% of the global smartphone market. Android users currently have no access to the app. Required for any serious growth beyond Apple ecosystem.

**Estimated Complexity**: XL

**Dependencies**: Stable API, well-documented backend. All backend features work for any client.

**Implementation Notes**:
- Research: Evaluate Kotlin Multiplatform (share models/networking with iOS) vs. native Kotlin vs. Flutter
- Research: Audit API for any iOS-specific assumptions
- Start with core feature subset: browse resorts, conditions, favorites, notifications
- Consider hiring/contracting for Android development
- FCM (Firebase Cloud Messaging) integration for push notifications (SNS already supports it)

---

## 3. Future Vision (Long Term)

These are ambitious features that would make Powder Chaser best-in-class. They require significant development effort or external partnerships.

### 3.1 Apple Watch App (Issue #25)

**Description**: Companion watchOS app showing conditions at-a-glance for favorited resorts. Complications for watch faces. On-wrist powder alerts.

**User Value**: Quick glance at conditions without pulling out your phone, especially useful on the mountain or while driving. Watch complications keep conditions visible all day.

**Estimated Complexity**: L

**Dependencies**: iOS app stable, Watch Connectivity framework, watchOS 11+ target.

---

### 3.2 GPS Ski Tracking

**Description**: Track runs on the mountain: speed, vertical, distance, run count, lift vs. skiing detection. Display stats on a trail map overlay. Store history for season totals.

**User Value**: This is what Slopes and Ski Tracks are known for. Adding tracking to a conditions app creates a single app for the entire ski experience. Massively increases on-mountain usage and daily engagement during ski days.

**Estimated Complexity**: XL

**Dependencies**: Apple Watch (for best tracking accuracy), resort trail map data, GPS processing, battery optimization.

---

### 3.3 Community Condition Reports

**Description**: Allow users to submit quick condition reports from the mountain: "Powder in the trees," "Icy groomers," "Wind hold on summit." Reports are timestamped, geotagged, and visible to other users on the resort detail page.

**User Value**: First-hand reports from people actually skiing are more trusted than any algorithm. OnTheSnow's user reports and photos are among its most valued features. Creates network effects -- the more users report, the more valuable the app becomes for everyone.

**Estimated Complexity**: L

**Dependencies**: User authentication, content moderation strategy, geolocation on mountain, potential abuse prevention.

**Implementation Notes**:
- Backend: New `condition_reports` table with user_id, resort_id, timestamp, report_type, text, photo_url
- Backend: Moderation pipeline (automated profanity filter + manual review queue)
- iOS: Quick-report UI (2 taps: select condition type + optional comment)
- iOS: Show recent reports on resort detail page, sorted by recency
- Reputation system: frequent reporters get trust badges

---

### 3.4 AI Conditions Summary

**Description**: Use an LLM to generate natural language condition summaries for each resort, synthesizing weather data, quality scores, recent trends, and forecast. "Whistler had 18cm overnight and it's still snowing. Expect excellent powder in the alpine with some wind effect on exposed ridges. Base area is firm but skiable. Best day of the week -- go."

**User Value**: OpenSnow's human-written daily forecasts are their killer feature and what people pay $30/year for. An AI-generated version at scale (900+ resorts) would be unprecedented. Transforms raw data into advice.

**Estimated Complexity**: M-L

**Dependencies**: All weather and quality data. LLM API (Claude, GPT). Prompt engineering. Cost management for 900+ daily summaries.

**Implementation Notes**:
- Backend: Daily Lambda that generates summaries for resorts with active users
- Backend: Cache summaries in DynamoDB (generate once per day per resort)
- Backend: Use Claude API with structured prompt including all conditions data
- iOS: "Today's Summary" card at top of resort detail
- Cost optimization: Only generate for resorts with favorited users, cache aggressively
- Start with top 50 resorts, expand based on usage

---

### 3.5 Social / Friends System

**Description**: Add friends, see what resorts your friends are tracking, share conditions and trip plans. "3 friends are watching Whistler this weekend." Optional: real-time location sharing on mountain.

**User Value**: Social features create retention loops and viral growth. Knowing friends are planning a trip creates urgency. The Ikon and Epic apps both have social components. Ski trips are inherently social activities.

**Estimated Complexity**: L-XL

**Dependencies**: User accounts (already have Apple Sign In), social graph infrastructure, privacy controls.

---

### 3.6 Gamification & Achievements

**Description**: Award badges and achievements for skiing milestones: "Powder Hunter" (visited resort on 5 powder days), "Explorer" (checked conditions at 50+ resorts), "Early Bird" (checked conditions before 6am), "Season Warrior" (checked in every week of the season). Seasonal leaderboards.

**User Value**: EpicMix proved that gamification drives engagement in skiing. Achievements give users reasons to open the app even when they are not planning a trip. Creates dopamine loops and long-term retention.

**Estimated Complexity**: M-L

**Dependencies**: User analytics/activity tracking. Achievement definition system. Potentially GPS tracking for on-mountain achievements.

---

### 3.7 Offline Mode with Cached Conditions

**Description**: Cache the last-fetched conditions for all favorited resorts locally so the app is fully functional without network connectivity. Critical for mountain use where cell service is spotty. Show "last updated X hours ago" indicators.

**User Value**: Ski resorts often have poor cell service. Users check conditions at the lodge, drive to the mountain, and lose connectivity. Having cached data available offline ensures the app is useful when it matters most.

**Estimated Complexity**: M

**Dependencies**: iOS caching infrastructure (CacheService.swift exists). Needs expansion to cover all data types.

**Implementation Notes**:
- iOS: Expand CacheService to persist conditions, quality, and timeline data to disk
- iOS: Clear "offline" indicator with last-updated timestamp
- iOS: Background refresh when connectivity returns
- iOS: Pre-fetch data for favorited resorts on Wi-Fi
- Consider using Core Data or SwiftData for structured offline storage

---

### 3.8 Storm Tracker

**Description**: Track incoming winter storms on a map overlay with predicted snowfall totals and timing. Show storm path, arrival time at each resort, and expected accumulation. "Storm arriving at Whistler in 18 hours -- 25-40cm expected."

**User Value**: Storm anticipation is the most exciting part of skiing. OpenSnow's storm tracking is their most shared feature. A well-executed storm tracker turns the app into appointment viewing during weather events.

**Estimated Complexity**: L

**Dependencies**: Weather grid data (Open-Meteo or alternative source), map overlay rendering, storm detection algorithms.

---

### 3.9 Resort Reviews & Ratings

**Description**: Allow users to rate and review resorts on multiple dimensions: snow quality reliability, terrain variety, lift infrastructure, crowds, value for money, family friendliness. Aggregate ratings visible on resort cards.

**User Value**: Helps users discover new resorts beyond their usual spots. Community ratings build trust and create content that keeps users browsing. Useful for trip planning decisions.

**Estimated Complexity**: M-L

**Dependencies**: User authentication, content moderation, review data model.

---

### 3.10 Multi-Source Data Aggregation (Issue #13)

**Description**: Integrate additional snow data sources beyond Open-Meteo: snow-forecast.com, Weather Unlocked, resort official APIs. Use multi-source consensus to improve accuracy and provide confidence indicators.

**User Value**: More data sources mean better accuracy. When sources agree, confidence is high. When they disagree, the app can flag uncertainty. This is the technical moat that differentiates from basic weather apps.

**Estimated Complexity**: L

**Dependencies**: Research phase (issue #13). API access agreements. Data normalization layer.

---

### 3.11 Road Conditions & Drive Time

**Description**: Show road conditions and estimated drive time from the user's location to each resort. Integrate with state DOT APIs (CDOT, Caltrans, etc.) for real-time road closures, chain requirements, and traffic delays.

**User Value**: "How long will it take to get there and are the roads open?" is the second question after "how's the snow?" Especially critical in Colorado (I-70), California (I-80), and mountain passes in Europe.

**Estimated Complexity**: L

**Dependencies**: DOT API integrations (varies by region), Apple Maps/Google Maps API for drive times.

---

### 3.12 Backcountry Mode

**Description**: Extend the app beyond groomed resorts to backcountry zones. Show avalanche danger ratings (from regional avalanche centers), snow stability, aspect-specific conditions, and link to official avalanche advisories.

**User Value**: Backcountry skiing is the fastest-growing segment. Apps like onX Backcountry serve this market but do not integrate resort conditions. A unified app for both resort and backcountry would be unique.

**Estimated Complexity**: XL

**Dependencies**: Avalanche center API integrations (avalanche.org, avalanche.ca), terrain data, safety considerations (liability).

---

### 3.13 Season Pass Value Tracker

**Description**: For users who enter their season pass type (Epic, Ikon, Mountain Collective, etc.), show which pass-included resorts have the best conditions right now. Track cost-per-visit as they use the pass throughout the season.

**User Value**: Pass holders are the most engaged skiers. Helping them maximize their pass creates strong utility. "Your Epic Pass has saved you $1,847 this season" is a shareable, sticky stat.

**Estimated Complexity**: M

**Dependencies**: Season pass resort mapping data (which resorts are on which pass). User input for pass type.

---

## 4. Research Needed

These features need investigation before committing to a development plan.

### 4.1 Webcam Feed Licensing & Terms of Use

**Research Question**: Which resort webcam feeds can be legally embedded or linked? What are the terms of use? Are there aggregator APIs (like Windy.com's webcam API) that simplify this?

**Why It Matters**: Webcams (feature 1.3) are high-impact but legally sensitive. Using feeds without permission could result in takedown requests or legal issues.

**Next Steps**:
- Survey top 30 resorts for publicly embeddable webcam feeds
- Evaluate Windy.com webcam API (has ski resort webcams, documented API)
- Contact 5 resort marketing departments to understand embedding policies
- Prototype with 3-5 freely available feeds

---

### 4.2 Alternative Snow Data Sources (Issue #13)

**Research Question**: Which additional data sources meaningfully improve accuracy over Open-Meteo alone? What do they cost? What are their API terms?

**Why It Matters**: Data accuracy is the foundational differentiator. More sources = better predictions = more user trust.

**Next Steps**:
- Evaluate Weather Unlocked API (free tier: 1000 req/day, 3 elevations, 3000+ resorts)
- Contact snow-forecast.com about API access
- Research SNOTEL/NRCS data for US resorts (free, government data)
- Design a multi-source scoring system (weighted consensus)
- Estimate cost for Weather Unlocked paid tier at scale

---

### 4.3 GPS Tracking Feasibility & Battery Impact

**Research Question**: Can the app perform GPS ski tracking with acceptable battery drain? What is the minimum viable implementation? Can it be done without Apple Watch?

**Why It Matters**: GPS tracking (feature 3.2) is the highest-impact long-term feature but also the most technically complex. Understanding feasibility early prevents wasted effort.

**Next Steps**:
- Prototype background GPS tracking on iPhone during a ski day
- Measure battery impact at various GPS update intervals (1s, 5s, 15s)
- Research lift-vs-run detection algorithms (altitude + speed heuristics)
- Evaluate whether Apple Watch is required for acceptable accuracy
- Study how Slopes handles background tracking and battery optimization

---

### 4.4 AI Summary Cost & Quality at Scale

**Research Question**: What does it cost to generate daily AI condition summaries for 900+ resorts? Can quality be maintained with smaller/cheaper models? What prompt engineering is needed?

**Why It Matters**: AI summaries (feature 3.4) could be the app's biggest differentiator vs. OpenSnow, but cost at scale could be prohibitive.

**Next Steps**:
- Generate sample summaries for 10 resorts using Claude Haiku (lowest cost)
- Evaluate quality vs. Sonnet/Opus for this use case
- Calculate daily cost at 900 resorts (tokens per summary * price per token)
- Prototype caching strategy (generate only for active resorts)
- User test: do AI summaries actually change behavior vs. raw data?

---

### 4.5 Android Development Approach

**Research Question**: What is the optimal approach for an Android app? Native Kotlin, Kotlin Multiplatform (share logic with iOS), or cross-platform (Flutter/React Native)?

**Why It Matters**: Android represents ~50% of the market. The choice of technology affects development speed, maintenance burden, and feature parity.

**Next Steps**:
- Audit current iOS codebase for logic that could be shared (networking, models, caching)
- Evaluate Kotlin Multiplatform for shared business logic with Swift interop
- Prototype a minimal Android app with resort list + conditions using native Kotlin
- Estimate development time for each approach to reach feature parity
- Consider: is it better to hire an Android developer or go cross-platform?

---

### 4.6 Monetization Strategy

**Research Question**: What is the right monetization model? Freemium (basic free, premium features paid)? Subscription? One-time purchase? Ad-supported?

**Why It Matters**: The app needs a sustainable business model. OpenSnow charges $30/year for All-Access. Slopes charges $30/year for premium. Understanding what users will pay for informs feature prioritization.

**Next Steps**:
- Survey competitive pricing (OpenSnow $30/yr, Slopes $30/yr, Ski Tracks $3 one-time)
- Identify which features could be premium (AI summaries, advanced alerts, GPS tracking, historical data)
- Research App Store subscription best practices and pricing tiers
- Consider: free tier should be valuable enough to attract users, premium should feel essential to power users
- Potential premium features: custom powder thresholds, AI summaries, storm tracker, GPS tracking, historical comparisons, ad-free experience

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| 1.1 Enhanced Powder Alerts | High | S-M | **Now** |
| 1.2 Snow History & Season Totals | High | M | **Now** |
| 1.3 Webcam Integration | High | M | **Now** |
| 1.4 Resort Comparison | Medium-High | S-M | **Now** |
| 1.5 Live Activities | Medium-High | M | **Now** |
| 2.1 Trip Planning | High | L | **Next** |
| 2.2 Resort Detail Enrichment | Medium | M | **Next** |
| 2.3 Snow Depth Map Overlay | Medium-High | M-L | **Next** |
| 2.4 Weekly Digest | Medium | M | **Next** |
| 2.5 Shareable Conditions Cards | Medium-High | S-M | **Next** |
| 2.6 Favorite Groups | Medium | S | **Next** |
| 2.7 Elevation Profile Viz | Medium | S-M | **Next** |
| 2.8 Android App | High | XL | **Research** |
| 3.1 Apple Watch | Medium | L | **Later** |
| 3.2 GPS Tracking | Very High | XL | **Later** |
| 3.3 Community Reports | High | L | **Later** |
| 3.4 AI Summaries | Very High | M-L | **Later** |
| 3.5 Social/Friends | High | L-XL | **Later** |
| 3.6 Gamification | Medium | M-L | **Later** |
| 3.7 Offline Mode | Medium | M | **Later** |
| 3.8 Storm Tracker | High | L | **Later** |
| 3.9 Resort Reviews | Medium | M-L | **Later** |
| 3.10 Multi-Source Data | High | L | **Later** |
| 3.11 Road Conditions | Medium | L | **Later** |
| 3.12 Backcountry Mode | Medium-High | XL | **Later** |
| 3.13 Season Pass Tracker | Medium | M | **Later** |

---

## Competitive Positioning

**Current strength**: Powder Chaser's ML-powered quality ratings across 3 elevation levels for 900+ resorts is a unique differentiator. No competitor provides per-elevation quality scoring at this scale.

**Key gaps vs. competitors**:
- vs. OpenSnow: Missing expert/AI daily forecasts, storm tracker, webcams
- vs. Slopes: Missing GPS tracking, social features, Apple Watch
- vs. OnTheSnow: Missing webcams, user-submitted reports, snow history
- vs. Epic/Ikon: Missing lift status, trail maps, season pass integration

**Recommended positioning**: "The smartest snow conditions app." Focus on data quality, ML predictions, and actionable alerts rather than trying to be everything. Win on accuracy and signal-to-noise ratio. Let others do GPS tracking and trail maps -- own the "should I go skiing tomorrow?" decision.

---

## Sources & Competitive Research

- [Best Ski Apps 2025 - AppSavvyTraveller](https://appsavvytraveller.com/ski-apps/)
- [Best Ski Apps - SnowBrains](https://snowbrains.com/5-best-apps-for-skiing-and-snowboarding/)
- [Best Ski Apps 2025-26 - OnTheSnow](https://www.onthesnow.co.uk/news/best-ski-apps-for-2025-26/)
- [OpenSnow App Features](https://opensnow.com/app)
- [Slopes - Track Your Winter Adventures](https://getslopes.com)
- [Slopes App Data-Driven Precision - SnowBrains](https://snowbrains.com/slopes-app-redefines-the-modern-ski-day-with-data-driven-precision/)
- [Best Ski Apps - Powder Magazine](https://www.powder.com/gear/best-apps-for-skiers)
- [OnTheSnow Mobile App](https://www.onthesnow.com/news/mobile/)
- [Gamification in Skiing - Alturos](https://www.alturos.com/en/skiline/gamification/)
- [onX Backcountry Ski App](https://www.onxmaps.com/backcountry/app/features/ski-splitboard)
- [Vail Resorts My Epic AI Assistant](https://vailresortsinc.gcs-web.com/news-releases/news-release-details/vail-resorts-announces-my-epic-assistant-my-epic-app-powered)
- [Ikon Pass Upgraded App - Travel And Tour World](https://www.travelandtourworld.com/news/article/ikon-pass-unveils-upgraded-app-for-winter-25-26-enhancing-access-to-many-ski-destinations-worldwide-what-you-need-to-know/)
- [Best Ski Apps for Apple Watch - Softonic](https://en.softonic.com/top/ski-apps-for-apple-watch)
