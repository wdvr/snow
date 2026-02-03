import Foundation
import SwiftUI

// MARK: - Raw Data Wrapper for arbitrary JSON

struct RawDataWrapper: Codable, Hashable, Sendable {
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

enum JSONValue: Codable, Hashable, Sendable {
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

enum SnowQuality: String, CaseIterable, Codable, Sendable {
    case excellent = "excellent"
    case good = "good"
    case fair = "fair"
    case poor = "poor"
    case bad = "bad"
    case horrible = "horrible"
    case unknown = "unknown"

    var displayName: String {
        switch self {
        case .excellent: return "Excellent"
        case .good: return "Good"
        case .fair: return "Fair"
        case .poor: return "Poor"
        case .bad: return "Icy"
        case .horrible: return "Not Skiable"
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
        case .horrible: return .black
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
        case .horrible: return "xmark.octagon.fill"
        case .unknown: return "questionmark.circle"
        }
    }

    var description: String {
        switch self {
        case .excellent: return "Fresh powder, perfect conditions"
        case .good: return "Good snow with minimal ice"
        case .fair: return "Some ice formation present"
        case .poor: return "Significant ice, limited fresh snow"
        case .bad: return "Icy surface, no fresh snow"
        case .horrible: return "Not skiable, dangerous conditions"
        case .unknown: return "Conditions unknown"
        }
    }

    /// Sort order for sorting resorts by snow quality (lower = better)
    var sortOrder: Int {
        switch self {
        case .excellent: return 1
        case .good: return 2
        case .fair: return 3
        case .poor: return 4
        case .bad: return 5
        case .horrible: return 6
        case .unknown: return 99
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
        case .horrible:
            return (
                title: "Not Skiable",
                description: "Dangerous conditions. No snow cover, actively melting, or exposed rocks/grass. Resort may be closed or limited.",
                criteria: "No skiable snow, warm temps actively melting remaining cover"
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

enum ConfidenceLevel: String, CaseIterable, Codable, Sendable {
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

struct WeatherCondition: Codable, Identifiable, Hashable, Sendable {
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

    // Current snow depth (total snow on ground)
    let snowDepthCm: Double?

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
        case snowDepthCm = "snow_depth_cm"
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
        guard let date = parsedTimestamp else {
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

    /// Total snow depth at this elevation (base snow + fresh)
    var formattedSnowDepth: String {
        guard let depth = snowDepthCm, depth > 0 else {
            return "No snow"
        }
        let inches = depth / 2.54
        return String(format: "%.0fcm (%.0f\")", depth, inches)
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
            let days = Int(hours / 24)
            return "\(days) days ago"
        } else if hours >= 24 {
            return "\(Int(hours / 24))d \(Int(hours.truncatingRemainder(dividingBy: 24)))h ago"
        } else {
            return "\(Int(hours))h ago"
        }
    }

    /// Surface type based on fresh snow and thaw-freeze status
    enum SurfaceType: String {
        case freshPowder = "Fresh Powder"
        case oldPowder = "Old Powder"
        case icy = "Icy"
        case unknown = "Unknown"

        var icon: String {
            switch self {
            case .freshPowder: return "snowflake"
            case .oldPowder: return "cloud.snow"
            case .icy: return "thermometer.snowflake"
            case .unknown: return "questionmark.circle"
            }
        }

        var color: Color {
            switch self {
            case .freshPowder: return .cyan
            case .oldPowder: return .blue
            case .icy: return .orange
            case .unknown: return .gray
            }
        }
    }

    /// Determine surface type based on fresh snow and time since freeze
    var surfaceType: SurfaceType {
        let snowCm = snowSinceFreeze
        let hoursSinceFreeze = lastFreezeThawHoursAgo ?? 0

        // If no thaw-freeze event in 72h and has snow, it's fresh or old powder
        if hoursSinceFreeze >= 72 || snowCm >= 2.54 {  // 1 inch = 2.54cm
            // Fresh powder: snow in last 24-48h
            if let hoursSinceSnow = hoursSinceLastSnowfall, hoursSinceSnow < 48 {
                return .freshPowder
            } else if snowCm >= 2.54 {
                return .oldPowder  // Has coverage but not recent
            }
        }

        // Recent thaw-freeze with little snow = icy
        if snowCm < 2.54 && hoursSinceFreeze < 72 {
            return .icy
        }

        // Default to old powder if we have some snow
        if snowCm > 0 {
            return .oldPowder
        }

        return .icy
    }

    /// Formatted snow since freeze in cm
    var formattedSnowSinceFreezeCm: String {
        let cm = snowSinceFreeze
        if cm < 0.1 {
            return "0 cm"
        }
        return String(format: "%.1f cm", cm)
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
        guard let date = parsedTimestamp else {
            return false
        }
        return Date().timeIntervalSince(date) < 3600 // Less than 1 hour old
    }

    var ageInHours: Double {
        guard let date = parsedTimestamp else {
            return 999.0
        }
        return Date().timeIntervalSince(date) / 3600.0
    }

    /// Parse timestamp handling multiple ISO8601 formats
    private var parsedTimestamp: Date? {
        // Guard against empty timestamp
        guard !timestamp.isEmpty else { return nil }

        // Try parsing with fractional seconds first (API returns timestamps like "2026-01-25T21:18:24.110234+00:00")
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        if let date = isoFormatter.date(from: timestamp) {
            return date
        }

        // Fallback to standard ISO8601 without fractional seconds
        let basicFormatter = ISO8601DateFormatter()
        if let date = basicFormatter.date(from: timestamp) {
            return date
        }

        // Try with timezone designator variations
        let flexFormatter = ISO8601DateFormatter()
        flexFormatter.formatOptions = [.withInternetDateTime, .withTimeZone]
        if let date = flexFormatter.date(from: timestamp) {
            return date
        }

        // Try DateFormatter for more flexible parsing (handles "Z" suffix, various formats)
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        dateFormatter.timeZone = TimeZone(secondsFromGMT: 0)

        // Try common API date formats
        let formats = [
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSSZZZZ",
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSSZ",
            "yyyy-MM-dd'T'HH:mm:ssZZZZ",
            "yyyy-MM-dd'T'HH:mm:ssZ",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss"
        ]

        for format in formats {
            dateFormatter.dateFormat = format
            if let date = dateFormatter.date(from: timestamp) {
                return date
            }
        }

        return nil
    }
}

// MARK: - Unit-Aware Formatting

extension WeatherCondition {
    /// Format temperature according to user preferences
    func formattedTemperature(_ prefs: UnitPreferences) -> String {
        switch prefs.temperature {
        case .celsius:
            return "\(Int(currentTempCelsius))°C"
        case .fahrenheit:
            return "\(Int(currentTempFahrenheit))°F"
        }
    }

    /// Format min temperature according to user preferences
    func formattedMinTemp(_ prefs: UnitPreferences) -> String {
        switch prefs.temperature {
        case .celsius:
            return "\(Int(minTempCelsius))°C"
        case .fahrenheit:
            let fahrenheit = minTempCelsius * 9.0/5.0 + 32.0
            return "\(Int(fahrenheit))°F"
        }
    }

    /// Format max temperature according to user preferences
    func formattedMaxTemp(_ prefs: UnitPreferences) -> String {
        switch prefs.temperature {
        case .celsius:
            return "\(Int(maxTempCelsius))°C"
        case .fahrenheit:
            let fahrenheit = maxTempCelsius * 9.0/5.0 + 32.0
            return "\(Int(fahrenheit))°F"
        }
    }

    /// Format snow depth in cm according to user preferences
    static func formatSnow(_ cm: Double, prefs: UnitPreferences) -> String {
        switch prefs.snowDepth {
        case .centimeters:
            if cm < 0.1 {
                return "0 cm"
            }
            return String(format: "%.1f cm", cm)
        case .inches:
            let inches = cm / 2.54
            if inches < 0.1 {
                return "0\""
            }
            return String(format: "%.1f\"", inches)
        }
    }

    /// Format snow depth in cm according to user preferences (short form without unit for tight spaces)
    static func formatSnowShort(_ cm: Double, prefs: UnitPreferences) -> String {
        switch prefs.snowDepth {
        case .centimeters:
            return String(format: "%.0fcm", cm)
        case .inches:
            let inches = cm / 2.54
            return String(format: "%.1f\"", inches)
        }
    }

    /// Format fresh snow according to user preferences
    func formattedFreshSnowWithPrefs(_ prefs: UnitPreferences) -> String {
        if freshSnowCm < 0.1 {
            return "No fresh snow"
        }
        return "\(Self.formatSnow(freshSnowCm, prefs: prefs)) fresh"
    }

    /// Format snow since freeze according to user preferences
    func formattedSnowSinceFreezeWithPrefs(_ prefs: UnitPreferences) -> String {
        let cm = snowSinceFreeze
        if cm < 0.1 {
            return "No fresh snow"
        }
        return "\(Self.formatSnow(cm, prefs: prefs)) fresh"
    }

    /// Format 24h snowfall according to user preferences
    func formattedSnowfall24hWithPrefs(_ prefs: UnitPreferences) -> String {
        if snowfall24hCm < 0.1 {
            return "No new snow"
        }
        return Self.formatSnow(snowfall24hCm, prefs: prefs)
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
            snowDepthCm: 150.0,
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
            snowDepthCm: 80.0,
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
