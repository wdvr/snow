import SwiftUI
import Combine

// MARK: - Snow Conditions Manager

@MainActor
class SnowConditionsManager: ObservableObject {
    @Published var resorts: [Resort] = []
    @Published var conditions: [String: [WeatherCondition]] = [:]
    @Published var snowQualitySummaries: [String: SnowQualitySummaryLight] = [:]
    @Published var isLoading = false
    @Published var isLoadingSnowQuality = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?
    @Published var isUsingCachedData = false
    @Published var cachedDataAge: String?

    private let apiClient = APIClient.shared
    private let cacheService = CacheService.shared
    private var hasLoadedInitialData = false

    /// Set to true to enable frontend caching of snow quality summaries
    private let useSnowQualityCache = true

    /// Minimum interval between pull-to-refresh requests (prevents spam)
    private let refreshRateLimitSeconds: TimeInterval = 5.0
    private var lastRefreshTime: Date?

    func loadInitialData() {
        // Prevent multiple calls (can happen with tab switching)
        guard !hasLoadedInitialData else {
            print("loadInitialData already called, skipping")
            return
        }
        hasLoadedInitialData = true

        // 1. Load cached data immediately so the UI is populated right away
        loadCachedDataSynchronously()

        // 2. Refresh from API in background
        Task {
            await fetchResorts()
            // Fetch snow quality summaries for all resorts (lightweight, fast)
            await fetchAllSnowQualitySummaries()
            // Fetch full conditions for all visible resorts so detail views are instant
            await fetchConditionsForAllResorts()
            // Clean up old cached data periodically
            cacheService.cleanupStaleCache()
        }
    }

    /// Loads cached resorts and snow quality summaries immediately so the UI
    /// doesn't show "Loading resorts..." while the network request is in flight.
    private func loadCachedDataSynchronously() {
        // Load cached resorts
        if let cachedResorts = cacheService.getCachedResorts() {
            resorts = cachedResorts.data
            isUsingCachedData = true
            cachedDataAge = cachedResorts.ageDescription
            print("loadCachedDataSynchronously: Loaded \(resorts.count) resorts from cache (stale: \(cachedResorts.isStale))")
        }

        // Load cached snow quality summaries
        if let cachedSummaries = cacheService.getCachedSnowQualitySummaries() {
            snowQualitySummaries = cachedSummaries.data
            print("loadCachedDataSynchronously: Loaded \(cachedSummaries.data.count) snow quality summaries from cache")
        }

        // Load cached conditions for favorites
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        for resortId in favoriteIds {
            if let cached = cacheService.getCachedConditions(for: resortId) {
                conditions[resortId] = cached.data
            }
        }
        if !favoriteIds.isEmpty {
            print("loadCachedDataSynchronously: Loaded cached conditions for \(favoriteIds.count) favorites")
        }
    }

    /// Maximum number of resorts to fetch snow quality for in one session
    /// This prevents excessive API calls when the backend returns thousands of resorts
    private let maxSnowQualityFetchCount = 300

    /// Fetch lightweight snow quality summaries for all resorts (for main list display)
    /// - Parameter forceRefresh: If true, bypasses cache and fetches fresh data from API
    func fetchAllSnowQualitySummaries(forceRefresh: Bool = false) async {
        guard !resorts.isEmpty else {
            print("fetchAllSnowQualitySummaries: No resorts loaded, skipping")
            return
        }

        // Check cache first - use if not stale (controlled by useSnowQualityCache flag)
        // Skip cache check if forceRefresh is true
        if !forceRefresh, useSnowQualityCache, let cached = cacheService.getCachedSnowQualitySummaries(), !cached.isStale {
            print("fetchAllSnowQualitySummaries: Using cached data (\(cached.data.count) summaries, age: \(cached.ageDescription))")
            snowQualitySummaries = cached.data
            return
        }

        if forceRefresh {
            print("fetchAllSnowQualitySummaries: Force refresh requested, bypassing cache")
        }

        isLoadingSnowQuality = true
        defer { isLoadingSnowQuality = false }

        // Prioritize favorites, then limit total to prevent excessive API calls
        let favoriteIds = Set(UserPreferencesManager.shared.favoriteResorts)
        let allResortIds = resorts.map { $0.id }

        // Sort favorites first, then limit total
        let sortedIds = allResortIds.sorted { id1, id2 in
            let isFav1 = favoriteIds.contains(id1)
            let isFav2 = favoriteIds.contains(id2)
            if isFav1 != isFav2 {
                return isFav1 // Favorites come first
            }
            return id1 < id2
        }

        let resortIds = Array(sortedIds.prefix(maxSnowQualityFetchCount))

        if allResortIds.count > maxSnowQualityFetchCount {
            print("fetchAllSnowQualitySummaries: Limiting from \(allResortIds.count) to \(resortIds.count) resorts (favorites prioritized)")
        }
        print("fetchAllSnowQualitySummaries: Fetching summaries for \(resortIds.count) resorts from API")

        // Batch fetch in chunks of 200 (API limit), updating UI progressively
        let batchSize = 200
        var totalLoaded = 0
        var allResults: [String: SnowQualitySummaryLight] = snowQualitySummaries // Start with existing data

        for batchStart in stride(from: 0, to: resortIds.count, by: batchSize) {
            let batchEnd = min(batchStart + batchSize, resortIds.count)
            let batchIds = Array(resortIds[batchStart..<batchEnd])
            let batchNumber = batchStart/batchSize + 1
            print("fetchAllSnowQualitySummaries: Fetching batch \(batchNumber) with \(batchIds.count) resorts")

            do {
                let batchResults = try await apiClient.getBatchSnowQuality(for: batchIds)
                for (resortId, summary) in batchResults {
                    allResults[resortId] = summary
                }
                totalLoaded += batchResults.count
                print("fetchAllSnowQualitySummaries: Batch \(batchNumber) loaded \(batchResults.count) summaries")

                // Update UI progressively after each batch so users see data faster
                snowQualitySummaries = allResults
            } catch {
                print("fetchAllSnowQualitySummaries: Batch \(batchNumber) failed: \(error.localizedDescription)")
                // Continue with next batch rather than failing completely
            }
        }

        // Cache the final results
        if !allResults.isEmpty {
            print("fetchAllSnowQualitySummaries: Caching \(allResults.count) summaries")
            cacheService.cacheSnowQualitySummaries(allResults)
        }

        print("fetchAllSnowQualitySummaries: Complete. Loaded \(totalLoaded) summaries total")
    }

    /// Get cached snow quality for a resort (from summary or conditions)
    func getSnowQuality(for resortId: String) -> SnowQuality {
        // First check if we have a lightweight summary (overall quality from backend)
        if let summary = snowQualitySummaries[resortId] {
            return summary.overallSnowQuality
        }
        // Fall back to best quality across loaded elevations
        if let resortConditions = conditions[resortId], !resortConditions.isEmpty {
            return resortConditions
                .map { $0.snowQuality }
                .min(by: { $0.sortOrder < $1.sortOrder }) ?? .unknown
        }
        return .unknown
    }

    /// Refresh all data - called by pull-to-refresh
    /// This bypasses cache to ensure fresh data is fetched
    /// Rate-limited to prevent API spam (5 second minimum between refreshes)
    func refreshData() async {
        // Rate limiting - prevent rapid successive refreshes
        if let lastRefresh = lastRefreshTime {
            let timeSinceLastRefresh = Date().timeIntervalSince(lastRefresh)
            if timeSinceLastRefresh < refreshRateLimitSeconds {
                print("refreshData: Rate limited, only \(String(format: "%.1f", timeSinceLastRefresh))s since last refresh")
                return
            }
        }

        print("refreshData: Starting full refresh (bypassing cache)")
        lastRefreshTime = Date()

        // Refresh snow quality summaries for all resorts (used by list view)
        await fetchAllSnowQualitySummaries(forceRefresh: true)
        // Refresh full conditions for all resorts
        await fetchConditionsForAllResorts()

        lastUpdated = Date()
        print("refreshData: Complete")
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

    /// Fetch conditions for all loaded resorts in the background
    /// This ensures detail views have data ready without lazy loading
    func fetchConditionsForAllResorts() async {
        let allIds = resorts.map { $0.id }
        guard !allIds.isEmpty else { return }

        // Prioritize favorites first, then fetch the rest
        let favoriteIds = Set(UserPreferencesManager.shared.favoriteResorts)
        let sortedIds = allIds.sorted { id1, id2 in
            let isFav1 = favoriteIds.contains(id1)
            let isFav2 = favoriteIds.contains(id2)
            if isFav1 != isFav2 { return isFav1 }
            return id1 < id2
        }

        // Skip resorts that already have fresh cached conditions
        let idsToFetch = sortedIds.filter { resortId in
            if let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale {
                // Already have fresh data, load from cache into memory
                if conditions[resortId] == nil {
                    conditions[resortId] = cached.data
                }
                return false
            }
            return true
        }

        guard !idsToFetch.isEmpty else {
            print("fetchConditionsForAllResorts: All \(sortedIds.count) resorts have fresh cached conditions")
            return
        }

        print("fetchConditionsForAllResorts: Fetching conditions for \(idsToFetch.count) resorts (\(sortedIds.count - idsToFetch.count) already cached)")
        await fetchConditionsForResorts(resortIds: idsToFetch)
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

        // Only show loading indicator if we have no data at all to display
        let hasExistingData = !resorts.isEmpty
        if !hasExistingData {
            isLoading = true
        }
        defer {
            if !hasExistingData {
                isLoading = false
            }
        }

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
        // Only show loading indicator if we have no cached resorts to display
        let showLoading = resorts.isEmpty
        if showLoading { isLoading = true }
        defer { if showLoading { isLoading = false } }

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
        let showLoading = resorts.isEmpty
        if showLoading { isLoading = true }
        defer { if showLoading { isLoading = false } }

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

    /// Regions that the user has chosen to hide from the app
    /// Default: oceania and japan are hidden (southern hemisphere and distant regions)
    @Published var hiddenRegions: Set<String> = [] {
        didSet {
            saveHiddenRegions()
            scheduleSyncToBackend()
        }
    }

    /// Whether the user has completed the onboarding flow
    @Published var hasCompletedOnboarding: Bool = false

    private let apiClient = APIClient.shared
    private let favoritesKey = "favoriteResorts"
    private let unitPreferencesKey = "unitPreferences"
    private let hiddenRegionsKey = "hiddenRegions"
    private let hasCompletedOnboardingKey = "hasCompletedOnboarding"
    private let appGroupId = "group.com.wouterdevriendt.snowtracker"

    /// Debounce task for syncing preferences to backend
    private var syncTask: Task<Void, Never>?

    /// Delay before syncing to backend (debounce interval)
    private let syncDebounceInterval: TimeInterval = 1.0

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

        // Load hidden regions
        loadHiddenRegions()

        // Load onboarding status
        loadOnboardingStatus()
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

    private func loadHiddenRegions() {
        let defaults = sharedDefaults ?? UserDefaults.standard

        if let savedRegions = defaults.array(forKey: hiddenRegionsKey) as? [String] {
            // User has explicitly set their preferences
            hiddenRegions = Set(savedRegions)
        } else {
            // First launch: set default hidden regions (oceania and japan)
            hiddenRegions = Set(["oceania", "japan"])
            saveHiddenRegions()
        }
    }

    private func saveHiddenRegions() {
        let regionsArray = Array(hiddenRegions)

        // Save to shared app group (for widget access)
        sharedDefaults?.set(regionsArray, forKey: hiddenRegionsKey)

        // Also save to standard UserDefaults as backup
        UserDefaults.standard.set(regionsArray, forKey: hiddenRegionsKey)
    }

    private func loadOnboardingStatus() {
        let defaults = sharedDefaults ?? UserDefaults.standard
        hasCompletedOnboarding = defaults.bool(forKey: hasCompletedOnboardingKey)
    }

    /// Mark onboarding as completed
    func completeOnboarding() {
        hasCompletedOnboarding = true

        // Save to shared app group
        sharedDefaults?.set(true, forKey: hasCompletedOnboardingKey)

        // Also save to standard UserDefaults as backup
        UserDefaults.standard.set(true, forKey: hasCompletedOnboardingKey)
    }

    /// Check if a region is visible (not hidden)
    func isRegionVisible(_ region: SkiRegion) -> Bool {
        !hiddenRegions.contains(region.rawValue)
    }

    /// Toggle visibility of a region
    func toggleRegionVisibility(_ region: SkiRegion) {
        if hiddenRegions.contains(region.rawValue) {
            hiddenRegions.remove(region.rawValue)
        } else {
            hiddenRegions.insert(region.rawValue)
        }
    }

    /// Filter resorts based on hidden regions
    func filterByVisibleRegions(_ resorts: [Resort]) -> [Resort] {
        resorts.filter { resort in
            !hiddenRegions.contains(resort.inferredRegion.rawValue)
        }
    }

    func toggleFavorite(resortId: String) {
        if favoriteResorts.contains(resortId) {
            favoriteResorts.remove(resortId)
        } else {
            favoriteResorts.insert(resortId)
        }

        saveLocalPreferences()
        scheduleSyncToBackend()
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

    /// Schedule a debounced sync to the backend
    /// This prevents too many API calls when rapidly toggling favorites
    private func scheduleSyncToBackend() {
        // Cancel any pending sync task
        syncTask?.cancel()

        // Schedule a new sync task with debounce delay
        syncTask = Task {
            // Wait for debounce interval
            try? await Task.sleep(nanoseconds: UInt64(syncDebounceInterval * 1_000_000_000))

            // Check if task was cancelled during sleep
            if Task.isCancelled { return }

            // Perform the sync
            await syncPreferencesToBackend()
        }
    }

    /// Sync user preferences (favorites and notification settings) to the backend
    /// This runs in the background and does not block the UI
    private func syncPreferencesToBackend() async {
        // Check if user is authenticated before syncing
        guard AuthenticationService.shared.isAuthenticated else {
            print("UserPreferencesManager: Not authenticated, skipping backend sync")
            return
        }

        do {
            // Build the UserPreferences object to sync
            var preferredUnitsDict: [String: String] = [
                "temperature": preferredUnits.temperature.rawValue,
                "distance": preferredUnits.distance.rawValue,
                "snow_depth": preferredUnits.snowDepth.rawValue
            ]
            // Include hidden regions in the preferences sync
            preferredUnitsDict["hidden_regions"] = Array(hiddenRegions).joined(separator: ",")

            let preferences = UserPreferences(
                userId: "", // Backend will use authenticated user ID
                favoriteResorts: Array(favoriteResorts),
                notificationPreferences: [
                    "notifications_enabled": notificationSettings.notificationsEnabled,
                    "fresh_snow_alerts": notificationSettings.freshSnowAlerts,
                    "event_alerts": notificationSettings.eventAlerts,
                    "thaw_freeze_alerts": notificationSettings.thawFreezeAlerts,
                    "weekly_summary": notificationSettings.weeklySummary
                ],
                preferredUnits: preferredUnitsDict,
                qualityThreshold: "good", // Default threshold
                createdAt: "", // Backend will handle timestamps
                updatedAt: ""
            )

            try await apiClient.updateUserPreferences(preferences)
            print("UserPreferencesManager: Successfully synced preferences to backend")
        } catch {
            // Log the error but don't block UI - local preferences are still saved
            print("UserPreferencesManager: Failed to sync preferences to backend: \(error.localizedDescription)")
        }
    }

    func savePreferences() async {
        saveLocalPreferences()
        // Also sync to backend when explicitly called
        await syncPreferencesToBackend()
    }

    /// Update notification settings and sync to backend
    func updateNotificationSettings(_ settings: NotificationSettings) {
        notificationSettings = settings
        scheduleSyncToBackend()
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

// NotificationSettings moved to PushNotificationService.swift
