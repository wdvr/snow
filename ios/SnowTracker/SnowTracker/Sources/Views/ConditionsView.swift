import SwiftUI

struct ConditionsView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

    var sortedResorts: [Resort] {
        snowConditionsManager.resorts.sorted { resort1, resort2 in
            let quality1 = snowConditionsManager.getLatestCondition(for: resort1.id)?.snowQuality ?? .unknown
            let quality2 = snowConditionsManager.getLatestCondition(for: resort2.id)?.snowQuality ?? .unknown
            return quality1.sortOrder < quality2.sortOrder
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 16) {
                    // Summary header
                    summaryHeader

                    // Resort conditions cards
                    ForEach(sortedResorts) { resort in
                        NavigationLink(destination: ResortDetailView(resort: resort)) {
                            ResortConditionCard(resort: resort)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                .padding()
            }
            .navigationTitle("Snow Conditions")
            .refreshable {
                await snowConditionsManager.refreshConditions()
            }
            .overlay {
                if snowConditionsManager.isLoading && snowConditionsManager.resorts.isEmpty {
                    ProgressView("Loading conditions...")
                }
            }
        }
    }

    private var summaryHeader: some View {
        VStack(spacing: 12) {
            if let lastUpdated = snowConditionsManager.lastUpdated {
                HStack {
                    Image(systemName: "clock")
                        .foregroundColor(.secondary)
                    Text("Last updated: \(lastUpdated.formatted(.relative(presentation: .named)))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            // Quality distribution
            HStack(spacing: 16) {
                qualityCountBadge(quality: .excellent)
                qualityCountBadge(quality: .good)
                qualityCountBadge(quality: .fair)
                qualityCountBadge(quality: .poor)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func qualityCountBadge(quality: SnowQuality) -> some View {
        let count = snowConditionsManager.resorts.filter { resort in
            snowConditionsManager.getLatestCondition(for: resort.id)?.snowQuality == quality
        }.count

        return VStack {
            Image(systemName: quality.icon)
                .foregroundColor(quality.color)
            Text("\(count)")
                .font(.title3)
                .fontWeight(.bold)
            Text(quality.displayName)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct ResortConditionCard: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

    private var conditions: [WeatherCondition] {
        snowConditionsManager.conditions[resort.id] ?? []
    }

    private var topCondition: WeatherCondition? {
        conditions.first { $0.elevationLevel == "top" }
    }

    private var baseCondition: WeatherCondition? {
        conditions.first { $0.elevationLevel == "base" }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                VStack(alignment: .leading) {
                    Text(resort.name)
                        .font(.headline)
                        .foregroundColor(.primary)
                    Text(resort.displayLocation)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                if let condition = topCondition {
                    VStack {
                        Image(systemName: condition.snowQuality.icon)
                            .font(.title2)
                            .foregroundColor(condition.snowQuality.color)
                        Text(condition.snowQuality.displayName)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(condition.snowQuality.color)
                    }
                }
            }

            Divider()

            // Elevation conditions
            HStack(spacing: 16) {
                if let top = topCondition {
                    elevationCondition(level: .top, condition: top)
                }

                if let base = baseCondition {
                    elevationCondition(level: .base, condition: base)
                }
            }

            // Fresh snow summary
            if let top = topCondition, top.freshSnowCm > 0 {
                HStack {
                    Image(systemName: "snowflake")
                        .foregroundColor(.cyan)
                    Text("\(String(format: "%.0f", top.freshSnowCm))cm fresh snow at summit")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func elevationCondition(level: ElevationLevel, condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: level.icon)
                    .foregroundColor(.blue)
                Text(level.displayName)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            HStack {
                Text("\(Int(condition.currentTempCelsius))°C")
                    .font(.body)
                    .fontWeight(.medium)

                Spacer()

                Image(systemName: condition.snowQuality.icon)
                    .foregroundColor(condition.snowQuality.color)
                    .font(.caption)
            }

            Text(condition.formattedSnowfall24h)
                .font(.caption)
                .foregroundColor(.blue)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// Extension for sorting
extension SnowQuality {
    var sortOrder: Int {
        switch self {
        case .excellent: return 0
        case .good: return 1
        case .fair: return 2
        case .poor: return 3
        case .bad: return 4
        case .unknown: return 5
        }
    }
}

#Preview("Conditions") {
    ConditionsView()
        .environmentObject(SnowConditionsManager())
}
