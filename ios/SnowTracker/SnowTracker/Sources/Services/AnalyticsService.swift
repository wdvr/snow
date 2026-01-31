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
    }

    // MARK: - Event Tracking

    /// Track resort viewed
    func trackResortViewed(resortId: String, resortName: String) {
        logEvent("resort_viewed", parameters: [
            "resort_id": resortId,
            "resort_name": resortName
        ])
    }

    /// Track resort added to favorites
    func trackResortFavorited(resortId: String) {
        logEvent("resort_favorited", parameters: [
            "resort_id": resortId
        ])
    }

    /// Track resort removed from favorites
    func trackResortUnfavorited(resortId: String) {
        logEvent("resort_unfavorited", parameters: [
            "resort_id": resortId
        ])
    }

    /// Track trip created
    func trackTripCreated(resortId: String, durationDays: Int) {
        logEvent("trip_created", parameters: [
            "resort_id": resortId,
            "duration_days": durationDays
        ])
    }

    /// Track recommendations viewed
    func trackRecommendationsViewed(count: Int, radiusKm: Double) {
        logEvent("recommendations_viewed", parameters: [
            "count": count,
            "radius_km": radiusKm
        ])
    }

    /// Track snow quality check
    func trackSnowQualityChecked(resortId: String, quality: String) {
        logEvent("snow_quality_checked", parameters: [
            "resort_id": resortId,
            "quality": quality
        ])
    }

    /// Track search performed
    func trackSearch(query: String, resultsCount: Int) {
        logEvent("search_performed", parameters: [
            "query": query,
            "results_count": resultsCount
        ])
    }

    /// Track sign in
    func trackSignIn(provider: String, isNewUser: Bool) {
        logEvent("sign_in", parameters: [
            "provider": provider,
            "is_new_user": isNewUser
        ])
    }

    // MARK: - Screen Tracking

    func trackScreen(_ screenName: String) {
        #if canImport(FirebaseAnalytics)
        Analytics.logEvent(AnalyticsEventScreenView, parameters: [
            AnalyticsParameterScreenName: screenName
        ])
        #endif
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
    }
}
