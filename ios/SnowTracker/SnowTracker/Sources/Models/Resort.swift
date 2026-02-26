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
    let latitude: Double?
    let longitude: Double?
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

    var coordinate: CLLocationCoordinate2D? {
        guard let latitude, let longitude else { return nil }
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
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

    func formattedElevation(prefs: UnitPreferences) -> String {
        prefs.distance == .metric ? formattedMeters : formattedFeet
    }
}

struct Resort: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let country: String
    let region: String
    let city: String?
    let stateProvince: String?
    let elevationPoints: [ElevationPoint]
    let timezone: String
    let officialWebsite: String?
    let trailMapUrl: String?
    let webcamUrl: String?
    let greenRunsPct: Int?
    let blueRunsPct: Int?
    let blackRunsPct: Int?
    let doubleBlackRunsPct: Int?
    let hasSnowmaking: Bool?
    let dayTicketPriceMinUsd: Int?
    let dayTicketPriceMaxUsd: Int?
    let annualSnowfallCm: Int?
    let epicPass: String?
    let ikonPass: String?
    let mountainCollective: String?
    let indyPass: String?
    let familyFriendly: Bool?
    let expertTerrain: Bool?
    let largeResort: Bool?
    let skiInOut: Bool?
    let weatherSources: [String]
    let createdAt: String?
    let updatedAt: String?

    private enum CodingKeys: String, CodingKey {
        case id = "resort_id"
        case name
        case country
        case region
        case city
        case stateProvince = "state_province"
        case elevationPoints = "elevation_points"
        case timezone
        case officialWebsite = "official_website"
        case trailMapUrl = "trail_map_url"
        case webcamUrl = "webcam_url"
        case greenRunsPct = "green_runs_pct"
        case blueRunsPct = "blue_runs_pct"
        case blackRunsPct = "black_runs_pct"
        case doubleBlackRunsPct = "double_black_runs_pct"
        case hasSnowmaking = "has_snowmaking"
        case dayTicketPriceMinUsd = "day_ticket_price_min_usd"
        case dayTicketPriceMaxUsd = "day_ticket_price_max_usd"
        case annualSnowfallCm = "annual_snowfall_cm"
        case epicPass = "epic_pass"
        case ikonPass = "ikon_pass"
        case mountainCollective = "mountain_collective"
        case indyPass = "indy_pass"
        case familyFriendly = "family_friendly"
        case expertTerrain = "expert_terrain"
        case largeResort = "large_resort"
        case skiInOut = "ski_in_out"
        case weatherSources = "weather_sources"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    // Computed properties for UI
    var displayLocation: String {
        // Prefer city + state/province + country when available
        if let city = city, !city.isEmpty {
            let state = stateProvince ?? regionDisplayName
            if state.isEmpty || state == countryName {
                return "\(city), \(countryName)"
            }
            return "\(city), \(state), \(countryName)"
        }

        let readableRegion = regionDisplayName
        // For NA resorts, show "State/Province, Country"
        // For others, if region is meaningful (not a raw key), show "Region, Country"
        // If region is a raw key or empty, show just the country
        if readableRegion.isEmpty || readableRegion == countryName {
            return countryName
        }
        return "\(readableRegion), \(countryName)"
    }

    /// Maps the raw `region` field to a human-readable name.
    /// The region field may contain state/province codes (BC, UT), full names
    /// (British Columbia, Hokkaido), or internal region keys (na_west, alps).
    var regionDisplayName: String {
        let internalKeys: [String] = [
            "na_west", "na_rockies", "na_east", "alps", "scandinavia",
            "japan", "oceania", "south_america", "europe_east", "asia"
        ]

        // US state codes
        let usStates: [String: String] = [
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming"
        ]

        // Canadian province codes
        let caProvinces: [String: String] = [
            "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
            "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
            "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
            "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
            "SK": "Saskatchewan", "YT": "Yukon"
        ]

        let lowered = region.lowercased()

        // Exact internal key -> empty (just show country name)
        if internalKeys.contains(lowered) {
            return ""
        }

        // Compound key like "na_west_BC", "alps_FR", "japan_Hokkaido"
        // Check if region starts with a known internal key prefix followed by "_"
        for key in internalKeys {
            let prefix = key + "_"
            if lowered.hasPrefix(prefix) {
                let suffix = String(region.dropFirst(prefix.count))
                let suffixUpper = suffix.uppercased()

                // Try resolving as a US state or Canadian province code
                if let stateName = usStates[suffixUpper] {
                    return stateName
                }
                if let provinceName = caProvinces[suffixUpper] {
                    return provinceName
                }

                // Non-NA compound keys (alps_FR, scandinavia_NO) -> empty
                if !key.hasPrefix("na_") {
                    return ""
                }

                // NA compound key with a full name suffix (e.g., "na_west_British Columbia")
                // Return the suffix as-is if it looks like a readable name (more than 2 chars)
                if suffix.count > 2 {
                    return suffix
                }

                return ""
            }
        }

        // Bare 2-letter code (legacy data where region = "BC", "CO", etc.)
        if country.uppercased() == "US", let stateName = usStates[region.uppercased()] {
            return stateName
        }
        if country.uppercased() == "CA", let provinceName = caProvinces[region.uppercased()] {
            return provinceName
        }

        // Filter out the scraper artifact "Montana" for non-US resorts
        if country.uppercased() != "US" && region == "Montana" {
            return ""
        }

        // Already a readable name (e.g., "Hokkaido", "Valais", "British Columbia")
        return region
    }

    var countryName: String {
        switch country.uppercased() {
        case "AD": return "Andorra"
        case "AR": return "Argentina"
        case "AT": return "Austria"
        case "AU": return "Australia"
        case "BG": return "Bulgaria"
        case "CA": return "Canada"
        case "CH": return "Switzerland"
        case "CL": return "Chile"
        case "CN": return "China"
        case "CZ": return "Czech Republic"
        case "DE": return "Germany"
        case "ES": return "Spain"
        case "FI": return "Finland"
        case "FR": return "France"
        case "IT": return "Italy"
        case "JP": return "Japan"
        case "KR": return "South Korea"
        case "NO": return "Norway"
        case "NZ": return "New Zealand"
        case "PL": return "Poland"
        case "RO": return "Romania"
        case "SE": return "Sweden"
        case "SI": return "Slovenia"
        case "SK": return "Slovakia"
        case "US": return "United States"
        default: return country
        }
    }

    var elevationRange: String {
        elevationRange(prefs: nil)
    }

    func elevationRange(prefs: UnitPreferences?) -> String {
        let useMetric = prefs?.distance == .metric
        let elevations = elevationPoints.map { useMetric ? Int($0.elevationMeters) : Int($0.elevationFeet) }.sorted()
        guard let min = elevations.first, let max = elevations.last else {
            return "Unknown elevation"
        }
        let unit = useMetric ? "m" : "ft"
        return "\(min) - \(max) \(unit)"
    }

    /// Logo URL derived from official website domain via Google Favicon API
    var logoURL: URL? {
        guard let website = officialWebsite,
              let components = URLComponents(string: website),
              let host = components.host else { return nil }
        return URL(string: "https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://\(host)&size=128")
    }

    /// Initials for fallback when logo isn't available
    var initials: String {
        let words = name.split(separator: " ").filter { !["ski", "resort", "mountain", "area"].contains($0.lowercased()) }
        if words.count >= 2 {
            return String(words[0].prefix(1) + words[1].prefix(1)).uppercased()
        }
        return String(name.prefix(2)).uppercased()
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
            region: "na_west_BC",
            city: "Kelowna",
            stateProvince: "BC",
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
            trailMapUrl: nil,
            webcamUrl: "https://www.skiresort.info/ski-resort/big-white/webcams/",
            greenRunsPct: 18,
            blueRunsPct: 56,
            blackRunsPct: 26,
            doubleBlackRunsPct: nil,
            hasSnowmaking: true,
            dayTicketPriceMinUsd: nil,
            dayTicketPriceMaxUsd: nil,
            annualSnowfallCm: 750,
            epicPass: "7 days",
            ikonPass: nil,
            mountainCollective: nil,
            indyPass: nil,
            familyFriendly: true,
            expertTerrain: nil,
            largeResort: nil,
            skiInOut: true,
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        ),
        Resort(
            id: "lake-louise",
            name: "Lake Louise Ski Resort",
            country: "CA",
            region: "na_rockies_AB",
            city: "Lake Louise",
            stateProvince: "AB",
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
            trailMapUrl: nil,
            webcamUrl: "https://www.skiresort.info/ski-resort/lake-louise/webcams/",
            greenRunsPct: 25,
            blueRunsPct: 45,
            blackRunsPct: 30,
            doubleBlackRunsPct: nil,
            hasSnowmaking: nil,
            dayTicketPriceMinUsd: nil,
            dayTicketPriceMaxUsd: nil,
            annualSnowfallCm: nil,
            epicPass: nil,
            ikonPass: "7 days",
            mountainCollective: nil,
            indyPass: nil,
            familyFriendly: nil,
            expertTerrain: nil,
            largeResort: true,
            skiInOut: nil,
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        ),
        Resort(
            id: "silver-star",
            name: "Silver Star Mountain Resort",
            country: "CA",
            region: "na_west_BC",
            city: "Vernon",
            stateProvince: "BC",
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
            trailMapUrl: nil,
            webcamUrl: "https://www.skiresort.info/ski-resort/silver-star/webcams/",
            greenRunsPct: 20,
            blueRunsPct: 50,
            blackRunsPct: 30,
            doubleBlackRunsPct: nil,
            hasSnowmaking: nil,
            dayTicketPriceMinUsd: nil,
            dayTicketPriceMaxUsd: nil,
            annualSnowfallCm: nil,
            epicPass: nil,
            ikonPass: nil,
            mountainCollective: nil,
            indyPass: nil,
            familyFriendly: nil,
            expertTerrain: nil,
            largeResort: nil,
            skiInOut: nil,
            weatherSources: ["weatherapi", "snow-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-20T08:00:00Z"
        )
    ]
}
