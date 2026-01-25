import XCTest
import CoreLocation
@testable import SnowTracker

final class LocationTests: XCTestCase {

    // MARK: - Resort Distance Tests

    func testResortDistanceFromLocation() {
        let resort = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(resort)

        // Create a location near Big White (Kelowna, BC)
        let kelownaLocation = CLLocation(latitude: 49.8880, longitude: -119.4960)

        guard let distance = resort?.distance(from: kelownaLocation) else {
            XCTFail("Distance calculation should not return nil")
            return
        }

        // Big White is about 55km from Kelowna
        let distanceKm = distance / 1000
        XCTAssertGreaterThan(distanceKm, 40)
        XCTAssertLessThan(distanceKm, 80)
    }

    func testResortDistanceFromFarLocation() {
        let resort = Resort.sampleResorts.first { $0.id == "big-white" }
        XCTAssertNotNil(resort)

        // Create a location in Europe (Zurich)
        let zurichLocation = CLLocation(latitude: 47.3769, longitude: 8.5417)

        guard let distance = resort?.distance(from: zurichLocation) else {
            XCTFail("Distance calculation should not return nil")
            return
        }

        // Distance should be thousands of km
        let distanceKm = distance / 1000
        XCTAssertGreaterThan(distanceKm, 5000)
    }

    func testResortDistanceWithNoBaseElevation() {
        // Create a resort with no elevation points
        let emptyResort = Resort(
            id: "empty",
            name: "Empty Resort",
            country: "CA",
            region: "BC",
            elevationPoints: [],
            timezone: "America/Vancouver",
            officialWebsite: nil,
            weatherSources: [],
            createdAt: nil,
            updatedAt: nil
        )

        let location = CLLocation(latitude: 49.0, longitude: -118.0)
        let distance = emptyResort.distance(from: location)

        XCTAssertNil(distance, "Distance should be nil when resort has no elevation points")
    }

    // MARK: - ElevationPoint Coordinate Tests

    func testElevationPointCoordinate() {
        let point = ElevationPoint(
            level: .base,
            elevationMeters: 1500,
            elevationFeet: 4921,
            latitude: 49.7167,
            longitude: -118.9333,
            weatherStationId: nil
        )

        let coordinate = point.coordinate
        XCTAssertEqual(coordinate.latitude, 49.7167, accuracy: 0.0001)
        XCTAssertEqual(coordinate.longitude, -118.9333, accuracy: 0.0001)
    }

    // MARK: - Distance Sorting Tests

    func testResortsSortByDistance() {
        let resorts = Resort.sampleResorts
        let kelownaLocation = CLLocation(latitude: 49.8880, longitude: -119.4960)

        // Sort resorts by distance
        let sortedResorts = resorts.sorted { resort1, resort2 in
            let dist1 = resort1.distance(from: kelownaLocation) ?? .infinity
            let dist2 = resort2.distance(from: kelownaLocation) ?? .infinity
            return dist1 < dist2
        }

        // Big White should be first (closest to Kelowna)
        XCTAssertEqual(sortedResorts.first?.id, "big-white")
    }

    func testResortsWithNoLocationSortToEnd() {
        var resorts = Resort.sampleResorts

        // Add a resort with no elevation points
        let emptyResort = Resort(
            id: "empty",
            name: "Empty Resort",
            country: "CA",
            region: "BC",
            elevationPoints: [],
            timezone: "America/Vancouver",
            officialWebsite: nil,
            weatherSources: [],
            createdAt: nil,
            updatedAt: nil
        )
        resorts.append(emptyResort)

        let kelownaLocation = CLLocation(latitude: 49.8880, longitude: -119.4960)

        // Sort resorts by distance
        let sortedResorts = resorts.sorted { resort1, resort2 in
            let dist1 = resort1.distance(from: kelownaLocation) ?? .infinity
            let dist2 = resort2.distance(from: kelownaLocation) ?? .infinity
            return dist1 < dist2
        }

        // Empty resort should be last
        XCTAssertEqual(sortedResorts.last?.id, "empty")
    }

    // MARK: - SnowQuality Sort Order Tests

    func testSnowQualitySortOrder() {
        XCTAssertEqual(SnowQuality.excellent.sortOrder, 0)
        XCTAssertEqual(SnowQuality.good.sortOrder, 1)
        XCTAssertEqual(SnowQuality.fair.sortOrder, 2)
        XCTAssertEqual(SnowQuality.poor.sortOrder, 3)
        XCTAssertEqual(SnowQuality.bad.sortOrder, 4)
        XCTAssertEqual(SnowQuality.horrible.sortOrder, 5)
        XCTAssertEqual(SnowQuality.unknown.sortOrder, 6)
    }

    func testSnowQualitySortOrdering() {
        let qualities: [SnowQuality] = [.unknown, .bad, .excellent, .fair, .poor, .good, .horrible]
        let sorted = qualities.sorted { $0.sortOrder < $1.sortOrder }

        XCTAssertEqual(sorted, [.excellent, .good, .fair, .poor, .bad, .horrible, .unknown])
    }

    // MARK: - Resort View Mode Tests

    func testResortViewModeIcons() {
        XCTAssertEqual(ResortViewMode.list.icon, "list.bullet")
        XCTAssertEqual(ResortViewMode.map.icon, "map")
    }

    func testResortViewModeRawValues() {
        XCTAssertEqual(ResortViewMode.list.rawValue, "list")
        XCTAssertEqual(ResortViewMode.map.rawValue, "map")
    }

    // MARK: - Resort Sort Option Tests

    func testResortSortOptionDisplayNames() {
        XCTAssertEqual(ResortSortOption.name.displayName, "Name")
        XCTAssertEqual(ResortSortOption.nearMe.displayName, "Near Me")
        XCTAssertEqual(ResortSortOption.snowQuality.displayName, "Snow Quality")
    }

    func testResortSortOptionIcons() {
        XCTAssertEqual(ResortSortOption.name.icon, "textformat")
        XCTAssertEqual(ResortSortOption.nearMe.icon, "location")
        XCTAssertEqual(ResortSortOption.snowQuality.icon, "snowflake")
    }
}
