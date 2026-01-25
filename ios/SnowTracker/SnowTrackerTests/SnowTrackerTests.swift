import XCTest
import CoreLocation
import MapKit
@testable import SnowTracker

final class SnowTrackerTests: XCTestCase {

    // MARK: - ElevationLevel Tests

    func testElevationLevelDisplayName() {
        XCTAssertEqual(ElevationLevel.base.displayName, "Base")
        XCTAssertEqual(ElevationLevel.mid.displayName, "Mid")
        XCTAssertEqual(ElevationLevel.top.displayName, "Top")
    }

    func testElevationLevelIcon() {
        XCTAssertEqual(ElevationLevel.base.icon, "arrowtriangle.down.circle")
        XCTAssertEqual(ElevationLevel.mid.icon, "circle")
        XCTAssertEqual(ElevationLevel.top.icon, "arrowtriangle.up.circle")
    }

    func testElevationLevelRawValue() {
        XCTAssertEqual(ElevationLevel.base.rawValue, "base")
        XCTAssertEqual(ElevationLevel.mid.rawValue, "mid")
        XCTAssertEqual(ElevationLevel.top.rawValue, "top")
    }

    func testElevationLevelFromRawValue() {
        XCTAssertEqual(ElevationLevel(rawValue: "base"), .base)
        XCTAssertEqual(ElevationLevel(rawValue: "mid"), .mid)
        XCTAssertEqual(ElevationLevel(rawValue: "top"), .top)
        XCTAssertNil(ElevationLevel(rawValue: "invalid"))
    }

    // MARK: - SnowQuality Tests

    func testSnowQualityDisplayName() {
        XCTAssertEqual(SnowQuality.excellent.displayName, "Excellent")
        XCTAssertEqual(SnowQuality.good.displayName, "Good")
        XCTAssertEqual(SnowQuality.fair.displayName, "Fair")
        XCTAssertEqual(SnowQuality.poor.displayName, "Poor")
        XCTAssertEqual(SnowQuality.bad.displayName, "Bad")
        XCTAssertEqual(SnowQuality.unknown.displayName, "Unknown")
    }

    func testSnowQualityIcon() {
        XCTAssertEqual(SnowQuality.excellent.icon, "snowflake")
        XCTAssertEqual(SnowQuality.good.icon, "cloud.snow")
        XCTAssertEqual(SnowQuality.fair.icon, "cloud")
        XCTAssertEqual(SnowQuality.poor.icon, "sun.max")
        XCTAssertEqual(SnowQuality.bad.icon, "thermometer.sun")
        XCTAssertEqual(SnowQuality.unknown.icon, "questionmark.circle")
    }

    func testSnowQualityDescription() {
        XCTAssertEqual(SnowQuality.excellent.description, "Fresh powder, perfect conditions")
        XCTAssertEqual(SnowQuality.unknown.description, "Conditions unknown")
    }

    // MARK: - ConfidenceLevel Tests

    func testConfidenceLevelPercentage() {
        XCTAssertEqual(ConfidenceLevel.veryHigh.percentage, 95)
        XCTAssertEqual(ConfidenceLevel.high.percentage, 85)
        XCTAssertEqual(ConfidenceLevel.medium.percentage, 70)
        XCTAssertEqual(ConfidenceLevel.low.percentage, 50)
        XCTAssertEqual(ConfidenceLevel.veryLow.percentage, 30)
    }

    func testConfidenceLevelDisplayName() {
        XCTAssertEqual(ConfidenceLevel.veryHigh.displayName, "Very High")
        XCTAssertEqual(ConfidenceLevel.high.displayName, "High")
        XCTAssertEqual(ConfidenceLevel.medium.displayName, "Medium")
        XCTAssertEqual(ConfidenceLevel.low.displayName, "Low")
        XCTAssertEqual(ConfidenceLevel.veryLow.displayName, "Very Low")
    }

    // MARK: - Resort Tests

    func testResortSampleData() {
        XCTAssertFalse(Resort.sampleResorts.isEmpty)
        XCTAssertGreaterThanOrEqual(Resort.sampleResorts.count, 2)
    }

    func testResortCountryName() {
        let canadianResort = Resort.sampleResorts.first { $0.country == "CA" }
        XCTAssertNotNil(canadianResort)
        XCTAssertEqual(canadianResort?.countryName, "Canada")
    }

    func testResortDisplayLocation() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)
        XCTAssertEqual(bigWhite?.displayLocation, "BC, Canada")
    }

    func testResortElevationRange() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)
        // Big White: base 4947ft, top 7608ft
        XCTAssertTrue(bigWhite?.elevationRange.contains("4947") ?? false)
        XCTAssertTrue(bigWhite?.elevationRange.contains("7608") ?? false)
    }

    func testResortElevationPoints() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)
        XCTAssertEqual(bigWhite?.elevationPoints.count, 3)

        // Test getting specific elevations
        XCTAssertNotNil(bigWhite?.baseElevation)
        XCTAssertNotNil(bigWhite?.midElevation)
        XCTAssertNotNil(bigWhite?.topElevation)

        XCTAssertEqual(bigWhite?.baseElevation?.level, .base)
        XCTAssertEqual(bigWhite?.midElevation?.level, .mid)
        XCTAssertEqual(bigWhite?.topElevation?.level, .top)
    }

    func testResortElevationPointForLevel() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)

        let topElevation = bigWhite?.elevationPoint(for: .top)
        XCTAssertNotNil(topElevation)
        XCTAssertEqual(topElevation?.elevationFeet, 7608, accuracy: 1)
    }

    // MARK: - ElevationPoint Tests

    func testElevationPointFormattedElevation() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        let topElevation = bigWhite?.topElevation
        XCTAssertNotNil(topElevation)
        XCTAssertEqual(topElevation?.formattedElevation, "7608ft (2319m)")
    }

    func testElevationPointCoordinate() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        let baseElevation = bigWhite?.baseElevation
        XCTAssertNotNil(baseElevation)

        guard let coordinate = baseElevation?.coordinate else {
            XCTFail("Coordinate should not be nil")
            return
        }
        XCTAssertEqual(coordinate.latitude, 49.7167, accuracy: 0.0001)
        XCTAssertEqual(coordinate.longitude, -118.9333, accuracy: 0.0001)
    }

    // MARK: - WeatherCondition Tests

    func testWeatherConditionSampleData() {
        XCTAssertFalse(WeatherCondition.sampleConditions.isEmpty)
        XCTAssertGreaterThanOrEqual(WeatherCondition.sampleConditions.count, 2)
    }

    func testWeatherConditionTemperatureConversion() {
        let condition = WeatherCondition.sampleConditions.first { $0.elevationLevel == "top" }
        XCTAssertNotNil(condition)

        // -8°C should be about 17.6°F
        let fahrenheit = condition?.currentTempFahrenheit ?? 0
        XCTAssertEqual(fahrenheit, 17.6, accuracy: 0.1)
    }

    func testWeatherConditionFormattedTemp() {
        let condition = WeatherCondition.sampleConditions.first { $0.elevationLevel == "top" }
        XCTAssertNotNil(condition)
        XCTAssertTrue(condition?.formattedCurrentTemp.contains("-8°C") ?? false)
    }

    func testWeatherConditionFormattedSnowfall() {
        let condition = WeatherCondition.sampleConditions.first { $0.snowfall24hCm > 0 }
        XCTAssertNotNil(condition)
        XCTAssertTrue(condition?.formattedSnowfall24h.contains("cm") ?? false)
    }

    func testWeatherConditionNoSnowfall() {
        // Create a condition with 0 snowfall
        let condition = WeatherCondition(
            resortId: "test",
            elevationLevel: "top",
            timestamp: "2026-01-20T10:00:00Z",
            currentTempCelsius: -5.0,
            minTempCelsius: -10.0,
            maxTempCelsius: 0.0,
            snowfall24hCm: 0.0,
            snowfall48hCm: 0.0,
            snowfall72hCm: 0.0,
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
            humidityPercent: nil,
            windSpeedKmh: nil,
            weatherDescription: nil,
            snowQuality: .fair,
            confidenceLevel: .medium,
            freshSnowCm: 0.0,
            dataSource: "test",
            sourceConfidence: .medium,
            rawData: nil
        )
        XCTAssertEqual(condition.formattedSnowfall24h, "No new snow")
        XCTAssertEqual(condition.formattedFreshSnow, "No fresh snow")
    }

    func testWeatherConditionElevationLevelEnum() {
        let topCondition = WeatherCondition.sampleConditions.first { $0.elevationLevel == "top" }
        XCTAssertEqual(topCondition?.elevationLevelEnum, .top)

        let baseCondition = WeatherCondition.sampleConditions.first { $0.elevationLevel == "base" }
        XCTAssertEqual(baseCondition?.elevationLevelEnum, .base)
    }

    func testWeatherConditionWindSpeed() {
        let condition = WeatherCondition.sampleConditions.first { $0.windSpeedKmh != nil }
        XCTAssertNotNil(condition)
        XCTAssertTrue(condition?.formattedWindSpeed.contains("km/h") ?? false)
        XCTAssertTrue(condition?.formattedWindSpeed.contains("mph") ?? false)
    }

    func testWeatherConditionHumidity() {
        let condition = WeatherCondition.sampleConditions.first { $0.humidityPercent != nil }
        XCTAssertNotNil(condition)
        XCTAssertTrue(condition?.formattedHumidity.contains("%") ?? false)
    }

    func testWeatherConditionNoWindData() {
        let condition = WeatherCondition(
            resortId: "test",
            elevationLevel: "top",
            timestamp: "2026-01-20T10:00:00Z",
            currentTempCelsius: -5.0,
            minTempCelsius: -10.0,
            maxTempCelsius: 0.0,
            snowfall24hCm: 10.0,
            snowfall48hCm: 20.0,
            snowfall72hCm: 30.0,
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
            humidityPercent: nil,
            windSpeedKmh: nil,
            weatherDescription: nil,
            snowQuality: .good,
            confidenceLevel: .high,
            freshSnowCm: 8.0,
            dataSource: "test",
            sourceConfidence: .high,
            rawData: nil
        )
        XCTAssertEqual(condition.formattedWindSpeed, "No wind data")
        XCTAssertEqual(condition.formattedHumidity, "No humidity data")
    }

    // MARK: - Resort JSON Decoding Tests

    func testResortJSONDecoding() throws {
        let json = """
        {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "CA",
            "region": "BC",
            "elevation_points": [
                {
                    "level": "base",
                    "elevation_meters": 1500,
                    "elevation_feet": 4921,
                    "latitude": 50.0,
                    "longitude": -118.0,
                    "weather_station_id": null
                }
            ],
            "timezone": "America/Vancouver",
            "official_website": "https://test.com",
            "weather_sources": ["weatherapi"],
            "created_at": "2026-01-20T08:00:00Z",
            "updated_at": "2026-01-20T08:00:00Z"
        }
        """

        let data = json.data(using: .utf8)!
        let resort = try JSONDecoder().decode(Resort.self, from: data)

        XCTAssertEqual(resort.id, "test-resort")
        XCTAssertEqual(resort.name, "Test Resort")
        XCTAssertEqual(resort.country, "CA")
        XCTAssertEqual(resort.region, "BC")
        XCTAssertEqual(resort.elevationPoints.count, 1)
        XCTAssertEqual(resort.timezone, "America/Vancouver")
        XCTAssertEqual(resort.officialWebsite, "https://test.com")
    }

    // MARK: - WeatherCondition JSON Decoding Tests

    func testWeatherConditionJSONDecoding() throws {
        let json = """
        {
            "resort_id": "test-resort",
            "elevation_level": "top",
            "timestamp": "2026-01-20T10:00:00Z",
            "current_temp_celsius": -10.0,
            "min_temp_celsius": -15.0,
            "max_temp_celsius": -5.0,
            "snowfall_24h_cm": 25.0,
            "snowfall_48h_cm": 40.0,
            "snowfall_72h_cm": 50.0,
            "hours_above_ice_threshold": 0.0,
            "max_consecutive_warm_hours": 0.0,
            "humidity_percent": 85.0,
            "wind_speed_kmh": 20.0,
            "weather_description": "Heavy snow",
            "snow_quality": "excellent",
            "confidence_level": "high",
            "fresh_snow_cm": 22.0,
            "data_source": "weatherapi",
            "source_confidence": "high",
            "raw_data": null
        }
        """

        let data = json.data(using: .utf8)!
        let condition = try JSONDecoder().decode(WeatherCondition.self, from: data)

        XCTAssertEqual(condition.resortId, "test-resort")
        XCTAssertEqual(condition.elevationLevel, "top")
        XCTAssertEqual(condition.currentTempCelsius, -10.0)
        XCTAssertEqual(condition.snowfall24hCm, 25.0)
        XCTAssertEqual(condition.snowQuality, .excellent)
        XCTAssertEqual(condition.confidenceLevel, .high)
        XCTAssertEqual(condition.freshSnowCm, 22.0)
    }

    // MARK: - AppConfiguration Tests

    func testAppConfigurationSharedInstance() {
        let config1 = AppConfiguration.shared
        let config2 = AppConfiguration.shared
        XCTAssertTrue(config1 === config2)
    }

    func testAppConfigurationURLValidation() {
        let config = AppConfiguration.shared

        // Valid URLs
        XCTAssertTrue(config.validateURL("http://localhost:8000"))
        XCTAssertTrue(config.validateURL("https://api.example.com"))
        XCTAssertTrue(config.validateURL("https://api.example.com/v1/path"))

        // Invalid URLs
        XCTAssertFalse(config.validateURL("not-a-url"))
        XCTAssertFalse(config.validateURL("ftp://example.com"))
        XCTAssertFalse(config.validateURL(""))
    }

    func testAppConfigurationDefaultAPIURL() {
        let config = AppConfiguration.shared

        // In DEBUG builds, default should be localhost for simulator
        // or dev URL for device
        XCTAssertNotNil(config.apiBaseURL)
        XCTAssertNotNil(config.apiBaseURL.host)
    }

    func testAppEnvironmentAPIURLs() {
        // Test each environment has a valid URL
        XCTAssertNotNil(AppEnvironment.development.apiBaseURL)
        XCTAssertNotNil(AppEnvironment.staging.apiBaseURL)
        XCTAssertNotNil(AppEnvironment.production.apiBaseURL)

        // Staging and production should use HTTPS
        XCTAssertEqual(AppEnvironment.staging.apiBaseURL.scheme, "https")
        XCTAssertEqual(AppEnvironment.production.apiBaseURL.scheme, "https")
    }

    func testAppEnvironmentCognitoConfig() {
        // Each environment should have Cognito configuration
        XCTAssertFalse(AppEnvironment.development.cognitoUserPoolId.isEmpty)
        XCTAssertFalse(AppEnvironment.staging.cognitoUserPoolId.isEmpty)
        XCTAssertFalse(AppEnvironment.production.cognitoUserPoolId.isEmpty)

        XCTAssertFalse(AppEnvironment.development.cognitoClientId.isEmpty)
        XCTAssertFalse(AppEnvironment.staging.cognitoClientId.isEmpty)
        XCTAssertFalse(AppEnvironment.production.cognitoClientId.isEmpty)
    }

    // MARK: - Snowflake Tests

    func testSnowflakeIdentifiable() {
        let snowflake1 = Snowflake(x: 0.5, y: 0.5, size: 10, opacity: 0.8, speed: 5, delay: 0)
        let snowflake2 = Snowflake(x: 0.5, y: 0.5, size: 10, opacity: 0.8, speed: 5, delay: 0)

        // Each snowflake should have a unique ID
        XCTAssertNotEqual(snowflake1.id, snowflake2.id)
    }

    func testSnowflakeProperties() {
        let snowflake = Snowflake(x: 0.3, y: 0.7, size: 8, opacity: 0.6, speed: 6, delay: 1.5)

        XCTAssertEqual(snowflake.x, 0.3)
        XCTAssertEqual(snowflake.y, 0.7)
        XCTAssertEqual(snowflake.size, 8)
        XCTAssertEqual(snowflake.opacity, 0.6)
        XCTAssertEqual(snowflake.speed, 6)
        XCTAssertEqual(snowflake.delay, 1.5)
    }

    // MARK: - Cache Configuration Tests

    func testCacheConfigurationDurations() {
        // Resort cache should be 24 hours
        XCTAssertEqual(CacheConfiguration.resortCacheDuration, 24 * 60 * 60)

        // Condition cache should be 30 minutes
        XCTAssertEqual(CacheConfiguration.conditionCacheDuration, 30 * 60)

        // Stale cache should be 7 days
        XCTAssertEqual(CacheConfiguration.staleCacheDuration, 7 * 24 * 60 * 60)
    }

    func testCachedDataAgeDescription() {
        let recentDate = Date().addingTimeInterval(-60) // 1 minute ago
        let cachedData = CachedData(data: "test", isStale: false, cachedAt: recentDate)

        // Should produce a relative time string
        XCTAssertFalse(cachedData.ageDescription.isEmpty)
    }

    func testCachedDataStaleFlag() {
        let freshData = CachedData(data: [1, 2, 3], isStale: false, cachedAt: Date())
        let staleData = CachedData(data: [1, 2, 3], isStale: true, cachedAt: Date())

        XCTAssertFalse(freshData.isStale)
        XCTAssertTrue(staleData.isStale)
    }

    // MARK: - Resort Coordinate Tests

    func testResortPrimaryCoordinate() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)

        // Primary coordinate should come from mid elevation
        let coordinate = bigWhite?.primaryCoordinate
        XCTAssertNotNil(coordinate)
        XCTAssertNotEqual(coordinate?.latitude, 0)
        XCTAssertNotEqual(coordinate?.longitude, 0)
    }

    func testResortDistanceCalculation() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(bigWhite)

        // Create a test location (Vancouver)
        let vancouver = CLLocation(latitude: 49.2827, longitude: -123.1207)
        let distance = bigWhite?.distance(from: vancouver)

        XCTAssertNotNil(distance)
        // Big White is ~400km from Vancouver
        XCTAssertGreaterThan(distance ?? 0, 300_000) // > 300km
        XCTAssertLessThan(distance ?? 0, 500_000) // < 500km
    }

    // MARK: - ResortAnnotation Tests

    func testResortAnnotationCreation() {
        let resort = Resort.sampleResorts.first!
        let condition = WeatherCondition.sampleConditions.first

        let annotation = ResortAnnotation(resort: resort, condition: condition)

        XCTAssertEqual(annotation.id, resort.id)
        XCTAssertEqual(annotation.resort.id, resort.id)
        XCTAssertEqual(annotation.snowQuality, condition?.snowQuality ?? .unknown)
    }

    func testResortAnnotationWithNilCondition() {
        let resort = Resort.sampleResorts.first!

        let annotation = ResortAnnotation(resort: resort, condition: nil)

        XCTAssertEqual(annotation.snowQuality, .unknown)
    }

    func testResortAnnotationMarkerTint() {
        let resort = Resort.sampleResorts.first!
        let excellentCondition = WeatherCondition.sampleConditions.first { $0.snowQuality == .excellent }

        let annotation = ResortAnnotation(resort: resort, condition: excellentCondition)

        XCTAssertEqual(annotation.markerTint, SnowQuality.excellent.color)
    }

    // MARK: - MapFilterOption Tests

    func testMapFilterOptionAll() {
        let allFilter = MapFilterOption.all
        XCTAssertEqual(allFilter.qualities.count, SnowQuality.allCases.count)
    }

    func testMapFilterOptionExcellent() {
        let excellentFilter = MapFilterOption.excellent
        XCTAssertEqual(excellentFilter.qualities, [.excellent])
    }

    func testMapFilterOptionPoor() {
        let poorFilter = MapFilterOption.poor
        XCTAssertTrue(poorFilter.qualities.contains(.poor))
        XCTAssertTrue(poorFilter.qualities.contains(.bad))
        XCTAssertTrue(poorFilter.qualities.contains(.horrible))
    }

    // MARK: - MapRegionPreset Tests

    func testMapRegionPresetNARockies() {
        let preset = MapRegionPreset.naRockies
        let region = preset.region

        // Center should be around Colorado/Utah
        XCTAssertEqual(region.center.latitude, 40.5, accuracy: 1.0)
        XCTAssertEqual(region.center.longitude, -106.5, accuracy: 1.0)
    }

    func testMapRegionPresetAlps() {
        let preset = MapRegionPreset.alps
        let region = preset.region

        // Center should be around Switzerland
        XCTAssertEqual(region.center.latitude, 46.5, accuracy: 1.0)
        XCTAssertEqual(region.center.longitude, 8.5, accuracy: 1.0)
    }

    func testMapRegionPresetIcons() {
        XCTAssertEqual(MapRegionPreset.userLocation.icon, "location.fill")
        XCTAssertEqual(MapRegionPreset.naRockies.icon, "mountain.2.fill")
        XCTAssertEqual(MapRegionPreset.alps.icon, "flag.fill")
    }

    // MARK: - MapViewModel Tests

    @MainActor
    func testMapViewModelInitialization() async {
        let viewModel = MapViewModel()

        XCTAssertTrue(viewModel.annotations.isEmpty)
        XCTAssertNil(viewModel.selectedAnnotation)
        XCTAssertEqual(viewModel.selectedFilter, .all)
    }

    @MainActor
    func testMapViewModelUpdateAnnotations() async {
        let viewModel = MapViewModel()
        let resorts = Resort.sampleResorts
        let conditions: [String: [WeatherCondition]] = [
            "big-white": WeatherCondition.sampleConditions.filter { $0.resortId == "big-white" }
        ]

        viewModel.updateAnnotations(resorts: resorts, conditions: conditions)

        XCTAssertEqual(viewModel.annotations.count, resorts.count)
    }

    @MainActor
    func testMapViewModelFilterAnnotations() async {
        let viewModel = MapViewModel()
        let resorts = Resort.sampleResorts
        let conditions: [String: [WeatherCondition]] = [
            "big-white": [WeatherCondition.sampleConditions.first!]
        ]

        // Set filter to excellent
        viewModel.selectedFilter = .excellent
        viewModel.updateAnnotations(resorts: resorts, conditions: conditions)

        // Only resorts with excellent conditions should be shown
        let excellentCount = viewModel.annotations.filter { $0.snowQuality == .excellent }.count
        XCTAssertEqual(viewModel.annotations.count, excellentCount)
    }

    @MainActor
    func testMapViewModelSelectAnnotation() async {
        let viewModel = MapViewModel()
        let resort = Resort.sampleResorts.first!
        let annotation = ResortAnnotation(resort: resort, condition: nil)

        viewModel.selectAnnotation(annotation)

        XCTAssertNotNil(viewModel.selectedAnnotation)
        XCTAssertEqual(viewModel.selectedAnnotation?.id, annotation.id)
    }

    @MainActor
    func testMapViewModelQualityStats() async {
        let viewModel = MapViewModel()
        let resorts = Resort.sampleResorts
        let conditions: [String: [WeatherCondition]] = [
            "big-white": [WeatherCondition.sampleConditions.first!]
        ]

        viewModel.updateAnnotations(resorts: resorts, conditions: conditions)

        let stats = viewModel.qualityStats
        XCTAssertFalse(stats.isEmpty)
    }

    @MainActor
    func testMapViewModelSetRegion() async {
        let viewModel = MapViewModel()

        viewModel.setRegion(.alps)

        XCTAssertEqual(viewModel.selectedRegionPreset, .alps)
    }
}
