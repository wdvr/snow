import SwiftUI

struct ConditionsView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var showingQualityInfo = false

    var sortedResorts: [Resort] {
        userPreferencesManager.filterByVisibleRegions(snowConditionsManager.resorts)
            .sorted { resort1, resort2 in
                let quality1 = snowConditionsManager.getSnowQuality(for: resort1.id)
                let quality2 = snowConditionsManager.getSnowQuality(for: resort2.id)
                return quality1.sortOrder < quality2.sortOrder
            }
    }

    /// Only show offline indicator if data is actually stale (> 5 minutes old)
    var isDataStale: Bool {
        guard let lastUpdated = snowConditionsManager.lastUpdated else { return true }
        return Date().timeIntervalSince(lastUpdated) > 300 // 5 minutes
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
            // Cached data indicator - only show if data is actually old (> 5 minutes)
            if snowConditionsManager.isUsingCachedData && isDataStale {
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .foregroundStyle(.orange)
                    Text("Offline mode - showing cached data")
                        .font(.caption)
                        .foregroundStyle(.orange)
                    if let age = snowConditionsManager.cachedDataAge {
                        Text("(\(age))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.orange.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            if let lastUpdated = snowConditionsManager.lastUpdated {
                HStack {
                    Image(systemName: "clock")
                        .foregroundStyle(.secondary)
                    Text("Last updated: \(lastUpdated.formatted(.relative(presentation: .named)))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
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
        .cardStyle()
    }

    private func qualityCountBadge(quality: SnowQuality) -> some View {
        let count = sortedResorts.filter { resort in
            snowConditionsManager.getSnowQuality(for: resort.id) == quality
        }.count

        return VStack {
            Image(systemName: quality.icon)
                .foregroundStyle(quality.color)
            Text("\(count)")
                .font(.title3)
                .fontWeight(.bold)
            Text(quality.displayName)
                .font(.caption2)
                .foregroundStyle(.secondary)
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
            // Header - use overall quality from summary for consistency
            HStack {
                VStack(alignment: .leading) {
                    Text(resort.name)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(resort.displayLocation)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                let displayQuality = snowConditionsManager.getSnowQuality(for: resort.id)
                if displayQuality != .unknown {
                    VStack {
                        Image(systemName: displayQuality.icon)
                            .font(.title2)
                            .foregroundStyle(displayQuality.color)
                        Text(displayQuality.displayName)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(displayQuality.color)
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
                            .foregroundStyle(.cyan)
                        Text("\(top.formattedSnowSinceFreezeWithPrefs(userPreferencesManager.preferredUnits)) since last thaw")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    // Warming indicator
                    if top.currentlyWarming == true {
                        HStack(spacing: 4) {
                            Image(systemName: "thermometer.sun.fill")
                                .foregroundStyle(.orange)
                            Text("Warming")
                                .font(.caption)
                                .foregroundStyle(.orange)
                        }
                    }
                }
            }
        }
        .cardStyle()
    }

    private func elevationCondition(level: ElevationLevel, condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: level.icon)
                    .foregroundStyle(.blue)
                Text(level.displayName)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack {
                Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                    .font(.body)
                    .fontWeight(.medium)

                Spacer()

                Image(systemName: condition.snowQuality.icon)
                    .foregroundStyle(condition.snowQuality.color)
                    .font(.caption)
            }

            // Snow depth (base depth at this elevation)
            if let depth = condition.snowDepthCm, depth > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.down.to.line")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(WeatherCondition.formatSnowShort(depth, prefs: userPreferencesManager.preferredUnits))
                        .font(.caption)
                        .foregroundStyle(.primary)
                    Text("base")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Text(condition.formattedSnowfall24hWithPrefs(userPreferencesManager.preferredUnits))
                .font(.caption)
                .foregroundStyle(.blue)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
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
                            .foregroundStyle(.secondary)

                        VStack(alignment: .leading, spacing: 8) {
                            HStack(spacing: 12) {
                                Image(systemName: "ruler")
                                    .foregroundStyle(.blue)
                                VStack(alignment: .leading) {
                                    Text("Fresh snow thresholds:")
                                        .font(.caption)
                                        .fontWeight(.medium)
                                    Text("3\"+ = Excellent, 2\"+ = Good, 1\"+ = Fair")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }

                            HStack(spacing: 12) {
                                Image(systemName: "thermometer.snowflake")
                                    .foregroundStyle(.orange)
                                VStack(alignment: .leading) {
                                    Text("Ice forms (thaw-freeze) when:")
                                        .font(.caption)
                                        .fontWeight(.medium)
                                    Text("3h @ +3°C, 6h @ +2°C, or 8h @ +1°C")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .padding()
                        .background(Color.blue.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
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
                    .foregroundStyle(quality.color)
                    .frame(width: 40, height: 40)
                    .background(quality.color.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            // Quality details
            VStack(alignment: .leading, spacing: 4) {
                Text(quality.detailedInfo.title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(quality.color)

                Text(quality.detailedInfo.description)
                    .font(.caption)
                    .foregroundStyle(.primary)

                Text(quality.detailedInfo.criteria)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
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
