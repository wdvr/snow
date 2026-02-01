import Foundation
import UserNotifications
import UIKit

// MARK: - Push Notification Service

@MainActor
final class PushNotificationService: NSObject, ObservableObject {
    static let shared = PushNotificationService()

    @Published var isAuthorized: Bool = false
    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined
    @Published var deviceToken: String?

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
            print("Error requesting notification authorization: \(error)")
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
        print("APNs device token: \(tokenString)")

        // Register token with backend
        Task {
            await registerTokenWithBackend(tokenString)
        }
    }

    /// Called when registration fails
    func didFailToRegisterForRemoteNotifications(withError error: Error) {
        print("Failed to register for remote notifications: \(error)")
    }

    /// Register token with backend API
    private func registerTokenWithBackend(_ token: String) async {
        guard AuthenticationService.shared.isAuthenticated else {
            print("Not authenticated, skipping token registration")
            return
        }

        do {
            try await apiClient.registerDeviceToken(
                deviceId: getDeviceId(),
                token: token,
                platform: "ios",
                appVersion: getAppVersion()
            )
            print("Device token registered with backend")
        } catch {
            print("Failed to register device token with backend: \(error)")
        }
    }

    /// Unregister device token when user signs out
    func unregisterDeviceToken() async {
        guard AuthenticationService.shared.isAuthenticated else { return }

        do {
            try await apiClient.unregisterDeviceToken(deviceId: getDeviceId())
            print("Device token unregistered from backend")
        } catch {
            print("Failed to unregister device token: \(error)")
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
                print("Error clearing badge: \(error)")
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
    }

    /// Called when user taps on notification
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo

        // Handle notification tap based on type
        if let notificationType = userInfo["notification_type"] as? String {
            handleNotificationTap(type: notificationType, userInfo: userInfo)
        }

        completionHandler()
    }

    private func handleNotificationTap(type: String, userInfo: [AnyHashable: Any]) {
        print("Notification tapped: \(type)")

        // Extract resort ID if available
        if let resortId = userInfo["resort_id"] as? String {
            print("Resort ID: \(resortId)")
            // TODO: Navigate to resort detail view
            // This would typically post a notification or use a navigation coordinator
        }
    }
}

// MARK: - Notification Settings Model

struct NotificationSettings: Codable {
    var notificationsEnabled: Bool
    var freshSnowAlerts: Bool
    var eventAlerts: Bool
    var thawFreezeAlerts: Bool
    var weeklySummary: Bool
    var defaultSnowThresholdCm: Double
    var gracePeriodHours: Int
    var resortSettings: [String: ResortNotificationSettings]
    var lastNotified: [String: String]

    enum CodingKeys: String, CodingKey {
        case notificationsEnabled = "notifications_enabled"
        case freshSnowAlerts = "fresh_snow_alerts"
        case eventAlerts = "event_alerts"
        case thawFreezeAlerts = "thaw_freeze_alerts"
        case weeklySummary = "weekly_summary"
        case defaultSnowThresholdCm = "default_snow_threshold_cm"
        case gracePeriodHours = "grace_period_hours"
        case resortSettings = "resort_settings"
        case lastNotified = "last_notified"
    }

    init() {
        notificationsEnabled = true
        freshSnowAlerts = true
        eventAlerts = true
        thawFreezeAlerts = true
        weeklySummary = false
        defaultSnowThresholdCm = 1.0
        gracePeriodHours = 24
        resortSettings = [:]
        lastNotified = [:]
    }
}

struct ResortNotificationSettings: Codable {
    var resortId: String
    var freshSnowEnabled: Bool
    var freshSnowThresholdCm: Double
    var eventNotificationsEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case freshSnowEnabled = "fresh_snow_enabled"
        case freshSnowThresholdCm = "fresh_snow_threshold_cm"
        case eventNotificationsEnabled = "event_notifications_enabled"
    }
}
