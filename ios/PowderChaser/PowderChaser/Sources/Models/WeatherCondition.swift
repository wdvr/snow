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
    case champagnePowder = "champagne_powder"
    case powderDay = "powder_day"
    case excellent = "excellent"
    case great = "great"
    case good = "good"
    case decent = "decent"
    case mediocre = "mediocre"
    case poor = "poor"
    case bad = "bad"
    case horrible = "horrible"
    case unknown = "unknown"

    // MARK: - Backward Compatibility Decoder

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let rawValue = try container.decode(String.self)
        switch rawValue {
        case "fair": self = .decent
        case "slushy": self = .mediocre
        default:
            guard let quality = SnowQuality(rawValue: rawValue) else {
                self = .unknown
                return
            }
            self = quality
        }
    }

    var displayName: String {
        switch self {
        case .champagnePowder: return "Champagne Powder"
        case .powderDay: return "Powder Day"
        case .excellent: return "Excellent"
        case .great: return "Great"
        case .good: return "Good"
        case .decent: return "Decent"
        case .mediocre: return "Mediocre"
        case .poor: return "Poor"
        case .bad: return "Bad"
        case .horrible: return "Horrible"
        case .unknown: return "Unknown"
        }
    }

    var color: Color {
        switch self {
        case .champagnePowder: return Color(red: 0.1, green: 0.2, blue: 0.7)
        case .powderDay: return Color(red: 0.2, green: 0.4, blue: 0.9)
        case .excellent: return Color(red: 0.0, green: 0.65, blue: 0.35) // Emerald green
        case .great: return .green
        case .good: return Color(red: 0.4, green: 0.75, blue: 0.3)
        case .decent: return .yellow
        case .mediocre: return .orange
        case .poor: return Color(red: 0.8, green: 0.3, blue: 0.1)
        case .bad: return .red
        case .horrible: return Color(.label)
        case .unknown: return .gray
        }
    }

    var icon: String {
        switch self {
        case .champagnePowder: return "sparkles"
        case .powderDay: return "snowflake.circle"
        case .excellent: return "snowflake"
        case .great: return "cloud.snow"
        case .good: return "sun.max"
        case .decent: return "cloud.sun"
        case .mediocre: return "cloud"
        case .poor: return "cloud.sleet"
        case .bad: return "exclamationmark.triangle"
        case .horrible: return "xmark.octagon.fill"
        case .unknown: return "questionmark.circle"
        }
    }

    var description: String {
        switch self {
        case .champagnePowder: return "Ultra-light, dry champagne powder"
        case .powderDay: return "Deep fresh powder, perfect conditions"
        case .excellent: return "Fresh powder, excellent conditions"
        case .great: return "Good snow with great coverage"
        case .good: return "Solid conditions, enjoyable skiing"
        case .decent: return "Some ice formation present"
        case .mediocre: return "Limited fresh snow, aging surface"
        case .poor: return "Hard packed, limited fresh snow"
        case .bad: return "Very poor conditions, icy or bare"
        case .horrible: return "Not skiable, no snow or dangerous"
        case .unknown: return "Conditions unknown"
        }
    }

    /// Sort order for sorting resorts by snow quality (lower = better)
    var sortOrder: Int {
        switch self {
        case .champagnePowder: return 1
        case .powderDay: return 2
        case .excellent: return 3
        case .great: return 4
        case .good: return 5
        case .decent: return 6
        case .mediocre: return 7
        case .poor: return 8
        case .bad: return 9
        case .horrible: return 10
        case .unknown: return 99
        }
    }

    /// Detailed explanation for the info (i) indicator
    var detailedInfo: (title: String, description: String, criteria: String) {
        switch self {
        case .champagnePowder:
            return (
                title: "Champagne Powder",
                description: "Ultra-light, dry powder with extremely low moisture content. The lightest, fluffiest snow — legendary conditions.",
                criteria: "Highest ML score — abundant fresh snow, very cold temps, low humidity, no warming"
            )
        case .powderDay:
            return (
                title: "Powder Day",
                description: "Deep fresh powder blanketing the mountain. Outstanding conditions for all types of skiing and riding.",
                criteria: "Very high ML score — deep fresh snow, cold temps, no recent thaw-freeze"
            )
        case .excellent:
            return (
                title: "Excellent - Fresh Powder",
                description: "Deep fresh powder with no recent thaw-freeze events. Great conditions for all types of skiing.",
                criteria: "High ML score from abundant fresh snow, cold temps, and no recent thaw-freeze"
            )
        case .great:
            return (
                title: "Great Conditions",
                description: "Good coverage of recent snow. Surface hasn't iced over. Enjoyable skiing on and off-piste.",
                criteria: "Strong ML score from fresh snow, stable cold temps, limited warming"
            )
        case .good:
            return (
                title: "Good Conditions",
                description: "Solid snow coverage with decent surface quality. Groomed runs in good shape, off-piste still enjoyable.",
                criteria: "Good ML score — fresh snow present, stable temperatures"
            )
        case .decent:
            return (
                title: "Decent - Some Fresh",
                description: "Some fresh snow on top of older base. May have thin crust in places. Groomed runs in good shape.",
                criteria: "Moderate ML score — some fresh snow but aging, or mild warming trends"
            )
        case .mediocre:
            return (
                title: "Mediocre - Aging Snow",
                description: "Limited fresh snow with aging surface. Snow may be getting heavy or crusty. Stick to groomed runs.",
                criteria: "Below-average ML score — minimal recent snowfall, surface degrading"
            )
        case .poor:
            return (
                title: "Poor - Limited Fresh Snow",
                description: "Limited fresh snow. Surface may be firm and packed (cold) or softening (warm). Groomed runs still skiable.",
                criteria: "Low ML score — minimal fresh snow, or surface aging"
            )
        case .bad:
            return (
                title: "Bad - Icy/Refrozen",
                description: "No fresh snow on top of icy base. Recent warm periods have created hard, refrozen surface. Challenging conditions.",
                criteria: "Very low ML score — recent thaw-freeze with no fresh snow to cover ice"
            )
        case .horrible:
            return (
                title: "Not Skiable",
                description: "Dangerous conditions. No snow cover, actively melting, or exposed rocks/grass. Resort may be closed or limited.",
                criteria: "Minimal ML score — no skiable snow, warm temps melting remaining cover"
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

// MARK: - Source Details (Data Transparency)

struct SourceDetails: Codable, Hashable, Sendable {
    let sources: [String: SourceInfo]
    let mergeMethod: String
    let consensusValueCm: Double?
    let sourceCount: Int

    struct SourceInfo: Codable, Hashable, Sendable {
        let snowfall24hCm: Double?
        let status: String  // "consensus", "outlier", or "included"
        let reason: String?

        private enum CodingKeys: String, CodingKey {
            case snowfall24hCm = "snowfall_24h_cm"
            case status
            case reason
        }
    }

    private enum CodingKeys: String, CodingKey {
        case sources
        case mergeMethod = "merge_method"
        case consensusValueCm = "consensus_value_cm"
        case sourceCount = "source_count"
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
    let windGustKmh: Double?
    let maxWindGust24h: Double?
    let visibilityM: Double?
    let minVisibility24hM: Double?
    let weatherDescription: String?

    // Snow quality assessment
    let snowQuality: SnowQuality
    let qualityScore: Double?
    let confidenceLevel: ConfidenceLevel
    let freshSnowCm: Double

    // Data source tracking
    let dataSource: String
    let sourceConfidence: ConfidenceLevel
    let rawData: RawDataWrapper?
    let sourceDetails: SourceDetails?

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
        case windGustKmh = "wind_gust_kmh"
        case maxWindGust24h = "max_wind_gust_24h"
        case visibilityM = "visibility_m"
        case minVisibility24hM = "min_visibility_24h_m"
        case weatherDescription = "weather_description"
        case snowQuality = "snow_quality"
        case qualityScore = "quality_score"
        case confidenceLevel = "confidence_level"
        case freshSnowCm = "fresh_snow_cm"
        case dataSource = "data_source"
        case sourceConfidence = "source_confidence"
        case rawData = "raw_data"
        case sourceDetails = "source_details"
    }

    // MARK: - Computed Properties

    var elevationLevelEnum: ElevationLevel? {
        ElevationLevel(rawValue: elevationLevel)
    }

    /// Snow score on 0-100 scale (derived from ML model's 1.0-6.0 raw score)
    var snowScore: Int? {
        guard let score = qualityScore else { return nil }
        return max(0, min(100, Int(((score - 1.0) / 5.0 * 100).rounded())))
    }

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.unitsStyle = .abbreviated
        return f
    }()

    var formattedTimestamp: String {
        guard let date = parsedTimestamp else {
            return "Unknown time"
        }
        return Self.relativeFormatter.localizedString(for: date, relativeTo: Date())
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

    /// Hours since last thaw-freeze event
    var formattedTimeSinceFreeze: String {
        guard let hours = lastFreezeThawHoursAgo else {
            return "Unknown"
        }
        // Backend caps at 336h (14 days) due to Open-Meteo history limit
        if hours >= 336 {
            return "14+ days ago"
        } else if hours >= 72 {
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
        case notSkiable = "Not Skiable"
        case unknown = "Unknown"

        var icon: String {
            switch self {
            case .freshPowder: return "snowflake"
            case .oldPowder: return "cloud.snow"
            case .icy: return "thermometer.snowflake"
            case .notSkiable: return "xmark.octagon.fill"
            case .unknown: return "questionmark.circle"
            }
        }

        var color: Color {
            switch self {
            case .freshPowder: return .cyan
            case .oldPowder: return .blue
            case .icy: return .orange
            case .notSkiable: return Color(.label)
            case .unknown: return .gray
            }
        }
    }

    /// Determine surface type based on fresh snow, temperature and time since freeze
    var surfaceType: SurfaceType {
        // If snow quality is horrible (not skiable), surface type should match
        // This handles warm temperatures that make skiing impossible
        if snowQuality == .horrible {
            return .notSkiable
        }

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

    // Static formatters for timestamp parsing (avoid per-call allocation)
    private static let isoFractionalFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let isoBasicFormatter = ISO8601DateFormatter()

    private static let isoFlexFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withTimeZone]
        return f
    }()

    /// Parse timestamp handling multiple ISO8601 formats
    private var parsedTimestamp: Date? {
        // Guard against empty timestamp
        guard !timestamp.isEmpty else { return nil }

        // Try parsing with fractional seconds first (API returns timestamps like "2026-01-25T21:18:24.110234+00:00")
        if let date = Self.isoFractionalFormatter.date(from: timestamp) {
            return date
        }

        // Fallback to standard ISO8601 without fractional seconds
        if let date = Self.isoBasicFormatter.date(from: timestamp) {
            return date
        }

        // Try with timezone designator variations
        if let date = Self.isoFlexFormatter.date(from: timestamp) {
            return date
        }

        // Try DateFormatter for more flexible parsing (handles "Z" suffix, various formats)
        // Create a new formatter per call to avoid thread-safety issues with shared DateFormatter
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

    /// Format fresh snow according to user preferences.
    /// Prefers 24h snowfall when available (most relevant to users), falls back to accumulated since thaw.
    func formattedFreshSnowWithPrefs(_ prefs: UnitPreferences) -> String {
        if snowfall24hCm >= 0.5 {
            return "\(Self.formatSnow(snowfall24hCm, prefs: prefs))/24h"
        }
        if freshSnowCm < 0.1 {
            return "No new snow"
        }
        return "\(Self.formatSnow(freshSnowCm, prefs: prefs)) fresh"
    }

    /// The most relevant snow label for stat displays: "24h" or "Fresh"
    var freshSnowLabel: String {
        snowfall24hCm >= 0.5 ? "24h" : "Fresh"
    }

    /// The most relevant fresh snow value in cm for stat displays
    var displayFreshSnowCm: Double {
        snowfall24hCm >= 0.5 ? snowfall24hCm : freshSnowCm
    }

    /// Format snow since freeze according to user preferences
    func formattedSnowSinceFreezeWithPrefs(_ prefs: UnitPreferences) -> String {
        let cm = snowSinceFreeze
        if cm < 0.1 {
            return "No fresh snow"
        }
        return "\(Self.formatSnow(cm, prefs: prefs)) fresh"
    }

    /// Format wind speed according to user preferences
    func formattedWindSpeedWithPrefs(_ prefs: UnitPreferences) -> String {
        guard let wind = windSpeedKmh else { return "No wind data" }
        switch prefs.distance {
        case .metric:
            return "\(Int(wind)) km/h"
        case .imperial:
            let mph = wind * 0.621371
            return "\(Int(mph)) mph"
        }
    }

    /// Format wind gust speed according to user preferences
    func formattedWindGustWithPrefs(_ prefs: UnitPreferences) -> String {
        guard let gust = windGustKmh else { return "No gust data" }
        switch prefs.distance {
        case .metric:
            return "\(Int(gust)) km/h"
        case .imperial:
            let mph = gust * 0.621371
            return "\(Int(mph)) mph"
        }
    }

    /// Format wind speed value in user-preferred units (static helper)
    static func formatWindSpeed(_ kmh: Double, prefs: UnitPreferences) -> String {
        switch prefs.distance {
        case .metric:
            return "\(Int(kmh)) km/h"
        case .imperial:
            let mph = kmh * 0.621371
            return "\(Int(mph)) mph"
        }
    }

    /// Format visibility distance for display
    static func formatVisibility(_ meters: Double, prefs: UnitPreferences) -> String {
        switch prefs.distance {
        case .metric:
            if meters < 1000 {
                return "\(Int(meters)) m"
            }
            return String(format: "%.1f km", meters / 1000.0)
        case .imperial:
            let miles = meters / 1609.344
            if miles < 0.5 {
                let feet = meters * 3.28084
                return "\(Int(feet)) ft"
            }
            return String(format: "%.1f mi", miles)
        }
    }

    /// Visibility category based on distance in meters
    enum VisibilityCategory {
        case veryPoor   // < 500m
        case poor       // < 1000m
        case low        // < 2000m
        case moderate   // < 5000m
        case good       // >= 5000m

        var label: String {
            switch self {
            case .veryPoor: return "Very Poor"
            case .poor: return "Poor"
            case .low: return "Low"
            case .moderate: return "Moderate"
            case .good: return "Good"
            }
        }

        var color: Color {
            switch self {
            case .veryPoor: return .red
            case .poor: return .orange
            case .low: return .yellow
            case .moderate: return .secondary
            case .good: return .green
            }
        }

        /// Whether this category should be shown as a warning
        var isNotable: Bool {
            self != .good
        }
    }

    /// Determine visibility category from meters
    static func visibilityCategory(meters: Double) -> VisibilityCategory {
        if meters < 500 { return .veryPoor }
        if meters < 1000 { return .poor }
        if meters < 2000 { return .low }
        if meters < 5000 { return .moderate }
        return .good
    }

    /// Whether wind conditions are notable (gusts > 50 km/h)
    var hasNotableWindGust: Bool {
        guard let gust = windGustKmh else { return false }
        return gust >= 50
    }

    /// Whether visibility is poor enough to show a warning (< 5000m)
    var hasPoorVisibility: Bool {
        guard let vis = visibilityM else { return false }
        return vis < 5000
    }

    /// Format 24h snowfall according to user preferences
    func formattedSnowfall24hWithPrefs(_ prefs: UnitPreferences) -> String {
        if snowfall24hCm < 0.1 {
            return "No new snow"
        }
        return Self.formatSnow(snowfall24hCm, prefs: prefs)
    }
}

// MARK: - Weather Overlay Type

enum WeatherOverlayType {
    case snow
    case sun
    case wind
    case none
}

extension WeatherCondition {
    /// Determine which weather overlay to show. Snow > Wind > Sun > None.
    var weatherOverlayType: WeatherOverlayType {
        // Snow: active snowfall or recent fresh snow
        if snowfall24hCm > 2 || freshSnowCm > 5 {
            return .snow
        }

        // Wind: strong winds or gusts
        if let wind = windSpeedKmh, wind > 40 {
            return .wind
        }
        if let gust = windGustKmh, gust > 60 {
            return .wind
        }

        // Sun: clear or sunny weather
        if let desc = weatherDescription?.lowercased(),
           desc.contains("clear") || desc.contains("sunny") {
            return .sun
        }

        return .none
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
            windGustKmh: 35.0,
            maxWindGust24h: 55.0,
            visibilityM: 800.0,
            minVisibility24hM: 400.0,
            weatherDescription: "Heavy snow",
            snowQuality: .excellent,
            qualityScore: 5.8,
            confidenceLevel: .high,
            freshSnowCm: 18.5,
            dataSource: "weatherapi",
            sourceConfidence: .high,
            rawData: nil,
            sourceDetails: nil
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
            windGustKmh: 45.0,
            maxWindGust24h: 60.0,
            visibilityM: 6000.0,
            minVisibility24hM: 3000.0,
            weatherDescription: "Light snow",
            snowQuality: .good,
            qualityScore: 4.6,
            confidenceLevel: .medium,
            freshSnowCm: 8.5,
            dataSource: "weatherapi",
            sourceConfidence: .medium,
            rawData: nil,
            sourceDetails: nil
        )
    ]
}
