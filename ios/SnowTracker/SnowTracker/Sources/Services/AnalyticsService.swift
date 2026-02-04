//
//  AnalyticsService.swift
//  SnowTracker
//
//  Firebase Analytics and Crashlytics integration
//

import Foundation
#if canImport(FirebaseCore)
import FirebaseCore
#endif
#if canImport(FirebaseAnalytics)
import FirebaseAnalytics
#endif
#if canImport(FirebaseCrashlytics)
import FirebaseCrashlytics
#endif

/// Analytics service for tracking user behavior and crashes
final class AnalyticsService: @unchecked Sendable {
    static let shared = AnalyticsService()

    /// Track screen view times
    private var screenStartTimes: [String: Date] = [:]
    private let queue = DispatchQueue(label: "com.snowtracker.analytics")

    /// Session tracking
    private var sessionStartTime: Date?
    private var sessionId: String?

    private init() {}

    // MARK: - Configuration

    /// Call this in App.init
    func configure() {
        #if canImport(FirebaseCore)
        // Only configure if not already configured
        if FirebaseApp.app() == nil {
            FirebaseApp.configure()
        }
        #endif

        // Enable analytics
        #if canImport(FirebaseAnalytics)
        Analytics.setAnalyticsCollectionEnabled(true)
        #endif

        // Start session tracking
        startSession()
    }

    // MARK: - Session Tracking

    /// Start a new session
    func startSession() {
        sessionStartTime = Date()
        sessionId = UUID().uuidString
        logEvent("session_start", parameters: [
            "session_id": sessionId ?? ""
        ])
    }

    /// End the current session and log duration
    func endSession() {
        guard let start = sessionStartTime else { return }
        let duration = Date().timeIntervalSince(start)
        logEvent("session_end", parameters: [
            "session_id": sessionId ?? "",
            "duration_seconds": Int(duration)
        ])
        sessionStartTime = nil
        sessionId = nil
    }

    /// Track app going to background
    func trackAppBackground() {
        guard let start = sessionStartTime else { return }
        let duration = Date().timeIntervalSince(start)
        logEvent("app_background", parameters: [
            "session_duration_seconds": Int(duration)
        ])
    }

    /// Track app coming to foreground
    func trackAppForeground() {
        logEvent("app_foreground", parameters: nil)
    }

    // MARK: - Screen Tracking

    /// Track screen view with automatic duration calculation
    func trackScreen(_ screenName: String, screenClass: String? = nil) {
        #if canImport(FirebaseAnalytics)
        var params: [String: Any] = [
            AnalyticsParameterScreenName: screenName
        ]
        if let screenClass = screenClass {
            params[AnalyticsParameterScreenClass] = screenClass
        }
        Analytics.logEvent(AnalyticsEventScreenView, parameters: params)
        #endif

        // Record start time for duration tracking
        queue.async {
            self.screenStartTimes[screenName] = Date()
        }
    }

    /// Track when user leaves a screen (to calculate time spent)
    func trackScreenExit(_ screenName: String) {
        queue.async {
            guard let startTime = self.screenStartTimes[screenName] else { return }
            let duration = Date().timeIntervalSince(startTime)
            self.screenStartTimes.removeValue(forKey: screenName)

            // Log time spent on screen
            self.logEvent("screen_time", parameters: [
                "screen_name": screenName,
                "duration_seconds": Int(duration)
            ])
        }
    }

    // MARK: - Resort Events

    /// Track resort viewed (when user opens resort detail)
    func trackResortViewed(resortId: String, resortName: String, region: String? = nil) {
        logEvent("resort_viewed", parameters: [
            "resort_id": resortId,
            "resort_name": resortName,
            "region": region ?? ""
        ])
    }

    /// Track resort clicked from list
    func trackResortClicked(resortId: String, resortName: String, source: String) {
        logEvent("resort_clicked", parameters: [
            "resort_id": resortId,
            "resort_name": resortName,
            "source": source // "list", "map", "favorites", "recommendations", "search"
        ])
    }

    /// Track resort added to favorites
    func trackResortFavorited(resortId: String, resortName: String? = nil) {
        logEvent("resort_favorited", parameters: [
            "resort_id": resortId,
            "resort_name": resortName ?? ""
        ])
    }

    /// Track resort removed from favorites
    func trackResortUnfavorited(resortId: String, resortName: String? = nil) {
        logEvent("resort_unfavorited", parameters: [
            "resort_id": resortId,
            "resort_name": resortName ?? ""
        ])
    }

    /// Track share action
    func trackResortShared(resortId: String, resortName: String) {
        logEvent("resort_shared", parameters: [
            "resort_id": resortId,
            "resort_name": resortName
        ])
    }

    /// Track external website visit
    func trackResortWebsiteVisited(resortId: String, resortName: String) {
        logEvent("resort_website_visited", parameters: [
            "resort_id": resortId,
            "resort_name": resortName
        ])
    }

    // MARK: - Trip Events

    /// Track trip created
    func trackTripCreated(resortId: String, resortName: String, durationDays: Int, partySize: Int) {
        logEvent("trip_created", parameters: [
            "resort_id": resortId,
            "resort_name": resortName,
            "duration_days": durationDays,
            "party_size": partySize
        ])
    }

    /// Track trip status changed
    func trackTripStatusChanged(tripId: String, resortName: String, newStatus: String) {
        logEvent("trip_status_changed", parameters: [
            "trip_id": tripId,
            "resort_name": resortName,
            "new_status": newStatus
        ])
    }

    /// Track trip deleted
    func trackTripDeleted(tripId: String, resortName: String) {
        logEvent("trip_deleted", parameters: [
            "trip_id": tripId,
            "resort_name": resortName
        ])
    }

    /// Track trip alert viewed
    func trackTripAlertViewed(tripId: String, alertType: String) {
        logEvent("trip_alert_viewed", parameters: [
            "trip_id": tripId,
            "alert_type": alertType
        ])
    }

    /// Track trip alerts marked as read
    func trackTripAlertsMarkedRead(tripId: String, alertCount: Int) {
        logEvent("trip_alerts_marked_read", parameters: [
            "trip_id": tripId,
            "alert_count": alertCount
        ])
    }

    // MARK: - Recommendations Events

    /// Track recommendations viewed
    func trackRecommendationsViewed(count: Int, radiusKm: Double, source: String) {
        logEvent("recommendations_viewed", parameters: [
            "count": count,
            "radius_km": radiusKm,
            "source": source // "nearby", "global"
        ])
    }

    /// Track recommendation clicked
    func trackRecommendationClicked(resortId: String, resortName: String, rank: Int, score: Double) {
        logEvent("recommendation_clicked", parameters: [
            "resort_id": resortId,
            "resort_name": resortName,
            "rank": rank,
            "score": score
        ])
    }

    // MARK: - Search & Filter Events

    /// Track search performed
    func trackSearch(query: String, resultsCount: Int) {
        logEvent("search_performed", parameters: [
            "query": query,
            "results_count": resultsCount
        ])
    }

    /// Track filter applied
    func trackFilterApplied(filterType: String, filterValue: String) {
        logEvent("filter_applied", parameters: [
            "filter_type": filterType, // "region", "sort", "map_filter"
            "filter_value": filterValue
        ])
    }

    /// Track region filter changed
    func trackRegionFilterChanged(region: String?, previousRegion: String?) {
        logEvent("region_filter_changed", parameters: [
            "new_region": region ?? "all",
            "previous_region": previousRegion ?? "all"
        ])
    }

    /// Track sort option changed
    func trackSortChanged(sortOption: String) {
        logEvent("sort_changed", parameters: [
            "sort_option": sortOption
        ])
    }

    // MARK: - Map Events

    /// Track map interaction
    func trackMapInteraction(action: String) {
        logEvent("map_interaction", parameters: [
            "action": action // "pan", "zoom", "style_change", "filter_change"
        ])
    }

    /// Track map region changed
    func trackMapRegionChanged(region: String) {
        logEvent("map_region_changed", parameters: [
            "region": region
        ])
    }

    /// Track map style changed
    func trackMapStyleChanged(style: String) {
        logEvent("map_style_changed", parameters: [
            "style": style // "standard", "satellite", "hybrid"
        ])
    }

    // MARK: - Snow Quality Events

    /// Track snow quality check
    func trackSnowQualityChecked(resortId: String, quality: String, elevation: String? = nil) {
        logEvent("snow_quality_checked", parameters: [
            "resort_id": resortId,
            "quality": quality,
            "elevation": elevation ?? "all"
        ])
    }

    /// Track elevation changed in detail view
    func trackElevationChanged(resortId: String, elevation: String) {
        logEvent("elevation_changed", parameters: [
            "resort_id": resortId,
            "elevation": elevation
        ])
    }

    // MARK: - Pull to Refresh Events

    /// Track pull to refresh
    func trackPullToRefresh(screen: String) {
        logEvent("pull_to_refresh", parameters: [
            "screen": screen
        ])
    }

    // MARK: - Settings Events

    /// Track settings opened
    func trackSettingsOpened() {
        logEvent("settings_opened", parameters: nil)
    }

    /// Track setting changed
    func trackSettingChanged(setting: String, value: String) {
        logEvent("setting_changed", parameters: [
            "setting": setting,
            "value": value
        ])
    }

    /// Track units changed
    func trackUnitsChanged(unitType: String, value: String) {
        logEvent("units_changed", parameters: [
            "unit_type": unitType, // "temperature", "distance", "snow_depth"
            "value": value
        ])
    }

    /// Track region visibility changed
    func trackRegionVisibilityChanged(region: String, isVisible: Bool) {
        logEvent("region_visibility_changed", parameters: [
            "region": region,
            "is_visible": isVisible
        ])
    }

    /// Track cache cleared
    func trackCacheCleared() {
        logEvent("cache_cleared", parameters: nil)
    }

    // MARK: - Notification Events

    /// Track notification permission requested
    func trackNotificationPermissionRequested(granted: Bool) {
        logEvent("notification_permission_requested", parameters: [
            "granted": granted
        ])
    }

    /// Track notification settings changed
    func trackNotificationSettingChanged(setting: String, enabled: Bool) {
        logEvent("notification_setting_changed", parameters: [
            "setting": setting,
            "enabled": enabled
        ])
    }

    /// Track notification received
    func trackNotificationReceived(type: String) {
        logEvent("notification_received", parameters: [
            "type": type
        ])
    }

    /// Track notification opened
    func trackNotificationOpened(type: String) {
        logEvent("notification_opened", parameters: [
            "type": type
        ])
    }

    // MARK: - Authentication Events

    /// Track sign in
    func trackSignIn(provider: String, isNewUser: Bool) {
        logEvent("sign_in", parameters: [
            "provider": provider,
            "is_new_user": isNewUser
        ])
    }

    /// Track sign out
    func trackSignOut() {
        logEvent("sign_out", parameters: nil)
    }

    /// Track guest mode started
    func trackGuestModeStarted() {
        logEvent("guest_mode_started", parameters: nil)
    }

    // MARK: - Onboarding Events

    /// Track onboarding started
    func trackOnboardingStarted() {
        logEvent("onboarding_started", parameters: nil)
    }

    /// Track onboarding completed
    func trackOnboardingCompleted(regionsSelected: Int) {
        logEvent("onboarding_completed", parameters: [
            "regions_selected": regionsSelected
        ])
    }

    /// Track onboarding region toggled
    func trackOnboardingRegionToggled(region: String, selected: Bool) {
        logEvent("onboarding_region_toggled", parameters: [
            "region": region,
            "selected": selected
        ])
    }

    // MARK: - Feedback Events

    /// Track feedback submitted
    func trackFeedbackSubmitted(type: String) {
        logEvent("feedback_submitted", parameters: [
            "type": type // "bug", "feature", "general"
        ])
    }

    // MARK: - Error Events

    /// Track error encountered
    func trackError(errorType: String, errorMessage: String, screen: String? = nil) {
        logEvent("error_encountered", parameters: [
            "error_type": errorType,
            "error_message": errorMessage,
            "screen": screen ?? ""
        ])
    }

    // MARK: - Crash Reporting

    /// Record a non-fatal error
    func recordError(_ error: Error, context: [String: Any]? = nil) {
        #if canImport(FirebaseCrashlytics)
        if let context = context {
            for (key, value) in context {
                Crashlytics.crashlytics().setCustomValue(value, forKey: key)
            }
        }
        Crashlytics.crashlytics().record(error: error)
        #endif
    }

    /// Set user identifier for crash reports (anonymized)
    func setUserId(_ userId: String?) {
        #if canImport(FirebaseCrashlytics)
        Crashlytics.crashlytics().setUserID(userId ?? "")
        #endif
        #if canImport(FirebaseAnalytics)
        Analytics.setUserID(userId)
        #endif
    }

    /// Set user property for analytics
    func setUserProperty(_ value: String?, forName name: String) {
        #if canImport(FirebaseAnalytics)
        Analytics.setUserProperty(value, forName: name)
        #endif
    }

    /// Log a breadcrumb message for crash context
    func log(_ message: String) {
        #if canImport(FirebaseCrashlytics)
        Crashlytics.crashlytics().log(message)
        #endif
    }

    // MARK: - Private

    private func logEvent(_ name: String, parameters: [String: Any]? = nil) {
        #if canImport(FirebaseAnalytics)
        Analytics.logEvent(name, parameters: parameters)
        #endif

        #if DEBUG
        print("[Analytics] \(name): \(parameters ?? [:])")
        #endif
    }
}
