import Foundation
import SwiftData

// MARK: - Cache Models

@Model
final class CachedResort {
    @Attribute(.unique) var id: String
    var name: String
    var country: String
    var region: String
    var timezone: String
    var officialWebsite: String?
    var elevationPointsData: Data
    var weatherSourcesData: Data
    var cachedAt: Date

    init(from resort: Resort) {
        self.id = resort.id
        self.name = resort.name
        self.country = resort.country
        self.region = resort.region
        self.timezone = resort.timezone
        self.officialWebsite = resort.officialWebsite

        // Encode elevation points
        let encoder = JSONEncoder()
        self.elevationPointsData = (try? encoder.encode(resort.elevationPoints)) ?? Data()
        self.weatherSourcesData = (try? encoder.encode(resort.weatherSources)) ?? Data()
        self.cachedAt = Date()
    }

    func toResort() -> Resort? {
        let decoder = JSONDecoder()
        guard let elevationPoints = try? decoder.decode([ElevationPoint].self, from: elevationPointsData),
              let weatherSources = try? decoder.decode([String].self, from: weatherSourcesData) else {
            return nil
        }

        return Resort(
            id: id,
            name: name,
            country: country,
            region: region,
            elevationPoints: elevationPoints,
            timezone: timezone,
            officialWebsite: officialWebsite,
            weatherSources: weatherSources,
            createdAt: nil,
            updatedAt: nil
        )
    }
}

@Model
final class CachedWeatherCondition {
    @Attribute(.unique) var cacheKey: String // resortId + elevationLevel
    var resortId: String
    var elevationLevel: String
    var conditionData: Data
    var cachedAt: Date

    init(from condition: WeatherCondition) {
        self.cacheKey = "\(condition.resortId)_\(condition.elevationLevel)"
        self.resortId = condition.resortId
        self.elevationLevel = condition.elevationLevel

        let encoder = JSONEncoder()
        self.conditionData = (try? encoder.encode(condition)) ?? Data()
        self.cachedAt = Date()
    }

    func toWeatherCondition() -> WeatherCondition? {
        let decoder = JSONDecoder()
        return try? decoder.decode(WeatherCondition.self, from: conditionData)
    }
}

@Model
final class CachedSnowQualitySummary {
    @Attribute(.unique) var resortId: String
    var overallQuality: String
    var lastUpdated: String?
    var temperatureC: Double?
    var snowfallFreshCm: Double?
    var snowfall24hCm: Double?
    var cachedAt: Date

    init(resortId: String, summary: SnowQualitySummaryLight) {
        self.resortId = resortId
        self.overallQuality = summary.overallQuality
        self.lastUpdated = summary.lastUpdated
        self.temperatureC = summary.temperatureC
        self.snowfallFreshCm = summary.snowfallFreshCm
        self.snowfall24hCm = summary.snowfall24hCm
        self.cachedAt = Date()
    }

    func toSnowQualitySummaryLight() -> SnowQualitySummaryLight {
        SnowQualitySummaryLight(
            resortId: resortId,
            overallQuality: overallQuality,
            lastUpdated: lastUpdated,
            temperatureC: temperatureC,
            snowfallFreshCm: snowfallFreshCm,
            snowfall24hCm: snowfall24hCm
        )
    }
}

// MARK: - Cache Configuration

enum CacheConfiguration {
    static let resortCacheDuration: TimeInterval = 24 * 60 * 60  // 24 hours
    static let conditionCacheDuration: TimeInterval = 30 * 60    // 30 minutes
    static let snowQualityCacheDuration: TimeInterval = 60 * 60  // 1 hour
    static let staleCacheDuration: TimeInterval = 7 * 24 * 60 * 60 // 7 days (max age for stale data)
}

// MARK: - Cache Status

struct CachedData<T> {
    let data: T
    let isStale: Bool
    let cachedAt: Date

    var ageDescription: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: cachedAt, relativeTo: Date())
    }
}

// MARK: - Cache Service

@MainActor
class CacheService {
    static let shared = CacheService()

    private var modelContainer: ModelContainer?
    private var modelContext: ModelContext?

    private init() {
        setupContainer()
    }

    private func setupContainer() {
        do {
            let schema = Schema([
                CachedResort.self,
                CachedWeatherCondition.self,
                CachedSnowQualitySummary.self
            ])
            let modelConfiguration = ModelConfiguration(
                schema: schema,
                isStoredInMemoryOnly: false
            )
            modelContainer = try ModelContainer(
                for: schema,
                configurations: [modelConfiguration]
            )
            modelContext = modelContainer?.mainContext
            print("CacheService: SwiftData container initialized successfully")
        } catch {
            print("CacheService: Failed to initialize SwiftData container: \(error)")
        }
    }

    // MARK: - Resort Caching

    func cacheResorts(_ resorts: [Resort]) {
        guard let context = modelContext else { return }

        for resort in resorts {
            // Check if already exists
            let descriptor = FetchDescriptor<CachedResort>(
                predicate: #Predicate { $0.id == resort.id }
            )

            if let existing = try? context.fetch(descriptor).first {
                // Update existing
                existing.name = resort.name
                existing.country = resort.country
                existing.region = resort.region
                existing.timezone = resort.timezone
                existing.officialWebsite = resort.officialWebsite
                let encoder = JSONEncoder()
                existing.elevationPointsData = (try? encoder.encode(resort.elevationPoints)) ?? Data()
                existing.weatherSourcesData = (try? encoder.encode(resort.weatherSources)) ?? Data()
                existing.cachedAt = Date()
            } else {
                // Insert new
                context.insert(CachedResort(from: resort))
            }
        }

        try? context.save()
        print("CacheService: Cached \(resorts.count) resorts")
    }

    func getCachedResorts() -> CachedData<[Resort]>? {
        guard let context = modelContext else { return nil }

        let descriptor = FetchDescriptor<CachedResort>(
            sortBy: [SortDescriptor(\.name)]
        )

        guard let cachedResorts = try? context.fetch(descriptor),
              !cachedResorts.isEmpty else {
            return nil
        }

        let resorts = cachedResorts.compactMap { $0.toResort() }
        guard !resorts.isEmpty else { return nil }

        // Find oldest cache time
        let oldestCache = cachedResorts.min(by: { $0.cachedAt < $1.cachedAt })?.cachedAt ?? Date()
        let isStale = Date().timeIntervalSince(oldestCache) > CacheConfiguration.resortCacheDuration

        return CachedData(data: resorts, isStale: isStale, cachedAt: oldestCache)
    }

    // MARK: - Weather Condition Caching

    func cacheConditions(_ conditions: [WeatherCondition], for resortId: String) {
        guard let context = modelContext else { return }

        for condition in conditions {
            let cacheKey = "\(condition.resortId)_\(condition.elevationLevel)"
            let descriptor = FetchDescriptor<CachedWeatherCondition>(
                predicate: #Predicate { $0.cacheKey == cacheKey }
            )

            if let existing = try? context.fetch(descriptor).first {
                // Update existing
                let encoder = JSONEncoder()
                existing.conditionData = (try? encoder.encode(condition)) ?? Data()
                existing.cachedAt = Date()
            } else {
                // Insert new
                context.insert(CachedWeatherCondition(from: condition))
            }
        }

        try? context.save()
        print("CacheService: Cached \(conditions.count) conditions for \(resortId)")
    }

    func getCachedConditions(for resortId: String) -> CachedData<[WeatherCondition]>? {
        guard let context = modelContext else { return nil }

        let descriptor = FetchDescriptor<CachedWeatherCondition>(
            predicate: #Predicate { $0.resortId == resortId }
        )

        guard let cachedConditions = try? context.fetch(descriptor),
              !cachedConditions.isEmpty else {
            return nil
        }

        let conditions = cachedConditions.compactMap { $0.toWeatherCondition() }
        guard !conditions.isEmpty else { return nil }

        // Find oldest cache time
        let oldestCache = cachedConditions.min(by: { $0.cachedAt < $1.cachedAt })?.cachedAt ?? Date()
        let isStale = Date().timeIntervalSince(oldestCache) > CacheConfiguration.conditionCacheDuration

        return CachedData(data: conditions, isStale: isStale, cachedAt: oldestCache)
    }

    // MARK: - Snow Quality Summary Caching

    func cacheSnowQualitySummaries(_ summaries: [String: SnowQualitySummaryLight]) {
        guard let context = modelContext else { return }

        for (resortId, summary) in summaries {
            let descriptor = FetchDescriptor<CachedSnowQualitySummary>(
                predicate: #Predicate { $0.resortId == resortId }
            )

            if let existing = try? context.fetch(descriptor).first {
                // Update existing - ensure all fields are updated
                existing.overallQuality = summary.overallQuality
                existing.lastUpdated = summary.lastUpdated
                existing.temperatureC = summary.temperatureC
                existing.snowfallFreshCm = summary.snowfallFreshCm
                existing.snowfall24hCm = summary.snowfall24hCm
                existing.cachedAt = Date()
            } else {
                // Insert new
                context.insert(CachedSnowQualitySummary(resortId: resortId, summary: summary))
            }
        }

        try? context.save()
        print("CacheService: Cached \(summaries.count) snow quality summaries")
    }

    func getCachedSnowQualitySummaries() -> CachedData<[String: SnowQualitySummaryLight]>? {
        guard let context = modelContext else { return nil }

        let descriptor = FetchDescriptor<CachedSnowQualitySummary>()

        guard let cachedSummaries = try? context.fetch(descriptor),
              !cachedSummaries.isEmpty else {
            return nil
        }

        var summaries: [String: SnowQualitySummaryLight] = [:]
        for cached in cachedSummaries {
            summaries[cached.resortId] = cached.toSnowQualitySummaryLight()
        }

        // Find oldest cache time
        let oldestCache = cachedSummaries.min(by: { $0.cachedAt < $1.cachedAt })?.cachedAt ?? Date()
        let isStale = Date().timeIntervalSince(oldestCache) > CacheConfiguration.snowQualityCacheDuration

        return CachedData(data: summaries, isStale: isStale, cachedAt: oldestCache)
    }

    // MARK: - Cache Cleanup

    func cleanupStaleCache() {
        guard let context = modelContext else { return }

        let staleDate = Date().addingTimeInterval(-CacheConfiguration.staleCacheDuration)

        // Delete stale resorts
        let resortDescriptor = FetchDescriptor<CachedResort>(
            predicate: #Predicate { $0.cachedAt < staleDate }
        )
        if let staleResorts = try? context.fetch(resortDescriptor) {
            for resort in staleResorts {
                context.delete(resort)
            }
            print("CacheService: Deleted \(staleResorts.count) stale resort entries")
        }

        // Delete stale conditions
        let conditionDescriptor = FetchDescriptor<CachedWeatherCondition>(
            predicate: #Predicate { $0.cachedAt < staleDate }
        )
        if let staleConditions = try? context.fetch(conditionDescriptor) {
            for condition in staleConditions {
                context.delete(condition)
            }
            print("CacheService: Deleted \(staleConditions.count) stale condition entries")
        }

        // Delete stale snow quality summaries
        let summaryDescriptor = FetchDescriptor<CachedSnowQualitySummary>(
            predicate: #Predicate { $0.cachedAt < staleDate }
        )
        if let staleSummaries = try? context.fetch(summaryDescriptor) {
            for summary in staleSummaries {
                context.delete(summary)
            }
            print("CacheService: Deleted \(staleSummaries.count) stale snow quality entries")
        }

        try? context.save()
    }

    func clearAllCache() {
        guard let context = modelContext else { return }

        // Delete all cached resorts
        let resortDescriptor = FetchDescriptor<CachedResort>()
        if let allResorts = try? context.fetch(resortDescriptor) {
            for resort in allResorts {
                context.delete(resort)
            }
        }

        // Delete all cached conditions
        let conditionDescriptor = FetchDescriptor<CachedWeatherCondition>()
        if let allConditions = try? context.fetch(conditionDescriptor) {
            for condition in allConditions {
                context.delete(condition)
            }
        }

        // Delete all cached snow quality summaries
        let summaryDescriptor = FetchDescriptor<CachedSnowQualitySummary>()
        if let allSummaries = try? context.fetch(summaryDescriptor) {
            for summary in allSummaries {
                context.delete(summary)
            }
        }

        try? context.save()
        print("CacheService: Cleared all cache")
    }
}
