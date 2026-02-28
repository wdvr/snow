import Foundation
import os.log

/// Information about an available app update.
struct AppUpdateInfo: Identifiable, Equatable {
    let id = UUID()
    let minimumVersion: String
    let latestVersion: String
    let updateMessage: String
    let updateURL: URL
    let forceUpdate: Bool

    static func == (lhs: AppUpdateInfo, rhs: AppUpdateInfo) -> Bool {
        lhs.minimumVersion == rhs.minimumVersion &&
        lhs.latestVersion == rhs.latestVersion &&
        lhs.updateMessage == rhs.updateMessage &&
        lhs.updateURL == rhs.updateURL &&
        lhs.forceUpdate == rhs.forceUpdate
    }
}

/// Checks for required app updates on launch by calling the `/api/v1/app-config` endpoint.
///
/// If the server returns a `minimum_ios_version` higher than the current app version,
/// the service sets `updateRequired = true` and populates `updateInfo`.
/// Network failures are silently ignored so the app is never blocked by a down server.
@MainActor
final class AppUpdateService: ObservableObject {
    @Published var updateRequired: Bool = false
    @Published var updateInfo: AppUpdateInfo?

    private var hasChecked = false
    private let log = Logger(subsystem: "com.snowtracker.app", category: "AppUpdateService")

    /// Fetches the app-config endpoint once per launch and compares versions.
    func checkForUpdate() async {
        guard !hasChecked else { return }
        hasChecked = true

        do {
            let info = try await fetchAppConfig()
            let currentVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0"

            if compareVersions(currentVersion, isOlderThan: info.minimumVersion) {
                updateRequired = true
                updateInfo = info
                log.info("Update required: current \(currentVersion) < minimum \(info.minimumVersion)")
            } else {
                log.debug("App is up to date: current \(currentVersion), minimum \(info.minimumVersion)")
            }
        } catch {
            // Silently fail — don't block the app if the server is unreachable
            log.debug("App config check failed (non-blocking): \(error.localizedDescription)")
        }
    }

    // MARK: - Networking

    private struct AppConfigResponse: Decodable {
        let minimum_ios_version: String
        let latest_ios_version: String
        let update_message: String
        let update_url: String
        let force_update: Bool
    }

    private func fetchAppConfig() async throws -> AppUpdateInfo {
        let baseURL = AppConfiguration.shared.apiBaseURL
        let url = baseURL.appendingPathComponent("api/v1/app-config")

        var request = URLRequest(url: url)
        request.timeoutInterval = 10
        request.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        let config = try decoder.decode(AppConfigResponse.self, from: data)

        guard let updateURL = URL(string: config.update_url) else {
            throw URLError(.badURL)
        }

        return AppUpdateInfo(
            minimumVersion: config.minimum_ios_version,
            latestVersion: config.latest_ios_version,
            updateMessage: config.update_message,
            updateURL: updateURL,
            forceUpdate: config.force_update
        )
    }

    // MARK: - Version Comparison

    /// Returns `true` when `lhs` is strictly older than `rhs` using semantic versioning.
    /// Components default to 0 when missing (e.g. "2.1" is treated as "2.1.0").
    func compareVersions(_ lhs: String, isOlderThan rhs: String) -> Bool {
        let lhsParts = lhs.split(separator: ".").compactMap { Int($0) }
        let rhsParts = rhs.split(separator: ".").compactMap { Int($0) }

        let maxLength = max(lhsParts.count, rhsParts.count)

        for i in 0..<maxLength {
            let lhsValue = i < lhsParts.count ? lhsParts[i] : 0
            let rhsValue = i < rhsParts.count ? rhsParts[i] : 0

            if lhsValue < rhsValue { return true }
            if lhsValue > rhsValue { return false }
        }

        return false // versions are equal
    }
}
