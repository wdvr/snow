import SwiftUI

struct ResortDetailView: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var selectedElevation: ElevationLevel = .top
    @State private var showingShareSheet: Bool = false
    @State private var showThawFreezeInfo: Bool = false

    private var conditions: [WeatherCondition] {
        snowConditionsManager.conditions[resort.id] ?? []
    }

    private var conditionForSelectedElevation: WeatherCondition? {
        conditions.first { $0.elevationLevel == selectedElevation.rawValue }
    }

    private var shareText: String {
        var text = "🏔️ \(resort.name) Snow Report\n"
        text += "📍 \(resort.displayLocation)\n\n"

        if let condition = conditionForSelectedElevation {
            let prefs = userPreferencesManager.preferredUnits
            text += "Current Conditions (\(selectedElevation.displayName)):\n"
            text += "❄️ Snow Quality: \(condition.snowQuality.displayName)\n"
            text += "🌡️ Temperature: \(condition.formattedTemperature(prefs))\n"
            text += "🆕 Fresh Snow: \(WeatherCondition.formatSnow(condition.freshSnowCm, prefs: prefs))\n"
            text += "📊 24h Snowfall: \(WeatherCondition.formatSnow(condition.snowfall24hCm, prefs: prefs))\n"
        } else {
            text += "No current conditions available.\n"
        }

        text += "\n📱 Tracked with Powder Chaser"
        return text
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Resort header
                resortHeader

                // Elevation picker
                elevationPicker

                // Current conditions
                if let condition = conditionForSelectedElevation {
                    currentConditionsCard(condition)
                    snowDetailsCard(condition)
                    TimelineCard(resortId: resort.id, elevation: selectedElevation)
                    predictionsCard(condition)
                    weatherDetailsCard(condition)
                } else if snowConditionsManager.isLoading {
                    loadingCard
                } else {
                    noDataCard
                }

                // All elevations summary
                allElevationsSummary
            }
            .padding()
        }
        .navigationTitle(resort.name)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 16) {
                    Button {
                        AnalyticsService.shared.trackResortShared(resortId: resort.id, resortName: resort.name)
                        showingShareSheet = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(.blue)
                    }
                    .accessibilityLabel("Share \(resort.name)")

                    Button {
                        let wasFavorite = userPreferencesManager.isFavorite(resortId: resort.id)
                        userPreferencesManager.toggleFavorite(resortId: resort.id)
                        if wasFavorite {
                            AnalyticsService.shared.trackResortUnfavorited(resortId: resort.id, resortName: resort.name)
                        } else {
                            AnalyticsService.shared.trackResortFavorited(resortId: resort.id, resortName: resort.name)
                        }
                    } label: {
                        Image(systemName: userPreferencesManager.isFavorite(resortId: resort.id) ? "heart.fill" : "heart")
                            .foregroundStyle(userPreferencesManager.isFavorite(resortId: resort.id) ? .red : .gray)
                    }
                    .sensoryFeedback(.impact(weight: .light), trigger: userPreferencesManager.isFavorite(resortId: resort.id))
                    .accessibilityLabel(userPreferencesManager.isFavorite(resortId: resort.id) ? "Remove from favorites" : "Add to favorites")
                }
            }
        }
        .sheet(isPresented: $showingShareSheet) {
            ShareSheet(items: [shareText])
        }
        .refreshable {
            AnalyticsService.shared.trackPullToRefresh(screen: "ResortDetail")
            await snowConditionsManager.fetchConditionsForResort(resort.id, forceRefresh: true)
        }
        .task {
            // Fetch conditions for this resort when view appears
            await snowConditionsManager.fetchConditionsForResort(resort.id)
        }
        .onAppear {
            AnalyticsService.shared.trackScreen("ResortDetail", screenClass: "ResortDetailView")
            AnalyticsService.shared.trackResortViewed(
                resortId: resort.id,
                resortName: resort.name,
                region: resort.inferredRegion.rawValue
            )
        }
        .onDisappear {
            AnalyticsService.shared.trackScreenExit("ResortDetail")
        }
        .onChange(of: selectedElevation) { _, newValue in
            AnalyticsService.shared.trackElevationChanged(resortId: resort.id, elevation: newValue.rawValue)
        }
    }

    // MARK: - Resort Header

    /// Best quality across all loaded elevations (used for header badge)
    private var bestElevationQuality: SnowQuality? {
        let qualities = conditions.map { $0.snowQuality }
        guard !qualities.isEmpty else { return nil }
        return qualities.min(by: { $0.sortOrder < $1.sortOrder })
    }

    /// Snow score (0-100) for the best elevation (top preferred)
    private var bestElevationSnowScore: Int? {
        let preferred = ["top", "mid", "base"]
        for level in preferred {
            if let condition = conditions.first(where: { $0.elevationLevel == level }),
               let score = condition.snowScore {
                return score
            }
        }
        return conditions.first?.snowScore
    }

    private var resortHeader: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text(resort.elevationRange)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Overall snow quality badge - use best quality across elevations
                if let quality = bestElevationQuality {
                    VStack(spacing: 4) {
                        // Numeric snow score (0-100) from ML model
                        if let score = bestElevationSnowScore {
                            Text("\(score)")
                                .font(.system(size: 28, weight: .bold, design: .rounded))
                                .foregroundStyle(quality.color)
                        }
                        Image(systemName: quality.icon)
                            .font(.title2)
                            .foregroundStyle(quality.color)
                        Text(quality.displayName)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(quality.color)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(quality.color.opacity(0.1))
                    )
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Snow quality: \(quality.displayName)\(bestElevationSnowScore.map { ", score \($0) out of 100" } ?? "")")
                }
            }

            if let website = resort.officialWebsite, let url = URL(string: website) {
                Link(destination: url) {
                    Label("Visit Website", systemImage: "safari")
                        .font(.caption)
                }
                .simultaneousGesture(TapGesture().onEnded {
                    AnalyticsService.shared.trackResortWebsiteVisited(resortId: resort.id, resortName: resort.name)
                })
            }
        }
        .cardStyle()
    }

    // MARK: - Elevation Picker

    private var elevationPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Select Elevation")
                .font(.headline)

            Picker("Elevation", selection: $selectedElevation) {
                ForEach(ElevationLevel.allCases, id: \.self) { level in
                    if let point = resort.elevationPoint(for: level) {
                        Text("\(level.displayName) - \(point.formattedFeet)")
                            .tag(level)
                    }
                }
            }
            .pickerStyle(.segmented)
            .sensoryFeedback(.selection, trigger: selectedElevation)
        }
    }

    // MARK: - Current Conditions Card

    private func currentConditionsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Current Conditions")
                    .font(.headline)

                Spacer()

                Text(condition.formattedTimestamp)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 20) {
                // Temperature
                VStack {
                    Image(systemName: "thermometer")
                        .font(.title2)
                        .foregroundStyle(.blue)
                    Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .frame(maxWidth: .infinity)

                // Snow Quality with score
                VStack(spacing: 2) {
                    if let score = condition.snowScore {
                        Text("\(score)")
                            .font(.system(size: 22, weight: .bold, design: .rounded))
                            .foregroundStyle(condition.snowQuality.color)
                    }
                    Image(systemName: condition.snowQuality.icon)
                        .font(.title2)
                        .foregroundStyle(condition.snowQuality.color)
                    Text(condition.snowQuality.displayName)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(condition.snowQuality.color)
                }
                .frame(maxWidth: .infinity)

                // Fresh Snow
                VStack {
                    Image(systemName: "snowflake")
                        .font(.title2)
                        .foregroundStyle(.cyan)
                    Text(WeatherCondition.formatSnowShort(condition.freshSnowCm, prefs: userPreferencesManager.preferredUnits))
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("Fresh")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .cardStyle()
    }

    // MARK: - Snow Details Card

    private func snowDetailsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Surface type badge
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: condition.surfaceType.icon)
                        .foregroundStyle(condition.surfaceType.color)
                    Text(condition.surfaceType.rawValue)
                        .font(.headline)
                        .foregroundStyle(condition.surfaceType.color)
                }

                Spacer()

                if condition.currentlyWarming == true {
                    HStack(spacing: 4) {
                        Image(systemName: "thermometer.sun.fill")
                            .foregroundStyle(.orange)
                        Text("Warming")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(.orange)
                    }
                }
            }

            // Key metrics in a clear format
            VStack(alignment: .leading, spacing: 8) {
                // Last thaw/freeze
                HStack {
                    Text("Last thaw/freeze:")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(condition.formattedTimeSinceFreeze)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Button {
                        showThawFreezeInfo = true
                    } label: {
                        Image(systemName: "info.circle")
                            .font(.caption)
                            .foregroundStyle(.blue)
                    }
                    .accessibilityLabel("Thaw-freeze cycle information")
                    .popover(isPresented: $showThawFreezeInfo) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Thaw-Freeze Cycles")
                                .font(.headline)
                            Text("A thaw-freeze cycle occurs when temperatures rise above freezing for several hours, then drop below freezing again. This creates an ice layer under the snow surface.")
                                .font(.subheadline)
                            Text("Fresh snow that falls after a thaw-freeze covers the ice and creates good skiing conditions. The more snow since the last cycle, the better the quality.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        .padding()
                        .frame(maxWidth: 300)
                        .presentationCompactAdaptation(.popover)
                    }
                }

                // Snow since then
                HStack {
                    Text("Snow since then:")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(WeatherCondition.formatSnow(condition.snowSinceFreeze, prefs: userPreferencesManager.preferredUnits))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }

                // Total snow depth (base depth at this elevation)
                if let depth = condition.snowDepthCm, depth > 0 {
                    HStack {
                        Text("Base depth:")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text(WeatherCondition.formatSnow(depth, prefs: userPreferencesManager.preferredUnits))
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        // Show warning for thin coverage
                        if depth < 50 {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption)
                                .foregroundStyle(depth < 20 ? .red : .orange)
                        }
                    }
                } else {
                    HStack {
                        Text("Base depth:")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text("No data")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.vertical, 4)

            // Quality explanation from backend
            if let explanation = snowConditionsManager.getExplanation(for: resort.id) {
                Divider()
                HStack(alignment: .top, spacing: 6) {
                    Image(systemName: "info.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.blue)
                    Text(explanation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Divider()

            Text("Recent Snowfall")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            HStack(spacing: 20) {
                snowfallItem(title: "24h", value: condition.snowfall24hCm)
                snowfallItem(title: "48h", value: condition.snowfall48hCm)
                snowfallItem(title: "72h", value: condition.snowfall72hCm)
            }
        }
        .cardStyle()
    }

    private func snowfallItem(title: String, value: Double) -> some View {
        VStack {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(WeatherCondition.formatSnow(value, prefs: userPreferencesManager.preferredUnits))
                .font(.title3)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Predictions Card

    private func predictionsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(.blue)
                Text("Snow Forecast")
                    .font(.headline)
            }

            HStack(spacing: 20) {
                predictionItem(
                    title: "Next 24h",
                    value: condition.predictedSnow24hCm ?? 0.0
                )
                predictionItem(
                    title: "Next 48h",
                    value: condition.predictedSnow48hCm ?? 0.0
                )
                predictionItem(
                    title: "Next 72h",
                    value: condition.predictedSnow72hCm ?? 0.0
                )
            }

            // Prediction insight
            if let predicted24h = condition.predictedSnow24hCm, predicted24h > 10 {
                HStack {
                    Image(systemName: "snowflake.circle.fill")
                        .foregroundStyle(.blue)
                    Text("Heavy snowfall expected!")
                        .font(.subheadline)
                        .foregroundStyle(.blue)
                        .fontWeight(.medium)
                }
                .padding(.top, 4)
            } else if let predicted24h = condition.predictedSnow24hCm, predicted24h > 5 {
                HStack {
                    Image(systemName: "cloud.snow")
                        .foregroundStyle(.secondary)
                    Text("Light snow expected")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 4)
            }
        }
        .cardStyle()
    }

    private func predictionItem(title: String, value: Double) -> some View {
        VStack {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(WeatherCondition.formatSnow(value, prefs: userPreferencesManager.preferredUnits))
                .font(.title3)
                .fontWeight(.semibold)
                .foregroundStyle(.blue)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Weather Details Card

    private func weatherDetailsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Weather Details")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                weatherDetailItem(
                    icon: "thermometer.low",
                    title: "Min Temp",
                    value: condition.formattedMinTemp(userPreferencesManager.preferredUnits)
                )

                weatherDetailItem(
                    icon: "thermometer.high",
                    title: "Max Temp",
                    value: condition.formattedMaxTemp(userPreferencesManager.preferredUnits)
                )

                if let humidity = condition.humidityPercent {
                    weatherDetailItem(
                        icon: "humidity",
                        title: "Humidity",
                        value: "\(Int(humidity))%"
                    )
                }

                if condition.windSpeedKmh != nil {
                    weatherDetailItem(
                        icon: "wind",
                        title: "Wind",
                        value: condition.formattedWindSpeedWithPrefs(userPreferencesManager.preferredUnits)
                    )
                }
            }

            if let description = condition.weatherDescription {
                HStack {
                    Image(systemName: "cloud")
                        .foregroundStyle(.secondary)
                    Text(description)
                        .font(.body)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .cardStyle()
    }

    private func weatherDetailItem(icon: String, title: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundStyle(.blue)
                .frame(width: 24)

            VStack(alignment: .leading) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.body)
                    .fontWeight(.medium)
            }

            Spacer()
        }
        .padding(.vertical, 4)
    }

    // MARK: - All Elevations Summary

    private var allElevationsSummary: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("All Elevations")
                .font(.headline)

            ForEach(ElevationLevel.allCases, id: \.self) { level in
                if let point = resort.elevationPoint(for: level),
                   let condition = conditions.first(where: { $0.elevationLevel == level.rawValue }) {
                    HStack {
                        Image(systemName: level.icon)
                            .foregroundStyle(.blue)
                            .frame(width: 24)

                        VStack(alignment: .leading) {
                            Text(level.displayName)
                                .font(.body)
                                .fontWeight(.medium)
                            Text(point.formattedFeet)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        VStack(alignment: .trailing) {
                            HStack(spacing: 4) {
                                Image(systemName: condition.snowQuality.icon)
                                    .foregroundStyle(condition.snowQuality.color)
                                Text(condition.snowQuality.displayName)
                                    .foregroundStyle(condition.snowQuality.color)
                            }
                            .font(.subheadline)

                            Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 8)

                    if level != .base {
                        Divider()
                    }
                }
            }
        }
        .cardStyle()
    }

    // MARK: - Loading Card

    private var loadingCard: some View {
        VStack(spacing: 12) {
            ProgressView()
                .scaleEffect(1.2)

            Text("Loading Conditions...")
                .font(.headline)

            Text("Fetching the latest weather data for this resort.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .cardStyle()
    }

    // MARK: - No Data Card

    private var noDataCard: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.orange)

            Text("No Data Available")
                .font(.headline)

            Text("Weather conditions for this elevation are not currently available. Pull to refresh.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .cardStyle()
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview("Resort Detail") {
    NavigationStack {
        ResortDetailView(resort: Resort.sampleResorts[0])
            .environmentObject(SnowConditionsManager())
            .environmentObject(UserPreferencesManager.shared)
    }
}
