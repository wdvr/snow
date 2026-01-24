import Foundation
import Alamofire
import KeychainSwift

// MARK: - API Client

class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let session: Session

    private init() {
        self.baseURL = AppConfiguration.shared.apiBaseURL

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 5
        configuration.timeoutIntervalForResource = 15

        self.session = Session(configuration: configuration)
    }

    static func configure() {
        // Perform any initial configuration
        print("API Client configured with base URL: \(shared.baseURL)")
    }

    // MARK: - Resort API

    func getResorts() async throws -> [Resort] {
        let url = baseURL.appendingPathComponent("api/v1/resorts")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: ResortsResponse.self) { response in
                    switch response.result {
                    case .success(let resortsResponse):
                        print("Successfully decoded \(resortsResponse.resorts.count) resorts from API")
                        continuation.resume(returning: resortsResponse.resorts)
                    case .failure(let error):
                        print("API Error decoding resorts: \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    func getResort(id: String) async throws -> Resort {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(id)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: Resort.self) { response in
                    switch response.result {
                    case .success(let resort):
                        continuation.resume(returning: resort)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    // MARK: - Weather Conditions API

    func getConditions(for resortId: String) async throws -> [WeatherCondition] {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/conditions")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: ConditionsResponse.self) { response in
                    switch response.result {
                    case .success(let conditionsResponse):
                        print("Successfully decoded \(conditionsResponse.conditions.count) conditions for \(resortId)")
                        continuation.resume(returning: conditionsResponse.conditions)
                    case .failure(let error):
                        print("API Error decoding conditions for \(resortId): \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    func getConditions(for resortId: String, elevation: ElevationLevel) async throws -> WeatherCondition {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/conditions/\(elevation.rawValue)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: WeatherCondition.self) { response in
                    switch response.result {
                    case .success(let condition):
                        continuation.resume(returning: condition)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    func getSnowQuality(for resortId: String) async throws -> SnowQualitySummary {
        let url = baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/snow-quality")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: SnowQualitySummary.self) { response in
                    switch response.result {
                    case .success(let summary):
                        continuation.resume(returning: summary)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    // MARK: - User API

    func getUserPreferences() async throws -> UserPreferences {
        let url = baseURL.appendingPathComponent("api/v1/user/preferences")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: UserPreferences.self) { response in
                    switch response.result {
                    case .success(let preferences):
                        continuation.resume(returning: preferences)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    func updateUserPreferences(_ preferences: UserPreferences) async throws {
        let url = baseURL.appendingPathComponent("api/v1/user/preferences")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .put,
                parameters: preferences,
                encoder: JSONParameterEncoder.default,
                headers: authHeaders()
            )
            .validate()
            .response { response in
                if let error = response.error {
                    continuation.resume(throwing: self.mapError(error))
                } else {
                    continuation.resume()
                }
            }
        }
    }

    // MARK: - Authentication

    private func authHeaders() -> HTTPHeaders {
        var headers = HTTPHeaders([
            "Content-Type": "application/json"
        ])

        // Get token from keychain directly (nonisolated)
        if let token = KeychainSwift().get("com.snowtracker.authToken") {
            headers.add(.authorization(bearerToken: token))
        }

        return headers
    }

    // MARK: - Error Mapping

    private func mapError(_ error: AFError) -> APIError {
        switch error {
        case .responseValidationFailed(let reason):
            if case .unacceptableStatusCode(let code) = reason {
                switch code {
                case 401:
                    return .unauthorized
                case 404:
                    return .notFound
                case 500...599:
                    return .serverError(code)
                default:
                    return .networkError(error.localizedDescription)
                }
            }
            return .networkError(error.localizedDescription)
        case .sessionTaskFailed(let error):
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet:
                    return .noConnection
                case .timedOut:
                    return .timeout
                default:
                    return .networkError(urlError.localizedDescription)
                }
            }
            return .networkError(error.localizedDescription)
        default:
            return .networkError(error.localizedDescription)
        }
    }
}

// MARK: - Response Models

struct ResortsResponse: Codable {
    let resorts: [Resort]
}

struct ConditionsResponse: Codable {
    let conditions: [WeatherCondition]
    let lastUpdated: String?
    let resortId: String?

    private enum CodingKeys: String, CodingKey {
        case conditions
        case lastUpdated = "last_updated"
        case resortId = "resort_id"
    }
}

struct SnowQualitySummary: Codable {
    let resortId: String
    let elevations: [String: ElevationSummary]
    let overallQuality: String
    let lastUpdated: String?

    private enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case elevations
        case overallQuality = "overall_quality"
        case lastUpdated = "last_updated"
    }

    var overallSnowQuality: SnowQuality {
        SnowQuality(rawValue: overallQuality) ?? .unknown
    }
}

struct ElevationSummary: Codable {
    let quality: String
    let freshSnowCm: Double
    let confidence: String
    let temperatureCelsius: Double
    let snowfall24hCm: Double
    let timestamp: String

    private enum CodingKeys: String, CodingKey {
        case quality
        case freshSnowCm = "fresh_snow_cm"
        case confidence
        case temperatureCelsius = "temperature_celsius"
        case snowfall24hCm = "snowfall_24h_cm"
        case timestamp
    }

    var snowQuality: SnowQuality {
        SnowQuality(rawValue: quality) ?? .unknown
    }

    var confidenceLevel: ConfidenceLevel {
        ConfidenceLevel(rawValue: confidence) ?? .medium
    }
}

struct UserPreferences: Codable {
    var userId: String
    var favoriteResorts: [String]
    var notificationPreferences: [String: Bool]
    var preferredUnits: [String: String]
    var qualityThreshold: String
    var createdAt: String
    var updatedAt: String

    private enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case favoriteResorts = "favorite_resorts"
        case notificationPreferences = "notification_preferences"
        case preferredUnits = "preferred_units"
        case qualityThreshold = "quality_threshold"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - API Errors

enum APIError: Error, LocalizedError {
    case invalidURL
    case noData
    case decodingError
    case networkError(String)
    case unauthorized
    case notFound
    case serverError(Int)
    case noConnection
    case timeout

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .noData:
            return "No data received"
        case .decodingError:
            return "Failed to decode response"
        case .networkError(let message):
            return "Network error: \(message)"
        case .unauthorized:
            return "Please sign in to continue"
        case .notFound:
            return "Resource not found"
        case .serverError(let code):
            return "Server error: \(code)"
        case .noConnection:
            return "No internet connection"
        case .timeout:
            return "Request timed out"
        }
    }
}
