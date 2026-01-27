import SwiftUI
import Combine

// MARK: - Authentication Manager

@MainActor
class AuthenticationManager: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?

    func checkAuthenticationStatus() {
        // TODO: Implement Firebase Auth check
        isLoading = true
        // Simulate auth check
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            self.isAuthenticated = false // Set to true when implementing
            self.isLoading = false
        }
    }

    func signInWithApple() async {
        // TODO: Implement Apple Sign In
        isLoading = true
        defer { isLoading = false }

        // Simulate sign in
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        isAuthenticated = true
    }

    func signOut() {
        // TODO: Implement sign out
        isAuthenticated = false
        currentUser = nil
    }
}

// MARK: - Snow Conditions Manager

@MainActor
class SnowConditionsManager: ObservableObject {
    @Published var resorts: [Resort] = []
    @Published var conditions: [String: [WeatherCondition]] = [:]
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?
    @Published var isUsingCachedData = false
    @Published var cachedDataAge: String?

    private let apiClient = APIClient.shared
    private let cacheService = CacheService.shared

    func loadInitialData() {
        Task {
            await fetchResorts()
            await fetchAllConditions()
            // Clean up old cached data periodically
            cacheService.cleanupStaleCache()
        }
    }

    func refreshData() async {
        await fetchAllConditions()
    }

    func refreshConditions() async {
        await fetchAllConditions()
    }

    func fetchResorts() async {
        isLoading = true
        defer { isLoading = false }

        do {
            // Try to fetch from API
            let fetchedResorts = try await apiClient.getResorts()
            resorts = fetchedResorts
            print("Loaded \(resorts.count) resorts from API")
            errorMessage = nil
            isUsingCachedData = false
            cachedDataAge = nil

            // Cache the fresh data
            cacheService.cacheResorts(fetchedResorts)
        } catch {
            print("API error: \(error.localizedDescription)")

            // Try to load from cache
            if let cachedData = cacheService.getCachedResorts() {
                resorts = cachedData.data
                isUsingCachedData = true
                cachedDataAge = cachedData.ageDescription

                if cachedData.isStale {
                    errorMessage = "Showing cached data (may be outdated)"
                } else {
                    errorMessage = nil
                }
                print("Loaded \(resorts.count) resorts from cache (stale: \(cachedData.isStale))")
            } else {
                // No cache available
                resorts = []
                errorMessage = "Unable to load resorts - check your connection"
                isUsingCachedData = false
            }
        }
    }

    func fetchAllConditions() async {
        isLoading = true
        defer { isLoading = false }

        let resortIds = resorts.map { $0.id }
        var anyFailed = false
        var anyFromCache = false

        // Batch fetch in chunks of 20 (API limit)
        let batchSize = 20
        for batchStart in stride(from: 0, to: resortIds.count, by: batchSize) {
            let batchEnd = min(batchStart + batchSize, resortIds.count)
            let batchIds = Array(resortIds[batchStart..<batchEnd])

            do {
                // Use batch endpoint for efficiency (single request per 20 resorts)
                let batchResults = try await apiClient.getBatchConditions(resortIds: batchIds)

                for (resortId, resortConditions) in batchResults {
                    conditions[resortId] = resortConditions
                    // Cache the fresh data
                    cacheService.cacheConditions(resortConditions, for: resortId)
                }
            } catch {
                print("Batch API error: \(error.localizedDescription)")
                anyFailed = true

                // Fallback: try individual requests or cache for failed batch
                for resortId in batchIds {
                    if let cachedData = cacheService.getCachedConditions(for: resortId) {
                        conditions[resortId] = cachedData.data
                        anyFromCache = true
                        print("Using cached conditions for \(resortId) (stale: \(cachedData.isStale))")
                    } else {
                        conditions[resortId] = []
                    }
                }
            }
        }

        lastUpdated = Date()

        if anyFromCache && anyFailed {
            isUsingCachedData = true
            if errorMessage == nil {
                errorMessage = "Some data from cache"
            }
        } else if !anyFailed {
            isUsingCachedData = false
        }
    }

    func getLatestCondition(for resortId: String) -> WeatherCondition? {
        conditions[resortId]?.first
    }

    func getConditions(for resortId: String, at elevation: ElevationLevel) -> WeatherCondition? {
        conditions[resortId]?.first { $0.elevationLevel == elevation.rawValue }
    }

    func clearCache() {
        cacheService.clearAllCache()
        isUsingCachedData = false
        cachedDataAge = nil
    }
}

// MARK: - User Preferences Manager

@MainActor
class UserPreferencesManager: ObservableObject {
    static let shared = UserPreferencesManager()

    @Published var favoriteResorts: Set<String> = []
    @Published var preferredUnits: UnitPreferences = UnitPreferences() {
        didSet {
            saveUnitPreferences()
        }
    }
    @Published var notificationSettings: NotificationSettings = NotificationSettings()

    private let apiClient = APIClient.shared
    private let favoritesKey = "favoriteResorts"
    private let unitPreferencesKey = "unitPreferences"
    private let appGroupId = "group.com.wouterdevriendt.snowtracker"

    private var sharedDefaults: UserDefaults? {
        UserDefaults(suiteName: appGroupId)
    }

    init() {
        loadLocalPreferences()
    }

    func loadPreferences() async {
        loadLocalPreferences()
    }

    private func loadLocalPreferences() {
        // Try to load from app group first (shared with widget)
        if let sharedDefaults = sharedDefaults,
           let savedFavorites = sharedDefaults.array(forKey: favoritesKey) as? [String] {
            favoriteResorts = Set(savedFavorites)
        } else if let savedFavorites = UserDefaults.standard.array(forKey: favoritesKey) as? [String] {
            // Fallback to standard UserDefaults
            favoriteResorts = Set(savedFavorites)
            // Migrate to shared defaults
            saveLocalPreferences()
        }

        // Load unit preferences
        loadUnitPreferences()
    }

    private func loadUnitPreferences() {
        let defaults = sharedDefaults ?? UserDefaults.standard

        if let data = defaults.data(forKey: unitPreferencesKey),
           let decoded = try? JSONDecoder().decode(UnitPreferences.self, from: data) {
            // Temporarily disable didSet to avoid re-saving during load
            preferredUnits = decoded
        }
    }

    private func saveUnitPreferences() {
        guard let encoded = try? JSONEncoder().encode(preferredUnits) else { return }

        // Save to shared app group (for widget access)
        sharedDefaults?.set(encoded, forKey: unitPreferencesKey)

        // Also save to standard UserDefaults as backup
        UserDefaults.standard.set(encoded, forKey: unitPreferencesKey)
    }

    func toggleFavorite(resortId: String) {
        if favoriteResorts.contains(resortId) {
            favoriteResorts.remove(resortId)
        } else {
            favoriteResorts.insert(resortId)
        }

        saveLocalPreferences()
    }

    func isFavorite(resortId: String) -> Bool {
        favoriteResorts.contains(resortId)
    }

    private func saveLocalPreferences() {
        let favoritesArray = Array(favoriteResorts)

        // Save to shared app group (for widget access)
        sharedDefaults?.set(favoritesArray, forKey: favoritesKey)

        // Also save to standard UserDefaults as backup
        UserDefaults.standard.set(favoritesArray, forKey: favoritesKey)
    }

    func savePreferences() async {
        saveLocalPreferences()
    }
}

// MARK: - Supporting Types

struct User: Codable {
    let id: String
    let email: String?
    let firstName: String?
    let lastName: String?
    let createdAt: String
}

struct UnitPreferences: Codable {
    var temperature: TemperatureUnit = .celsius
    var distance: DistanceUnit = .metric
    var snowDepth: SnowDepthUnit = .centimeters

    enum TemperatureUnit: String, CaseIterable, Codable {
        case celsius = "celsius"
        case fahrenheit = "fahrenheit"
    }

    enum DistanceUnit: String, CaseIterable, Codable {
        case metric = "metric"
        case imperial = "imperial"
    }

    enum SnowDepthUnit: String, CaseIterable, Codable {
        case centimeters = "cm"
        case inches = "inches"
    }
}

struct NotificationSettings: Codable {
    var snowAlerts: Bool = true
    var conditionUpdates: Bool = true
    var weeklySummary: Bool = false
}
