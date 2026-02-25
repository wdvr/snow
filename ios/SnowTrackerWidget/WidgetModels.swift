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
