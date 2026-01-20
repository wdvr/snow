import Foundation
import Alamofire

// MARK: - API Client

class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let session: Session

    private init() {
        // TODO: Read from configuration
        #if DEBUG
        self.baseURL = URL(string: "https://api-dev.snow-tracker.com")!
        #else
        self.baseURL = URL(string: "https://api.snow-tracker.com")!
        #endif

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60

        self.session = Session(configuration: configuration)
    }

    static func configure() {
        // Perform any initial configuration
    }

    // MARK: - Resort API

    func getResorts() async throws -> [Resort] {
        let url = baseURL.appendingPathComponent("/api/v1/resorts")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: ResortsResponse.self) { response in
                    switch response.result {
                    case .success(let resortsResponse):
                        continuation.resume(returning: resortsResponse.resorts)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    func getResort(id: String) async throws -> Resort {
        let url = baseURL.appendingPathComponent("/api/v1/resorts/\(id)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: Resort.self) { response in
                    switch response.result {
                    case .success(let resort):
                        continuation.resume(returning: resort)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Weather Conditions API

    func getConditions(for resortId: String) async throws -> [WeatherCondition] {
        let url = baseURL.appendingPathComponent("/api/v1/resorts/\(resortId)/conditions")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: ConditionsResponse.self) { response in
                    switch response.result {
                    case .success(let conditionsResponse):
                        continuation.resume(returning: conditionsResponse.conditions)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    func getConditions(for resortId: String, elevation: ElevationLevel) async throws -> WeatherCondition {
        let url = baseURL.appendingPathComponent("/api/v1/resorts/\(resortId)/conditions/\(elevation.rawValue)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: WeatherCondition.self) { response in
                    switch response.result {
                    case .success(let condition):
                        continuation.resume(returning: condition)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - User API

    func getUserPreferences() async throws -> UserPreferences {
        let url = baseURL.appendingPathComponent("/api/v1/user/preferences")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: UserPreferences.self) { response in
                    switch response.result {
                    case .success(let preferences):
                        continuation.resume(returning: preferences)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    func updateUserPreferences(_ preferences: UserPreferences) async throws {
        let url = baseURL.appendingPathComponent("/api/v1/user/preferences")

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
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume()
                }
            }
        }
    }

    // MARK: - Authentication

    private func authHeaders() -> HTTPHeaders {
        // TODO: Implement JWT token retrieval from keychain
        return HTTPHeaders([
            "Authorization": "Bearer \(getAuthToken() ?? "")",
            "Content-Type": "application/json"
        ])
    }

    private func getAuthToken() -> String? {
        // TODO: Retrieve JWT token from keychain
        return nil
    }
}

// MARK: - Response Models

struct ResortsResponse: Codable {
    let resorts: [Resort]
}

struct ConditionsResponse: Codable {
    let conditions: [WeatherCondition]
    let lastUpdated: String
}

struct UserPreferences: Codable {
    let userId: String
    let favoriteResorts: [String]
    let notificationPreferences: [String: Bool]
    let preferredUnits: [String: String]
    let qualityThreshold: String
    let createdAt: String
    let updatedAt: String

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
    case serverError(Int)

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
            return "Authentication required"
        case .serverError(let code):
            return "Server error: \(code)"
        }
    }
}