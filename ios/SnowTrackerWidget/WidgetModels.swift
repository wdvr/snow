import SwiftUI

// MARK: - Resort Condition Data for Widget

struct ResortConditionData: Identifiable {
    let id = UUID()
    let resortId: String
    let resortName: String
    let location: String
    let snowQuality: WidgetSnowQuality
    let temperature: Double
    let freshSnow: Double
    let predictedSnow24h: Double
}

// MARK: - Snow Quality for Widget

enum WidgetSnowQuality: String {
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
}

// MARK: - Sample Data

extension ResortConditionData {
    static let sample = ResortConditionData(
        resortId: "big-white",
        resortName: "Big White",
        location: "BC, Canada",
        snowQuality: .excellent,
        temperature: -8,
        freshSnow: 20,
        predictedSnow24h: 15
    )

    static let sample2 = ResortConditionData(
        resortId: "vail",
        resortName: "Vail",
        location: "CO, USA",
        snowQuality: .good,
        temperature: -5,
        freshSnow: 12,
        predictedSnow24h: 8
    )
}
