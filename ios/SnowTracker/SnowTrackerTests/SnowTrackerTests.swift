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
        XCTAssertEqual(SnowQuality.poor.displayName, "Soft")
        XCTAssertEqual(SnowQuality.slushy.displayName, "Slushy")
        XCTAssertEqual(SnowQuality.bad.displayName, "Icy")
        XCTAssertEqual(SnowQuality.unknown.displayName, "Unknown")
    }

    func testSnowQualityIcon() {
        XCTAssertEqual(SnowQuality.excellent.icon, "snowflake")
        XCTAssertEqual(SnowQuality.good.icon, "cloud.snow")
        XCTAssertEqual(SnowQuality.fair.icon, "cloud")
        XCTAssertEqual(SnowQuality.poor.icon, "drop.fill")
        XCTAssertEqual(SnowQuality.slushy.icon, "drop.fill")
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
        XCTAssertEqual(topElevation?.elevationFeet ?? 0, 7608.0, accuracy: 1.0)
    }

    // MARK: - ElevationPoint Tests

    func testElevationPointFormattedElevation() {
        let bigWhite = Resort.sampleResorts.first { $0.id == "big-white" }
        let topElevation = bigWhite?.topElevation
        XCTAssertNotNil(topElevation)
        XCTAssertEqual(topElevation?.formattedElevation, "7,608 ft (2,319 m)")
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
            snowDepthCm: 50.0,
            predictedSnow24hCm: nil,
            predictedSnow48hCm: nil,
            predictedSnow72hCm: nil,
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
            snowfallAfterFreezeCm: nil,
            hoursSinceLastSnowfall: nil,
            lastFreezeThawHoursAgo: nil,
            currentlyWarming: nil,
            humidityPercent: nil,
            windSpeedKmh: nil,
            weatherDescription: nil,
            snowQuality: .fair,
            qualityScore: nil,
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
            snowDepthCm: 100.0,
            predictedSnow24hCm: nil,
            predictedSnow48hCm: nil,
            predictedSnow72hCm: nil,
            hoursAboveIceThreshold: 0.0,
            maxConsecutiveWarmHours: 0.0,
            snowfallAfterFreezeCm: nil,
            hoursSinceLastSnowfall: nil,
            lastFreezeThawHoursAgo: nil,
            currentlyWarming: nil,
            humidityPercent: nil,
            windSpeedKmh: nil,
            weatherDescription: nil,
            snowQuality: .good,
            qualityScore: nil,
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

    @MainActor
    func testAppConfigurationSharedInstance() {
        let config1 = AppConfiguration.shared
        let config2 = AppConfiguration.shared
        XCTAssertTrue(config1 === config2)
    }

    @MainActor
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

    @MainActor
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

    // MARK: - TripStatus Tests

    func testTripStatusRawValues() {
        XCTAssertEqual(TripStatus.planned.rawValue, "planned")
        XCTAssertEqual(TripStatus.active.rawValue, "active")
        XCTAssertEqual(TripStatus.completed.rawValue, "completed")
        XCTAssertEqual(TripStatus.cancelled.rawValue, "cancelled")
    }

    func testTripStatusFromRawValue() {
        XCTAssertEqual(TripStatus(rawValue: "planned"), .planned)
        XCTAssertEqual(TripStatus(rawValue: "active"), .active)
        XCTAssertEqual(TripStatus(rawValue: "completed"), .completed)
        XCTAssertEqual(TripStatus(rawValue: "cancelled"), .cancelled)
        XCTAssertNil(TripStatus(rawValue: "invalid"))
    }

    // MARK: - TripAlertType Tests

    func testTripAlertTypeRawValues() {
        XCTAssertEqual(TripAlertType.powderAlert.rawValue, "powder_alert")
        XCTAssertEqual(TripAlertType.warmSpell.rawValue, "warm_spell")
        XCTAssertEqual(TripAlertType.conditionsImproved.rawValue, "conditions_improved")
        XCTAssertEqual(TripAlertType.conditionsDegraded.rawValue, "conditions_degraded")
        XCTAssertEqual(TripAlertType.tripReminder.rawValue, "trip_reminder")
    }

    func testTripAlertTypeDisplayName() {
        XCTAssertEqual(TripAlertType.powderAlert.displayName, "Powder Alert")
        XCTAssertEqual(TripAlertType.warmSpell.displayName, "Warm Spell Warning")
        XCTAssertEqual(TripAlertType.conditionsImproved.displayName, "Conditions Improved")
        XCTAssertEqual(TripAlertType.conditionsDegraded.displayName, "Conditions Degraded")
        XCTAssertEqual(TripAlertType.tripReminder.displayName, "Trip Reminder")
    }

    func testTripAlertTypeIcon() {
        XCTAssertEqual(TripAlertType.powderAlert.icon, "snowflake")
        XCTAssertEqual(TripAlertType.warmSpell.icon, "sun.max.fill")
        XCTAssertEqual(TripAlertType.conditionsImproved.icon, "arrow.up.circle.fill")
        XCTAssertEqual(TripAlertType.conditionsDegraded.icon, "arrow.down.circle.fill")
        XCTAssertEqual(TripAlertType.tripReminder.icon, "bell.fill")
    }

    // MARK: - TripConditionSnapshot Tests

    func testTripConditionSnapshotQuality() throws {
        let json = """
        {
            "timestamp": "2026-01-20T10:00:00Z",
            "snow_quality": "excellent",
            "fresh_snow_cm": 25.0,
            "predicted_snow_cm": 15.0,
            "temperature_celsius": -8.0
        }
        """

        let data = json.data(using: .utf8)!
        let snapshot = try JSONDecoder().decode(TripConditionSnapshot.self, from: data)

        XCTAssertEqual(snapshot.quality, .excellent)
        XCTAssertEqual(snapshot.freshSnowCm, 25.0)
        XCTAssertEqual(snapshot.predictedSnowCm, 15.0)
        XCTAssertEqual(snapshot.temperatureCelsius, -8.0)
    }

    func testTripConditionSnapshotUnknownQuality() throws {
        let json = """
        {
            "timestamp": "2026-01-20T10:00:00Z",
            "snow_quality": "invalid_quality",
            "fresh_snow_cm": 0.0,
            "predicted_snow_cm": 0.0,
            "temperature_celsius": null
        }
        """

        let data = json.data(using: .utf8)!
        let snapshot = try JSONDecoder().decode(TripConditionSnapshot.self, from: data)

        XCTAssertEqual(snapshot.quality, .unknown)
        XCTAssertNil(snapshot.temperatureCelsius)
    }

    // MARK: - TripAlert Tests

    func testTripAlertDecoding() throws {
        let json = """
        {
            "alert_id": "alert-123",
            "alert_type": "powder_alert",
            "message": "20cm fresh powder expected!",
            "created_at": "2026-01-20T08:00:00Z",
            "is_read": false,
            "data": {"snow_cm": 20}
        }
        """

        let data = json.data(using: .utf8)!
        let alert = try JSONDecoder().decode(TripAlert.self, from: data)

        XCTAssertEqual(alert.id, "alert-123")
        XCTAssertEqual(alert.alertId, "alert-123")
        XCTAssertEqual(alert.type, .powderAlert)
        XCTAssertEqual(alert.message, "20cm fresh powder expected!")
        XCTAssertFalse(alert.isRead)
    }

    func testTripAlertUnknownType() throws {
        let json = """
        {
            "alert_id": "alert-456",
            "alert_type": "unknown_type",
            "message": "Test message",
            "created_at": "2026-01-20T08:00:00Z",
            "is_read": true,
            "data": {}
        }
        """

        let data = json.data(using: .utf8)!
        let alert = try JSONDecoder().decode(TripAlert.self, from: data)

        XCTAssertEqual(alert.type, .tripReminder) // Default fallback
        XCTAssertTrue(alert.isRead)
    }

    // MARK: - Trip Tests

    func testTripDecoding() throws {
        let json = """
        {
            "trip_id": "trip-123",
            "user_id": "user-456",
            "resort_id": "big-white",
            "resort_name": "Big White",
            "start_date": "2026-02-15",
            "end_date": "2026-02-20",
            "status": "planned",
            "notes": "Family ski trip",
            "party_size": 4,
            "conditions_at_creation": {
                "timestamp": "2026-01-20T10:00:00Z",
                "snow_quality": "good",
                "fresh_snow_cm": 10.0,
                "predicted_snow_cm": 20.0,
                "temperature_celsius": -5.0
            },
            "latest_conditions": null,
            "alerts": [],
            "alert_preferences": {"powder_alert": true, "warm_spell": false},
            "created_at": "2026-01-20T08:00:00Z",
            "updated_at": "2026-01-20T08:00:00Z"
        }
        """

        let data = json.data(using: .utf8)!
        let trip = try JSONDecoder().decode(Trip.self, from: data)

        XCTAssertEqual(trip.id, "trip-123")
        XCTAssertEqual(trip.tripId, "trip-123")
        XCTAssertEqual(trip.userId, "user-456")
        XCTAssertEqual(trip.resortId, "big-white")
        XCTAssertEqual(trip.resortName, "Big White")
        XCTAssertEqual(trip.startDate, "2026-02-15")
        XCTAssertEqual(trip.endDate, "2026-02-20")
        XCTAssertEqual(trip.status, "planned")
        XCTAssertEqual(trip.notes, "Family ski trip")
        XCTAssertEqual(trip.partySize, 4)
        XCTAssertNotNil(trip.conditionsAtCreation)
        XCTAssertNil(trip.latestConditions)
        XCTAssertTrue(trip.alerts.isEmpty)
    }

    func testTripTripStatus() throws {
        let jsonPlanned = """
        {
            "trip_id": "trip-1", "user_id": "user-1", "resort_id": "r1", "resort_name": "R1",
            "start_date": "2026-02-15", "end_date": "2026-02-20", "status": "planned",
            "notes": null, "party_size": 2, "conditions_at_creation": null, "latest_conditions": null,
            "alerts": [], "alert_preferences": {}, "created_at": "2026-01-20T08:00:00Z", "updated_at": "2026-01-20T08:00:00Z"
        }
        """

        let data = jsonPlanned.data(using: .utf8)!
        let trip = try JSONDecoder().decode(Trip.self, from: data)

        XCTAssertEqual(trip.tripStatus, .planned)
    }

    func testTripWithAlerts() throws {
        let json = """
        {
            "trip_id": "trip-123",
            "user_id": "user-456",
            "resort_id": "big-white",
            "resort_name": "Big White",
            "start_date": "2026-02-15",
            "end_date": "2026-02-20",
            "status": "active",
            "notes": null,
            "party_size": 2,
            "conditions_at_creation": null,
            "latest_conditions": null,
            "alerts": [
                {
                    "alert_id": "alert-1",
                    "alert_type": "powder_alert",
                    "message": "Fresh powder!",
                    "created_at": "2026-01-20T08:00:00Z",
                    "is_read": false,
                    "data": {}
                },
                {
                    "alert_id": "alert-2",
                    "alert_type": "warm_spell",
                    "message": "Warming expected",
                    "created_at": "2026-01-20T09:00:00Z",
                    "is_read": true,
                    "data": {}
                }
            ],
            "alert_preferences": {},
            "created_at": "2026-01-20T08:00:00Z",
            "updated_at": "2026-01-20T08:00:00Z"
        }
        """

        let data = json.data(using: .utf8)!
        let trip = try JSONDecoder().decode(Trip.self, from: data)

        XCTAssertEqual(trip.alerts.count, 2)
        XCTAssertEqual(trip.alerts[0].type, .powderAlert)
        XCTAssertEqual(trip.alerts[1].type, .warmSpell)
        XCTAssertEqual(trip.tripStatus, .active)
    }

    // MARK: - TripCreateRequest Tests

    func testTripCreateRequestEncoding() throws {
        let request = TripCreateRequest(
            resortId: "big-white",
            startDate: "2026-02-15",
            endDate: "2026-02-20",
            notes: "Family trip",
            partySize: 4,
            alertPreferences: ["powder_alert": true, "warm_spell": false]
        )

        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["resort_id"] as? String, "big-white")
        XCTAssertEqual(json["start_date"] as? String, "2026-02-15")
        XCTAssertEqual(json["end_date"] as? String, "2026-02-20")
        XCTAssertEqual(json["notes"] as? String, "Family trip")
        XCTAssertEqual(json["party_size"] as? Int, 4)
    }

    // MARK: - TripUpdateRequest Tests

    func testTripUpdateRequestPartialEncoding() throws {
        let request = TripUpdateRequest(
            startDate: nil,
            endDate: nil,
            notes: "Updated notes",
            partySize: 6,
            status: "completed",
            alertPreferences: nil
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["notes"] as? String, "Updated notes")
        XCTAssertEqual(json["party_size"] as? Int, 6)
        XCTAssertEqual(json["status"] as? String, "completed")
    }

    // MARK: - ResortRecommendation Tests

    func testResortRecommendationDecoding() throws {
        let json = """
        {
            "resort": {
                "resort_id": "big-white",
                "name": "Big White",
                "country": "CA",
                "region": "BC",
                "elevation_points": [],
                "timezone": "America/Vancouver",
                "official_website": "https://bigwhite.com",
                "weather_sources": ["weatherapi"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            },
            "distance_km": 450.5,
            "distance_miles": 280.0,
            "snow_quality": "excellent",
            "quality_score": 0.95,
            "distance_score": 0.7,
            "combined_score": 0.85,
            "fresh_snow_cm": 25.0,
            "predicted_snow_72h_cm": 40.0,
            "current_temp_celsius": -8.0,
            "confidence_level": "high",
            "reason": "25cm fresh powder with more on the way!",
            "elevation_conditions": {}
        }
        """

        let data = json.data(using: .utf8)!
        let recommendation = try JSONDecoder().decode(ResortRecommendation.self, from: data)

        XCTAssertEqual(recommendation.id, "big-white")
        XCTAssertEqual(recommendation.resort.name, "Big White")
        XCTAssertEqual(recommendation.distanceKm, 450.5)
        XCTAssertEqual(recommendation.distanceMiles, 280.0)
        XCTAssertEqual(recommendation.quality, .excellent)
        XCTAssertEqual(recommendation.qualityScore, 0.95)
        XCTAssertEqual(recommendation.combinedScore, 0.85)
        XCTAssertEqual(recommendation.freshSnowCm, 25.0)
        XCTAssertEqual(recommendation.predictedSnow72hCm, 40.0)
        XCTAssertEqual(recommendation.currentTempCelsius, -8.0)
        XCTAssertEqual(recommendation.confidence, .high)
        XCTAssertEqual(recommendation.reason, "25cm fresh powder with more on the way!")
    }

    func testResortRecommendationQualityUnknown() throws {
        let json = """
        {
            "resort": {
                "resort_id": "test-resort",
                "name": "Test Resort",
                "country": "US",
                "region": "CO",
                "elevation_points": [],
                "timezone": "America/Denver",
                "official_website": null,
                "weather_sources": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            },
            "distance_km": 100.0,
            "distance_miles": 62.0,
            "snow_quality": "invalid_quality",
            "quality_score": 0.5,
            "distance_score": 0.8,
            "combined_score": 0.6,
            "fresh_snow_cm": 0.0,
            "predicted_snow_72h_cm": 0.0,
            "current_temp_celsius": 2.0,
            "confidence_level": "low",
            "reason": "No recent data available",
            "elevation_conditions": {}
        }
        """

        let data = json.data(using: .utf8)!
        let recommendation = try JSONDecoder().decode(ResortRecommendation.self, from: data)

        XCTAssertEqual(recommendation.quality, .unknown)
        XCTAssertEqual(recommendation.confidence, .low)
    }

    func testResortRecommendationFormattedDistanceMetric() throws {
        let json = """
        {
            "resort": {
                "resort_id": "test",
                "name": "Test",
                "country": "CA",
                "region": "BC",
                "elevation_points": [],
                "timezone": "America/Vancouver",
                "official_website": null,
                "weather_sources": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            },
            "distance_km": 0.5,
            "distance_miles": 0.31,
            "snow_quality": "good",
            "quality_score": 0.8,
            "distance_score": 0.95,
            "combined_score": 0.85,
            "fresh_snow_cm": 10.0,
            "predicted_snow_72h_cm": 5.0,
            "current_temp_celsius": -3.0,
            "confidence_level": "medium",
            "reason": "Good conditions nearby",
            "elevation_conditions": {}
        }
        """

        let data = json.data(using: .utf8)!
        let recommendation = try JSONDecoder().decode(ResortRecommendation.self, from: data)

        // Test metric formatting for short distance
        XCTAssertEqual(recommendation.formattedDistance(useMetric: true), "500 m")
    }

    func testResortRecommendationFormattedDistanceLongMetric() throws {
        let json = """
        {
            "resort": {
                "resort_id": "test",
                "name": "Test",
                "country": "CA",
                "region": "BC",
                "elevation_points": [],
                "timezone": "America/Vancouver",
                "official_website": null,
                "weather_sources": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            },
            "distance_km": 150.0,
            "distance_miles": 93.2,
            "snow_quality": "good",
            "quality_score": 0.8,
            "distance_score": 0.6,
            "combined_score": 0.7,
            "fresh_snow_cm": 10.0,
            "predicted_snow_72h_cm": 5.0,
            "current_temp_celsius": -3.0,
            "confidence_level": "medium",
            "reason": "Good conditions",
            "elevation_conditions": {}
        }
        """

        let data = json.data(using: .utf8)!
        let recommendation = try JSONDecoder().decode(ResortRecommendation.self, from: data)

        // Test metric formatting for long distance
        XCTAssertEqual(recommendation.formattedDistance(useMetric: true), "150 km")
    }

    func testResortRecommendationFormattedDistanceImperial() throws {
        let json = """
        {
            "resort": {
                "resort_id": "test",
                "name": "Test",
                "country": "CA",
                "region": "BC",
                "elevation_points": [],
                "timezone": "America/Vancouver",
                "official_website": null,
                "weather_sources": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            },
            "distance_km": 80.0,
            "distance_miles": 50.0,
            "snow_quality": "good",
            "quality_score": 0.8,
            "distance_score": 0.7,
            "combined_score": 0.75,
            "fresh_snow_cm": 10.0,
            "predicted_snow_72h_cm": 5.0,
            "current_temp_celsius": -3.0,
            "confidence_level": "medium",
            "reason": "Good conditions",
            "elevation_conditions": {}
        }
        """

        let data = json.data(using: .utf8)!
        let recommendation = try JSONDecoder().decode(ResortRecommendation.self, from: data)

        // Test imperial formatting
        XCTAssertEqual(recommendation.formattedDistance(useMetric: false), "50 mi")
    }

    // MARK: - RecommendationsResponse Tests

    func testRecommendationsResponseDecoding() throws {
        let json = """
        {
            "recommendations": [
                {
                    "resort": {
                        "resort_id": "big-white",
                        "name": "Big White",
                        "country": "CA",
                        "region": "BC",
                        "elevation_points": [],
                        "timezone": "America/Vancouver",
                        "official_website": null,
                        "weather_sources": [],
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z"
                    },
                    "distance_km": 100.0,
                    "distance_miles": 62.0,
                    "snow_quality": "excellent",
                    "quality_score": 0.95,
                    "distance_score": 0.8,
                    "combined_score": 0.9,
                    "fresh_snow_cm": 30.0,
                    "predicted_snow_72h_cm": 20.0,
                    "current_temp_celsius": -10.0,
                    "confidence_level": "high",
                    "reason": "Epic powder day!",
                    "elevation_conditions": {}
                }
            ],
            "search_center": {
                "latitude": 49.28,
                "longitude": -123.12
            },
            "search_radius_km": 500,
            "generated_at": "2026-01-20T10:00:00Z"
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(RecommendationsResponse.self, from: data)

        XCTAssertEqual(response.recommendations.count, 1)
        XCTAssertEqual(response.recommendations[0].resort.name, "Big White")
        XCTAssertEqual(response.searchCenter?.latitude, 49.28)
        XCTAssertEqual(response.searchCenter?.longitude, -123.12)
        XCTAssertEqual(response.searchRadiusKm, 500)
    }

    // MARK: - TripsResponse Tests

    func testTripsResponseDecoding() throws {
        let json = """
        {
            "trips": [
                {
                    "trip_id": "trip-1",
                    "user_id": "user-1",
                    "resort_id": "big-white",
                    "resort_name": "Big White",
                    "start_date": "2026-02-15",
                    "end_date": "2026-02-20",
                    "status": "planned",
                    "notes": null,
                    "party_size": 2,
                    "conditions_at_creation": null,
                    "latest_conditions": null,
                    "alerts": [],
                    "alert_preferences": {},
                    "created_at": "2026-01-20T08:00:00Z",
                    "updated_at": "2026-01-20T08:00:00Z"
                }
            ],
            "count": 1
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(TripsResponse.self, from: data)

        XCTAssertEqual(response.count, 1)
        XCTAssertEqual(response.trips.count, 1)
        XCTAssertEqual(response.trips[0].resortName, "Big White")
    }

    // MARK: - ElevationConditionSummary Tests

    func testElevationConditionSummaryDecoding() throws {
        let json = """
        {
            "quality": "good",
            "temp_celsius": -5.0,
            "fresh_snow_cm": 15.0,
            "snowfall_24h_cm": 10.0,
            "predicted_24h_cm": 5.0
        }
        """

        let data = json.data(using: .utf8)!
        let summary = try JSONDecoder().decode(ElevationConditionSummary.self, from: data)

        XCTAssertEqual(summary.quality, "good")
        XCTAssertEqual(summary.snowQuality, .good)
        XCTAssertEqual(summary.freshSnowCm, 15.0)
        XCTAssertEqual(summary.tempCelsius, -5.0)
        XCTAssertEqual(summary.snowfall24hCm, 10.0)
        XCTAssertEqual(summary.predicted24hCm, 5.0)
    }

    func testElevationConditionSummarySnowQuality() throws {
        let json = """
        {
            "quality": "fair",
            "temp_celsius": 0.0,
            "fresh_snow_cm": 0.0,
            "snowfall_24h_cm": 0.0,
            "predicted_24h_cm": 0.0
        }
        """

        let data = json.data(using: .utf8)!
        let summary = try JSONDecoder().decode(ElevationConditionSummary.self, from: data)

        XCTAssertEqual(summary.quality, "fair")
        XCTAssertEqual(summary.snowQuality, .fair)
        XCTAssertEqual(summary.freshSnowCm, 0.0)
    }

    // MARK: - Timeline Model Tests

    func testTimelinePointDecoding() throws {
        let json = """
        {
            "date": "2026-02-19",
            "time_label": "morning",
            "hour": 7,
            "timestamp": "2026-02-19T07:00:00Z",
            "temperature_c": -5.2,
            "wind_speed_kmh": 12.3,
            "snowfall_cm": 2.1,
            "snow_depth_cm": 145.0,
            "snow_quality": "good",
            "weather_code": 71,
            "weather_description": "Slight snow fall",
            "is_forecast": false
        }
        """
        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let point = try decoder.decode(TimelinePoint.self, from: data)

        XCTAssertEqual(point.date, "2026-02-19")
        XCTAssertEqual(point.timeLabel, "morning")
        XCTAssertEqual(point.hour, 7)
        XCTAssertEqual(point.temperatureC, -5.2, accuracy: 0.01)
        XCTAssertEqual(point.snowQuality, .good)
        XCTAssertEqual(point.isForecast, false)
        XCTAssertEqual(point.timeDisplay, "AM")
    }

    func testTimelinePointTimeDisplay() throws {
        // Test the timeDisplay computed property for each time label
        let makeJSON: (String, Int) -> String = { label, hour in
            """
            {
                "date": "2026-02-19",
                "time_label": "\(label)",
                "hour": \(hour),
                "timestamp": "2026-02-19T\(String(format: "%02d", hour)):00:00Z",
                "temperature_c": 0.0,
                "wind_speed_kmh": null,
                "snowfall_cm": 0.0,
                "snow_depth_cm": null,
                "snow_quality": "fair",
                "weather_code": null,
                "weather_description": null,
                "is_forecast": false
            }
            """
        }

        let morningPoint = try JSONDecoder().decode(TimelinePoint.self, from: makeJSON("morning", 7).data(using: .utf8)!)
        XCTAssertEqual(morningPoint.timeDisplay, "AM")

        let middayPoint = try JSONDecoder().decode(TimelinePoint.self, from: makeJSON("midday", 12).data(using: .utf8)!)
        XCTAssertEqual(middayPoint.timeDisplay, "Noon")

        let afternoonPoint = try JSONDecoder().decode(TimelinePoint.self, from: makeJSON("afternoon", 16).data(using: .utf8)!)
        XCTAssertEqual(afternoonPoint.timeDisplay, "PM")
    }

    func testTimelineResponseDecoding() throws {
        let json = """
        {
            "timeline": [
                {
                    "date": "2026-02-19",
                    "time_label": "morning",
                    "hour": 7,
                    "timestamp": "2026-02-19T07:00:00Z",
                    "temperature_c": -5.2,
                    "wind_speed_kmh": 12.3,
                    "snowfall_cm": 2.1,
                    "snow_depth_cm": 145.0,
                    "snow_quality": "good",
                    "weather_code": 71,
                    "weather_description": "Slight snow fall",
                    "is_forecast": false
                }
            ],
            "elevation_level": "mid",
            "elevation_meters": 2200,
            "resort_id": "whistler-blackcomb"
        }
        """
        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        let response = try decoder.decode(TimelineResponse.self, from: data)

        XCTAssertEqual(response.timeline.count, 1)
        XCTAssertEqual(response.elevationLevel, "mid")
        XCTAssertEqual(response.elevationMeters, 2200)
        XCTAssertEqual(response.resortId, "whistler-blackcomb")
    }

    func testTimelinePointWithNullOptionals() throws {
        // Test decoding when optional fields are null
        let json = """
        {
            "date": "2026-02-19",
            "time_label": "afternoon",
            "hour": 16,
            "timestamp": "2026-02-19T16:00:00Z",
            "temperature_c": 2.0,
            "wind_speed_kmh": null,
            "snowfall_cm": 0.0,
            "snow_depth_cm": null,
            "snow_quality": "fair",
            "weather_code": null,
            "weather_description": null,
            "is_forecast": true
        }
        """
        let data = json.data(using: .utf8)!
        let point = try JSONDecoder().decode(TimelinePoint.self, from: data)

        XCTAssertNil(point.windSpeedKmh)
        XCTAssertNil(point.snowDepthCm)
        XCTAssertNil(point.weatherCode)
        XCTAssertEqual(point.isForecast, true)
        XCTAssertEqual(point.timeDisplay, "PM")
    }
}
