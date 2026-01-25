import Foundation
import SwiftUI

// MARK: - Raw Data Wrapper for arbitrary JSON

struct RawDataWrapper: Codable, Hashable {
    private var storage: [String: JSONValue] = [:]

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let dict = try? container.decode([String: JSONValue].self) {
            storage = dict
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(storage)
    }
}

enum JSONValue: Codable, Hashable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode(Int.self) {
            self = .int(value)
        } else if let value = try? container.decode(Double.self) {
            self = .double(value)
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if container.decodeNil() {
            self = .null
        } else {
            throw DecodingError.typeMismatch(JSONValue.self, DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unknown JSON type"))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .double(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

// MARK: - Weather and Snow Quality Models

enum SnowQuality: String, CaseIterable, Codable {
    case excellent = "excellent"
    case good = "good"
    case fair = "fair"
    case poor = "poor"
    case bad = "bad"
    case unknown = "unknown"

    var displayName: String {
        switch self {
        case .excellent: return "Excellent"
        case .good: return "Good"
        case .fair: return "Fair"
        case .poor: return "Poor"
        case .bad: return "Bad"
        case .unknown: return "Unknown"
        }
    }

    var color: Color {
        switch self {
        case .excellent: return .green
        case .good: return Color(.systemGreen)
        case .fair: return .orange
        case .poor: return Color(.systemOrange)
        case .bad: return .red
        case .unknown: return .gray
        }
    }

    var icon: String {
        switch self {
        case .excellent: return "snowflake"
        case .good: return "cloud.snow"
        case .fair: return "cloud"
        case .poor: return "sun.max"
        case .bad: return "thermometer.sun"
        case .unknown: return "questionmark.circle"
        }
    }

    var description: String {
        switch self {
        case .excellent: return "Fresh powder, perfect conditions"
        case .good: return "Good snow with minimal ice"
        case .fair: return "Some ice formation present"
        case .poor: return "Significant ice, limited fresh snow"
        case .bad: return "Mostly iced, poor conditions"
        case .unknown: return "Conditions unknown"
        }
    }

    /// Detailed explanation for the info (i) indicator
    var detailedInfo: (title: String, description: String, criteria: String) {
        switch self {
        case .excellent:
            return (
                title: "Excellent - Fresh Powder",
                description: "3+ inches of fresh powder on top. No recent thaw-freeze events. Great conditions for all types of skiing.",
                criteria: "3+ inches (7.6+ cm) of snow since last thaw-freeze, currently cold"
            )
        case .good:
            return (
                title: "Good - Soft Surface",
                description: "2+ inches of non-refrozen snow. Surface hasn't iced over. Enjoyable skiing on and off-piste.",
                criteria: "2-3 inches (5-7.6 cm) of snow since last thaw-freeze, temps staying cold"
            )
        case .fair:
            return (
                title: "Fair - Some Fresh",
                description: "About 1 inch of fresh snow on top of older base. May have thin crust in places. Groomed runs in good shape.",
                criteria: "1-2 inches (2.5-5 cm) since last thaw-freeze, or currently warming"
            )
        case .poor:
            return (
                title: "Poor - Thin Cover",
                description: "Less than 1 inch of fresh snow since last ice event. Harder surface with some soft spots.",
                criteria: "Less than 1 inch since last thaw-freeze (3h@+3°C, 6h@+2°C, or 8h@+1°C)"
            )
        case .bad:
            return (
                title: "Icy - Refrozen",
                description: "No fresh snow on top of icy base. Recent warm periods have created hard, refrozen surface. Challenging conditions.",
                criteria: "No snow since last thaw-freeze cycle, surface has refrozen"
            )
        case .unknown:
            return (
                title: "Unknown",
                description: "Insufficient data to assess conditions. Check resort reports directly.",
                criteria: "Weather data unavailable or incomplete"
            )
        }
    }
}

enum ConfidenceLevel: String, CaseIterable, Codable {
    case veryHigh = "very_high"
    case high = "high"
    case medium = "medium"
    case low = "low"
    case veryLow = "very_low"

    private enum CodingKeys: String, CodingKey {
        case veryHigh = "very_high"
        case high = "high"
        case medium = "medium"
        case low = "low"
        case veryLow = "very_low"
    }

    var displayName: String {
        switch self {
        case .veryHigh: return "Very High"
        case .high: return "High"
        case .medium: return "Medium"
        case .low: return "Low"
        case .veryLow: return "Very Low"
        }
    }

    var color: Color {
        switch self {
        case .veryHigh: return .green
        case .high: return Color(.systemGreen)
        case .medium: return .orange
        case .low: return Color(.systemOrange)
        case .veryLow: return .red
        }
    }

    var percentage: Int {
        switch self {
        case .veryHigh: return 95
        case .high: return 85
        case .medium: return 70
        case .low: return 50
        case .veryLow: return 30
        }
    }
}

struct WeatherCondition: Codable, Identifiable, Hashable {
    let id = UUID()
    let resortId: String
    let elevationLevel: String
    let timestamp: String

    // Temperature data
    let currentTempCelsius: Double
    let minTempCelsius: Double
    let maxTempCelsius: Double

    // Precipitation data (past snowfall)
    let snowfall24hCm: Double
    let snowfall48hCm: Double
    let snowfall72hCm: Double

    // Snow predictions (future snowfall) - optional for backward compatibility
    let predictedSnow24hCm: Double?
    let predictedSnow48hCm: Double?
    let predictedSnow72hCm: Double?

    // Ice formation factors
    let hoursAboveIceThreshold: Double
    let maxConsecutiveWarmHours: Double

    // Fresh powder tracking (snow since last thaw-freeze event)
    let snowfallAfterFreezeCm: Double?
    let hoursSinceLastSnowfall: Double?
    let lastFreezeThawHoursAgo: Double?
    let currentlyWarming: Bool?

    // Weather conditions
    let humidityPercent: Double?
    let windSpeedKmh: Double?
    let weatherDescription: String?

    // Snow quality assessment
    let snowQuality: SnowQuality
    let confidenceLevel: ConfidenceLevel
    let freshSnowCm: Double

    // Data source tracking
    let dataSource: String
    let sourceConfidence: ConfidenceLevel
    let rawData: RawDataWrapper?

    private enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case elevationLevel = "elevation_level"
        case timestamp
        case currentTempCelsius = "current_temp_celsius"
        case minTempCelsius = "min_temp_celsius"
        case maxTempCelsius = "max_temp_celsius"
        case snowfall24hCm = "snowfall_24h_cm"
        case snowfall48hCm = "snowfall_48h_cm"
        case snowfall72hCm = "snowfall_72h_cm"
        case predictedSnow24hCm = "predicted_snow_24h_cm"
        case predictedSnow48hCm = "predicted_snow_48h_cm"
        case predictedSnow72hCm = "predicted_snow_72h_cm"
        case hoursAboveIceThreshold = "hours_above_ice_threshold"
        case maxConsecutiveWarmHours = "max_consecutive_warm_hours"
        case snowfallAfterFreezeCm = "snowfall_after_freeze_cm"
        case hoursSinceLastSnowfall = "hours_since_last_snowfall"
        case lastFreezeThawHoursAgo = "last_freeze_thaw_hours_ago"
        case currentlyWarming = "currently_warming"
        case humidityPercent = "humidity_percent"
        case windSpeedKmh = "wind_speed_kmh"
        case weatherDescription = "weather_description"
        case snowQuality = "snow_quality"
        case confidenceLevel = "confidence_level"
        case freshSnowCm = "fresh_snow_cm"
        case dataSource = "data_source"
        case sourceConfidence = "source_confidence"
        case rawData = "raw_data"
    }

    // MARK: - Computed Properties

    var elevationLevelEnum: ElevationLevel? {
        ElevationLevel(rawValue: elevationLevel)
    }

    var formattedTimestamp: String {
        guard let date = ISO8601DateFormatter().date(from: timestamp) else {
            return "Unknown time"
        }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    var currentTempFahrenheit: Double {
        currentTempCelsius * 9.0/5.0 + 32.0
    }

    var formattedCurrentTemp: String {
        "\(Int(currentTempCelsius))°C (\(Int(currentTempFahrenheit))°F)"
    }

    var formattedSnowfall24h: String {
        if snowfall24hCm < 0.1 {
            return "No new snow"
        }
        return "\(String(format: "%.1f", snowfall24hCm))cm"
    }

    var formattedFreshSnow: String {
        if freshSnowCm < 0.1 {
            return "No fresh snow"
        }
        return "\(String(format: "%.1f", freshSnowCm))cm fresh"
    }

    /// Fresh snow since last thaw-freeze event (the key quality metric)
    var snowSinceFreeze: Double {
        snowfallAfterFreezeCm ?? freshSnowCm
    }

    /// Formatted fresh snow since freeze in inches
    var formattedSnowSinceFreezeInches: String {
        let inches = snowSinceFreeze / 2.54
        if inches < 0.1 {
            return "No fresh snow"
        }
        return String(format: "%.1f\" fresh", inches)
    }

    /// Hours since last thaw-freeze event
    var formattedTimeSinceFreeze: String {
        guard let hours = lastFreezeThawHoursAgo else {
            return "Unknown"
        }
        if hours >= 72 {
            return "3+ days"
        } else if hours >= 24 {
            return "\(Int(hours / 24))d \(Int(hours.truncatingRemainder(dividingBy: 24)))h"
        } else {
            return "\(Int(hours))h ago"
        }
    }

    var formattedWindSpeed: String {
        guard let windSpeed = windSpeedKmh else { return "No wind data" }
        let windSpeedMph = windSpeed * 0.621371
        return "\(Int(windSpeed))km/h (\(Int(windSpeedMph))mph)"
    }

    var formattedHumidity: String {
        guard let humidity = humidityPercent else { return "No humidity data" }
        return "\(Int(humidity))%"
    }

    var isRecent: Bool {
        guard let date = ISO8601DateFormatter().date(from: timestamp) else {
            return false
        }
        return Date().timeIntervalSince(date) < 3600 // Less than 1 hour old
    }

    var ageInHours: Double {
        guard let date = ISO8601DateFormatter().date(from: timestamp) else {
            return 999.0
        }
        return Date().timeIntervalSince(date) / 3600.0
    }
}

// MARK: - Sample Data

extension WeatherCondition {
    static let sampleConditions: [WeatherCondition] = [
        WeatherCondition(
            resortId: "big-white",
            elevationLevel: "top",
            timestamp: "2026-01-20T10:00:00Z",
            currentTempCelsius: -8.0,
            minTempCelsius: -12.0,
            maxTempCelsius: -4.0,
            snowfall24hCm: 20.0,
            snowfall48hCm: 35.0,
            snowfall72hCm: 40.0,
            predictedSnow24hCm: 15.0,
            predictedSnow48hCm: 25.0,
            predictedSnow72hCm: 30.0,
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
            snowfallAfterFreezeCm: 18.5,
            hoursSinceLastSnowfall: 2.0,
            lastFreezeThawHoursAgo: 48.0,
            currentlyWarming: false,
            humidityPercent: 90.0,
            windSpeedKmh: 15.0,
            weatherDescription: "Heavy snow",
            snowQuality: .excellent,
            confidenceLevel: .high,
            freshSnowCm: 18.5,
            dataSource: "weatherapi",
            sourceConfidence: .high,
            rawData: nil
        ),
        WeatherCondition(
            resortId: "big-white",
            elevationLevel: "base",
            timestamp: "2026-01-20T10:00:00Z",
            currentTempCelsius: -2.0,
            minTempCelsius: -5.0,
            maxTempCelsius: 1.0,
            snowfall24hCm: 12.0,
            snowfall48hCm: 20.0,
            snowfall72hCm: 25.0,
            predictedSnow24hCm: 8.0,
            predictedSnow48hCm: 15.0,
            predictedSnow72hCm: 20.0,
            hoursAboveIceThreshold: 2.0,
            maxConsecutiveWarmHours: 1.5,
            snowfallAfterFreezeCm: 8.5,
            hoursSinceLastSnowfall: 6.0,
            lastFreezeThawHoursAgo: 24.0,
            currentlyWarming: false,
            humidityPercent: 80.0,
            windSpeedKmh: 20.0,
            weatherDescription: "Light snow",
            snowQuality: .good,
            confidenceLevel: .medium,
            freshSnowCm: 8.5,
            dataSource: "weatherapi",
            sourceConfidence: .medium,
            rawData: nil
        )
    ]
}
