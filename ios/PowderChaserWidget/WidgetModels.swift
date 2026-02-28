import SwiftUI

// MARK: - Unit Preferences for Widget

struct WidgetUnitPreferences: Codable, Sendable {
    var temperature: TemperatureUnit = .celsius
    var snowDepth: SnowDepthUnit = .centimeters

    enum TemperatureUnit: String, Codable {
        case celsius = "celsius"
        case fahrenheit = "fahrenheit"
    }

    enum SnowDepthUnit: String, Codable {
        case centimeters = "cm"
        case inches = "inches"
    }

    /// Load preferences from shared UserDefaults
    static func load() -> WidgetUnitPreferences {
        guard let defaults = UserDefaults(suiteName: "group.com.wouterdevriendt.snowtracker"),
              let data = defaults.data(forKey: "unitPreferences"),
              let decoded = try? JSONDecoder().decode(WidgetUnitPreferences.self, from: data) else {
            return WidgetUnitPreferences()
        }
        return decoded
    }

    /// Format temperature according to preferences
    func formatTemperature(_ celsius: Double) -> String {
        switch temperature {
        case .celsius:
            return "\(Int(celsius))°"
        case .fahrenheit:
            let fahrenheit = celsius * 9.0/5.0 + 32.0
            return "\(Int(fahrenheit))°"
        }
    }

    /// Format snow depth according to preferences
    func formatSnow(_ cm: Double) -> String {
        switch snowDepth {
        case .centimeters:
            return "\(Int(cm))cm"
        case .inches:
            let inches = cm / 2.54
            return String(format: "%.1f\"", inches)
        }
    }
}

// MARK: - Resort Condition Data for Widget

struct ResortConditionData: Identifiable, Sendable {
    let id = UUID()
    let resortId: String
    let resortName: String
    let location: String
    let snowQuality: WidgetSnowQuality
    let snowScore: Int?
    let temperature: Double
    let freshSnow: Double
    let predictedSnow24h: Double
}

// MARK: - Snow Quality for Widget

enum WidgetSnowQuality: String, Sendable {
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

    /// Initialize with backward compatibility for old quality values
    init(fromString value: String) {
        switch value {
        case "fair": self = .decent
        case "slushy": self = .mediocre
        default: self = WidgetSnowQuality(rawValue: value) ?? .unknown
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
        case .horrible: return "Not Skiable"
        case .unknown: return "Unknown"
        }
    }

    var color: Color {
        switch self {
        case .champagnePowder: return Color(red: 0.1, green: 0.2, blue: 0.7)
        case .powderDay: return Color(red: 0.2, green: 0.4, blue: 0.9)
        case .excellent: return Color(red: 0.0, green: 0.65, blue: 0.35)
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
}

// MARK: - Region Display Helper

/// Maps raw region strings (e.g. "na_rockies_Alberta") to display-friendly location strings.
enum RegionDisplayHelper {
    private static let internalKeys: Set<String> = [
        "na_west", "na_rockies", "na_east", "alps", "scandinavia",
        "japan", "oceania", "south_america", "europe_east", "asia"
    ]

    private static let usStates: [String: String] = [
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "ID": "Idaho",
        "ME": "Maine", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
        "MT": "Montana", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
        "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "OR": "Oregon",
        "PA": "Pennsylvania", "UT": "Utah", "VT": "Vermont", "WA": "Washington",
        "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
    ]

    private static let caProvinces: [String: String] = [
        "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
        "NB": "New Brunswick", "NL": "Newfoundland", "NS": "Nova Scotia",
        "ON": "Ontario", "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon"
    ]

    private static let countryNames: [String: String] = [
        "US": "USA", "CA": "Canada", "FR": "France", "CH": "Switzerland",
        "AT": "Austria", "IT": "Italy", "DE": "Germany", "NO": "Norway",
        "SE": "Sweden", "FI": "Finland", "JP": "Japan", "AU": "Australia",
        "NZ": "New Zealand", "CL": "Chile", "AR": "Argentina", "ES": "Spain",
        "AD": "Andorra", "SI": "Slovenia", "PL": "Poland", "CZ": "Czech Republic",
        "SK": "Slovakia", "RO": "Romania", "BG": "Bulgaria", "KR": "South Korea",
        "CN": "China"
    ]

    /// Format location from raw region and country code into "State/Province, Country" or just "Country".
    static func formatLocation(region: String, country: String) -> String {
        let countryDisplay = countryNames[country] ?? country
        let lowered = region.lowercased()

        // Exact internal key (e.g. "alps") -> just country
        if internalKeys.contains(lowered) {
            return countryDisplay
        }

        // Compound key like "na_rockies_AB" or "alps_FR"
        for key in internalKeys {
            let prefix = key + "_"
            if lowered.hasPrefix(prefix) {
                let suffix = String(region.dropFirst(prefix.count))
                let suffixUpper = suffix.uppercased()

                if let state = usStates[suffixUpper] {
                    return "\(state), \(countryDisplay)"
                }
                if let province = caProvinces[suffixUpper] {
                    return "\(province), \(countryDisplay)"
                }

                // Non-NA compound key (alps_FR) -> just country
                if !key.hasPrefix("na_") {
                    return countryDisplay
                }

                // Full name suffix (e.g. "na_west_British Columbia")
                if suffix.count > 2 {
                    return "\(suffix), \(countryDisplay)"
                }

                return countryDisplay
            }
        }

        // Bare 2-letter code
        if country.uppercased() == "US", let state = usStates[region.uppercased()] {
            return "\(state), \(countryDisplay)"
        }
        if country.uppercased() == "CA", let province = caProvinces[region.uppercased()] {
            return "\(province), \(countryDisplay)"
        }

        // Already readable (e.g. "Hokkaido", "Valais")
        if region.count > 2 {
            return "\(region), \(countryDisplay)"
        }

        return countryDisplay
    }
}

// MARK: - Sample Data

extension ResortConditionData {
    static let sample = ResortConditionData(
        resortId: "big-white",
        resortName: "Big White",
        location: "BC, Canada",
        snowQuality: .excellent,
        snowScore: 92,
        temperature: -8,
        freshSnow: 20,
        predictedSnow24h: 15
    )

    static let sample2 = ResortConditionData(
        resortId: "vail",
        resortName: "Vail",
        location: "CO, USA",
        snowQuality: .good,
        snowScore: 72,
        temperature: -5,
        freshSnow: 12,
        predictedSnow24h: 8
    )

    static let sample3 = ResortConditionData(
        resortId: "chamonix",
        resortName: "Chamonix",
        location: "Haute-Savoie, FR",
        snowQuality: .good,
        snowScore: 68,
        temperature: -6,
        freshSnow: 15,
        predictedSnow24h: 10
    )

    static let sample4 = ResortConditionData(
        resortId: "zermatt",
        resortName: "Zermatt",
        location: "Valais, CH",
        snowQuality: .decent,
        snowScore: 55,
        temperature: -3,
        freshSnow: 8,
        predictedSnow24h: 5
    )

    static let sample5 = ResortConditionData(
        resortId: "niseko",
        resortName: "Niseko United",
        location: "Hokkaido, JP",
        snowQuality: .excellent,
        snowScore: 95,
        temperature: -12,
        freshSnow: 35,
        predictedSnow24h: 20
    )
}
