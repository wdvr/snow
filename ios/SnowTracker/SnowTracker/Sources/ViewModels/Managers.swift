import SwiftUI
import Combine
import os.log

private let managerLog = Logger(subsystem: "com.snowtracker.app", category: "Managers")

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

    /// Tracks resort IDs queued for lazy condition fetching (visible on screen)
    private var pendingVisibleResortIds: Set<String> = []
    /// Debounce task for batching visible resort condition fetches
    private var visibleFetchTask: Task<Void, Never>?

    func loadInitialData() {
        // Prevent multiple calls (can happen with tab switching)
        guard !hasLoadedInitialData else {
            managerLog.debug("loadInitialData already called, skipping")
            return
        }
        hasLoadedInitialData = true

        // 0. Check if API URL changed (e.g. switched from staging to prod)
        //    and invalidate stale cache from the old environment
        cacheService.checkAndInvalidateIfAPIChanged()

        // 1. Load cached data immediately so the UI is populated right away
        loadCachedDataSynchronously()

        // 2. Refresh from API in background
        Task {
            await fetchResorts()
            // Fetch snow quality summaries for all resorts (lightweight, fast)
            await fetchAllSnowQualitySummaries()
            // Pre-fetch full conditions for favorites; visible resorts will be
            // loaded lazily via onResortAppeared as the list scrolls
            await fetchConditionsForFavorites()
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
            managerLog.debug("loadCachedDataSynchronously: Loaded \(self.resorts.count) resorts from cache (stale: \(cachedResorts.isStale))")
        }

        // Load cached snow quality summaries
        if let cachedSummaries = cacheService.getCachedSnowQualitySummaries() {
            snowQualitySummaries = cachedSummaries.data
            managerLog.debug("loadCachedDataSynchronously: Loaded \(cachedSummaries.data.count) snow quality summaries from cache")
        }

        // Load cached conditions for favorites
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        for resortId in favoriteIds {
            if let cached = cacheService.getCachedConditions(for: resortId) {
                conditions[resortId] = cached.data
            }
        }
        if !favoriteIds.isEmpty {
            managerLog.debug("loadCachedDataSynchronously: Loaded cached conditions for \(favoriteIds.count) favorites")
        }
    }

    /// Maximum number of resorts to fetch snow quality for in one session
    /// This prevents excessive API calls when the backend returns thousands of resorts
    private let maxSnowQualityFetchCount = 2000

    /// Fetch lightweight snow quality summaries for all resorts (for main list display)
    /// - Parameter forceRefresh: If true, bypasses cache and fetches fresh data from API
    func fetchAllSnowQualitySummaries(forceRefresh: Bool = false) async {
        guard !resorts.isEmpty else {
            managerLog.debug("fetchAllSnowQualitySummaries: No resorts loaded, skipping")
            return
        }

        // Check cache first - use if not stale (controlled by useSnowQualityCache flag)
        // Skip cache check if forceRefresh is true
        if !forceRefresh, useSnowQualityCache, let cached = cacheService.getCachedSnowQualitySummaries(), !cached.isStale {
            managerLog.debug("fetchAllSnowQualitySummaries: Using cached data (\(cached.data.count) summaries, age: \(cached.ageDescription))")
            snowQualitySummaries = cached.data
            return
        }

        if forceRefresh {
            managerLog.debug("fetchAllSnowQualitySummaries: Force refresh requested, bypassing cache")
        }

        isLoadingSnowQuality = true

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
            managerLog.debug("fetchAllSnowQualitySummaries: Limiting from \(allResortIds.count) to \(resortIds.count) resorts (favorites prioritized)")
        }
        managerLog.debug("fetchAllSnowQualitySummaries: Fetching summaries for \(resortIds.count) resorts from API")

        // Batch fetch in chunks of 200 (API limit) — all batches run in PARALLEL
        let batchSize = 200
        let chunks: [[String]] = stride(from: 0, to: resortIds.count, by: batchSize).map { start in
            Array(resortIds[start..<min(start + batchSize, resortIds.count)])
        }

        managerLog.info("fetchAllSnowQualitySummaries: Fetching \(chunks.count) batches in parallel")

        // Fire all batch requests concurrently
        let batchResults: [[(String, SnowQualitySummaryLight)]] = await withTaskGroup(
            of: [(String, SnowQualitySummaryLight)].self,
            returning: [[(String, SnowQualitySummaryLight)]].self
        ) { group in
            for (index, chunk) in chunks.enumerated() {
                group.addTask { [apiClient] in
                    let t0 = CFAbsoluteTimeGetCurrent()
                    do {
                        let results = try await apiClient.getBatchSnowQuality(for: chunk)
                        managerLog.info("fetchAllSnowQualitySummaries: Batch \(index + 1)/\(chunks.count) (\(chunk.count) resorts) completed in \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s")
                        return results.map { ($0.key, $0.value) }
                    } catch {
                        managerLog.error("fetchAllSnowQualitySummaries: Batch \(index + 1) failed after \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s: \(error.localizedDescription)")
                        return []
                    }
                }
            }

            var allResults: [[(String, SnowQualitySummaryLight)]] = []
            for await result in group {
                allResults.append(result)
            }
            return allResults
        }

        // Merge all results in a single UI update
        var updated = snowQualitySummaries
        var totalLoaded = 0
        for batch in batchResults {
            for (resortId, summary) in batch {
                updated[resortId] = summary
            }
            totalLoaded += batch.count
        }
        snowQualitySummaries = updated
        isLoadingSnowQuality = false

        // Cache the final results
        if !self.snowQualitySummaries.isEmpty {
            managerLog.debug("fetchAllSnowQualitySummaries: Caching \(self.snowQualitySummaries.count) summaries")
            cacheService.cacheSnowQualitySummaries(self.snowQualitySummaries)
        }

        managerLog.debug("fetchAllSnowQualitySummaries: Complete. Loaded \(totalLoaded) summaries total")
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

    /// Get snow score (0-100) for a resort
    func getSnowScore(for resortId: String) -> Int? {
        if let summary = snowQualitySummaries[resortId] {
            return summary.snowScore
        }
        if let resortConditions = conditions[resortId], !resortConditions.isEmpty {
            // Prefer top elevation
            for level in ["top", "mid", "base"] {
                if let cond = resortConditions.first(where: { $0.elevationLevel == level }),
                   let score = cond.snowScore {
                    return score
                }
            }
        }
        return nil
    }

    /// Get quality explanation for a resort
    func getExplanation(for resortId: String) -> String? {
        snowQualitySummaries[resortId]?.explanation
    }

    /// Refresh all data - called by pull-to-refresh
    /// Fetches summaries + conditions in parallel for visible + favorites
    /// Rate-limited to prevent API spam (5 second minimum between refreshes)
    func refreshData(visibleResortIds: [String] = []) async {
        // Rate limiting - prevent rapid successive refreshes
        if let lastRefresh = lastRefreshTime {
            let timeSinceLastRefresh = Date().timeIntervalSince(lastRefresh)
            if timeSinceLastRefresh < refreshRateLimitSeconds {
                managerLog.debug("refreshData: Rate limited, only \(String(format: "%.1f", timeSinceLastRefresh))s since last refresh")
                return
            }
        }

        let refreshStart = CFAbsoluteTimeGetCurrent()
        managerLog.info("refreshData: Starting full refresh")
        lastRefreshTime = Date()

        // Capture favorites before entering task group (UserPreferencesManager is @MainActor)
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        let idsToFetch = Array(Set(visibleResortIds + favoriteIds))

        // Fetch summaries and conditions IN PARALLEL (not sequentially)
        await withTaskGroup(of: Void.self) { group in
            group.addTask {
                let t0 = CFAbsoluteTimeGetCurrent()
                await self.fetchAllSnowQualitySummaries(forceRefresh: true)
                managerLog.info("refreshData: Summaries took \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s")
            }
            if !idsToFetch.isEmpty {
                group.addTask {
                    let t0 = CFAbsoluteTimeGetCurrent()
                    managerLog.info("refreshData: Fetching conditions for \(idsToFetch.count) resorts (visible + favorites)")
                    await self.fetchConditionsForResorts(resortIds: idsToFetch)
                    managerLog.info("refreshData: Conditions took \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s")
                }
            }
            // Wait for ALL tasks (both summaries and conditions)
            for await _ in group {}
        }

        let totalTime = CFAbsoluteTimeGetCurrent() - refreshStart
        lastUpdated = Date()
        managerLog.info("refreshData: Complete in \(String(format: "%.1f", totalTime))s")
    }

    func refreshConditions() async {
        let t0 = CFAbsoluteTimeGetCurrent()
        await fetchConditionsForFavorites()
        managerLog.info("refreshConditions: Complete in \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s")
    }

    /// Fetch conditions for favorites only - efficient for startup
    func fetchConditionsForFavorites() async {
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        guard !favoriteIds.isEmpty else { return }
        await fetchConditionsForResorts(resortIds: favoriteIds)
    }

    /// Fetch conditions for all loaded resorts in the background
    /// This ensures detail views have data ready without lazy loading
    func fetchConditionsForAllResorts(forceRefresh: Bool = false) async {
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

        let idsToFetch: [String]
        if forceRefresh {
            idsToFetch = sortedIds
        } else {
            // Skip resorts that already have fresh cached conditions
            // Accumulate cache loads to avoid per-resort @Published updates
            var cachedUpdates: [String: [WeatherCondition]] = [:]
            idsToFetch = sortedIds.filter { resortId in
                if let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale {
                    if conditions[resortId] == nil {
                        cachedUpdates[resortId] = cached.data
                    }
                    return false
                }
                return true
            }
            // Single batch update for all cached conditions
            if !cachedUpdates.isEmpty {
                var merged = conditions
                for (id, data) in cachedUpdates {
                    merged[id] = data
                }
                conditions = merged
            }
        }

        guard !idsToFetch.isEmpty else {
            managerLog.debug("fetchConditionsForAllResorts: All \(sortedIds.count) resorts have fresh cached conditions")
            return
        }

        managerLog.debug("fetchConditionsForAllResorts: Fetching conditions for \(idsToFetch.count) resorts (\(sortedIds.count - idsToFetch.count) already cached)")
        await fetchConditionsForResorts(resortIds: idsToFetch)
    }

    /// Called when a resort row appears on screen. Batches up visible resort IDs
    /// and fetches conditions in a debounced batch (avoids per-row API calls).
    func onResortAppeared(_ resortId: String) {
        // Skip if we already have conditions for this resort
        if conditions[resortId] != nil { return }
        if let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale {
            // Load from cache into memory without API call
            conditions[resortId] = cached.data
            return
        }

        pendingVisibleResortIds.insert(resortId)

        // Debounce: wait 200ms to batch up visible rows, then fetch together
        visibleFetchTask?.cancel()
        visibleFetchTask = Task {
            try? await Task.sleep(nanoseconds: 200_000_000)
            guard !Task.isCancelled else { return }
            let ids = Array(pendingVisibleResortIds)
            pendingVisibleResortIds.removeAll()
            guard !ids.isEmpty else { return }
            managerLog.debug("onResortAppeared: Fetching conditions for \(ids.count) visible resorts")
            await fetchConditionsForResorts(resortIds: ids)
        }
    }

    /// Called when a list view needs conditions for a page of visible resorts + buffer.
    /// Used by pull-to-refresh: refresh summaries + conditions for visible resorts.
    func refreshVisibleResorts(_ visibleIds: [String]) async {
        await fetchAllSnowQualitySummaries(forceRefresh: true)
        if !visibleIds.isEmpty {
            await fetchConditionsForResorts(resortIds: visibleIds)
        }
    }

    /// Fetch conditions for a single resort - use when opening detail view
    func fetchConditionsForResort(_ resortId: String, forceRefresh: Bool = false) async {
        if !forceRefresh {
            // Check if we already have fresh conditions
            if let existing = conditions[resortId], !existing.isEmpty {
                // Check if cached data is still fresh (less than 5 minutes old)
                if let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale {
                    return
                }
            }
        }
        await fetchConditionsForResorts(resortIds: [resortId])
    }

    /// Fetch conditions for a list of resorts (batch API call)
    func fetchConditionsForResorts(resortIds: [String]) async {
        guard !resortIds.isEmpty else { return }

        let t0 = CFAbsoluteTimeGetCurrent()

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
        // Accumulate results locally to avoid per-resort @Published updates
        do {
            let batchResults = try await apiClient.getBatchConditions(resortIds: resortIds)
            let networkTime = CFAbsoluteTimeGetCurrent() - t0
            managerLog.info("fetchConditionsForResorts: API call for \(resortIds.count) resorts took \(String(format: "%.1f", networkTime))s")

            var updatedConditions = conditions
            var updatedSummaries = snowQualitySummaries
            for (resortId, resortConditions) in batchResults {
                updatedConditions[resortId] = resortConditions
                cacheService.cacheConditions(resortConditions, for: resortId)
                // Sync summary from fresh conditions so list view stays current
                if let summary = synthesizeSummary(from: resortConditions, resortId: resortId) {
                    updatedSummaries[resortId] = summary
                }
            }
            // Single UI update instead of N individual updates
            conditions = updatedConditions
            snowQualitySummaries = updatedSummaries
            isUsingCachedData = false
            errorMessage = nil
            lastUpdated = Date()
        } catch {
            managerLog.error("fetchConditionsForResorts: Failed after \(String(format: "%.1f", CFAbsoluteTimeGetCurrent() - t0))s: \(error.localizedDescription)")
            // Fall back to cache for each resort
            var updatedConditions = conditions
            for resortId in resortIds {
                if let cached = cacheService.getCachedConditions(for: resortId) {
                    updatedConditions[resortId] = cached.data
                    isUsingCachedData = true
                }
            }
            conditions = updatedConditions
            if isUsingCachedData {
                errorMessage = "Using cached data"
            }
        }
    }

    /// Build a lightweight summary from full conditions so the list view stays in sync
    private func synthesizeSummary(from conditions: [WeatherCondition], resortId: String) -> SnowQualitySummaryLight? {
        guard !conditions.isEmpty else { return nil }

        // Use the representative condition (mid > top > base, same as backend)
        let representative = conditions.first { $0.elevationLevel == "mid" }
            ?? conditions.first { $0.elevationLevel == "top" }
            ?? conditions.first

        guard let cond = representative else { return nil }

        // Compute overall quality as weighted average (matches backend logic)
        let top = conditions.first { $0.elevationLevel == "top" }
        let mid = conditions.first { $0.elevationLevel == "mid" }
        let base = conditions.first { $0.elevationLevel == "base" }

        let overallQuality: String
        let overallScore: Int?

        if let topScore = top?.snowScore, let midScore = mid?.snowScore, let baseScore = base?.snowScore {
            let weighted = Double(topScore) * 0.50 + Double(midScore) * 0.35 + Double(baseScore) * 0.15
            overallScore = Int(weighted.rounded())
            overallQuality = qualityFromScore(overallScore!)
        } else {
            overallScore = cond.snowScore
            overallQuality = cond.snowQuality.rawValue
        }

        // Preserve existing explanation if available (conditions don't carry explanation text)
        let existingExplanation = snowQualitySummaries[resortId]?.explanation

        return SnowQualitySummaryLight(
            resortId: resortId,
            overallQuality: overallQuality,
            snowScore: overallScore,
            explanation: existingExplanation,
            lastUpdated: cond.timestamp,
            temperatureC: cond.currentTempCelsius,
            snowfallFreshCm: cond.snowfallAfterFreezeCm ?? cond.snowfall24hCm,
            snowfall24hCm: cond.snowfall24hCm,
            snowDepthCm: cond.snowDepthCm,
            predictedSnow48hCm: cond.predictedSnow48hCm
        )
    }

    /// Map a numeric snow score to a quality string (matches backend thresholds)
    private func qualityFromScore(_ score: Int) -> String {
        let s = Double(score)
        if s >= 92 { return "excellent" }
        if s >= 75 { return "good" }
        if s >= 58 { return "fair" }
        if s >= 42 { return "poor" }
        if s >= 25 { return "bad" }
        return "horrible"
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
            managerLog.debug("Loaded \(self.resorts.count) resorts from API")
            errorMessage = nil
            isUsingCachedData = false
            cachedDataAge = nil

            // Cache the fresh data
            cacheService.cacheResorts(fetchedResorts)
        } catch {
            managerLog.error("API error: \(error.localizedDescription)")

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
                managerLog.debug("Loaded \(self.resorts.count) resorts from cache (stale: \(cachedData.isStale))")
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

        // Accumulate all results locally to avoid per-resort @Published updates
        var updatedConditions = conditions

        // Try batch endpoint first, fall back to individual calls if it fails
        let batchSize = 50
        for batchStart in stride(from: 0, to: resortIds.count, by: batchSize) {
            let batchEnd = min(batchStart + batchSize, resortIds.count)
            let batchIds = Array(resortIds[batchStart..<batchEnd])

            do {
                let batchResults = try await apiClient.getBatchConditions(resortIds: batchIds)

                for (resortId, resortConditions) in batchResults {
                    updatedConditions[resortId] = resortConditions
                    cacheService.cacheConditions(resortConditions, for: resortId)
                }
                managerLog.debug("Fetched batch conditions for \(batchIds.count) resorts")
            } catch {
                managerLog.warning("Batch API error: \(error.localizedDescription). Falling back to individual calls.")

                for resortId in batchIds {
                    do {
                        let resortConditions = try await apiClient.getConditions(for: resortId)
                        updatedConditions[resortId] = resortConditions
                        cacheService.cacheConditions(resortConditions, for: resortId)
                        managerLog.debug("Fetched conditions for \(resortId) via individual call")
                    } catch {
                        managerLog.warning("Individual API error for \(resortId): \(error.localizedDescription)")
                        allSucceeded = false

                        if let cachedData = cacheService.getCachedConditions(for: resortId) {
                            updatedConditions[resortId] = cachedData.data
                            anyFromCache = true
                            managerLog.debug("Using cached conditions for \(resortId) (stale: \(cachedData.isStale))")
                        } else {
                            updatedConditions[resortId] = []
                            managerLog.debug("No cached data available for \(resortId)")
                        }
                    }
                }
            }
        }

        // Single UI update with all accumulated results
        conditions = updatedConditions
        lastUpdated = Date()

        if anyFromCache {
            isUsingCachedData = true
            cachedDataAge = "some data from cache"
            if errorMessage == nil {
                errorMessage = "Some data from cache"
            }
        } else {
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

    /// Pre-fetch conditions, snow quality, and timeline data for all favorite
    /// resorts. Call this when the app enters the foreground and the network is
    /// available so that detail views are ready instantly.
    func prefetchFavoriteData() async {
        let favoriteIds = Array(UserPreferencesManager.shared.favoriteResorts)
        guard !favoriteIds.isEmpty else { return }

        managerLog.debug("prefetchFavoriteData: Starting pre-fetch for \(favoriteIds.count) favorites")

        // 1. Conditions — only if stale
        let staleConditionIds = favoriteIds.filter { resortId in
            guard let cached = cacheService.getCachedConditions(for: resortId), !cached.isStale else {
                return true
            }
            // Make sure in-memory dict is populated
            if conditions[resortId] == nil {
                conditions[resortId] = cached.data
            }
            return false
        }
        if !staleConditionIds.isEmpty {
            managerLog.debug("prefetchFavoriteData: Fetching conditions for \(staleConditionIds.count) stale favorites")
            await fetchConditionsForResorts(resortIds: staleConditionIds)
        }

        // 2. Snow quality summaries — only if stale
        if let cached = cacheService.getCachedSnowQualitySummaries(), !cached.isStale {
            if snowQualitySummaries.isEmpty {
                snowQualitySummaries = cached.data
            }
        } else {
            await fetchAllSnowQualitySummaries()
        }

        // 3. Timelines — only if stale
        for resortId in favoriteIds {
            if let cached = cacheService.getCachedTimeline(for: resortId), !cached.isStale {
                continue
            }
            do {
                let timeline = try await apiClient.getTimeline(for: resortId)
                cacheService.cacheTimeline(timeline, for: resortId)
            } catch {
                managerLog.debug("prefetchFavoriteData: Failed to fetch timeline for \(resortId): \(error.localizedDescription)")
            }
        }

        managerLog.debug("prefetchFavoriteData: Complete")
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
    @Published var favoriteGroups: [FavoriteGroup] = []
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
    private let favoriteGroupsKey = "favoriteGroups"
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

        // Load favorite groups
        loadFavoriteGroups()

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

    // MARK: - Favorite Groups

    private func loadFavoriteGroups() {
        let defaults = sharedDefaults ?? UserDefaults.standard
        if let data = defaults.data(forKey: favoriteGroupsKey),
           let decoded = try? JSONDecoder().decode([FavoriteGroup].self, from: data) {
            favoriteGroups = decoded
        }
    }

    func saveFavoriteGroups() {
        guard let encoded = try? JSONEncoder().encode(favoriteGroups) else { return }
        sharedDefaults?.set(encoded, forKey: favoriteGroupsKey)
        UserDefaults.standard.set(encoded, forKey: favoriteGroupsKey)
    }

    func createGroup(name: String) {
        let group = FavoriteGroup(name: name)
        favoriteGroups.append(group)
        saveFavoriteGroups()
    }

    func renameGroup(id: String, name: String) {
        guard let index = favoriteGroups.firstIndex(where: { $0.id == id }) else { return }
        favoriteGroups[index].name = name
        saveFavoriteGroups()
    }

    func deleteGroup(id: String) {
        favoriteGroups.removeAll { $0.id == id }
        saveFavoriteGroups()
    }

    func addResortToGroup(resortId: String, groupId: String) {
        // Remove from any existing group first
        for i in favoriteGroups.indices {
            favoriteGroups[i].resortIds.removeAll { $0 == resortId }
        }
        // Add to target group
        if let index = favoriteGroups.firstIndex(where: { $0.id == groupId }) {
            favoriteGroups[index].resortIds.append(resortId)
        }
        saveFavoriteGroups()
    }

    func removeResortFromGroup(resortId: String, groupId: String) {
        if let index = favoriteGroups.firstIndex(where: { $0.id == groupId }) {
            favoriteGroups[index].resortIds.removeAll { $0 == resortId }
        }
        saveFavoriteGroups()
    }

    /// Resorts not assigned to any group
    func ungroupedFavoriteResortIds() -> Set<String> {
        let grouped = Set(favoriteGroups.flatMap(\.resortIds))
        return favoriteResorts.subtracting(grouped)
    }

    func groupForResort(_ resortId: String) -> FavoriteGroup? {
        favoriteGroups.first { $0.resortIds.contains(resortId) }
    }

    func toggleFavorite(resortId: String) {
        if favoriteResorts.contains(resortId) {
            favoriteResorts.remove(resortId)
            // Remove from any group
            for i in favoriteGroups.indices {
                favoriteGroups[i].resortIds.removeAll { $0 == resortId }
            }
            saveFavoriteGroups()
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
            managerLog.debug("UserPreferencesManager: Not authenticated, skipping backend sync")
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
            managerLog.debug("UserPreferencesManager: Synced preferences to backend")
        } catch {
            // Log the error but don't block UI - local preferences are still saved
            managerLog.error("UserPreferencesManager: Failed to sync preferences: \(error.localizedDescription)")
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

// MARK: - Favorite Groups

struct FavoriteGroup: Codable, Identifiable {
    let id: String
    var name: String
    var resortIds: [String]

    init(id: String = UUID().uuidString, name: String, resortIds: [String] = []) {
        self.id = id
        self.name = name
        self.resortIds = resortIds
    }
}
