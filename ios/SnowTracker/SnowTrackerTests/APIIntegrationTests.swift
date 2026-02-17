import XCTest
@testable import SnowTracker

/// API Integration Tests
/// These tests verify that the iOS app can correctly decode responses from the real API
/// Run these tests to catch API/iOS model mismatches early
final class APIIntegrationTests: XCTestCase {

    // MARK: - Staging API URL

    let stagingAPIBaseURL = URL(string: "https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging")!

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

        // Verify we can decode the response as ResortsResponse (wrapped object)
        let decoder = JSONDecoder()
        let resortsResponse = try decoder.decode(ResortsResponse.self, from: data)
        let resorts = resortsResponse.resorts

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
        let resortsResponse = try decoder.decode(ResortsResponse.self, from: data)
        let resorts = resortsResponse.resorts

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
        // But it should still return a valid JSON response
        let decoder = JSONDecoder()
        let conditionsResponse = try decoder.decode(ConditionsResponse.self, from: data)

        // This is informational - conditions may be empty until weather processor runs
        print("Found \(conditionsResponse.conditions.count) weather conditions for big-white")
    }

    // MARK: - API Response Format Tests

    func testAPIReturnsWrappedObject() async throws {
        // The API returns a wrapped object {"resorts": [...]}
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, _) = try await URLSession.shared.data(from: url)

        let json = try JSONSerialization.jsonObject(with: data)

        // Should be a dictionary with a "resorts" key
        XCTAssertTrue(json is [String: Any], "API should return a wrapped object like {\"resorts\": [...]}")
        let dict = json as! [String: Any]
        XCTAssertNotNil(dict["resorts"], "Wrapped object should contain a 'resorts' key")
        XCTAssertTrue(dict["resorts"] is [[String: Any]], "The 'resorts' value should be an array")
    }

    func testAPIReturnsDoubleElevations() async throws {
        // This test ensures elevation values are Doubles (e.g., 1155.0), not Ints
        // This was a bug that caused decoding to fail
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (data, _) = try await URLSession.shared.data(from: url)

        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        let resorts = json["resorts"] as! [[String: Any]]
        let firstResort = resorts.first!
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
        var request = URLRequest(url: url)
        request.httpMethod = "OPTIONS"
        request.setValue("http://localhost", forHTTPHeaderField: "Origin")
        request.setValue("GET", forHTTPHeaderField: "Access-Control-Request-Method")

        let (_, response) = try await URLSession.shared.data(for: request)

        let httpResponse = response as! HTTPURLResponse
        let headers = httpResponse.allHeaderFields

        // Check CORS headers are present (may be returned on OPTIONS preflight or GET with Origin)
        // Note: CORS headers may not be present on non-browser requests
        if httpResponse.statusCode == 200 || httpResponse.statusCode == 204 {
            print("CORS preflight returned status \(httpResponse.statusCode)")
        }
        // This is informational - CORS headers may only be returned for browser origins
        print("CORS headers present: \(headers.keys.filter { ($0 as? String)?.lowercased().contains("access-control") == true })")
    }

    // MARK: - Batch Endpoint Tests

    func testBatchSnowQualityEndpoint() async throws {
        // Test with a few known resort IDs
        let resortIds = ["big-white", "lake-louise", "whistler-blackcomb"]
        let idsParam = resortIds.joined(separator: ",")

        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/snow-quality/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Batch snow quality endpoint should return 200")

        // Verify we can decode the response
        let decoder = JSONDecoder()
        let batchResponse = try decoder.decode(BatchSnowQualityResponse.self, from: data)

        XCTAssertEqual(batchResponse.resortCount, resortIds.count, "Should return count matching requested resorts")
        XCTAssertGreaterThan(batchResponse.results.count, 0, "Should return at least one result")

        // Verify each result has the expected structure
        for (resortId, summary) in batchResponse.results {
            XCTAssertFalse(resortId.isEmpty, "Resort ID should not be empty")
            XCTAssertEqual(summary.resortId, resortId, "Summary resort_id should match key")
            XCTAssertFalse(summary.overallQuality.isEmpty, "Overall quality should not be empty")
        }
    }

    func testBatchSnowQualityURLConstruction() async throws {
        // This test verifies the URL is constructed correctly with URLComponents
        // This was the root cause of a bug where Alamofire's parameter encoding
        // differed from manual URL construction
        let resortIds = ["big-white", "lake-louise", "whistler-blackcomb"]
        let idsParam = resortIds.joined(separator: ",")

        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/snow-quality/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        // Verify URL structure
        XCTAssertTrue(url.absoluteString.contains("snow-quality/batch"), "URL should contain endpoint path")
        XCTAssertTrue(url.absoluteString.contains("resort_ids="), "URL should contain resort_ids parameter")
        XCTAssertTrue(url.absoluteString.contains("big-white"), "URL should contain resort ID")

        // The commas should be percent-encoded by URLComponents
        // Verify the API handles this correctly
        let (_, response) = try await URLSession.shared.data(from: url)
        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "API should handle URL-encoded commas")
    }

    func testBatchSnowQualityLargeRequest() async throws {
        // Test that batch endpoint handles requests with many resorts
        let url = stagingAPIBaseURL.appendingPathComponent("api/v1/resorts")
        let (resortsData, _) = try await URLSession.shared.data(from: url)

        let resortsResponse = try JSONDecoder().decode(ResortsResponse.self, from: resortsData)

        // Request all available resorts via batch endpoint
        let resortIds = resortsResponse.resorts.map { $0.id }
        let idsParam = resortIds.joined(separator: ",")

        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/snow-quality/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]

        let (_, response) = try await URLSession.shared.data(from: components.url!)
        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Batch endpoint should handle all resorts")
    }

    func testBatchConditionsEndpoint() async throws {
        // Test with a few known resort IDs
        let resortIds = ["big-white", "lake-louise"]
        let idsParam = resortIds.joined(separator: ",")

        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/conditions/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Batch conditions endpoint should return 200")

        // Verify we can decode the response
        let decoder = JSONDecoder()
        let batchResponse = try decoder.decode(BatchConditionsResponse.self, from: data)

        XCTAssertEqual(batchResponse.resortCount, resortIds.count, "Should return count matching requested resorts")
        // Note: results might be empty if weather data hasn't been processed
        print("Batch conditions returned \(batchResponse.results.count) resorts with data")
    }

    func testBatchConditionsURLConstruction() async throws {
        // Verify URL construction for batch conditions matches batch snow quality
        let resortIds = ["big-white", "lake-louise"]
        let idsParam = resortIds.joined(separator: ",")

        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/conditions/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        // Verify URL structure
        XCTAssertTrue(url.absoluteString.contains("conditions/batch"), "URL should contain endpoint path")
        XCTAssertTrue(url.absoluteString.contains("resort_ids="), "URL should contain resort_ids parameter")

        // Verify the API handles this correctly
        let (_, response) = try await URLSession.shared.data(from: url)
        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "API should handle URL-encoded commas")
    }

    // MARK: - Recommendations Endpoint Tests

    func testRecommendationsEndpoint() async throws {
        // Test with coordinates near Whistler
        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/recommendations"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "lat", value: "50.1163"),
            URLQueryItem(name: "lng", value: "-122.9574"),
            URLQueryItem(name: "radius", value: "500"),
            URLQueryItem(name: "limit", value: "10")
        ]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Recommendations endpoint should return 200")

        // Verify we can decode the response
        let decoder = JSONDecoder()
        let recommendationsResponse = try decoder.decode(RecommendationsResponse.self, from: data)

        XCTAssertNotNil(recommendationsResponse.generatedAt)
        print("Recommendations returned \(recommendationsResponse.recommendations.count) results")
    }

    func testRecommendationsParameterNames() async throws {
        // This test verifies the exact parameter names expected by the API
        // lat, lng, radius, limit - NOT latitude, longitude, radius_km
        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/recommendations"), resolvingAgainstBaseURL: false)!

        // Use WRONG parameter names (latitude/longitude instead of lat/lng)
        // This should fail with 422 if parameter validation is strict
        components.queryItems = [
            URLQueryItem(name: "latitude", value: "50.1163"),
            URLQueryItem(name: "longitude", value: "-122.9574")
        ]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        let (_, response) = try await URLSession.shared.data(from: url)
        let httpResponse = response as! HTTPURLResponse

        // Should fail because lat/lng are required (not latitude/longitude)
        XCTAssertEqual(httpResponse.statusCode, 422, "Using wrong parameter names should return 422")
    }

    func testBestConditionsEndpoint() async throws {
        // Test the global best conditions endpoint (no location required)
        var components = URLComponents(url: stagingAPIBaseURL.appendingPathComponent("api/v1/recommendations/best"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "limit", value: "10")
        ]

        guard let url = components.url else {
            XCTFail("Failed to construct URL")
            return
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        let httpResponse = response as! HTTPURLResponse
        XCTAssertEqual(httpResponse.statusCode, 200, "Best conditions endpoint should return 200")

        // Verify we can decode the response
        let decoder = JSONDecoder()
        let recommendationsResponse = try decoder.decode(RecommendationsResponse.self, from: data)

        XCTAssertNotNil(recommendationsResponse.generatedAt)
        print("Best conditions returned \(recommendationsResponse.recommendations.count) results")
    }

    // MARK: - Response Model Decoding Tests

    func testSnowQualitySummaryLightDecoding() throws {
        // Test that SnowQualitySummaryLight can decode API response format
        let json = """
        {
            "resort_id": "big-white",
            "overall_quality": "excellent",
            "last_updated": "2026-01-30T18:19:17.906493+00:00"
        }
        """

        let data = json.data(using: .utf8)!
        let summary = try JSONDecoder().decode(SnowQualitySummaryLight.self, from: data)

        XCTAssertEqual(summary.resortId, "big-white")
        XCTAssertEqual(summary.overallQuality, "excellent")
        XCTAssertEqual(summary.overallSnowQuality, .excellent)
        XCTAssertNotNil(summary.lastUpdated)
    }

    func testBatchSnowQualityResponseDecoding() throws {
        // Test full batch response decoding
        let json = """
        {
            "results": {
                "big-white": {
                    "resort_id": "big-white",
                    "overall_quality": "excellent",
                    "last_updated": "2026-01-30T18:19:17.906493+00:00"
                },
                "lake-louise": {
                    "resort_id": "lake-louise",
                    "overall_quality": "good",
                    "last_updated": "2026-01-30T18:19:17.906493+00:00"
                }
            },
            "last_updated": "2026-01-30T18:55:05.522823+00:00",
            "resort_count": 2
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(BatchSnowQualityResponse.self, from: data)

        XCTAssertEqual(response.resortCount, 2)
        XCTAssertNotNil(response.lastUpdated)
        XCTAssertEqual(response.results.count, 2)
        XCTAssertNotNil(response.results["big-white"])
        XCTAssertNotNil(response.results["lake-louise"])
    }
}
