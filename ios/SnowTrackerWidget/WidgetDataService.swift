import Foundation
import os.log

// MARK: - Widget Data Service

class WidgetDataService {
    static let shared = WidgetDataService()

    private let baseURL: URL
    private let logger = Logger(subsystem: "com.snowtracker.app.widget", category: "DataService")

    private init() {
        // Use production API for widgets
        self.baseURL = URL(string: "https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod")!
        logger.info("WidgetDataService initialized with URL: \(self.baseURL.absoluteString)")
    }

    // MARK: - Fetch Best Resorts

    func fetchBestResorts() async throws -> [ResortConditionData] {
        logger.info("Fetching best resorts...")

        // Fetch all resorts and their conditions, then sort by snow quality
        let resorts = try await fetchAllResortsWithConditions()
        logger.info("Fetched \(resorts.count) resorts with conditions")

        // Sort by snow quality (excellent first) and fresh snow
        let sorted = resorts.sorted { a, b in
            let qualityOrder: [WidgetSnowQuality] = [.excellent, .good, .fair, .poor, .bad, .unknown]
            let aIndex = qualityOrder.firstIndex(of: a.snowQuality) ?? 5
            let bIndex = qualityOrder.firstIndex(of: b.snowQuality) ?? 5

            if aIndex != bIndex {
                return aIndex < bIndex
            }
            return a.freshSnow > b.freshSnow
        }

        let result = Array(sorted.prefix(2))
        logger.info("Returning \(result.count) best resorts")
        return result
    }

    // MARK: - Fetch Favorite Resorts

    func fetchFavoriteResorts() async throws -> [ResortConditionData] {
        // Load favorites from UserDefaults (shared with main app via App Group)
        let favorites = loadFavorites()
        logger.info("Loaded \(favorites.count) favorites: \(favorites.joined(separator: ", "))")

        if favorites.isEmpty {
            logger.info("No favorites set, returning empty array")
            return []
        }

        let allResorts = try await fetchAllResortsWithConditions()
        logger.info("Fetched \(allResorts.count) resorts, filtering to favorites")

        // Filter to only favorites
        let favoriteResorts = allResorts.filter { favorites.contains($0.resortId) }
        logger.info("Found \(favoriteResorts.count) favorite resorts with data")

        // Sort by quality
        let sorted = favoriteResorts.sorted { a, b in
            let qualityOrder: [WidgetSnowQuality] = [.excellent, .good, .fair, .poor, .bad, .unknown]
            let aIndex = qualityOrder.firstIndex(of: a.snowQuality) ?? 5
            let bIndex = qualityOrder.firstIndex(of: b.snowQuality) ?? 5
            return aIndex < bIndex
        }

        return Array(sorted.prefix(2))
    }

    // MARK: - Private Methods

    private func fetchAllResortsWithConditions() async throws -> [ResortConditionData] {
        // Fetch resorts
        let resortsURL = baseURL.appendingPathComponent("api/v1/resorts")
        logger.info("Fetching resorts from: \(resortsURL.absoluteString)")

        let (resortsData, response) = try await URLSession.shared.data(from: resortsURL)

        if let httpResponse = response as? HTTPURLResponse {
            logger.info("Resorts API response status: \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        do {
            let resortsResponse = try decoder.decode(ResortsAPIResponse.self, from: resortsData)
            logger.info("Decoded \(resortsResponse.resorts.count) resorts")

            var results: [ResortConditionData] = []

            // Fetch conditions for each resort (limit to avoid too many requests)
            for resort in resortsResponse.resorts.prefix(10) {
                do {
                    let condition = try await fetchConditions(for: resort.resortId)
                    results.append(ResortConditionData(
                        resortId: resort.resortId,
                        resortName: resort.name,
                        location: "\(resort.region), \(resort.country)",
                        snowQuality: WidgetSnowQuality(rawValue: condition.snowQuality) ?? .unknown,
                        temperature: condition.currentTempCelsius,
                        freshSnow: condition.freshSnowCm,
                        predictedSnow24h: condition.predictedSnow24hCm ?? 0
                    ))
                    logger.info("Fetched conditions for \(resort.resortId)")
                } catch {
                    logger.error("Failed to fetch conditions for \(resort.resortId): \(error.localizedDescription)")
                }
            }

            logger.info("Total results with conditions: \(results.count)")
            return results
        } catch {
            logger.error("Failed to decode resorts: \(error.localizedDescription)")
            if let jsonString = String(data: resortsData, encoding: .utf8) {
                logger.debug("Raw response: \(jsonString.prefix(500))")
            }
            throw WidgetError.decodingError
        }
    }

    private func fetchConditions(for resortId: String) async throws -> WidgetCondition {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/conditions")
        let (data, response) = try await URLSession.shared.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            logger.debug("Conditions API status for \(resortId): \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        // CodingKeys handle the snake_case to camelCase conversion

        do {
            let conditionsResponse = try decoder.decode(ConditionsAPIResponse.self, from: data)

            guard let topCondition = conditionsResponse.conditions.first(where: { $0.elevationLevel == "top" }) ?? conditionsResponse.conditions.first else {
                logger.warning("No conditions found for \(resortId)")
                throw WidgetError.noData
            }

            return topCondition
        } catch {
            logger.error("Failed to decode conditions for \(resortId): \(error.localizedDescription)")
            throw WidgetError.decodingError
        }
    }

    private func loadFavorites() -> Set<String> {
        // Try to load from App Group UserDefaults
        if let defaults = UserDefaults(suiteName: "group.com.snowtracker.app") {
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

private struct ConditionsAPIResponse: Codable {
    let conditions: [WidgetCondition]
}

private struct WidgetCondition: Codable {
    let resortId: String
    let elevationLevel: String
    let snowQuality: String
    let currentTempCelsius: Double
    let freshSnowCm: Double
    let predictedSnow24hCm: Double?

    enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case elevationLevel = "elevation_level"
        case snowQuality = "snow_quality"
        case currentTempCelsius = "current_temp_celsius"
        case freshSnowCm = "fresh_snow_cm"
        case predictedSnow24hCm = "predicted_snow_24h_cm"
    }
}

// MARK: - Widget Errors

enum WidgetError: Error {
    case networkError
    case decodingError
    case noData
}
