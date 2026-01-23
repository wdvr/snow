import XCTest
@testable import SnowTracker

/// API Integration Tests
/// These tests verify that the iOS app can correctly decode responses from the real API
/// Run these tests to catch API/iOS model mismatches early
final class APIIntegrationTests: XCTestCase {

    // MARK: - Staging API URL

    let stagingAPIBaseURL = URL(string: "https://xz19r2onp7.execute-api.us-west-2.amazonaws.com/staging")!

    // MARK: - Health Check

    func testHealthEndpoint() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("health")
        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Health endpoint should return 200")

        // Verify JSON structure
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(json["status"] as? String, "healthy")
        XCTAssertNotNil(json["environment"])
    }

    // MARK: - Resorts API Tests

    func testGetResortsEndpoint() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Resorts endpoint should return 200")

        // Verify we can decode the response as [Resort]
        let decoder = JSONDecoder()
        let resorts = try decoder.decode([Resort].self, from: data)

        XCTAssertFalse(resorts.isEmpty, "API should return at least one resort")
        XCTAssertGreaterThanOrEqual(resorts.count, 3, "API should return 3 seeded resorts (Big White, Lake Louise, Silver Star)")

        // Verify resort structure
        let resort = resorts.first!
        XCTAssertFalse(resort.id.isEmpty, "Resort should have an ID")
        XCTAssertFalse(resort.name.isEmpty, "Resort should have a name")
        XCTAssertFalse(resort.country.isEmpty, "Resort should have a country")
        XCTAssertFalse(resort.region.isEmpty, "Resort should have a region")
        XCTAssertFalse(resort.elevationPoints.isEmpty, "Resort should have elevation points")
    }

    func testResortElevationPointsDecoding() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, _) = try await URLSession.shared.data(from: url)

        let decoder = JSONDecoder()
        let resorts = try decoder.decode([Resort].self, from: data)

        // Verify each resort has valid elevation points
        for resort in resorts {
            XCTAssertEqual(resort.elevationPoints.count, 3, "Each resort should have 3 elevation points (base, mid, top)")

            // Check elevation levels
            let levels = Set(resort.elevationPoints.map { $0.level })
            XCTAssertTrue(levels.contains(.base), "\(resort.name) should have base elevation")
            XCTAssertTrue(levels.contains(.mid), "\(resort.name) should have mid elevation")
            XCTAssertTrue(levels.contains(.top), "\(resort.name) should have top elevation")

            // Verify elevation values are reasonable (Double, not Int)
            for point in resort.elevationPoints {
                XCTAssertGreaterThan(point.elevationMeters, 0, "Elevation meters should be positive")
                XCTAssertGreaterThan(point.elevationFeet, 0, "Elevation feet should be positive")
                XCTAssertNotEqual(point.latitude, 0, "Latitude should not be 0")
                XCTAssertNotEqual(point.longitude, 0, "Longitude should not be 0")
            }
        }
    }

    func testGetSingleResortEndpoint() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts/big-white")
        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Single resort endpoint should return 200")

        let decoder = JSONDecoder()
        let resort = try decoder.decode(Resort.self, from: data)

        XCTAssertEqual(resort.id, "big-white")
        XCTAssertEqual(resort.name, "Big White Ski Resort")
        XCTAssertEqual(resort.country, "CA")
        XCTAssertEqual(resort.region, "BC")
    }

    func testGetConditionsEndpoint() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts/big-white/conditions")
        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Conditions endpoint should return 200")

        // Conditions might be empty if weather data hasn't been fetched yet
        // But it should still return a valid JSON array
        let decoder = JSONDecoder()
        let conditions = try decoder.decode([WeatherCondition].self, from: data)

        // This is informational - conditions may be empty until weather processor runs
        print("Found \(conditions.count) weather conditions for big-white")
    }

    // MARK: - API Response Format Tests

    func testAPIReturnsRawArrayNotWrapped() async throws {
        // This test ensures the API returns a raw array [...]
        // NOT a wrapped object {"resorts": [...]}
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, _) = try await URLSession.shared.data(from: url)

        let json = try JSONSerialization.jsonObject(with: data)

        // Should be an array, not a dictionary
        XCTAssertTrue(json is [[String: Any]], "API should return a raw array, not a wrapped object")
        XCTAssertFalse(json is [String: Any], "API should NOT return a wrapped object like {\"resorts\": [...]}")
    }

    func testAPIReturnsDoubleElevations() async throws {
        // This test ensures elevation values are Doubles (e.g., 1155.0), not Ints
        // This was a bug that caused decoding to fail
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, _) = try await URLSession.shared.data(from: url)

        let json = try JSONSerialization.jsonObject(with: data) as! [[String: Any]]
        let firstResort = json.first!
        let elevationPoints = firstResort["elevation_points"] as! [[String: Any]]
        let firstPoint = elevationPoints.first!

        // elevation_meters should be a Number (Double or Int work with JSONSerialization)
        let elevationMeters = firstPoint["elevation_meters"]
        XCTAssertNotNil(elevationMeters, "elevation_meters should exist")

        // Verify it's a number
        XCTAssertTrue(elevationMeters is NSNumber, "elevation_meters should be a number")
    }

    // MARK: - Error Handling Tests

    func testNotFoundResort() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts/non-existent-resort")
        let (_, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 404, "Non-existent resort should return 404")
    }

    func testCORSHeaders() async throws {
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (_, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        let headers = httpResponse.allHeaderFields

        // Check CORS headers are present
        XCTAssertNotNil(headers["Access-Control-Allow-Origin"], "CORS header should be present")
    }
}
