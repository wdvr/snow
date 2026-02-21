import Foundation
import CoreLocation

// MARK: - Resort Models

enum ElevationLevel: String, CaseIterable, Codable {
    case base = "base"
    case mid = "mid"
    case top = "top"

    var displayName: String {
        switch self {
        case .base: return "Base"
        case .mid: return "Mid"
        case .top: return "Top"
        }
    }

    var icon: String {
        switch self {
        case .base: return "arrowtriangle.down.circle"
        case .mid: return "circle"
        case .top: return "arrowtriangle.up.circle"
        }
    }
}

struct ElevationPoint: Codable, Identifiable, Hashable {
    let id = UUID()
    let level: ElevationLevel
    let elevationMeters: Double
    let elevationFeet: Double
    let latitude: Double
    let longitude: Double
    let weatherStationId: String?

    private enum CodingKeys: String, CodingKey {
        case level
        case elevationMeters = "elevation_meters"
        case elevationFeet = "elevation_feet"
        case latitude
        case longitude
        case weatherStationId = "weather_station_id"
    }

    // Convenience initializer for Int values (used in sample data)
    init(level: ElevationLevel, elevationMeters: Int, elevationFeet: Int, latitude: Double, longitude: Double, weatherStationId: String?) {
        self.level = level
        self.elevationMeters = Double(elevationMeters)
        self.elevationFeet = Double(elevationFeet)
        self.latitude = latitude
        self.longitude = longitude
        self.weatherStationId = weatherStationId
    }

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    var formattedElevation: String {
        "\(formattedFeet) (\(formattedMeters))"
    }

    private static let elevationFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.maximumFractionDigits = 0
        return f
    }()

    var formattedFeet: String {
        (Self.elevationFormatter.string(from: NSNumber(value: elevationFeet)) ?? "\(Int(elevationFeet))") + " ft"
    }

    var formattedMeters: String {
        (Self.elevationFormatter.string(from: NSNumber(value: elevationMeters)) ?? "\(Int(elevationMeters))") + " m"
    }
}

struct Resort: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let country: String
    let region: String
    let elevationPoints: [ElevationPoint]
    let timezone: String
    let officialWebsite: String?
    let weatherSources: [String]
    let createdAt: String?
    let updatedAt: String?

    private enum CodingKeys: String, CodingKey {
        case id = "resort_id"
        case name
        case country
        case region
        case elevationPoints = "elevation_points"
        case timezone
        case officialWebsite = "official_website"
        case weatherSources = "weather_sources"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    // Computed properties for UI
    var displayLocation: String {
        "\(region), \(countryName)"
    }

    var countryName: String {
        switch country.uppercased() {
        case "CA": return "Canada"
        case "US": return "United States"
        case "FR": return "France"
        case "CH": return "Switzerland"
        case "AT": return "Austria"
        case "IT": return "Italy"
        case "JP": return "Japan"
        case "NZ": return "New Zealand"
        case "AU": return "Australia"
        case "CL": return "Chile"
        case "DE": return "Germany"
        case "NO": return "Norway"
        case "SE": return "Sweden"
        default: return country
        }
    }

    var elevationRange: String {
        let elevations = elevationPoints.map { Int($0.elevationFeet) }.sorted()
        guard let min = elevations.first, let max = elevations.last else {
            return "Unknown elevation"
        }
        return "\(min) - \(max) ft"
    }

    var baseElevation: ElevationPoint? {
        elevationPoints.first { $0.level == .base }
    }

    var midElevation: ElevationPoint? {
        elevationPoints.first { $0.level == .mid }
    }

    var topElevation: ElevationPoint? {
        elevationPoints.first { $0.level == .top }
    }

    func elevationPoint(for level: ElevationLevel) -> ElevationPoint? {
        elevationPoints.first { $0.level == level }
    }
}

// MARK: - Extensions

extension Resort {
    static let sampleResorts: [Resort] = [
        Resort(
            id: "big-white",
            name: "Big White Ski Resort",
            country: "CA",
            region: "BC",
            elevationPoints: [
                ElevationPoint(
                    level: .base,
                    elevationMeters: 1508,
                    elevationFeet: 4947,
                    latitude: 49.7167,
                    longitude: -118.9333,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .mid,
                    elevationMeters: 1800,
                    elevationFeet: 5906,
                    latitude: 49.7200,
                    longitude: -118.9300,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .top,
                    elevationMeters: 2319,
                    elevationFeet: 7608,
                    latitude: 49.7233,
                    longitude: -118.9267,
                    weatherStationId: nil
                )
            ],
            timezone: "America/Vancouver",
            officialWebsite: "https://www.bigwhite.com",
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        ),
        Resort(
            id: "lake-louise",
            name: "Lake Louise Ski Resort",
            country: "CA",
            region: "AB",
            elevationPoints: [
                ElevationPoint(
                    level: .base,
                    elevationMeters: 1645,
                    elevationFeet: 5397,
                    latitude: 51.4178,
                    longitude: -116.1669,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .mid,
                    elevationMeters: 2100,
                    elevationFeet: 6890,
                    latitude: 51.4200,
                    longitude: -116.1650,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .top,
                    elevationMeters: 2637,
                    elevationFeet: 8650,
                    latitude: 51.4222,
                    longitude: -116.1631,
                    weatherStationId: nil
                )
            ],
            timezone: "America/Edmonton",
            officialWebsite: "https://www.skilouise.com",
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        ),
        Resort(
            id: "silver-star",
            name: "Silver Star Mountain Resort",
            country: "CA",
            region: "BC",
            elevationPoints: [
                ElevationPoint(
                    level: .base,
                    elevationMeters: 1155,
                    elevationFeet: 3789,
                    latitude: 50.3608,
                    longitude: -119.0581,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .mid,
                    elevationMeters: 1609,
                    elevationFeet: 5279,
                    latitude: 50.3650,
                    longitude: -119.0600,
                    weatherStationId: nil
                ),
                ElevationPoint(
                    level: .top,
                    elevationMeters: 1915,
                    elevationFeet: 6283,
                    latitude: 50.3692,
                    longitude: -119.0619,
                    weatherStationId: nil
                )
            ],
            timezone: "America/Vancouver",
            officialWebsite: "https://www.skisilverstar.com",
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        )
    ]
}
