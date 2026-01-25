import Foundation

// MARK: - Region Model

enum SkiRegion: String, CaseIterable, Identifiable, Codable {
    case naWest = "na_west"
    case naRockies = "na_rockies"
    case naEast = "na_east"
    case alps = "alps"
    case scandinavia = "scandinavia"
    case japan = "japan"
    case oceania = "oceania"
    case southAmerica = "south_america"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .naWest: return "NA West Coast"
        case .naRockies: return "Rockies"
        case .naEast: return "NA East Coast"
        case .alps: return "Alps"
        case .scandinavia: return "Scandinavia"
        case .japan: return "Japan"
        case .oceania: return "Oceania"
        case .southAmerica: return "South America"
        }
    }

    var fullName: String {
        switch self {
        case .naWest: return "North America - West Coast"
        case .naRockies: return "North America - Rocky Mountains"
        case .naEast: return "North America - East Coast"
        case .alps: return "European Alps"
        case .scandinavia: return "Scandinavia"
        case .japan: return "Japan"
        case .oceania: return "Australia & New Zealand"
        case .southAmerica: return "South America"
        }
    }

    var icon: String {
        switch self {
        case .naWest: return "sun.max"
        case .naRockies: return "mountain.2"
        case .naEast: return "snowflake"
        case .alps: return "mountain.2.fill"
        case .scandinavia: return "snowflake.circle"
        case .japan: return "circle.inset.filled"  // Represents Japanese flag
        case .oceania: return "globe.asia.australia"
        case .southAmerica: return "globe.americas"
        }
    }

    var countries: [String] {
        switch self {
        case .naWest: return ["CA", "US"]
        case .naRockies: return ["CA", "US"]
        case .naEast: return ["CA", "US"]
        case .alps: return ["FR", "CH", "AT", "IT", "DE"]
        case .scandinavia: return ["NO", "SE", "FI"]
        case .japan: return ["JP"]
        case .oceania: return ["AU", "NZ"]
        case .southAmerica: return ["CL", "AR"]
        }
    }

    var hemisphere: Hemisphere {
        switch self {
        case .oceania, .southAmerica: return .southern
        default: return .northern
        }
    }

    var seasonMonths: String {
        switch hemisphere {
        case .northern: return "Nov - Apr"
        case .southern: return "Jun - Oct"
        }
    }

    enum Hemisphere {
        case northern
        case southern
    }
}

// MARK: - Region Info (from API)

struct RegionInfo: Codable, Identifiable {
    let id: String
    let name: String
    let displayName: String
    let countries: [String]
    let resortCount: Int

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case displayName = "display_name"
        case countries
        case resortCount = "resort_count"
    }

    var region: SkiRegion? {
        SkiRegion(rawValue: id)
    }
}

// MARK: - Resort Extension for Region

extension Resort {
    /// Infer the region based on country and location
    var inferredRegion: SkiRegion {
        switch country.uppercased() {
        case "CA", "US":
            // Check longitude to distinguish west coast vs rockies vs east
            if let point = elevationPoints.first {
                if point.longitude < -115 {
                    return .naWest
                } else if point.longitude < -100 {
                    return .naRockies
                } else {
                    return .naEast
                }
            }
            return .naRockies
        case "FR", "CH", "AT", "IT", "DE":
            return .alps
        case "NO", "SE", "FI":
            return .scandinavia
        case "JP":
            return .japan
        case "AU", "NZ":
            return .oceania
        case "CL", "AR":
            return .southAmerica
        default:
            return .alps
        }
    }
}
