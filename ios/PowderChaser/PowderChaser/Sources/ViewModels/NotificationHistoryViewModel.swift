import SwiftUI
import UserNotifications
import os.log

@MainActor
final class NotificationHistoryViewModel: ObservableObject {
    @Published var notifications: [NotificationHistoryItem] = []
    @Published var unreadCount: Int = 0 {
        didSet { updateAppBadge() }
    }
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var cursor: String?
    private var hasMore = true
    private let apiClient = APIClient.shared
    private let log = Logger(subsystem: "com.snowtracker.app", category: "NotificationHistoryVM")

    /// Sync the app icon badge with the unread notification count
    private func updateAppBadge() {
        let count = unreadCount
        UNUserNotificationCenter.current().setBadgeCount(count) { [self] error in
            if let error {
                log.error("Failed to set badge count: \(error.localizedDescription)")
            }
        }
    }

    func loadNotifications() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.getNotificationHistory(limit: 30)
            notifications = response.notifications
            cursor = response.cursor
            hasMore = response.cursor != nil
            errorMessage = nil
        } catch {
            log.error("Error loading notifications: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }

    func loadMore() async {
        guard hasMore, !isLoading, let cursor else { return }

        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.getNotificationHistory(limit: 30, cursor: cursor)
            notifications.append(contentsOf: response.notifications)
            self.cursor = response.cursor
            hasMore = response.cursor != nil
        } catch {
            log.error("Error loading more notifications: \(error.localizedDescription)")
        }
    }

    func markAsRead(_ notification: NotificationHistoryItem) async {
        guard notification.isUnread else { return }

        do {
            try await apiClient.markNotificationRead(notificationId: notification.notificationId)
            if let index = notifications.firstIndex(where: { $0.id == notification.id }) {
                // Create updated item with read_at set
                let item = notifications[index]
                let updated = NotificationHistoryItem(
                    notificationId: item.notificationId,
                    notificationType: item.notificationType,
                    resortId: item.resortId,
                    resortName: item.resortName,
                    title: item.title,
                    body: item.body,
                    sentAt: item.sentAt,
                    readAt: ISO8601DateFormatter().string(from: Date()),
                    data: item.data
                )
                notifications[index] = updated
            }
            unreadCount = max(0, unreadCount - 1)
        } catch {
            log.error("Error marking notification as read: \(error.localizedDescription)")
        }
    }

    func markAllAsRead() async {
        do {
            try await apiClient.markAllNotificationsRead()
            // Update all local items to read
            notifications = notifications.map { item in
                guard item.isUnread else { return item }
                return NotificationHistoryItem(
                    notificationId: item.notificationId,
                    notificationType: item.notificationType,
                    resortId: item.resortId,
                    resortName: item.resortName,
                    title: item.title,
                    body: item.body,
                    sentAt: item.sentAt,
                    readAt: ISO8601DateFormatter().string(from: Date()),
                    data: item.data
                )
            }
            unreadCount = 0
        } catch {
            log.error("Error marking all as read: \(error.localizedDescription)")
        }
    }

    func deleteNotification(_ notification: NotificationHistoryItem) async {
        // Optimistic: remove locally first
        let wasUnread = notification.isUnread
        notifications.removeAll { $0.id == notification.id }
        if wasUnread {
            unreadCount = max(0, unreadCount - 1)
        }

        do {
            try await apiClient.deleteNotification(notificationId: notification.notificationId)
        } catch {
            log.error("Error deleting notification: \(error.localizedDescription)")
            // Don't re-add — user intent is clear, server will catch up on next deploy
        }
    }

    func deleteAllNotifications() async {
        let previousNotifications = notifications
        let previousUnread = unreadCount

        // Optimistic: clear locally
        notifications = []
        unreadCount = 0

        do {
            try await apiClient.deleteAllNotifications()
        } catch {
            log.error("Error deleting all notifications: \(error.localizedDescription)")
            // Restore on failure
            notifications = previousNotifications
            unreadCount = previousUnread
        }
    }

    func fetchUnreadCount() async {
        do {
            unreadCount = try await apiClient.getUnreadNotificationCount()
        } catch {
            log.error("Error fetching unread count: \(error.localizedDescription)")
        }
    }
}
