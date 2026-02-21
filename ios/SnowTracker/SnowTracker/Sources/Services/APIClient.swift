import Foundation
import Alamofire
import KeychainSwift
import os.log

// MARK: - API Client

@MainActor
final class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let session: Session
    private let log = Logger(subsystem: "com.snowtracker.app", category: "APIClient")

    private init() {
        self.baseURL = AppConfiguration.shared.apiBaseURL

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60

        // Retry transient failures with exponential backoff
        let retryPolicy = RetryPolicy(
            retryLimit: 2,
            exponentialBackoffBase: 2,
            exponentialBackoffScale: 0.5,
            retryableHTTPStatusCodes: Set([408, 500, 502, 503, 504])
        )

        self.session = Session(
            configuration: configuration,
            interceptor: retryPolicy
        )
    }

    static func configure() {
        _ = shared
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
                        self.log.debug("Decoded \(resortsResponse.resorts.count) resorts")
                        continuation.resume(returning: resortsResponse.resorts)
                    case .failure(let error):
                        self.log.error("Error decoding resorts: \(error)")
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

    /// Fetch resorts near a given location, sorted by distance
    func getNearbyResorts(latitude: Double, longitude: Double, radiusKm: Double = 200, limit: Int = 20) async throws -> NearbyResortsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/resorts/nearby"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "lat", value: String(latitude)),
            URLQueryItem(name: "lon", value: String(longitude)),
            URLQueryItem(name: "radius", value: String(radiusKm)),
            URLQueryItem(name: "limit", value: String(limit))
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: NearbyResortsResponse.self) { response in
                    switch response.result {
                    case .success(let nearbyResponse):
                        self.log.debug("Fetched \(nearbyResponse.count) nearby resorts")
                        continuation.resume(returning: nearbyResponse)
                    case .failure(let error):
                        self.log.error("Error fetching nearby resorts: \(error)")
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
                        self.log.debug("Decoded \(conditionsResponse.conditions.count) conditions for \(resortId)")
                        continuation.resume(returning: conditionsResponse.conditions)
                    case .failure(let error):
                        self.log.error("Error decoding conditions for \(resortId): \(error)")
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

    /// Fetch conditions for multiple resorts in a single request (max 20)
    func getBatchConditions(resortIds: [String]) async throws -> [String: [WeatherCondition]] {
        // Build URL with query parameter
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/conditions/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "resort_ids", value: resortIds.joined(separator: ","))
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: BatchConditionsResponse.self) { response in
                    switch response.result {
                    case .success(let batchResponse):
                        // Convert response to dict of conditions
                        var result: [String: [WeatherCondition]] = [:]
                        for (resortId, resortResult) in batchResponse.results {
                            result[resortId] = resortResult.conditions
                        }
                        self.log.debug("Fetched batch conditions for \(batchResponse.resortCount) resorts")
                        continuation.resume(returning: result)
                    case .failure(let error):
                        self.log.error("Error fetching batch conditions: \(error)")
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

    /// Fetch timeline data for a resort at a specific elevation
    func getTimeline(for resortId: String, elevation: ElevationLevel = .mid) async throws -> TimelineResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/resorts/\(resortId)/timeline"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "elevation", value: elevation.rawValue)
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: TimelineResponse.self) { response in
                    switch response.result {
                    case .success(let timelineResponse):
                        continuation.resume(returning: timelineResponse)
                    case .failure(let error):
                        self.log.error("Error fetching timeline for \(resortId): \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    func getBatchSnowQuality(for resortIds: [String]) async throws -> [String: SnowQualitySummaryLight] {
        guard !resortIds.isEmpty else { return [:] }

        // Limit to 200 resorts per batch (backend supports up to 200)
        let ids = Array(resortIds.prefix(200))

        // Build URL with query parameter (same pattern as getBatchConditions)
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/snow-quality/batch"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "resort_ids", value: ids.joined(separator: ","))
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url)
                .validate()
                .responseDecodable(of: BatchSnowQualityResponse.self) { response in
                    switch response.result {
                    case .success(let batchResponse):
                        continuation.resume(returning: batchResponse.results)
                    case .failure(let error):
                        self.log.error("Error fetching batch snow quality: \(error)")
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

    // MARK: - Recommendations API

    /// Get location-based resort recommendations
    func getRecommendations(
        latitude: Double,
        longitude: Double,
        radiusKm: Double = 500,
        limit: Int = 10,
        minQuality: SnowQuality? = nil
    ) async throws -> RecommendationsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/recommendations"), resolvingAgainstBaseURL: false)!
        var queryItems = [
            URLQueryItem(name: "lat", value: String(latitude)),
            URLQueryItem(name: "lng", value: String(longitude)),
            URLQueryItem(name: "radius", value: String(radiusKm)),
            URLQueryItem(name: "limit", value: String(limit))
        ]
        if let minQuality = minQuality {
            queryItems.append(URLQueryItem(name: "min_quality", value: minQuality.rawValue))
        }
        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: RecommendationsResponse.self) { response in
                    switch response.result {
                    case .success(let recommendationsResponse):
                        self.log.debug("Fetched \(recommendationsResponse.recommendations.count) recommendations")
                        continuation.resume(returning: recommendationsResponse)
                    case .failure(let error):
                        self.log.error("Error fetching recommendations: \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    /// Get global best snow conditions
    func getBestConditions(limit: Int = 10, minQuality: SnowQuality? = nil) async throws -> RecommendationsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/recommendations/best"), resolvingAgainstBaseURL: false)!
        var queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        if let minQuality = minQuality {
            queryItems.append(URLQueryItem(name: "min_quality", value: minQuality.rawValue))
        }
        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: RecommendationsResponse.self) { response in
                    switch response.result {
                    case .success(let recommendationsResponse):
                        self.log.debug("Fetched \(recommendationsResponse.recommendations.count) best conditions")
                        continuation.resume(returning: recommendationsResponse)
                    case .failure(let error):
                        self.log.error("Error fetching best conditions: \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    // MARK: - Authentication API

    /// Authenticate with Apple Sign In
    func authenticateWithApple(identityToken: String, authorizationCode: String?, firstName: String?, lastName: String?) async throws -> AuthResponse {
        let url = baseURL.appendingPathComponent("api/v1/auth/apple")

        let request = AppleSignInRequest(
            identityToken: identityToken,
            authorizationCode: authorizationCode,
            firstName: firstName,
            lastName: lastName
        )

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: request,
                encoder: JSONParameterEncoder.default
            )
            .validate()
            .responseDecodable(of: AuthResponse.self) { response in
                switch response.result {
                case .success(let authResponse):
                    self.log.debug("Authenticated with Apple")
                    continuation.resume(returning: authResponse)
                case .failure(let error):
                    self.log.error("Error authenticating with Apple: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Authenticate as guest
    func authenticateAsGuest(deviceId: String) async throws -> AuthResponse {
        let url = baseURL.appendingPathComponent("api/v1/auth/guest")

        let request = GuestAuthRequest(deviceId: deviceId)

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: request,
                encoder: JSONParameterEncoder.default
            )
            .validate()
            .responseDecodable(of: AuthResponse.self) { response in
                switch response.result {
                case .success(let authResponse):
                    self.log.debug("Authenticated as guest")
                    continuation.resume(returning: authResponse)
                case .failure(let error):
                    self.log.error("Error authenticating as guest: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Refresh authentication tokens
    func refreshAuthTokens(refreshToken: String) async throws -> AuthResponse {
        let url = baseURL.appendingPathComponent("api/v1/auth/refresh")

        let request = RefreshTokenRequest(refreshToken: refreshToken)

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: request,
                encoder: JSONParameterEncoder.default
            )
            .validate()
            .responseDecodable(of: AuthResponse.self) { response in
                switch response.result {
                case .success(let authResponse):
                    self.log.debug("Refreshed tokens")
                    continuation.resume(returning: authResponse)
                case .failure(let error):
                    self.log.error("Error refreshing tokens: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Get current user info
    func getCurrentUser() async throws -> AuthenticatedUserInfo {
        let url = baseURL.appendingPathComponent("api/v1/auth/me")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: AuthenticatedUserInfo.self) { response in
                    switch response.result {
                    case .success(let userInfo):
                        continuation.resume(returning: userInfo)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    // MARK: - Trip Planning API

    /// Create a new trip
    func createTrip(_ tripData: TripCreateRequest) async throws -> Trip {
        let url = baseURL.appendingPathComponent("api/v1/trips")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: tripData,
                encoder: JSONParameterEncoder.default,
                headers: authHeaders()
            )
            .validate()
            .responseDecodable(of: Trip.self) { response in
                switch response.result {
                case .success(let trip):
                    self.log.debug("Created trip: \(trip.tripId)")
                    continuation.resume(returning: trip)
                case .failure(let error):
                    self.log.error("Error creating trip: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Get all trips for current user
    func getTrips(status: TripStatus? = nil, includePast: Bool = true) async throws -> TripsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/trips"), resolvingAgainstBaseURL: false)!
        var queryItems: [URLQueryItem] = []
        if let status = status {
            queryItems.append(URLQueryItem(name: "status", value: status.rawValue))
        }
        queryItems.append(URLQueryItem(name: "include_past", value: String(includePast)))
        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: TripsResponse.self) { response in
                    switch response.result {
                    case .success(let tripsResponse):
                        self.log.debug("Fetched \(tripsResponse.trips.count) trips")
                        continuation.resume(returning: tripsResponse)
                    case .failure(let error):
                        self.log.error("Error fetching trips: \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    /// Get a specific trip
    func getTrip(tripId: String) async throws -> Trip {
        let url = baseURL.appendingPathComponent("api/v1/trips/\(tripId)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: Trip.self) { response in
                    switch response.result {
                    case .success(let trip):
                        continuation.resume(returning: trip)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    /// Update a trip
    func updateTrip(tripId: String, update: TripUpdateRequest) async throws -> Trip {
        let url = baseURL.appendingPathComponent("api/v1/trips/\(tripId)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .put,
                parameters: update,
                encoder: JSONParameterEncoder.default,
                headers: authHeaders()
            )
            .validate()
            .responseDecodable(of: Trip.self) { response in
                switch response.result {
                case .success(let trip):
                    self.log.debug("Updated trip: \(trip.tripId)")
                    continuation.resume(returning: trip)
                case .failure(let error):
                    self.log.error("Error updating trip: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Delete a trip
    func deleteTrip(tripId: String) async throws {
        let url = baseURL.appendingPathComponent("api/v1/trips/\(tripId)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, method: .delete, headers: authHeaders())
                .validate()
                .response { response in
                    if let error = response.error {
                        continuation.resume(throwing: self.mapError(error))
                    } else {
                        self.log.debug("Deleted trip: \(tripId)")
                        continuation.resume()
                    }
                }
        }
    }

    /// Refresh trip conditions
    func refreshTripConditions(tripId: String) async throws -> Trip {
        let url = baseURL.appendingPathComponent("api/v1/trips/\(tripId)/refresh-conditions")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, method: .post, headers: authHeaders())
                .validate()
                .responseDecodable(of: Trip.self) { response in
                    switch response.result {
                    case .success(let trip):
                        self.log.debug("Refreshed trip conditions")
                        continuation.resume(returning: trip)
                    case .failure(let error):
                        self.log.error("Error refreshing trip conditions: \(error)")
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    /// Mark trip alerts as read
    func markAlertsRead(tripId: String, alertIds: [String]? = nil) async throws -> Trip {
        let url = baseURL.appendingPathComponent("api/v1/trips/\(tripId)/alerts/read")

        let request = MarkAlertsReadRequest(alertIds: alertIds)

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: request,
                encoder: JSONParameterEncoder.default,
                headers: authHeaders()
            )
            .validate()
            .responseDecodable(of: Trip.self) { response in
                switch response.result {
                case .success(let trip):
                    self.log.debug("Marked alerts as read")
                    continuation.resume(returning: trip)
                case .failure(let error):
                    self.log.error("Error marking alerts read: \(error)")
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    // MARK: - Feedback API

    func submitFeedback(_ feedback: FeedbackSubmission) async throws {
        let url = baseURL.appendingPathComponent("api/v1/feedback")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: feedback,
                encoder: JSONParameterEncoder.default
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

    // MARK: - Device Token API

    /// Register a device token for push notifications
    func registerDeviceToken(deviceId: String, token: String, platform: String, appVersion: String?) async throws {
        let url = baseURL.appendingPathComponent("api/v1/user/device-tokens")

        let request = DeviceTokenRequest(
            deviceId: deviceId,
            token: token,
            platform: platform,
            appVersion: appVersion
        )

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                parameters: request,
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

    /// Unregister a device token
    func unregisterDeviceToken(deviceId: String) async throws {
        let url = baseURL.appendingPathComponent("api/v1/user/device-tokens/\(deviceId)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, method: .delete, headers: authHeaders())
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

    // MARK: - Notification Settings API

    /// Get notification settings
    func getNotificationSettings() async throws -> NotificationSettings {
        let url = baseURL.appendingPathComponent("api/v1/user/notification-settings")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(url, headers: authHeaders())
                .validate()
                .responseDecodable(of: NotificationSettings.self) { response in
                    switch response.result {
                    case .success(let settings):
                        continuation.resume(returning: settings)
                    case .failure(let error):
                        continuation.resume(throwing: self.mapError(error))
                    }
                }
        }
    }

    /// Update notification settings
    func updateNotificationSettings(_ settings: NotificationSettingsUpdate) async throws {
        let url = baseURL.appendingPathComponent("api/v1/user/notification-settings")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .put,
                parameters: settings,
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

    /// Update resort-specific notification settings
    func updateResortNotificationSettings(resortId: String, settings: ResortNotificationSettingsUpdate) async throws {
        let url = baseURL.appendingPathComponent("api/v1/user/notification-settings/resorts/\(resortId)")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .put,
                parameters: settings,
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

    // MARK: - Debug/Test Endpoints

    /// Send a test push notification (staging only)
    func sendTestPushNotification() async throws -> DebugResponse {
        let url = baseURL.appendingPathComponent("api/v1/debug/test-push-notification")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                headers: authHeaders()
            )
            .validate()
            .responseDecodable(of: DebugResponse.self) { response in
                switch response.result {
                case .success(let result):
                    continuation.resume(returning: result)
                case .failure(let error):
                    continuation.resume(throwing: self.mapError(error))
                }
            }
        }
    }

    /// Trigger the notification processor Lambda (staging only)
    func triggerNotificationProcessor() async throws -> DebugResponse {
        let url = baseURL.appendingPathComponent("api/v1/debug/trigger-notifications")

        return try await withCheckedThrowingContinuation { continuation in
            session.request(
                url,
                method: .post,
                headers: authHeaders()
            )
            .validate()
            .responseDecodable(of: DebugResponse.self) { response in
                switch response.result {
                case .success(let result):
                    continuation.resume(returning: result)
                case .failure(let error):
                    continuation.resume(throwing: self.mapError(error))
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

    private nonisolated func mapError(_ error: AFError) -> APIError {
        switch error {
        case .responseValidationFailed(let reason):
            if case .unacceptableStatusCode(let code) = reason {
                switch code {
                case 401:
                    return .unauthorized
                case 403:
                    return .forbidden
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

struct NearbyResortsResponse: Codable {
    let resorts: [NearbyResortResult]
    let count: Int
    let searchCenter: SearchCenter
    let searchRadiusKm: Double

    private enum CodingKeys: String, CodingKey {
        case resorts
        case count
        case searchCenter = "search_center"
        case searchRadiusKm = "search_radius_km"
    }
}

struct NearbyResortResult: Codable, Identifiable {
    let resort: Resort
    let distanceKm: Double
    let distanceMiles: Double

    var id: String { resort.id }

    private enum CodingKeys: String, CodingKey {
        case resort
        case distanceKm = "distance_km"
        case distanceMiles = "distance_miles"
    }

    /// Formatted distance string based on user preferences
    func formattedDistance(useMetric: Bool) -> String {
        if useMetric {
            if distanceKm < 1 {
                return String(format: "%.0f m", distanceKm * 1000)
            } else if distanceKm < 10 {
                return String(format: "%.1f km", distanceKm)
            } else {
                return String(format: "%.0f km", distanceKm)
            }
        } else {
            if distanceMiles < 1 {
                return String(format: "%.1f mi", distanceMiles)
            } else if distanceMiles < 10 {
                return String(format: "%.1f mi", distanceMiles)
            } else {
                return String(format: "%.0f mi", distanceMiles)
            }
        }
    }
}

struct SearchCenter: Codable {
    let latitude: Double
    let longitude: Double
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

struct BatchConditionsResponse: Codable {
    let results: [String: ResortConditionsResult]
    let lastUpdated: String?
    let resortCount: Int

    private enum CodingKeys: String, CodingKey {
        case results
        case lastUpdated = "last_updated"
        case resortCount = "resort_count"
    }
}

struct ResortConditionsResult: Codable {
    let conditions: [WeatherCondition]
    let error: String?
}

struct SnowQualitySummary: Codable {
    let resortId: String
    let elevations: [String: ElevationSummary]
    let overallQuality: String
    let overallSnowScore: Int?
    let overallExplanation: String?
    let lastUpdated: String?

    private enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case elevations
        case overallQuality = "overall_quality"
        case overallSnowScore = "overall_snow_score"
        case overallExplanation = "overall_explanation"
        case lastUpdated = "last_updated"
    }

    var overallSnowQuality: SnowQuality {
        SnowQuality(rawValue: overallQuality) ?? .unknown
    }
}

struct SnowQualitySummaryLight: Codable {
    let resortId: String
    let overallQuality: String
    let snowScore: Int?
    let explanation: String?
    let lastUpdated: String?
    let temperatureC: Double?
    let snowfallFreshCm: Double?
    let snowfall24hCm: Double?

    private enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case overallQuality = "overall_quality"
        case snowScore = "snow_score"
        case explanation
        case lastUpdated = "last_updated"
        case temperatureC = "temperature_c"
        case snowfallFreshCm = "snowfall_fresh_cm"
        case snowfall24hCm = "snowfall_24h_cm"
    }

    // Explicit initializer for cache reconstruction
    init(resortId: String, overallQuality: String, snowScore: Int? = nil,
         explanation: String? = nil, lastUpdated: String?,
         temperatureC: Double? = nil, snowfallFreshCm: Double? = nil, snowfall24hCm: Double? = nil) {
        self.resortId = resortId
        self.overallQuality = overallQuality
        self.snowScore = snowScore
        self.explanation = explanation
        self.lastUpdated = lastUpdated
        self.temperatureC = temperatureC
        self.snowfallFreshCm = snowfallFreshCm
        self.snowfall24hCm = snowfall24hCm
    }

    /// Snow quality with frontend temperature override
    /// Only overrides at extreme temperatures where skiing is definitely impossible
    var overallSnowQuality: SnowQuality {
        let baseQuality = SnowQuality(rawValue: overallQuality) ?? .unknown

        // Only override at summer temperatures (>= 15°C) where no snow can exist
        // For moderate temps, trust the backend's quality assessment which has snow depth data
        if let temp = temperatureC, temp >= 15.0 {
            // Summer temperatures - definitely not skiable
            return .horrible
        }

        return baseQuality
    }

    /// Raw quality without temperature override (for debugging)
    var rawSnowQuality: SnowQuality {
        SnowQuality(rawValue: overallQuality) ?? .unknown
    }

    /// Formatted temperature string (e.g., "-5°C (21°F)")
    var formattedTemperature: String? {
        guard let temp = temperatureC else { return nil }
        let fahrenheit = temp * 9 / 5 + 32
        return String(format: "%.0f°C (%.0f°F)", temp, fahrenheit)
    }

    /// Formatted fresh snow depth - shows the meaningful "fresh snow on ice" metric
    var formattedFreshSnow: String? {
        guard let snow = snowfallFreshCm else { return nil }
        return String(format: "%.1fcm", snow)
    }

    private static let isoFractionalFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let isoBasicFormatter = ISO8601DateFormatter()

    /// Formatted timestamp relative to now
    var formattedTimestamp: String? {
        guard let lastUpdated = lastUpdated else { return nil }
        if let date = Self.isoFractionalFormatter.date(from: lastUpdated) {
            return formatRelativeTime(date)
        }
        if let date = Self.isoBasicFormatter.date(from: lastUpdated) {
            return formatRelativeTime(date)
        }
        return nil
    }

    private func formatRelativeTime(_ date: Date) -> String {
        let interval = Date().timeIntervalSince(date)
        if interval < 60 {
            return "Just now"
        } else if interval < 3600 {
            let minutes = Int(interval / 60)
            return "\(minutes)m ago"
        } else if interval < 86400 {
            let hours = Int(interval / 3600)
            return "\(hours)h ago"
        } else {
            let days = Int(interval / 86400)
            return "\(days)d ago"
        }
    }
}

struct BatchSnowQualityResponse: Codable {
    let results: [String: SnowQualitySummaryLight]
    let lastUpdated: String
    let resortCount: Int

    private enum CodingKeys: String, CodingKey {
        case results
        case lastUpdated = "last_updated"
        case resortCount = "resort_count"
    }
}

struct ElevationSummary: Codable {
    let quality: String
    let snowScore: Int?
    let freshSnowCm: Double
    let confidence: String
    let temperatureCelsius: Double
    let snowfall24hCm: Double
    let explanation: String?
    let timestamp: String

    private enum CodingKeys: String, CodingKey {
        case quality
        case snowScore = "snow_score"
        case freshSnowCm = "fresh_snow_cm"
        case confidence
        case temperatureCelsius = "temperature_celsius"
        case snowfall24hCm = "snowfall_24h_cm"
        case explanation
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

// MARK: - Feedback Submission Model

struct FeedbackSubmission: Codable {
    let subject: String
    let message: String
    let email: String?
    let appVersion: String
    let buildNumber: String
    let deviceModel: String
    let iosVersion: String

    private enum CodingKeys: String, CodingKey {
        case subject
        case message
        case email
        case appVersion = "app_version"
        case buildNumber = "build_number"
        case deviceModel = "device_model"
        case iosVersion = "ios_version"
    }
}

// MARK: - Recommendations Models

struct RecommendationsResponse: Codable {
    let recommendations: [ResortRecommendation]
    let searchCenter: SearchLocation?
    let searchRadiusKm: Double?
    let generatedAt: String

    private enum CodingKeys: String, CodingKey {
        case recommendations
        case searchCenter = "search_center"
        case searchRadiusKm = "search_radius_km"
        case generatedAt = "generated_at"
    }
}

struct SearchLocation: Codable {
    let latitude: Double
    let longitude: Double
}

struct ResortRecommendation: Codable, Identifiable {
    let resort: Resort
    let distanceKm: Double
    let distanceMiles: Double
    let snowQuality: String
    let qualityScore: Double
    let distanceScore: Double
    let combinedScore: Double
    let freshSnowCm: Double
    let predictedSnow72hCm: Double
    let currentTempCelsius: Double
    let confidenceLevel: String
    let reason: String
    let elevationConditions: [String: ElevationConditionSummary]

    var id: String { resort.id }

    private enum CodingKeys: String, CodingKey {
        case resort
        case distanceKm = "distance_km"
        case distanceMiles = "distance_miles"
        case snowQuality = "snow_quality"
        case qualityScore = "quality_score"
        case distanceScore = "distance_score"
        case combinedScore = "combined_score"
        case freshSnowCm = "fresh_snow_cm"
        case predictedSnow72hCm = "predicted_snow_72h_cm"
        case currentTempCelsius = "current_temp_celsius"
        case confidenceLevel = "confidence_level"
        case reason
        case elevationConditions = "elevation_conditions"
    }

    var quality: SnowQuality {
        SnowQuality(rawValue: snowQuality) ?? .unknown
    }

    var confidence: ConfidenceLevel {
        ConfidenceLevel(rawValue: confidenceLevel) ?? .medium
    }

    func formattedDistance(useMetric: Bool) -> String {
        if useMetric {
            if distanceKm < 1 {
                return String(format: "%.0f m", distanceKm * 1000)
            } else if distanceKm < 10 {
                return String(format: "%.1f km", distanceKm)
            } else {
                return String(format: "%.0f km", distanceKm)
            }
        } else {
            if distanceMiles < 1 {
                return String(format: "%.1f mi", distanceMiles)
            } else if distanceMiles < 10 {
                return String(format: "%.1f mi", distanceMiles)
            } else {
                return String(format: "%.0f mi", distanceMiles)
            }
        }
    }
}

struct ElevationConditionSummary: Codable {
    let quality: String
    let tempCelsius: Double
    let freshSnowCm: Double
    let snowfall24hCm: Double
    let predicted24hCm: Double

    private enum CodingKeys: String, CodingKey {
        case quality
        case tempCelsius = "temp_celsius"
        case freshSnowCm = "fresh_snow_cm"
        case snowfall24hCm = "snowfall_24h_cm"
        case predicted24hCm = "predicted_24h_cm"
    }

    var snowQuality: SnowQuality {
        SnowQuality(rawValue: quality) ?? .unknown
    }
}

// MARK: - Authentication Models

struct AppleSignInRequest: Codable {
    let identityToken: String
    let authorizationCode: String?
    let firstName: String?
    let lastName: String?

    private enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case authorizationCode = "authorization_code"
        case firstName = "first_name"
        case lastName = "last_name"
    }
}

struct GuestAuthRequest: Codable {
    let deviceId: String

    private enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
    }
}

struct RefreshTokenRequest: Codable {
    let refreshToken: String

    private enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

struct AuthResponse: Codable {
    let user: AuthenticatedUserInfo
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int

    private enum CodingKeys: String, CodingKey {
        case user
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct AuthenticatedUserInfo: Codable {
    let userId: String
    let email: String?
    let firstName: String?
    let lastName: String?
    let provider: String
    let isNewUser: Bool

    private enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case email
        case firstName = "first_name"
        case lastName = "last_name"
        case provider
        case isNewUser = "is_new_user"
    }

    var displayName: String {
        if let first = firstName, let last = lastName {
            return "\(first) \(last)"
        } else if let first = firstName {
            return first
        } else if let email = email {
            return email
        } else {
            return "Guest"
        }
    }
}

// MARK: - Trip Models

struct Trip: Codable, Identifiable, Sendable {
    let tripId: String
    let userId: String
    let resortId: String
    let resortName: String
    let startDate: String
    let endDate: String
    let status: String
    let notes: String?
    let partySize: Int
    let conditionsAtCreation: TripConditionSnapshot?
    let latestConditions: TripConditionSnapshot?
    let alerts: [TripAlert]
    let alertPreferences: [String: Bool]
    let createdAt: String
    let updatedAt: String

    var id: String { tripId }

    private enum CodingKeys: String, CodingKey {
        case tripId = "trip_id"
        case userId = "user_id"
        case resortId = "resort_id"
        case resortName = "resort_name"
        case startDate = "start_date"
        case endDate = "end_date"
        case status
        case notes
        case partySize = "party_size"
        case conditionsAtCreation = "conditions_at_creation"
        case latestConditions = "latest_conditions"
        case alerts
        case alertPreferences = "alert_preferences"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    var tripStatus: TripStatus {
        TripStatus(rawValue: status) ?? .planned
    }

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    var startDateFormatted: Date? {
        Self.dateFormatter.date(from: startDate)
    }

    var endDateFormatted: Date? {
        Self.dateFormatter.date(from: endDate)
    }

    var daysUntilTrip: Int? {
        guard let start = startDateFormatted else { return nil }
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        let startDay = calendar.startOfDay(for: start)
        let components = calendar.dateComponents([.day], from: today, to: startDay)
        return components.day
    }

    var tripDurationDays: Int {
        guard let start = startDateFormatted, let end = endDateFormatted else { return 1 }
        let calendar = Calendar.current
        let components = calendar.dateComponents([.day], from: start, to: end)
        return (components.day ?? 0) + 1
    }

    var unreadAlertCount: Int {
        alerts.filter { !$0.isRead }.count
    }
}

struct TripConditionSnapshot: Codable, Sendable {
    let timestamp: String
    let snowQuality: String
    let freshSnowCm: Double
    let predictedSnowCm: Double
    let temperatureCelsius: Double?

    private enum CodingKeys: String, CodingKey {
        case timestamp
        case snowQuality = "snow_quality"
        case freshSnowCm = "fresh_snow_cm"
        case predictedSnowCm = "predicted_snow_cm"
        case temperatureCelsius = "temperature_celsius"
    }

    var quality: SnowQuality {
        SnowQuality(rawValue: snowQuality) ?? .unknown
    }
}

struct TripAlert: Codable, Identifiable, @unchecked Sendable {
    let alertId: String
    let alertType: String
    let message: String
    let createdAt: String
    let isRead: Bool
    let data: [String: AnyCodable]

    var id: String { alertId }

    private enum CodingKeys: String, CodingKey {
        case alertId = "alert_id"
        case alertType = "alert_type"
        case message
        case createdAt = "created_at"
        case isRead = "is_read"
        case data
    }

    var type: TripAlertType {
        TripAlertType(rawValue: alertType) ?? .tripReminder
    }
}

// Helper for dynamic JSON data
struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
}

enum TripStatus: String, Codable, Sendable {
    case planned
    case active
    case completed
    case cancelled
}

enum TripAlertType: String, Codable {
    case powderAlert = "powder_alert"
    case warmSpell = "warm_spell"
    case conditionsImproved = "conditions_improved"
    case conditionsDegraded = "conditions_degraded"
    case tripReminder = "trip_reminder"

    var displayName: String {
        switch self {
        case .powderAlert: return "Powder Alert"
        case .warmSpell: return "Warm Spell Warning"
        case .conditionsImproved: return "Conditions Improved"
        case .conditionsDegraded: return "Conditions Degraded"
        case .tripReminder: return "Trip Reminder"
        }
    }

    var icon: String {
        switch self {
        case .powderAlert: return "snowflake"
        case .warmSpell: return "sun.max.fill"
        case .conditionsImproved: return "arrow.up.circle.fill"
        case .conditionsDegraded: return "arrow.down.circle.fill"
        case .tripReminder: return "bell.fill"
        }
    }
}

struct TripCreateRequest: Codable, Sendable {
    let resortId: String
    let startDate: String
    let endDate: String
    let notes: String?
    let partySize: Int
    let alertPreferences: [String: Bool]?

    private enum CodingKeys: String, CodingKey {
        case resortId = "resort_id"
        case startDate = "start_date"
        case endDate = "end_date"
        case notes
        case partySize = "party_size"
        case alertPreferences = "alert_preferences"
    }
}

struct TripUpdateRequest: Codable, Sendable {
    let startDate: String?
    let endDate: String?
    let notes: String?
    let partySize: Int?
    let status: String?
    let alertPreferences: [String: Bool]?

    private enum CodingKeys: String, CodingKey {
        case startDate = "start_date"
        case endDate = "end_date"
        case notes
        case partySize = "party_size"
        case status
        case alertPreferences = "alert_preferences"
    }
}

struct MarkAlertsReadRequest: Codable {
    let alertIds: [String]?

    private enum CodingKeys: String, CodingKey {
        case alertIds = "alert_ids"
    }
}

struct TripsResponse: Codable, Sendable {
    let trips: [Trip]
    let count: Int
}

// MARK: - Device Token Models

struct DeviceTokenRequest: Codable {
    let deviceId: String
    let token: String
    let platform: String
    let appVersion: String?

    private enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case token
        case platform
        case appVersion = "app_version"
    }
}

// MARK: - Notification Settings Models

struct NotificationSettingsUpdate: Codable {
    var notificationsEnabled: Bool?
    var freshSnowAlerts: Bool?
    var eventAlerts: Bool?
    var thawFreezeAlerts: Bool?
    var weeklySummary: Bool?
    var defaultSnowThresholdCm: Double?
    var gracePeriodHours: Int?

    private enum CodingKeys: String, CodingKey {
        case notificationsEnabled = "notifications_enabled"
        case freshSnowAlerts = "fresh_snow_alerts"
        case eventAlerts = "event_alerts"
        case thawFreezeAlerts = "thaw_freeze_alerts"
        case weeklySummary = "weekly_summary"
        case defaultSnowThresholdCm = "default_snow_threshold_cm"
        case gracePeriodHours = "grace_period_hours"
    }
}

struct ResortNotificationSettingsUpdate: Codable {
    var freshSnowEnabled: Bool?
    var freshSnowThresholdCm: Double?
    var eventNotificationsEnabled: Bool?

    private enum CodingKeys: String, CodingKey {
        case freshSnowEnabled = "fresh_snow_enabled"
        case freshSnowThresholdCm = "fresh_snow_threshold_cm"
        case eventNotificationsEnabled = "event_notifications_enabled"
    }
}

struct DebugResponse: Codable {
    let message: String
    let statusCode: Int?
    let environment: String?
    let tokensFound: Int?
    let results: [DebugNotificationResult]?

    private enum CodingKeys: String, CodingKey {
        case message
        case statusCode = "status_code"
        case environment
        case tokensFound = "tokens_found"
        case results
    }
}

struct DebugNotificationResult: Codable {
    let deviceId: String?
    let status: String
    let error: String?

    private enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case status
        case error
    }
}

// MARK: - API Errors

enum APIError: Error, LocalizedError {
    case invalidURL
    case noData
    case decodingError
    case networkError(String)
    case unauthorized
    case forbidden
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
            return "Session expired. Please sign out and sign in again."
        case .forbidden:
            return "This feature is not available"
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
