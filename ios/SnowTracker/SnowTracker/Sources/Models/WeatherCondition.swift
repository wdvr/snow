import Foundation
import SwiftUI

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

    // Precipitation data
    let snowfall24hCm: Double
    let snowfall48hCm: Double
    let snowfall72hCm: Double

    // Ice formation factors
    let hoursAboveIceThreshold: Double
    let maxConsecutiveWarmHours: Double

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
    let rawData: [String: String]?

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
        case hoursAboveIceThreshold = "hours_above_ice_threshold"
        case maxConsecutiveWarmHours = "max_consecutive_warm_hours"
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
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
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
            hoursAboveIceThreshold: 2.0,
            maxConsecutiveWarmHours: 1.5,
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
