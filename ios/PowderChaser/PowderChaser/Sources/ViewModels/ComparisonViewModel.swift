import SwiftUI
import os.log

@MainActor
final class ComparisonViewModel: ObservableObject {
    @Published var selectedResorts: [Resort] = []
    @Published var conditions: [String: [WeatherCondition]] = [:]
    @Published var summaries: [String: SnowQualitySummaryLight] = [:]
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiClient = APIClient.shared
    private let log = Logger(subsystem: "com.snowtracker.app", category: "ComparisonViewModel")

    static let maxResorts = 4

    var canAddMore: Bool {
        selectedResorts.count < Self.maxResorts
    }

    func addResort(_ resort: Resort) {
        guard canAddMore, !selectedResorts.contains(where: { $0.id == resort.id }) else { return }
        selectedResorts.append(resort)
        Task { await fetchDataForResort(resort.id) }
    }

    func removeResort(_ resort: Resort) {
        selectedResorts.removeAll { $0.id == resort.id }
        conditions.removeValue(forKey: resort.id)
        summaries.removeValue(forKey: resort.id)
    }

    func fetchAllData() async {
        guard !selectedResorts.isEmpty else { return }
        isLoading = true
        defer { isLoading = false }

        let ids = selectedResorts.map { $0.id }

        do {
            async let conditionsResult = apiClient.getBatchConditions(resortIds: ids)
            async let qualityResult = apiClient.getBatchSnowQuality(for: ids)

            let (fetchedConditions, fetchedQuality) = try await (conditionsResult, qualityResult)
            conditions = fetchedConditions
            summaries = fetchedQuality
            errorMessage = nil
        } catch {
            log.error("Failed to fetch comparison data: \(error)")
            errorMessage = "Failed to load comparison data"
        }
    }

    private func fetchDataForResort(_ resortId: String) async {
        do {
            async let conditionsResult = apiClient.getBatchConditions(resortIds: [resortId])
            async let qualityResult = apiClient.getBatchSnowQuality(for: [resortId])

            let (fetchedConditions, fetchedQuality) = try await (conditionsResult, qualityResult)
            for (key, value) in fetchedConditions { conditions[key] = value }
            for (key, value) in fetchedQuality { summaries[key] = value }
        } catch {
            log.error("Failed to fetch data for \(resortId): \(error)")
        }
    }

    // MARK: - Comparison Helpers

    func topCondition(for resortId: String) -> WeatherCondition? {
        conditions[resortId]?.first { $0.elevationLevel == "top" }
            ?? conditions[resortId]?.first { $0.elevationLevel == "mid" }
            ?? conditions[resortId]?.first
    }

    func snowQuality(for resortId: String) -> SnowQuality {
        if let summary = summaries[resortId] {
            return summary.overallSnowQuality
        }
        return .unknown
    }

    func snowScore(for resortId: String) -> Int? {
        summaries[resortId]?.snowScore
    }

    /// Returns the resort ID(s) that are "best" for a given metric
    func bestResortIds(for metric: ComparisonMetric) -> Set<String> {
        guard !selectedResorts.isEmpty else { return [] }

        switch metric {
        case .quality:
            let best = selectedResorts.min { snowQuality(for: $0.id).sortOrder < snowQuality(for: $1.id).sortOrder }
            let bestSort = best.map { snowQuality(for: $0.id).sortOrder } ?? 99
            return Set(selectedResorts.filter { snowQuality(for: $0.id).sortOrder == bestSort }.map { $0.id })

        case .snowScore:
            let scores = selectedResorts.compactMap { r in snowScore(for: r.id).map { (r.id, $0) } }
            guard let best = scores.max(by: { $0.1 < $1.1 }) else { return [] }
            return Set(scores.filter { $0.1 == best.1 }.map { $0.0 })

        case .freshSnow:
            let values = selectedResorts.compactMap { r in topCondition(for: r.id).map { (r.id, $0.freshSnowCm) } }
            guard let best = values.max(by: { $0.1 < $1.1 }), best.1 > 0 else { return [] }
            return Set(values.filter { $0.1 == best.1 }.map { $0.0 })

        case .temperature:
            // "Best" temp for skiing = coldest (preserves snow)
            let values = selectedResorts.compactMap { r in topCondition(for: r.id).map { (r.id, $0.currentTempCelsius) } }
            guard let best = values.min(by: { $0.1 < $1.1 }) else { return [] }
            return Set(values.filter { $0.1 == best.1 }.map { $0.0 })

        case .wind:
            // Best wind = lowest
            let values = selectedResorts.compactMap { r in
                topCondition(for: r.id)?.windSpeedKmh.map { (r.id, $0) }
            }
            guard let best = values.min(by: { $0.1 < $1.1 }) else { return [] }
            return Set(values.filter { $0.1 == best.1 }.map { $0.0 })

        case .snowDepth:
            let values = selectedResorts.compactMap { r in
                topCondition(for: r.id)?.snowDepthCm.map { (r.id, $0) }
            }
            guard let best = values.max(by: { $0.1 < $1.1 }), best.1 > 0 else { return [] }
            return Set(values.filter { $0.1 == best.1 }.map { $0.0 })

        case .forecast:
            let values = selectedResorts.compactMap { r in
                topCondition(for: r.id)?.predictedSnow48hCm.map { (r.id, $0) }
            }
            guard let best = values.max(by: { $0.1 < $1.1 }), best.1 > 0 else { return [] }
            return Set(values.filter { $0.1 == best.1 }.map { $0.0 })
        }
    }
}

enum ComparisonMetric {
    case quality, snowScore, freshSnow, temperature, wind, snowDepth, forecast
}
