import Foundation

// MARK: - Daily Snow History

struct DailySnowHistory: Codable, Identifiable {
    let date: String
    let snowfall24hCm: Double
    let snowDepthCm: Double?
    let tempMinC: Double
    let tempMaxC: Double
    let qualityScore: Double?
    let snowQuality: String?

    var id: String { date }

    /// Parse date string into a Date for chart rendering
    var chartDate: Date {
        Self.dateFormatter.date(from: date) ?? Date()
    }

    private enum Formatters {
        static let dateFormatter: DateFormatter = {
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd"
            f.timeZone = TimeZone(identifier: "UTC")
            return f
        }()
    }

    private static let dateFormatter = Formatters.dateFormatter

    enum CodingKeys: String, CodingKey {
        case date
        case snowfall24hCm = "snowfall_24h_cm"
        case snowDepthCm = "snow_depth_cm"
        case tempMinC = "temp_min_c"
        case tempMaxC = "temp_max_c"
        case qualityScore = "quality_score"
        case snowQuality = "snow_quality"
    }
}

// MARK: - Season Summary

struct SeasonSummary: Codable {
    let totalSnowfallCm: Double
    let snowDays: Int
    let avgQualityScore: Double?
    let bestDay: DailySnowHistory?
    let daysTracked: Int

    enum CodingKeys: String, CodingKey {
        case totalSnowfallCm = "total_snowfall_cm"
        case snowDays = "snow_days"
        case avgQualityScore = "avg_quality_score"
        case bestDay = "best_day"
        case daysTracked = "days_tracked"
    }
}

// MARK: - API Response

struct SnowHistoryResponse: Codable {
    let resortId: String
    let history: [DailySnowHistory]
    let seasonSummary: SeasonSummary

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case history
        case seasonSummary = "season_summary"
    }
}
