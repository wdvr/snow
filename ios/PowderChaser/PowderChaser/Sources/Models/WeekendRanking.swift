import Foundation

// MARK: - Best This Weekend

/// Response of GET /api/v1/rankings/weekend.
struct WeekendRankingsResponse: Codable {
    let window: WeekendWindow
    let scope: String
    let passes: [String]
    let rankings: [WeekendRanking]
    let count: Int
    let generatedAt: String

    private enum CodingKeys: String, CodingKey {
        case window, scope, passes, rankings, count
        case generatedAt = "generated_at"
    }
}

struct WeekendWindow: Codable, Equatable {
    let start: String
    let end: String
    let isDefaultWeekend: Bool

    private enum CodingKeys: String, CodingKey {
        case start, end
        case isDefaultWeekend = "is_default_weekend"
    }

    /// "Sat Nov 21 – Sun Nov 22" (or a single day).
    var displayRange: String {
        guard let startDate = WeekendDateFormat.parse(start),
              let endDate = WeekendDateFormat.parse(end) else {
            return "\(start) – \(end)"
        }
        let startText = WeekendDateFormat.dayMonth.string(from: startDate)
        if start == end {
            return startText
        }
        return "\(startText) – \(WeekendDateFormat.dayMonth.string(from: endDate))"
    }
}

/// Access status for one day in the window.
enum WeekendDayAccess: String, Codable {
    case open
    case passholderOnly = "passholder_only"
    case closed
    case unknown
}

struct WeekendDay: Codable, Identifiable, Equatable {
    let date: String
    let access: WeekendDayAccess
    let forecastSnowCm: Double?
    let powderCm: Double
    let note: String?

    var id: String { date }

    private enum CodingKeys: String, CodingKey {
        case date, access, note
        case forecastSnowCm = "forecast_snow_cm"
        case powderCm = "powder_cm"
    }

    /// Short weekday ("Sat").
    var weekday: String {
        guard let parsed = WeekendDateFormat.parse(date) else { return date }
        return WeekendDateFormat.weekday.string(from: parsed)
    }
}

struct WeekendRanking: Codable, Identifiable, Equatable {
    let resortId: String
    let name: String
    let region: String?
    let stateProvince: String?
    let passes: [String]
    let rank: Int
    let score: Int?
    let forecastWindowCm: Double?
    let snowfall7dCm: Double?
    let baseDepthCm: Double?
    let terrainOpenPct: Double?
    let liftsOpen: Int?
    let liftsTotal: Int?
    let runsOpen: Int?
    let runsTotal: Int?
    let snowScore: Int?
    let accessibleDays: Int
    let windowDays: Int
    let accessStatus: String
    let bestDay: String?
    let bestDayLabel: String?
    let flags: [String]
    let reason: String
    let days: [WeekendDay]

    var id: String { resortId }

    private enum CodingKeys: String, CodingKey {
        case name, region, passes, rank, score, flags, reason, days
        case resortId = "resort_id"
        case stateProvince = "state_province"
        case forecastWindowCm = "forecast_window_cm"
        case snowfall7dCm = "snowfall_7d_cm"
        case baseDepthCm = "base_depth_cm"
        case terrainOpenPct = "terrain_open_pct"
        case liftsOpen = "lifts_open"
        case liftsTotal = "lifts_total"
        case runsOpen = "runs_open"
        case runsTotal = "runs_total"
        case snowScore = "snow_score"
        case accessibleDays = "accessible_days"
        case windowDays = "window_days"
        case accessStatus = "access_status"
        case bestDay = "best_day"
        case bestDayLabel = "best_day_label"
    }

    /// No day in the window is skiable for this user.
    var isInaccessible: Bool { accessibleDays == 0 }

    var isPassholderOnly: Bool { accessStatus == "passholder_only" }

    /// "Best: Sun (powder day)".
    var bestDayText: String? {
        guard let bestDay, let parsed = WeekendDateFormat.parse(bestDay) else { return nil }
        let weekday = WeekendDateFormat.weekday.string(from: parsed)
        if let bestDayLabel {
            return "Best: \(weekday) · \(bestDayLabel)"
        }
        return "Best: \(weekday)"
    }

    /// Lifts/runs open text, e.g. "4/8 lifts · 36/67 runs".
    var terrainText: String? {
        var parts: [String] = []
        if let liftsOpen, let liftsTotal, liftsTotal > 0 {
            parts.append("\(liftsOpen)/\(liftsTotal) lifts")
        }
        if let runsOpen, let runsTotal, runsTotal > 0 {
            parts.append("\(runsOpen)/\(runsTotal) runs")
        }
        if parts.isEmpty, let terrainOpenPct {
            return "\(Int(terrainOpenPct.rounded()))% open"
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }
}

// MARK: - Date helpers

enum WeekendDateFormat {
    /// API dates (YYYY-MM-DD), interpreted as calendar days.
    static let api: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    static let weekday: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone.current
        formatter.setLocalizedDateFormatFromTemplate("EEE")
        return formatter
    }()

    static let dayMonth: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone.current
        formatter.setLocalizedDateFormatFromTemplate("EEE MMM d")
        return formatter
    }()

    static func parse(_ value: String) -> Date? {
        api.date(from: value)
    }

    static func string(_ date: Date) -> String {
        api.string(from: date)
    }
}
