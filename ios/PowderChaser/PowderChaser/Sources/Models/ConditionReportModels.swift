import SwiftUI

// MARK: - Condition Type

enum ConditionType: String, Codable, CaseIterable {
    case powder
    case packedPowder = "packed_powder"
    case soft
    case ice
    case crud
    case spring
    case hardpack
    case windblown

    var displayName: String {
        switch self {
        case .powder: "Powder"
        case .packedPowder: "Packed Powder"
        case .soft: "Soft"
        case .ice: "Ice"
        case .crud: "Crud"
        case .spring: "Spring"
        case .hardpack: "Hardpack"
        case .windblown: "Windblown"
        }
    }

    var icon: String {
        switch self {
        case .powder: "snowflake"
        case .packedPowder: "snowflake.circle"
        case .soft: "cloud.snow"
        case .ice: "thermometer.snowflake"
        case .crud: "wind.snow"
        case .spring: "sun.max"
        case .hardpack: "square.stack.3d.up"
        case .windblown: "wind"
        }
    }

    var color: Color {
        switch self {
        case .powder: .blue
        case .packedPowder: .cyan
        case .soft: .mint
        case .ice: .red
        case .crud: .orange
        case .spring: .yellow
        case .hardpack: .gray
        case .windblown: .purple
        }
    }
}

// MARK: - Elevation Level for Reports

enum ReportElevationLevel: String, Codable, CaseIterable {
    case base
    case mid
    case top

    var displayName: String {
        switch self {
        case .base: "Base"
        case .mid: "Mid"
        case .top: "Top"
        }
    }
}

// MARK: - Condition Report

struct ConditionReport: Codable, Identifiable {
    let reportId: String
    let resortId: String
    let userId: String
    let conditionType: String
    let score: Int
    let comment: String?
    let elevationLevel: String?
    let createdAt: String
    let userName: String?

    var id: String { reportId }

    private enum CodingKeys: String, CodingKey {
        case reportId = "report_id"
        case resortId = "resort_id"
        case userId = "user_id"
        case conditionType = "condition_type"
        case score
        case comment
        case elevationLevel = "elevation_level"
        case createdAt = "created_at"
        case userName = "user_name"
    }

    var condition: ConditionType {
        ConditionType(rawValue: conditionType) ?? .powder
    }

    var elevation: ReportElevationLevel? {
        guard let elevationLevel else { return nil }
        return ReportElevationLevel(rawValue: elevationLevel)
    }

    private static let isoFractionalFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let isoBasicFormatter = ISO8601DateFormatter()

    var formattedTimestamp: String {
        let date: Date?
        if let d = Self.isoFractionalFormatter.date(from: createdAt) {
            date = d
        } else if let d = Self.isoBasicFormatter.date(from: createdAt) {
            date = d
        } else {
            date = nil
        }

        guard let date else { return createdAt }

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

    var scoreLabel: String {
        switch score {
        case 1...2: "Terrible"
        case 3...4: "Poor"
        case 5...6: "Fair"
        case 7...8: "Good"
        case 9...10: "Epic"
        default: "Unknown"
        }
    }
}

// MARK: - Condition Report Summary

struct ConditionReportSummary: Codable {
    let totalReports: Int
    let averageScore: Double?
    let dominantCondition: String?
    let reportsLast24h: Int

    private enum CodingKeys: String, CodingKey {
        case totalReports = "total_reports"
        case averageScore = "average_score"
        case dominantCondition = "dominant_condition"
        case reportsLast24h = "reports_last_24h"
    }

    var dominant: ConditionType? {
        guard let dominantCondition else { return nil }
        return ConditionType(rawValue: dominantCondition)
    }
}

// MARK: - Condition Reports Response

struct ConditionReportsResponse: Codable {
    let reports: [ConditionReport]
    let summary: ConditionReportSummary?
}

// MARK: - Submit Condition Report Request

struct SubmitConditionReportRequest: Codable {
    let conditionType: String
    let score: Int
    let comment: String?
    let elevationLevel: String?

    private enum CodingKeys: String, CodingKey {
        case conditionType = "condition_type"
        case score
        case comment
        case elevationLevel = "elevation_level"
    }
}
