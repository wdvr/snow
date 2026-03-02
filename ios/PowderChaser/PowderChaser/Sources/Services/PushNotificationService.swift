import Foundation
import UserNotifications
import UIKit
import os.log

extension Notification.Name {
    static let didReceiveForegroundNotification = Notification.Name("didReceiveForegroundNotification")
}

private let pushLog = Logger(subsystem: "com.snowtracker.app", category: "PushNotifications")

// MARK: - Push Notification Service

@MainActor
final class PushNotificationService: NSObject, ObservableObject {
    static let shared = PushNotificationService()

    @Published var isAuthorized: Bool = false
    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined
    @Published var deviceToken: String?
    @Published var pendingResortId: String?

    private let apiClient = APIClient.shared
    private let notificationCenter = UNUserNotificationCenter.current()

    private override init() {
        super.init()
        notificationCenter.delegate = self
        Task {
            await checkAuthorizationStatus()
        }
    }

    // MARK: - Authorization

    /// Check current notification authorization status
    func checkAuthorizationStatus() async {
        let settings = await notificationCenter.notificationSettings()
        authorizationStatus = settings.authorizationStatus
        isAuthorized = settings.authorizationStatus == .authorized
    }

    /// Request notification permissions
    func requestAuthorization() async -> Bool {
        do {
            let granted = try await notificationCenter.requestAuthorization(
                options: [.alert, .badge, .sound]
            )

            await checkAuthorizationStatus()

            if granted {
                await registerForRemoteNotifications()
            }

            return granted
        } catch {
            pushLog.error("Error requesting notification authorization: \(error)")
            return false
        }
    }

    /// Register for remote notifications (call after authorization is granted)
    func registerForRemoteNotifications() async {
        await MainActor.run {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    // MARK: - Device Token Management

    /// Called when device token is received from APNs
    func didRegisterForRemoteNotifications(withDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        self.deviceToken = tokenString
        pushLog.debug("APNs device token registered")

        // Register token with backend
        Task {
            await registerTokenWithBackend(tokenString)
        }
    }

    /// Called when registration fails
    func didFailToRegisterForRemoteNotifications(withError error: Error) {
        pushLog.error("Failed to register for remote notifications: \(error)")
    }

    /// Re-register the device token with the backend when auth state changes.
    /// This ensures the token is stored under the authenticated user's ID
    /// rather than the anonymous device:UUID fallback.
    func reregisterTokenIfNeeded() async {
        guard let token = deviceToken else { return }
        await registerTokenWithBackend(token)
    }

    /// Register token with backend API
    private func registerTokenWithBackend(_ token: String) async {
        // Always register — the backend uses optional auth and falls back to
        // device:UUID if not authenticated, so the token is stored either way.
        do {
            try await apiClient.registerDeviceToken(
                deviceId: getDeviceId(),
                token: token,
                platform: "ios",
                appVersion: getAppVersion()
            )
            pushLog.debug("Device token registered with backend")
            AnalyticsService.shared.trackPushTokenRegistered(success: true)
        } catch {
            pushLog.error("Failed to register device token with backend: \(error)")
            AnalyticsService.shared.trackPushTokenRegistered(success: false)
        }
    }

    /// Unregister device token when user signs out
    func unregisterDeviceToken() async {
        guard AuthenticationService.shared.isAuthenticated else { return }

        do {
            try await apiClient.unregisterDeviceToken(deviceId: getDeviceId())
            pushLog.debug("Device token unregistered from backend")
        } catch {
            pushLog.error("Failed to unregister device token: \(error)")
        }
    }

    // MARK: - Helpers

    private func getDeviceId() -> String {
        // Use identifierForVendor as device ID
        UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
    }

    private func getAppVersion() -> String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown"
    }

    // MARK: - Badge Management

    func clearBadge() {
        UNUserNotificationCenter.current().setBadgeCount(0) { error in
            if let error = error {
                pushLog.error("Error clearing badge: \(error)")
            }
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension PushNotificationService: UNUserNotificationCenterDelegate {
    /// Called when notification is received while app is in foreground
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // Show notification even when app is in foreground
        completionHandler([.banner, .badge, .sound])
        // Notify bell button to refresh unread count
        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .didReceiveForegroundNotification, object: nil)
        }
    }

    /// Called when user taps on notification
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo

        // Handle notification tap based on type - extract values before crossing actor boundary
        if let notificationType = userInfo["notification_type"] as? String {
            let resortId = userInfo["resort_id"] as? String
            Task { @MainActor in
                self.handleNotificationTap(type: notificationType, resortId: resortId)
            }
        }

        completionHandler()
    }

    private func handleNotificationTap(type: String, resortId: String?) {
        pushLog.debug("Notification tapped: \(type)")

        if let resortId = resortId {
            pushLog.debug("Navigating to resort: \(resortId)")
            pendingResortId = resortId
        }
    }
}

// MARK: - Notification Settings Model

struct NotificationSettings: Codable {
    var notificationsEnabled: Bool
    var freshSnowAlerts: Bool
    var eventAlerts: Bool
    var thawFreezeAlerts: Bool
    var powderAlerts: Bool
    var forecastAlerts: Bool
    var weeklySummary: Bool
    var defaultSnowThresholdCm: Double
    var powderSnowThresholdCm: Double
    var forecastSnowThresholdCm: Double
    var gracePeriodHours: Int
    var resortSettings: [String: ResortNotificationSettings]
    var lastNotified: [String: String]

    enum CodingKeys: String, CodingKey {
        case notificationsEnabled = "notifications_enabled"
        case freshSnowAlerts = "fresh_snow_alerts"
        case eventAlerts = "event_alerts"
        case thawFreezeAlerts = "thaw_freeze_alerts"
        case powderAlerts = "powder_alerts"
        case forecastAlerts = "forecast_alerts"
        case weeklySummary = "weekly_summary"
        case defaultSnowThresholdCm = "default_snow_threshold_cm"
        case powderSnowThresholdCm = "powder_snow_threshold_cm"
        case forecastSnowThresholdCm = "forecast_snow_threshold_cm"
        case gracePeriodHours = "grace_period_hours"
        case resortSettings = "resort_settings"
        case lastNotified = "last_notified"
    }

    init() {
        notificationsEnabled = true
        freshSnowAlerts = true
        eventAlerts = true
        thawFreezeAlerts = true
        powderAlerts = true
        forecastAlerts = true
        weeklySummary = false
        defaultSnowThresholdCm = 1.0
        powderSnowThresholdCm = 15.0
        forecastSnowThresholdCm = 10.0
        gracePeriodHours = 24
        resortSettings = [:]
        lastNotified = [:]
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        notificationsEnabled = try container.decode(Bool.self, forKey: .notificationsEnabled)
        freshSnowAlerts = try container.decode(Bool.self, forKey: .freshSnowAlerts)
        eventAlerts = try container.decode(Bool.self, forKey: .eventAlerts)
        thawFreezeAlerts = try container.decode(Bool.self, forKey: .thawFreezeAlerts)
        powderAlerts = try container.decode(Bool.self, forKey: .powderAlerts)
        forecastAlerts = try container.decodeIfPresent(Bool.self, forKey: .forecastAlerts) ?? true
        weeklySummary = try container.decode(Bool.self, forKey: .weeklySummary)
        defaultSnowThresholdCm = try container.decode(Double.self, forKey: .defaultSnowThresholdCm)
        powderSnowThresholdCm = try container.decode(Double.self, forKey: .powderSnowThresholdCm)
        forecastSnowThresholdCm = try container.decodeIfPresent(Double.self, forKey: .forecastSnowThresholdCm) ?? 10.0
        gracePeriodHours = try container.decode(Int.self, forKey: .gracePeriodHours)
        resortSettings = try container.decode([String: ResortNotificationSettings].self, forKey: .resortSettings)
        lastNotified = try container.decode([String: String].self, forKey: .lastNotified)
    }
}

struct ResortNotificationSettings: Codable {
    var resortId: String
    var freshSnowEnabled: Bool
    var freshSnowThresholdCm: Double
    var eventNotificationsEnabled: Bool
    var powderAlertsEnabled: Bool
    var powderThresholdCm: Double?

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case freshSnowEnabled = "fresh_snow_enabled"
        case freshSnowThresholdCm = "fresh_snow_threshold_cm"
        case eventNotificationsEnabled = "event_notifications_enabled"
        case powderAlertsEnabled = "powder_alerts_enabled"
        case powderThresholdCm = "powder_threshold_cm"
    }
}
