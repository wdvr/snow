import SwiftUI

struct ResortComparisonView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @StateObject private var viewModel = ComparisonViewModel()
    @State private var showResortPicker = false

    /// Pre-selected resorts (from favorites multi-select)
    let initialResorts: [Resort]

    init(initialResorts: [Resort] = []) {
        self.initialResorts = initialResorts
    }

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.selectedResorts.isEmpty {
                    emptyState
                } else {
                    comparisonContent
                }
            }
            .navigationTitle("Compare")
            .toolbar {
                if viewModel.canAddMore {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showResortPicker = true
                        } label: {
                            Label("Add Resort", systemImage: "plus")
                        }
                    }
                }
            }
            .sheet(isPresented: $showResortPicker) {
                ResortPickerSheet(
                    allResorts: snowConditionsManager.resorts,
                    selectedIds: Set(viewModel.selectedResorts.map { $0.id }),
                    maxSelections: ComparisonViewModel.maxResorts,
                    onSelect: { resort in
                        viewModel.addResort(resort)
                    }
                )
                .environmentObject(snowConditionsManager)
                .environmentObject(userPreferencesManager)
            }
            .onAppear {
                if viewModel.selectedResorts.isEmpty && !initialResorts.isEmpty {
                    for resort in initialResorts {
                        viewModel.addResort(resort)
                    }
                }
                AnalyticsService.shared.trackScreen("ResortComparison", screenClass: "ResortComparisonView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("ResortComparison")
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 20) {
            Image(systemName: "rectangle.split.3x1")
                .font(.system(size: 60))
                .foregroundStyle(.gray)

            Text("Compare Resorts")
                .font(.title2)
                .fontWeight(.semibold)

            VStack(spacing: 8) {
                Text("Select up to 4 resorts to compare conditions side by side.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Text("Compare snow quality, temperature, fresh snow, and forecasts at a glance.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 40)

            Button {
                showResortPicker = true
            } label: {
                Label("Add Resorts", systemImage: "plus.circle.fill")
                    .font(.headline)
                    .padding()
                    .background(Color.blue)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }

    private var comparisonContent: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Resort headers with remove buttons
                resortHeaders

                // Quality comparison
                comparisonSection("Snow Quality", metric: .quality) { resortId in
                    let quality = viewModel.snowQuality(for: resortId)
                    VStack(spacing: 4) {
                        Image(systemName: quality.icon)
                            .font(.title2)
                            .foregroundStyle(quality.color)
                        Text(quality.displayName)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(quality.color)
                    }
                }

                // Snow score
                comparisonSection("Snow Score", metric: .snowScore) { resortId in
                    if let score = viewModel.snowScore(for: resortId) {
                        VStack(spacing: 4) {
                            Text("\(score)")
                                .font(.title2)
                                .fontWeight(.bold)
                            Text("/ 100")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    } else {
                        Text("--")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    }
                }

                // Fresh snow
                comparisonSection("Fresh Snow", metric: .freshSnow) { resortId in
                    if let condition = viewModel.topCondition(for: resortId) {
                        VStack(spacing: 4) {
                            Text(condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits))
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // Temperature
                comparisonSection("Temperature", metric: .temperature) { resortId in
                    if let condition = viewModel.topCondition(for: resortId) {
                        VStack(spacing: 4) {
                            Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // Wind
                comparisonSection("Wind", metric: .wind) { resortId in
                    if let condition = viewModel.topCondition(for: resortId),
                       condition.windSpeedKmh != nil {
                        VStack(spacing: 4) {
                            Text(condition.formattedWindSpeedWithPrefs(userPreferencesManager.preferredUnits))
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // Snow depth
                comparisonSection("Snow Depth", metric: .snowDepth) { resortId in
                    if let condition = viewModel.topCondition(for: resortId),
                       let depth = condition.snowDepthCm, depth > 0 {
                        VStack(spacing: 4) {
                            Text(WeatherCondition.formatSnow(depth, prefs: userPreferencesManager.preferredUnits))
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // 48h forecast
                comparisonSection("48h Forecast", metric: .forecast) { resortId in
                    if let condition = viewModel.topCondition(for: resortId),
                       let predicted = condition.predictedSnow48hCm, predicted > 0 {
                        VStack(spacing: 4) {
                            Text("+\(WeatherCondition.formatSnow(predicted, prefs: userPreferencesManager.preferredUnits))")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundStyle(.blue)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // 24h snowfall
                comparisonSection("24h Snowfall", metric: .freshSnow) { resortId in
                    if let condition = viewModel.topCondition(for: resortId) {
                        VStack(spacing: 4) {
                            Text(condition.formattedSnowfall24hWithPrefs(userPreferencesManager.preferredUnits))
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // Explanation
                comparisonSection("Conditions", metric: .quality) { resortId in
                    if let summary = viewModel.summaries[resortId],
                       let explanation = summary.explanation {
                        Text(explanation)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .lineLimit(4)
                    } else {
                        Text("No data")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding()
        }
        .refreshable {
            await viewModel.fetchAllData()
        }
    }

    private var resortHeaders: some View {
        HStack(spacing: 8) {
            ForEach(viewModel.selectedResorts) { resort in
                VStack(spacing: 4) {
                    Text(resort.name)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .lineLimit(2)
                        .multilineTextAlignment(.center)

                    Text(resort.country)
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    if resort.epicPass != nil || resort.ikonPass != nil {
                        HStack(spacing: 4) {
                            if resort.epicPass != nil {
                                PassBadge(passName: "Epic", color: .indigo)
                            }
                            if resort.ikonPass != nil {
                                PassBadge(passName: "Ikon", color: .orange)
                            }
                        }
                    }

                    Button {
                        withAnimation { viewModel.removeResort(resort) }
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                            .font(.caption)
                    }
                    .buttonStyle(.plain)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
        .cardStyle()
    }

    private func comparisonSection<Content: View>(
        _ title: String,
        metric: ComparisonMetric,
        @ViewBuilder content: @escaping (String) -> Content
    ) -> some View {
        VStack(spacing: 8) {
            Text(title)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            let bestIds = viewModel.bestResortIds(for: metric)

            HStack(spacing: 8) {
                ForEach(viewModel.selectedResorts) { resort in
                    VStack {
                        content(resort.id)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(bestIds.contains(resort.id) ? Color.green.opacity(0.1) : Color.clear)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(bestIds.contains(resort.id) ? Color.green.opacity(0.5) : Color.clear, lineWidth: 1)
                    )
                    .accessibilityLabel("\(resort.name): \(title)")
                    .accessibilityValue(bestIds.contains(resort.id) ? "Best" : "")
                }
            }
        }
        .padding()
        .cardStyle()
    }
}

// MARK: - Resort Picker Sheet

struct ResortPickerSheet: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @State private var searchText = ""

    let allResorts: [Resort]
    let selectedIds: Set<String>
    let maxSelections: Int
    let onSelect: (Resort) -> Void

    private var filteredResorts: [Resort] {
        let available = allResorts.filter { !selectedIds.contains($0.id) }
        if searchText.isEmpty {
            return available
        }
        return available.filter {
            $0.name.localizedCaseInsensitiveContains(searchText) ||
            $0.country.localizedCaseInsensitiveContains(searchText) ||
            $0.region.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationStack {
            List(filteredResorts) { resort in
                Button {
                    onSelect(resort)
                    if selectedIds.count + 1 >= maxSelections {
                        dismiss()
                    }
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(resort.name)
                                .font(.body)
                                .foregroundStyle(.primary)
                            Text(resort.displayLocation)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        let quality = snowConditionsManager.getSnowQuality(for: resort.id)
                        if quality != .unknown {
                            Image(systemName: quality.icon)
                                .foregroundStyle(quality.color)
                        }
                    }
                }
            }
            .searchable(text: $searchText, prompt: "Search resorts")
            .navigationTitle("Add Resort")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

#Preview("Comparison") {
    ResortComparisonView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
