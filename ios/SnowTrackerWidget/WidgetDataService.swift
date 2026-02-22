import Foundation
import os.log

// MARK: - Widget Data Service

final class WidgetDataService: @unchecked Sendable {
    static let shared = WidgetDataService()

    private let baseURL: URL
    private let logger = Logger(subsystem: "com.snowtracker.app.widget", category: "DataService")
    private let session: URLSession

    private init() {
        // Use production API for widgets
        self.baseURL = URL(string: "https://api.powderchaserapp.com")!

        // Configure URLSession with shorter timeouts for widget context
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10  // 10 seconds per request
        config.timeoutIntervalForResource = 25 // 25 seconds total
        self.session = URLSession(configuration: config)

        logger.info("WidgetDataService initialized with URL: \(self.baseURL.absoluteString)")
    }

    // MARK: - Fetch Best Resorts (via recommendations endpoint — 1 request)

    func fetchBestResorts(region: String? = nil) async throws -> [ResortConditionData] {
        if let region = region {
            logger.info("Fetching best resorts for region: \(region)")
        } else {
            logger.info("Fetching best resorts (all regions)...")
        }

        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/recommendations/best"), resolvingAgainstBaseURL: false)!
        var queryItems = [URLQueryItem(name: "limit", value: "3")]
        if let region = region {
            queryItems.append(URLQueryItem(name: "region", value: region))
        }
        components.queryItems = queryItems

        let url = components.url!
        logger.info("Fetching recommendations from: \(url.absoluteString)")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            logger.info("Recommendations API response status: \(httpResponse.statusCode)")
            guard httpResponse.statusCode == 200 else {
                logger.error("Bad status code: \(httpResponse.statusCode)")
                throw WidgetError.networkError
            }
        }

        let decoder = JSONDecoder()
        do {
            let recResponse = try decoder.decode(RecommendationsAPIResponse.self, from: data)
            logger.info("Decoded \(recResponse.recommendations.count) recommendations")

            let resorts = recResponse.recommendations.map { rec in
                ResortConditionData(
                    resortId: rec.resort.resortId,
                    resortName: rec.resort.name,
                    location: "\(rec.resort.region), \(rec.resort.country)",
                    snowQuality: WidgetSnowQuality(rawValue: rec.snowQuality) ?? .unknown,
                    temperature: rec.currentTempCelsius,
                    freshSnow: rec.freshSnowCm,
                    predictedSnow24h: rec.predictedSnow72hCm / 3.0 // Approximate 24h from 72h
                )
            }

            logger.info("Returning \(resorts.count) best resorts")
            return resorts
        } catch {
            logger.error("Failed to decode recommendations: \(error.localizedDescription)")
            throw WidgetError.decodingError
        }
    }

    // MARK: - Fetch Favorite Resorts (via batch endpoint — 2 requests max)

    func fetchFavoriteResorts() async throws -> [ResortConditionData] {
        let favorites = loadFavorites()
        logger.info("Loaded \(favorites.count) favorites: \(favorites.joined(separator: ", "))")

        if favorites.isEmpty {
            logger.info("No favorites set, returning empty array")
            return []
        }

        // Fetch resort names and batch conditions in parallel
        let resortIds = Array(favorites)

        async let resortNamesTask = fetchResortNames(for: resortIds)
        async let batchTask = fetchBatchQuality(for: resortIds)

        let (resortNames, batchResults) = try await (resortNamesTask, batchTask)

        logger.info("Got \(resortNames.count) resort names and \(batchResults.count) batch results")

        // Combine into ResortConditionData
        let resorts = batchResults.compactMap { (resortId, summary) -> ResortConditionData? in
            guard let name = resortNames[resortId] else {
                logger.warning("No name found for resort \(resortId)")
                return nil
            }
            return ResortConditionData(
                resortId: resortId,
                resortName: name.name,
                location: name.location,
                snowQuality: WidgetSnowQuality(rawValue: summary.overallQuality) ?? .unknown,
                temperature: summary.temperatureC ?? 0,
                freshSnow: summary.snowfallFreshCm ?? 0,
                predictedSnow24h: (summary.predictedSnow48hCm ?? 0) / 2.0
            )
        }

        // Sort by quality
        let sorted = resorts.sorted { a, b in
            let qualityOrder: [WidgetSnowQuality] = [.excellent, .good, .fair, .poor, .bad, .unknown]
            let aIndex = qualityOrder.firstIndex(of: a.snowQuality) ?? 5
            let bIndex = qualityOrder.firstIndex(of: b.snowQuality) ?? 5

            if aIndex != bIndex {
                return aIndex < bIndex
            }
            return a.freshSnow > b.freshSnow
        }

        return Array(sorted.prefix(2))
    }

    // MARK: - Private Methods

    private func fetchBatchQuality(for resortIds: [String]) async throws -> [String: BatchSummary] {
        let idsParam = resortIds.joined(separator: ",")
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/snow-quality/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "resort_ids", value: idsParam)]
        let url = components.url!

        logger.info("Fetching batch quality for \(resortIds.count) resorts")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            logger.info("Batch API response status: \(httpResponse.statusCode)")
            guard httpResponse.statusCode == 200 else {
                throw WidgetError.networkError
            }
        }

        let decoded = try JSONDecoder().decode(BatchQualityResponse.self, from: data)
        return decoded.results
    }

    private func fetchResortNames(for resortIds: [String]) async throws -> [String: ResortNameInfo] {
        // Fetch all resorts and filter to the ones we need
        let url = baseURL.appendingPathComponent("api/v1/resorts")
        logger.info("Fetching resort list for names")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            guard httpResponse.statusCode == 200 else {
                throw WidgetError.networkError
            }
        }

        let resortsResponse = try JSONDecoder().decode(ResortsAPIResponse.self, from: data)
        let idSet = Set(resortIds)
        var nameMap: [String: ResortNameInfo] = [:]
        for resort in resortsResponse.resorts where idSet.contains(resort.resortId) {
            nameMap[resort.resortId] = ResortNameInfo(name: resort.name, location: "\(resort.region), \(resort.country)")
        }
        return nameMap
    }

    private func loadFavorites() -> Set<String> {
        // Try to load from App Group UserDefaults
        if let defaults = UserDefaults(suiteName: "group.com.wouterdevriendt.snowtracker") {
            let favorites = defaults.stringArray(forKey: "favoriteResorts") ?? []
            logger.info("Loaded \(favorites.count) favorites from app group")
            return Set(favorites)
        }

        logger.warning("Could not access app group, falling back to standard UserDefaults")

        // Fallback to standard UserDefaults
        let favorites = UserDefaults.standard.stringArray(forKey: "favoriteResorts") ?? []
        logger.info("Loaded \(favorites.count) favorites from standard UserDefaults")
        return Set(favorites)
    }
}

// MARK: - API Response Models

private struct ResortsAPIResponse: Codable {
    let resorts: [WidgetResort]
}

private struct WidgetResort: Codable {
    let resortId: String
    let name: String
    let country: String
    let region: String

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case name
        case country
        case region
    }
}

private struct ResortNameInfo {
    let name: String
    let location: String
}

// MARK: - Recommendations Response

private struct RecommendationsAPIResponse: Codable {
    let recommendations: [Recommendation]
}

private struct Recommendation: Codable {
    let resort: RecommendationResort
    let snowQuality: String
    let freshSnowCm: Double
    let predictedSnow72hCm: Double
    let currentTempCelsius: Double

    enum CodingKeys: String, CodingKey {
        case resort
        case snowQuality = "snow_quality"
        case freshSnowCm = "fresh_snow_cm"
        case predictedSnow72hCm = "predicted_snow_72h_cm"
        case currentTempCelsius = "current_temp_celsius"
    }
}

private struct RecommendationResort: Codable {
    let resortId: String
    let name: String
    let country: String
    let region: String

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case name
        case country
        case region
    }
}

// MARK: - Batch Quality Response

private struct BatchQualityResponse: Codable {
    let results: [String: BatchSummary]
}

private struct BatchSummary: Codable {
    let overallQuality: String
    let temperatureC: Double?
    let snowfallFreshCm: Double?
    let snowDepthCm: Double?
    let predictedSnow48hCm: Double?

    enum CodingKeys: String, CodingKey {
        case overallQuality = "overall_quality"
        case temperatureC = "temperature_c"
        case snowfallFreshCm = "snowfall_fresh_cm"
        case snowDepthCm = "snow_depth_cm"
        case predictedSnow48hCm = "predicted_snow_48h_cm"
    }
}

// MARK: - Widget Errors

enum WidgetError: Error {
    case networkError
    case decodingError
    case noData
}
