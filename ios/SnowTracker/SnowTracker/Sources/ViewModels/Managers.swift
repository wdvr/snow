import SwiftUI
import Combine

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
            // Only fetch conditions for favorites on startup (not all 1000+ resorts)
            await fetchConditionsForFavorites()
            // Clean up old cached data periodically
            cacheService.cleanupStaleCache()
        }
    }

    func refreshData() async {
        await fetchConditionsForFavorites()
    }

    func refreshConditions() async {
        await fetchConditionsForFavorites()
    }

    /// Fetch conditions for favorites only - efficient for startup
    func fetchConditionsForFavorites() async {
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        guard !favoriteIds.isEmpty else { return }
        await fetchConditionsForResorts(resortIds: favoriteIds)
    }

    /// Fetch conditions for a single resort - use when opening detail view
    func fetchConditionsForResort(_ resortId: String) async {
        // Check if we already have fresh conditions
        if let existing = conditions[resortId], !existing.isEmpty {
            // Check if cached data is still fresh (less than 5 minutes old)
            if let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale {
                return
            }
        }
        await fetchConditionsForResorts(resortIds: [resortId])
    }

    /// Fetch conditions for a list of resorts (batch API call)
    func fetchConditionsForResorts(resortIds: [String]) async {
        guard !resortIds.isEmpty else { return }

        isLoading = true
        defer { isLoading = false }

        // Use batch API for efficiency
        do {
            let batchResults = try await apiClient.getBatchConditions(resortIds: resortIds)
            for (resortId, resortConditions) in batchResults {
                conditions[resortId] = resortConditions
                cacheService.cacheConditions(resortConditions, for: resortId)
            }
            isUsingCachedData = false
            errorMessage = nil
            lastUpdated = Date()
        } catch {
            // Fall back to cache for each resort
            for resortId in resortIds {
                if let cached = cacheService.getCachedConditions(for: resortId) {
                    conditions[resortId] = cached.data
                    isUsingCachedData = true
                }
            }
            if isUsingCachedData {
                errorMessage = "Using cached data"
            }
        }
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
        var anyFromCache = false
        var allSucceeded = true

        // Try batch endpoint first, fall back to individual calls if it fails
        // Note: The batch endpoint may not be available (requires API Gateway configuration)
        let batchSize = 20
        for batchStart in stride(from: 0, to: resortIds.count, by: batchSize) {
            let batchEnd = min(batchStart + batchSize, resortIds.count)
            let batchIds = Array(resortIds[batchStart..<batchEnd])

            do {
                // Try batch endpoint for efficiency (single request per 20 resorts)
                let batchResults = try await apiClient.getBatchConditions(resortIds: batchIds)

                for (resortId, resortConditions) in batchResults {
                    conditions[resortId] = resortConditions
                    // Cache the fresh data
                    cacheService.cacheConditions(resortConditions, for: resortId)
                }
                print("Successfully fetched batch conditions for \(batchIds.count) resorts")
            } catch {
                // Batch endpoint failed - fall back to individual API calls
                print("Batch API error: \(error.localizedDescription). Falling back to individual calls.")

                for resortId in batchIds {
                    do {
                        // Try individual API call
                        let resortConditions = try await apiClient.getConditions(for: resortId)
                        conditions[resortId] = resortConditions
                        // Cache the fresh data
                        cacheService.cacheConditions(resortConditions, for: resortId)
                        print("Successfully fetched conditions for \(resortId) via individual call")
                    } catch {
                        // Individual call also failed - try cache
                        print("Individual API error for \(resortId): \(error.localizedDescription)")
                        allSucceeded = false

                        if let cachedData = cacheService.getCachedConditions(for: resortId) {
                            conditions[resortId] = cachedData.data
                            anyFromCache = true
                            print("Using cached conditions for \(resortId) (stale: \(cachedData.isStale))")
                        } else {
                            conditions[resortId] = []
                            print("No cached data available for \(resortId)")
                        }
                    }
                }
            }
        }

        lastUpdated = Date()

        // Update cached data state based on results
        if anyFromCache {
            isUsingCachedData = true
            cachedDataAge = "some data from cache"
            if errorMessage == nil {
                errorMessage = "Some data from cache"
            }
        } else {
            // All data is fresh from API
            isUsingCachedData = false
            cachedDataAge = nil
            if allSucceeded {
                errorMessage = nil
            }
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
