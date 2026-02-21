import Foundation

// MARK: - Timeline Models

struct TimelinePoint: Codable, Identifiable, Sendable {
    var id: String { timestamp }
    let date: String
    let timeLabel: String
    let hour: Int
    let timestamp: String
    let temperatureC: Double
    let windSpeedKmh: Double?
    let snowfallCm: Double
    let snowDepthCm: Double?
    let snowQuality: SnowQuality
    let qualityScore: Double?
    let snowScore: Int?
    let explanation: String?
    let weatherCode: Int?
    let weatherDescription: String?
    let isForecast: Bool

    private enum CodingKeys: String, CodingKey {
        case date
        case timeLabel = "time_label"
        case hour
        case timestamp
        case temperatureC = "temperature_c"
        case windSpeedKmh = "wind_speed_kmh"
        case snowfallCm = "snowfall_cm"
        case snowDepthCm = "snow_depth_cm"
        case snowQuality = "snow_quality"
        case qualityScore = "quality_score"
        case snowScore = "snow_score"
        case explanation
        case weatherCode = "weather_code"
        case weatherDescription = "weather_description"
        case isForecast = "is_forecast"
    }

    /// Day of week abbreviation (e.g., "Mon", "Tue")
    var dayOfWeek: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let dateObj = formatter.date(from: date) else { return "" }
        formatter.dateFormat = "EEE"
        return formatter.string(from: dateObj)
    }

    /// Time label for display (AM, Noon, PM)
    var timeDisplay: String {
        switch timeLabel {
        case "morning": return "AM"
        case "midday": return "Noon"
        case "afternoon": return "PM"
        default: return timeLabel
        }
    }

    /// Whether this point represents today
    var isToday: Bool {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let todayStr = formatter.string(from: Date())
        return date == todayStr
    }

    /// Format temperature for display
    func formattedTemperature(_ prefs: UnitPreferences) -> String {
        switch prefs.temperature {
        case .celsius:
            return "\(Int(temperatureC))°"
        case .fahrenheit:
            let f = temperatureC * 9.0 / 5.0 + 32.0
            return "\(Int(f))°"
        }
    }
}

struct TimelineResponse: Codable, Sendable {
    let timeline: [TimelinePoint]
    let elevationLevel: String
    let elevationMeters: Int
    let resortId: String

    private enum CodingKeys: String, CodingKey {
        case timeline
        case elevationLevel = "elevation_level"
        case elevationMeters = "elevation_meters"
        case resortId = "resort_id"
    }
}
