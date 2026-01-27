import SwiftUI

struct ConditionsView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var showingQualityInfo = false

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
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: { showingQualityInfo = true }) {
                        Image(systemName: "info.circle")
                    }
                }
            }
            .refreshable {
                await snowConditionsManager.refreshConditions()
            }
            .overlay {
                if snowConditionsManager.isLoading && snowConditionsManager.resorts.isEmpty {
                    ProgressView("Loading conditions...")
                }
            }
            .sheet(isPresented: $showingQualityInfo) {
                QualityInfoSheet()
            }
        }
    }

    private var summaryHeader: some View {
        VStack(spacing: 12) {
            // Cached data indicator
            if snowConditionsManager.isUsingCachedData {
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .foregroundColor(.orange)
                    Text("Offline mode - showing cached data")
                        .font(.caption)
                        .foregroundColor(.orange)
                    if let age = snowConditionsManager.cachedDataAge {
                        Text("(\(age))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            }

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
        .onTapGesture {
            showingQualityInfo = true
        }
    }
}

struct ResortConditionCard: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

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

            // Fresh snow summary (since last thaw-freeze)
            if let top = topCondition {
                HStack {
                    if top.snowSinceFreeze > 0 {
                        Image(systemName: "snowflake")
                            .foregroundColor(.cyan)
                        Text("\(top.formattedSnowSinceFreezeWithPrefs(userPreferencesManager.preferredUnits)) since last thaw")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    // Warming indicator
                    if top.currentlyWarming == true {
                        HStack(spacing: 4) {
                            Image(systemName: "thermometer.sun.fill")
                                .foregroundColor(.orange)
                            Text("Warming")
                                .font(.caption)
                                .foregroundColor(.orange)
                        }
                    }
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
                Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                    .font(.body)
                    .fontWeight(.medium)

                Spacer()

                Image(systemName: condition.snowQuality.icon)
                    .foregroundColor(condition.snowQuality.color)
                    .font(.caption)
            }

            Text(condition.formattedSnowfall24hWithPrefs(userPreferencesManager.preferredUnits))
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
        case .horrible: return 5
        case .unknown: return 6
        }
    }
}

// MARK: - Quality Info Sheet

struct QualityInfoSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Algorithm explanation
                    VStack(alignment: .leading, spacing: 8) {
                        Text("How Quality is Calculated")
                            .font(.headline)

                        Text("Quality ratings are based on **fresh powder since the last thaw-freeze event** — snow that hasn't turned to ice.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        VStack(alignment: .leading, spacing: 8) {
                            HStack(spacing: 12) {
                                Image(systemName: "ruler")
                                    .foregroundColor(.blue)
                                VStack(alignment: .leading) {
                                    Text("Fresh snow thresholds:")
                                        .font(.caption)
                                        .fontWeight(.medium)
                                    Text("3\"+ = Excellent, 2\"+ = Good, 1\"+ = Fair")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }

                            HStack(spacing: 12) {
                                Image(systemName: "thermometer.snowflake")
                                    .foregroundColor(.orange)
                                VStack(alignment: .leading) {
                                    Text("Ice forms (thaw-freeze) when:")
                                        .font(.caption)
                                        .fontWeight(.medium)
                                    Text("3h @ +3°C, 6h @ +2°C, or 8h @ +1°C")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                        .padding()
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(8)
                    }
                    .padding(.horizontal)

                    Divider()

                    // Quality levels
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Quality Levels")
                            .font(.headline)
                            .padding(.horizontal)

                        ForEach(SnowQuality.allCases, id: \.self) { quality in
                            QualityInfoRow(quality: quality)
                        }
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Snow Quality Guide")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct QualityInfoRow: View {
    let quality: SnowQuality

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Quality icon
            VStack {
                Image(systemName: quality.icon)
                    .font(.title2)
                    .foregroundColor(quality.color)
                    .frame(width: 40, height: 40)
                    .background(quality.color.opacity(0.15))
                    .cornerRadius(8)
            }

            // Quality details
            VStack(alignment: .leading, spacing: 4) {
                Text(quality.detailedInfo.title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(quality.color)

                Text(quality.detailedInfo.description)
                    .font(.caption)
                    .foregroundColor(.primary)

                Text(quality.detailedInfo.criteria)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .italic()
            }

            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }
}

#Preview("Conditions") {
    ConditionsView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}

#Preview("Quality Info") {
    QualityInfoSheet()
}
