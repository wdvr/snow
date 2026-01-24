import Foundation

// MARK: - Widget Data Service

class WidgetDataService {
    static let shared = WidgetDataService()

    private let baseURL: URL

    private init() {
        // Use production API for widgets
        self.baseURL = URL(string: "https://nzp9wfv4rb.execute-api.us-west-2.amazonaws.com/prod")!
    }

    // MARK: - Fetch Best Resorts

    func fetchBestResorts() async throws -> [ResortConditionData] {
        // Fetch all resorts and their conditions, then sort by snow quality
        let resorts = try await fetchAllResortsWithConditions()

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

        return Array(sorted.prefix(2))
    }

    // MARK: - Fetch Favorite Resorts

    func fetchFavoriteResorts() async throws -> [ResortConditionData] {
        // Load favorites from UserDefaults (shared with main app via App Group)
        let favorites = loadFavorites()

        if favorites.isEmpty {
            return []
        }

        let allResorts = try await fetchAllResortsWithConditions()

        // Filter to only favorites
        let favoriteResorts = allResorts.filter { favorites.contains($0.resortId) }

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
        let (resortsData, _) = try await URLSession.shared.data(from: resortsURL)

        guard let resortsResponse = try? JSONDecoder().decode(ResortsAPIResponse.self, from: resortsData) else {
            throw WidgetError.decodingError
        }

        var results: [ResortConditionData] = []

        // Fetch conditions for each resort (limit to avoid too many requests)
        for resort in resortsResponse.resorts.prefix(10) {
            if let condition = try? await fetchConditions(for: resort.resortId) {
                results.append(ResortConditionData(
                    resortId: resort.resortId,
                    resortName: resort.name,
                    location: "\(resort.region), \(resort.country)",
                    snowQuality: WidgetSnowQuality(rawValue: condition.snowQuality) ?? .unknown,
                    temperature: condition.currentTempCelsius,
                    freshSnow: condition.freshSnowCm,
                    predictedSnow24h: condition.predictedSnow24hCm ?? 0
                ))
            }
        }

        return results
    }

    private func fetchConditions(for resortId: String) async throws -> WidgetCondition {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/conditions")
        let (data, _) = try await URLSession.shared.data(from: url)

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase

        guard let response = try? decoder.decode(ConditionsAPIResponse.self, from: data),
              let topCondition = response.conditions.first(where: { $0.elevationLevel == "top" }) ?? response.conditions.first else {
            throw WidgetError.noData
        }

        return topCondition
    }

    private func loadFavorites() -> Set<String> {
        // Try to load from App Group UserDefaults
        if let defaults = UserDefaults(suiteName: "group.com.snowtracker.app") {
            let favorites = defaults.stringArray(forKey: "favoriteResorts") ?? []
            return Set(favorites)
        }

        // Fallback to standard UserDefaults
        let favorites = UserDefaults.standard.stringArray(forKey: "favoriteResorts") ?? []
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
