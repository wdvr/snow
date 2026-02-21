import Foundation
import SwiftUI

// Import models
// Note: These will be available since this file is part of the same target

/// Demo data service for App Store screenshots and UI testing
/// Provides beautiful, consistent data that showcases all app features
@MainActor
class DemoDataService {
    static let shared = DemoDataService()

    private init() {}

    /// Whether demo mode is active (enabled via launch arguments)
    var isDemoMode: Bool {
        ProcessInfo.processInfo.arguments.contains("DEMO_DATA")
    }

    /// Whether screenshot mode is active (for UI testing)
    var isScreenshotMode: Bool {
        ProcessInfo.processInfo.arguments.contains("SCREENSHOT_MODE")
    }

    // MARK: - Demo Resorts

    /// Comprehensive set of demo resorts showcasing different regions and conditions
    let demoResorts: [Resort] = [
        // North America - West Coast
        Resort(
            id: "whistler-blackcomb",
            name: "Whistler Blackcomb",
            country: "CA",
            region: "na_west",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 652, elevationFeet: 2140, latitude: 50.1163, longitude: -122.9574, weatherStationId: "whistler-village"),
                ElevationPoint(level: .mid, elevationMeters: 1200, elevationFeet: 3937, latitude: 50.1200, longitude: -122.9550, weatherStationId: "mid-station"),
                ElevationPoint(level: .top, elevationMeters: 2284, elevationFeet: 7494, latitude: 50.1284, longitude: -122.9484, weatherStationId: "peak-2-peak")
            ],
            timezone: "America/Vancouver",
            officialWebsite: "https://www.whistlerblackcomb.com",
            weatherSources: ["weatherapi", "avalanche-canada", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        Resort(
            id: "mammoth-mountain",
            name: "Mammoth Mountain",
            country: "US",
            region: "na_west",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 2424, elevationFeet: 7953, latitude: 37.6308, longitude: -119.0326, weatherStationId: "main-lodge"),
                ElevationPoint(level: .mid, elevationMeters: 2900, elevationFeet: 9515, latitude: 37.6400, longitude: -119.0300, weatherStationId: "mid-chalet"),
                ElevationPoint(level: .top, elevationMeters: 3369, elevationFeet: 11059, latitude: 37.6508, longitude: -119.0274, weatherStationId: "summit")
            ],
            timezone: "America/Los_Angeles",
            officialWebsite: "https://www.mammothmountain.com",
            weatherSources: ["noaa", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        // North America - Rockies
        Resort(
            id: "lake-louise",
            name: "Lake Louise Ski Resort",
            country: "CA",
            region: "na_rockies",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 1645, elevationFeet: 5397, latitude: 51.4178, longitude: -116.1669, weatherStationId: "base-lodge"),
                ElevationPoint(level: .mid, elevationMeters: 2100, elevationFeet: 6890, latitude: 51.4200, longitude: -116.1650, weatherStationId: "whitehorn-lodge"),
                ElevationPoint(level: .top, elevationMeters: 2637, elevationFeet: 8650, latitude: 51.4222, longitude: -116.1631, weatherStationId: "summit-platter")
            ],
            timezone: "America/Edmonton",
            officialWebsite: "https://www.skilouise.com",
            weatherSources: ["environment-canada", "avalanche-canada", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        Resort(
            id: "jackson-hole",
            name: "Jackson Hole Mountain Resort",
            country: "US",
            region: "na_rockies",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 1924, elevationFeet: 6311, latitude: 43.5828, longitude: -110.8278, weatherStationId: "village"),
                ElevationPoint(level: .mid, elevationMeters: 2500, elevationFeet: 8202, latitude: 43.5900, longitude: -110.8250, weatherStationId: "casper-bowl"),
                ElevationPoint(level: .top, elevationMeters: 3185, elevationFeet: 10450, latitude: 43.6028, longitude: -110.8178, weatherStationId: "rendezvous-mountain")
            ],
            timezone: "America/Denver",
            officialWebsite: "https://www.jacksonhole.com",
            weatherSources: ["noaa", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        // European Alps
        Resort(
            id: "chamonix",
            name: "Chamonix Mont-Blanc",
            country: "FR",
            region: "alps",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 1035, elevationFeet: 3396, latitude: 45.9237, longitude: 6.8694, weatherStationId: "chamonix-town"),
                ElevationPoint(level: .mid, elevationMeters: 2000, elevationFeet: 6562, latitude: 45.9100, longitude: 6.9000, weatherStationId: "plan-de-aiguille"),
                ElevationPoint(level: .top, elevationMeters: 3842, elevationFeet: 12605, latitude: 45.8467, longitude: 6.8844, weatherStationId: "aiguille-du-midi")
            ],
            timezone: "Europe/Paris",
            officialWebsite: "https://www.chamonix.com",
            weatherSources: ["meteofrance", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        Resort(
            id: "zermatt",
            name: "Zermatt",
            country: "CH",
            region: "alps",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 1620, elevationFeet: 5315, latitude: 46.0207, longitude: 7.7491, weatherStationId: "zermatt-village"),
                ElevationPoint(level: .mid, elevationMeters: 2500, elevationFeet: 8202, latitude: 46.0100, longitude: 7.7300, weatherStationId: "gornergrat"),
                ElevationPoint(level: .top, elevationMeters: 3883, elevationFeet: 12739, latitude: 45.9755, longitude: 7.7085, weatherStationId: "klein-matterhorn")
            ],
            timezone: "Europe/Zurich",
            officialWebsite: "https://www.zermatt.ch",
            weatherSources: ["meteosuisse", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        // Japan
        Resort(
            id: "niseko-united",
            name: "Niseko United",
            country: "JP",
            region: "japan",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 308, elevationFeet: 1011, latitude: 42.8048, longitude: 140.6875, weatherStationId: "hirafu-village"),
                ElevationPoint(level: .mid, elevationMeters: 800, elevationFeet: 2625, latitude: 42.8100, longitude: 140.6800, weatherStationId: "mid-station"),
                ElevationPoint(level: .top, elevationMeters: 1308, elevationFeet: 4291, latitude: 42.8200, longitude: 140.6700, weatherStationId: "annupuri-peak")
            ],
            timezone: "Asia/Tokyo",
            officialWebsite: "https://www.niseko.ne.jp",
            weatherSources: ["jma", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        ),

        // Oceania
        Resort(
            id: "the-remarkables",
            name: "The Remarkables",
            country: "NZ",
            region: "oceania",
            elevationPoints: [
                ElevationPoint(level: .base, elevationMeters: 1585, elevationFeet: 5200, latitude: -45.0306, longitude: 168.7575, weatherStationId: "base-building"),
                ElevationPoint(level: .mid, elevationMeters: 1800, elevationFeet: 5906, latitude: -45.0200, longitude: 168.7500, weatherStationId: "mid-station"),
                ElevationPoint(level: .top, elevationMeters: 1943, elevationFeet: 6375, latitude: -45.0100, longitude: 168.7400, weatherStationId: "sugar-bowl")
            ],
            timezone: "Pacific/Auckland",
            officialWebsite: "https://www.theremarkables.co.nz",
            weatherSources: ["metservice", "weatherapi", "resort-report"],
            createdAt: "2026-01-20T08:00:00Z",
            updatedAt: "2026-01-27T10:30:00Z"
        )
    ]

    // MARK: - Demo Weather Conditions

    private static let isoFormatter = ISO8601DateFormatter()

    /// Generate beautiful demo conditions for all demo resorts
    func demoConditions(for resortId: String? = nil) -> [String: [WeatherCondition]] {
        let currentTime = Self.isoFormatter.string(from: Date())

        var allConditions: [String: [WeatherCondition]] = [:]

        for resort in demoResorts {
            if let targetResortId = resortId, resort.id != targetResortId {
                continue
            }

            let conditions = generateDemoConditionsForResort(resort, timestamp: currentTime)
            allConditions[resort.id] = conditions
        }

        return allConditions
    }

    private func generateDemoConditionsForResort(_ resort: Resort, timestamp: String) -> [WeatherCondition] {
        var conditions: [WeatherCondition] = []

        // Generate conditions for each elevation level
        for elevationPoint in resort.elevationPoints {
            let condition = generateConditionForElevation(
                resort: resort,
                elevation: elevationPoint,
                timestamp: timestamp
            )
            conditions.append(condition)
        }

        return conditions
    }

    private func generateConditionForElevation(resort: Resort, elevation: ElevationPoint, timestamp: String) -> WeatherCondition {
        // Create realistic conditions based on resort and elevation
        let (quality, temps, snowData) = getRealisticDataForResort(resort, elevation: elevation)

        return WeatherCondition(
            resortId: resort.id,
            elevationLevel: elevation.level.rawValue,
            timestamp: timestamp,
            currentTempCelsius: temps.current,
            minTempCelsius: temps.min,
            maxTempCelsius: temps.max,
            snowfall24hCm: snowData.snowfall24h,
            snowfall48hCm: snowData.snowfall48h,
            snowfall72hCm: snowData.snowfall72h,
            snowDepthCm: elevation.elevationMeters > 2000 ? 180.0 : (elevation.elevationMeters > 1500 ? 120.0 : 80.0),
            predictedSnow24hCm: snowData.predicted24h,
            predictedSnow48hCm: snowData.predicted48h,
            predictedSnow72hCm: snowData.predicted72h,
            hoursAboveIceThreshold: quality == .bad ? 8.0 : (quality == .poor ? 4.0 : 0.0),
            maxConsecutiveWarmHours: quality == .bad ? 6.0 : (quality == .poor ? 2.0 : 0.0),
            snowfallAfterFreezeCm: snowData.freshSnow,
            hoursSinceLastSnowfall: quality == .excellent ? 2.0 : (quality == .good ? 12.0 : 24.0),
            lastFreezeThawHoursAgo: quality == .bad ? 12.0 : (quality == .poor ? 36.0 : 72.0),
            currentlyWarming: temps.current > -2.0,
            humidityPercent: getHumidityForResort(resort),
            windSpeedKmh: getWindSpeedForElevation(elevation.level),
            weatherDescription: getWeatherDescription(quality),
            snowQuality: quality,
            qualityScore: nil,
            confidenceLevel: getConfidenceLevel(quality),
            freshSnowCm: snowData.freshSnow,
            dataSource: "demo-service",
            sourceConfidence: .high,
            rawData: nil
        )
    }

    private func getRealisticDataForResort(_ resort: Resort, elevation: ElevationPoint) -> (quality: SnowQuality, temps: (current: Double, min: Double, max: Double), snowData: (snowfall24h: Double, snowfall48h: Double, snowfall72h: Double, predicted24h: Double, predicted48h: Double, predicted72h: Double, freshSnow: Double)) {

        // Base temperatures on region and elevation
        let baseTemp = getBaseTempForRegion(resort.inferredRegion)
        let elevationAdjustment = -(elevation.elevationMeters / 300.0) // ~2°C cooler per 300m
        let currentTemp = baseTemp + elevationAdjustment

        // Vary conditions to showcase different qualities
        let quality: SnowQuality
        let snowData: (snowfall24h: Double, snowfall48h: Double, snowfall72h: Double, predicted24h: Double, predicted48h: Double, predicted72h: Double, freshSnow: Double)

        switch resort.id {
        case "whistler-blackcomb", "niseko-united":
            // Excellent powder conditions
            quality = .excellent
            snowData = (snowfall24h: 25.0, snowfall48h: 45.0, snowfall72h: 60.0, predicted24h: 20.0, predicted48h: 35.0, predicted72h: 50.0, freshSnow: 28.0)

        case "mammoth-mountain", "chamonix":
            // Good conditions
            quality = .good
            snowData = (snowfall24h: 8.0, snowfall48h: 15.0, snowfall72h: 20.0, predicted24h: 5.0, predicted48h: 12.0, predicted72h: 18.0, freshSnow: 12.0)

        case "lake-louise", "zermatt":
            // Fair conditions
            quality = .fair
            snowData = (snowfall24h: 3.0, snowfall48h: 7.0, snowfall72h: 10.0, predicted24h: 2.0, predicted48h: 8.0, predicted72h: 15.0, freshSnow: 4.5)

        case "jackson-hole":
            // Poor conditions (showcase problem areas)
            quality = .poor
            snowData = (snowfall24h: 0.5, snowfall48h: 2.0, snowfall72h: 3.0, predicted24h: 0.0, predicted48h: 1.0, predicted72h: 3.0, freshSnow: 1.2)

        default:
            // The Remarkables - mix of conditions
            quality = elevation.level == .top ? .good : .fair
            snowData = (snowfall24h: 5.0, snowfall48h: 12.0, snowfall72h: 18.0, predicted24h: 8.0, predicted48h: 15.0, predicted72h: 25.0, freshSnow: 8.0)
        }

        let temps = (
            current: currentTemp,
            min: currentTemp - 5.0,
            max: currentTemp + 3.0
        )

        return (quality, temps, snowData)
    }

    private func getBaseTempForRegion(_ region: SkiRegion) -> Double {
        switch region {
        case .japan: return -4.0 // Japan gets cold
        case .naRockies: return -12.0 // Rocky Mountains are very cold
        case .naWest: return -6.0 // West coast, milder
        case .alps: return -8.0 // Alpine climate
        case .oceania: return -2.0 // Southern hemisphere, not as cold
        default: return -8.0
        }
    }

    private func getHumidityForResort(_ resort: Resort) -> Double {
        switch resort.inferredRegion {
        case .japan: return 95.0 // Very humid
        case .naWest: return 85.0 // Coastal influence
        case .alps: return 75.0 // Continental
        case .naRockies: return 65.0 // Dry mountain air
        case .oceania: return 80.0 // Maritime influence
        default: return 75.0
        }
    }

    private func getWindSpeedForElevation(_ level: ElevationLevel) -> Double {
        switch level {
        case .base: return Double.random(in: 5...15)
        case .mid: return Double.random(in: 15...25)
        case .top: return Double.random(in: 25...40)
        }
    }

    private func getWeatherDescription(_ quality: SnowQuality) -> String {
        switch quality {
        case .excellent: return "Heavy snow"
        case .good: return "Light snow"
        case .fair: return "Partly cloudy"
        case .poor: return "Sunny"
        case .slushy: return "Warm, wet conditions"
        case .bad: return "Rain/snow mix"
        case .horrible: return "Rain"
        case .unknown: return "Conditions unknown"
        }
    }

    private func getConfidenceLevel(_ quality: SnowQuality) -> ConfidenceLevel {
        switch quality {
        case .excellent, .good: return .high
        case .fair: return .medium
        case .poor, .slushy: return .medium
        case .bad, .horrible: return .high
        case .unknown: return .low
        }
    }

    // MARK: - Demo User Preferences

    /// Demo user preferences for consistent screenshot appearance
    let demoPreferences = UnitPreferences(
        temperature: .celsius,
        distance: .metric,
        snowDepth: .centimeters
    )

    /// Demo favorite resorts (for favorites tab screenshots)
    let demoFavorites: Set<String> = [
        "whistler-blackcomb",
        "chamonix",
        "niseko-united"
    ]

    // MARK: - Demo Integration

    /// Replace APIClient methods with demo data when in demo mode
    func shouldUseDemoData() -> Bool {
        return isDemoMode || isScreenshotMode
    }
}
