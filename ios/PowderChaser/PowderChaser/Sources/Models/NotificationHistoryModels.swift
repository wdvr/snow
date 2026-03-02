import SwiftUI

// MARK: - Alert Notification Type

enum AlertNotificationType: String, Codable, CaseIterable {
    case freshSnow = "fresh_snow"
    case resortEvent = "resort_event"
    case powderAlert = "powder_alert"
    case conditionsImproved = "conditions_improved"
    case thawAlert = "thaw_alert"
    case freezeAlert = "freeze_alert"
    case weeklySummary = "weekly_summary"
    case forecastSnow = "forecast_snow"

    var displayName: String {
        switch self {
        case .freshSnow: "Fresh Snow"
        case .resortEvent: "Event"
        case .powderAlert: "Powder Day"
        case .conditionsImproved: "Conditions Improved"
        case .thawAlert: "Thaw Alert"
        case .freezeAlert: "Freeze Alert"
        case .weeklySummary: "Weekly Summary"
        case .forecastSnow: "Snow Forecast"
        }
    }

    var icon: String {
        switch self {
        case .freshSnow: "snowflake"
        case .resortEvent: "calendar"
        case .powderAlert: "snowflake.circle.fill"
        case .conditionsImproved: "arrow.up.circle.fill"
        case .thawAlert: "sun.max.fill"
        case .freezeAlert: "thermometer.snowflake"
        case .weeklySummary: "chart.bar.fill"
        case .forecastSnow: "cloud.snow.fill"
        }
    }

    var color: Color {
        switch self {
        case .freshSnow: .blue
        case .resortEvent: .purple
        case .powderAlert: .cyan
        case .conditionsImproved: .green
        case .thawAlert: .orange
        case .freezeAlert: .red
        case .weeklySummary: .indigo
        case .forecastSnow: .teal
        }
    }
}

// MARK: - Notification History Item

struct NotificationHistoryItem: Codable, Identifiable {
    let notificationId: String
    let notificationType: String
    let resortId: String?
    let resortName: String?
    let title: String
    let body: String
    let sentAt: String
    let readAt: String?
    let data: [String: String]?

    var id: String { notificationId }

    private enum CodingKeys: String, CodingKey {
        case notificationId = "notification_id"
        case notificationType = "notification_type"
        case resortId = "resort_id"
        case resortName = "resort_name"
        case title
        case body
        case sentAt = "sent_at"
        case readAt = "read_at"
        case data
    }

    var alertType: AlertNotificationType {
        AlertNotificationType(rawValue: notificationType) ?? .freshSnow
    }

    var isUnread: Bool {
        readAt == nil
    }

    private static let isoFractionalFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let isoBasicFormatter = ISO8601DateFormatter()

    var formattedTimestamp: String {
        let date: Date?
        if let d = Self.isoFractionalFormatter.date(from: sentAt) {
            date = d
        } else if let d = Self.isoBasicFormatter.date(from: sentAt) {
            date = d
        } else {
            date = nil
        }

        guard let date else { return sentAt }

        let interval = Date().timeIntervalSince(date)
        if interval < 60 {
            return "Just now"
        } else if interval < 3600 {
            let minutes = Int(interval / 60)
            return "\(minutes)m ago"
        } else if interval < 86400 {
            let hours = Int(interval / 3600)
            return "\(hours)h ago"
        } else {
            let days = Int(interval / 86400)
            return "\(days)d ago"
        }
    }
}

// MARK: - Response Types

struct NotificationHistoryResponse: Codable {
    let notifications: [NotificationHistoryItem]
    let cursor: String?
}

struct UnreadCountResponse: Codable {
    let unreadCount: Int

    private enum CodingKeys: String, CodingKey {
        case unreadCount = "unread_count"
    }
}
