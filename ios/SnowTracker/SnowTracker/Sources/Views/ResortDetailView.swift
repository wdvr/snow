import SafariServices
import SwiftUI

struct ResortDetailView: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @StateObject private var liveActivityService = LiveActivityService.shared
    @State private var selectedElevation: ElevationLevel = .top
    @State private var showingShareSheet: Bool = false
    @State private var showThawFreezeInfo: Bool = false
    @State private var isRetrying: Bool = false
    @State private var showDataSources: Bool = false
    @State private var safariURL: IdentifiableURL?
    @State private var showingSuggestEdit: Bool = false
    @State private var showingTrailMap: Bool = false

    private var conditions: [WeatherCondition] {
        snowConditionsManager.conditions[resort.id] ?? []
    }

    private var conditionForSelectedElevation: WeatherCondition? {
        // Try exact match first, then fall back through elevations
        if let exact = conditions.first(where: { $0.elevationLevel == selectedElevation.rawValue }) {
            return exact
        }
        // Fallback: top > mid > base
        for level in ["top", "mid", "base"] where level != selectedElevation.rawValue {
            if let fallback = conditions.first(where: { $0.elevationLevel == level }) {
                return fallback
            }
        }
        return conditions.first
    }

    private var shareText: String {
        var text = "\(resort.name) Snow Report\n"
        text += "\(resort.displayLocation)\n\n"

        if let condition = conditionForSelectedElevation {
            let prefs = userPreferencesManager.preferredUnits

            // Snow score if available
            if let score = snowConditionsManager.getSnowScore(for: resort.id) {
                text += "Snow Score: \(score)/100 (\(condition.snowQuality.displayName))\n"
            } else {
                text += "Snow Quality: \(condition.snowQuality.displayName)\n"
            }

            text += "Temperature: \(condition.formattedTemperature(prefs))\n"
            text += "Fresh Snow: \(WeatherCondition.formatSnow(condition.freshSnowCm, prefs: prefs))\n"

            if let depth = condition.snowDepthCm, depth > 0 {
                text += "Snow Depth: \(WeatherCondition.formatSnow(depth, prefs: prefs))\n"
            }

            if let predicted = condition.predictedSnow48hCm, predicted >= 5 {
                text += "48h Forecast: +\(WeatherCondition.formatSnow(predicted, prefs: prefs))\n"
            }
        } else {
            text += "No current conditions available.\n"
        }

        text += "\nTracked with Powder Chaser"
        return text
    }

    /// Overlay type based on the top-elevation condition (most representative)
    private var currentOverlayType: WeatherOverlayType {
        let topCondition = conditions.first { $0.elevationLevel == "top" }
            ?? conditions.first { $0.elevationLevel == "mid" }
            ?? conditions.first
        return topCondition?.weatherOverlayType ?? .none
    }

    var body: some View {
        ZStack {
            WeatherOverlayView(overlayType: currentOverlayType)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    // Resort header
                    resortHeader

                    // Elevation picker
                    elevationPicker

                    // Current conditions
                    if let condition = conditionForSelectedElevation {
                        Group {
                            currentConditionsCard(condition)
                            snowDetailsCard(condition)
                            FreshSnowChartView(resortId: resort.id, elevation: selectedElevation, condition: condition)
                            TimelineCard(resortId: resort.id, elevation: selectedElevation)
                            predictionsCard(condition)
                            weatherDetailsCard(condition)
                        }
                        .transition(.opacity.combined(with: .move(edge: .trailing)))
                        .id(selectedElevation)
                    } else if snowConditionsManager.isLoading {
                        loadingCard
                    } else {
                        noDataCard
                    }

                    // Elevation profile and resort details
                    if !conditions.isEmpty {
                        ElevationProfileView(
                            resort: resort,
                            conditions: conditions,
                            prefs: userPreferencesManager.preferredUnits
                        )
                    }

                    runDifficultySection

                    // Snow history chart
                    SnowHistoryView(resortId: resort.id)

                    // Community condition reports
                    ConditionReportSection(resortId: resort.id)

                    // All elevations summary
                    allElevationsSummary

                    // Data sources (at the very bottom)
                    if let condition = conditionForSelectedElevation {
                        dataSourcesCard(condition)
                    }

                    // Suggest an Edit
                    suggestEditButton
                }
                .padding()
            }
        }
        .appBackground()
        .navigationTitle(resort.name)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 16) {
                    if liveActivityService.isSupported {
                        Button {
                            toggleLiveActivity()
                        } label: {
                            VStack(spacing: 2) {
                                Image(systemName: liveActivityService.isActive(for: resort.id) ? "antenna.radiowaves.left.and.right.circle.fill" : "antenna.radiowaves.left.and.right.circle")
                                    .foregroundStyle(liveActivityService.isActive(for: resort.id) ? .green : .gray)
                                Text("Live")
                                    .font(.system(size: 9, weight: .medium))
                                    .foregroundStyle(liveActivityService.isActive(for: resort.id) ? .green : .gray)
                            }
                        }
                        .sensoryFeedback(.impact(weight: .light), trigger: liveActivityService.isActive(for: resort.id))
                        .accessibilityLabel(liveActivityService.isActive(for: resort.id) ? "Stop Live Activity tracking" : "Start Live Activity tracking for \(resort.name)")
                        .accessibilityHint(liveActivityService.isActive(for: resort.id) ? "Removes the live conditions widget from your Lock Screen" : "Shows live snow conditions on your Lock Screen and Dynamic Island")
                    }

                    Button {
                        AnalyticsService.shared.trackResortShared(resortId: resort.id, resortName: resort.name)
                        showingShareSheet = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(.blue)
                    }
                    .accessibilityLabel("Share \(resort.name)")
                    .accessibilityIdentifier(AccessibilityID.ResortDetail.shareButton)

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
                    .accessibilityIdentifier(AccessibilityID.ResortDetail.favoriteButton)
                }
            }
        }
        .sheet(isPresented: $showingShareSheet) {
            let image = ConditionsCardRenderer.render(
                resort: resort,
                condition: conditionForSelectedElevation,
                quality: snowConditionsManager.getSnowQuality(for: resort.id),
                snowScore: snowConditionsManager.getSnowScore(for: resort.id),
                prefs: userPreferencesManager.preferredUnits
            )
            ShareSheet(items: [image, shareText])
        }
        .sheet(isPresented: $showingSuggestEdit) {
            SuggestEditView(resortId: resort.id, resortName: resort.name)
        }
        .fullScreenCover(isPresented: $showingTrailMap) {
            if let urlStr = resort.trailMapUrl, let url = URL(string: urlStr) {
                TrailMapView(url: url, resortName: resort.name)
            }
        }
        .safariOverlay(url: $safariURL)
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
        .animation(.easeInOut(duration: 0.25), value: selectedElevation)
        .onChange(of: selectedElevation) { _, newValue in
            AnalyticsService.shared.trackElevationChanged(resortId: resort.id, elevation: newValue.rawValue)
        }
        .onChange(of: conditions) { _, _ in
            updateLiveActivityIfNeeded()
        }
    }

    // MARK: - Live Activity

    private func toggleLiveActivity() {
        if liveActivityService.isActive(for: resort.id) {
            liveActivityService.end(resortId: resort.id)
        } else {
            guard let condition = conditionForSelectedElevation else { return }
            let quality = snowConditionsManager.getSnowQuality(for: resort.id).rawValue
            let score = snowConditionsManager.getSnowScore(for: resort.id)
            liveActivityService.start(
                resortId: resort.id,
                resortName: resort.name,
                resortLocation: resort.displayLocation,
                freshSnowCm: condition.freshSnowCm,
                temperatureCelsius: condition.currentTempCelsius,
                snowQuality: quality,
                snowScore: score
            )
        }
    }

    private func updateLiveActivityIfNeeded() {
        guard liveActivityService.isActive(for: resort.id),
              let condition = conditionForSelectedElevation else { return }
        let quality = snowConditionsManager.getSnowQuality(for: resort.id).rawValue
        let score = snowConditionsManager.getSnowScore(for: resort.id)
        liveActivityService.update(
            freshSnowCm: condition.freshSnowCm,
            temperatureCelsius: condition.currentTempCelsius,
            snowQuality: quality,
            snowScore: score
        )
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
                ResortLogoView(resort: resort, size: 44)

                VStack(alignment: .leading, spacing: 4) {
                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text(resort.elevationRange(prefs: userPreferencesManager.preferredUnits))
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    // Pass affiliation badges
                    if resort.epicPass != nil || resort.ikonPass != nil || resort.indyPass != nil {
                        HStack(spacing: 6) {
                            if let epicPass = resort.epicPass {
                                PassBadge(passName: "Epic", detail: epicPass, color: .indigo)
                            }
                            if let ikonPass = resort.ikonPass {
                                PassBadge(passName: "Ikon", detail: ikonPass, color: .orange)
                            }
                            if let indyPass = resort.indyPass {
                                PassBadge(passName: "Indy", detail: indyPass, color: .green)
                            }
                        }
                    }
                }

                Spacer()

                // Overall snow quality badge - use best quality across elevations
                if let quality = bestElevationQuality {
                    VStack(spacing: 4) {
                        // Numeric snow score (0-100) from ML model
                        if let score = bestElevationSnowScore {
                            Text("\(score)")
                                .font(.title.weight(.bold))
                                .fontDesign(.rounded)
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
                        LinearGradient(
                            colors: [quality.color.opacity(0.15), quality.color.opacity(0.05)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    )
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Snow quality: \(quality.displayName)\(bestElevationSnowScore.map { ", score \($0) out of 100" } ?? "")")
                }
            }

            // Links row
            HStack(spacing: 16) {
                if let website = resort.officialWebsite, let url = URL(string: website) {
                    Button {
                        AnalyticsService.shared.trackResortWebsiteVisited(resortId: resort.id, resortName: resort.name)
                        safariURL = IdentifiableURL(url: url)
                    } label: {
                        Label("Website", systemImage: "safari")
                            .font(.caption)
                    }
                }

                if let mapUrlStr = resort.trailMapUrl, let mapUrl = URL(string: mapUrlStr) {
                    Button {
                        if mapUrlStr.hasSuffix(".jpg") || mapUrlStr.hasSuffix(".jpeg") || mapUrlStr.hasSuffix(".png") {
                            showingTrailMap = true
                        } else {
                            safariURL = IdentifiableURL(url: mapUrl)
                        }
                    } label: {
                        Label("Trail Map", systemImage: "map")
                            .font(.caption)
                    }
                }

                if let webcamUrlStr = resort.webcamUrl, let webcamUrl = URL(string: webcamUrlStr) {
                    Button {
                        safariURL = IdentifiableURL(url: webcamUrl)
                    } label: {
                        Label("Webcams", systemImage: "web.camera")
                            .font(.caption)
                    }
                }

                Spacer()
            }
        }
        .cardStyleElevated()
    }

    // MARK: - Elevation Picker

    private var elevationPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Select Elevation")
                .font(.headline)

            Picker("Elevation", selection: $selectedElevation) {
                ForEach(ElevationLevel.allCases, id: \.self) { level in
                    if let point = resort.elevationPoint(for: level) {
                        Text("\(level.displayName) - \(point.formattedElevation(prefs: userPreferencesManager.preferredUnits))")
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
                            .font(.title2.weight(.bold))
                            .fontDesign(.rounded)
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
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title) snowfall: \(WeatherCondition.formatSnow(value, prefs: userPreferencesManager.preferredUnits))")
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
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title) forecast: \(WeatherCondition.formatSnow(value, prefs: userPreferencesManager.preferredUnits))")
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

                if condition.windGustKmh != nil {
                    weatherDetailItem(
                        icon: "wind.snow",
                        title: "Gusts",
                        value: condition.formattedWindGustWithPrefs(userPreferencesManager.preferredUnits)
                    )
                }

                if let maxGust = condition.maxWindGust24h {
                    weatherDetailItem(
                        icon: "wind.circle",
                        title: "Max Gust 24h",
                        value: WeatherCondition.formatWindSpeed(maxGust, prefs: userPreferencesManager.preferredUnits)
                    )
                }
            }

            // Visibility warning
            if let vis = condition.visibilityM, vis < 5000 {
                let category = WeatherCondition.visibilityCategory(meters: vis)
                Divider()
                HStack(spacing: 8) {
                    Image(systemName: "cloud.fog")
                        .foregroundStyle(category.color)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 4) {
                            Text("Visibility: \(category.label)")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundStyle(category.color)
                        }
                        Text(WeatherCondition.formatVisibility(vis, prefs: userPreferencesManager.preferredUnits))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if let minVis = condition.minVisibility24hM, minVis < vis {
                            Text("Low today: \(WeatherCondition.formatVisibility(minVis, prefs: userPreferencesManager.preferredUnits))")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Visibility \(category.label), \(WeatherCondition.formatVisibility(vis, prefs: userPreferencesManager.preferredUnits))")
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
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Suggest an Edit

    private var suggestEditButton: some View {
        Button {
            showingSuggestEdit = true
        } label: {
            HStack {
                Image(systemName: "pencil.line")
                Text("Suggest an Edit")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
        }
        .accessibilityIdentifier(AccessibilityID.SuggestEdit.button)
        .accessibilityLabel("Suggest an edit to \(resort.name) information")
    }

    // MARK: - Data Sources Card

    @ViewBuilder
    private func dataSourcesCard(_ condition: WeatherCondition) -> some View {
        if let details = condition.sourceDetails, details.sourceCount > 0 {
            VStack(alignment: .leading, spacing: 12) {
                // Expandable header
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showDataSources.toggle()
                    }
                } label: {
                    HStack {
                        Image(systemName: "antenna.radiowaves.left.and.right")
                            .foregroundStyle(.blue)
                        Text("Data Sources")
                            .font(.headline)
                            .foregroundStyle(.primary)

                        Spacer()

                        // Confidence badge
                        Text(condition.sourceConfidence.displayName)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(condition.sourceConfidence.color)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(
                                Capsule()
                                    .fill(condition.sourceConfidence.color.opacity(0.15))
                            )

                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .rotationEffect(.degrees(showDataSources ? 90 : 0))
                    }
                }
                .buttonStyle(.plain)

                if showDataSources {
                    VStack(alignment: .leading, spacing: 8) {
                        // Merge method
                        HStack(spacing: 6) {
                            Image(systemName: "gearshape.2")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(formatMergeMethod(details.mergeMethod))
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            Text("\(details.sourceCount) sources")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 1)
                                .background(
                                    Capsule()
                                        .strokeBorder(Color.secondary.opacity(0.3), lineWidth: 0.5)
                                )
                        }

                        Divider()

                        // Per-source details — sort: consensus first, then included, then outlier, then no_data
                        let prefs = userPreferencesManager.preferredUnits
                        let sortedSources = details.sources.sorted { a, b in
                            sourceStatusOrder(a.value.status) < sourceStatusOrder(b.value.status)
                        }
                        ForEach(sortedSources, id: \.key) { sourceName, info in
                            sourceRow(sourceName: sourceName, info: info, prefs: prefs)
                        }
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .cardStyle()
            .accessibilityElement(children: .contain)
            .accessibilityLabel("Data Sources, \(details.sourceCount) sources, confidence \(condition.sourceConfidence.displayName)")
        }
    }

    @ViewBuilder
    private func sourceRow(sourceName: String, info: SourceDetails.SourceInfo, prefs: UnitPreferences) -> some View {
        let isExcluded = info.status == "outlier" || info.status == "no_data"
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 10) {
                // Status icon
                Image(systemName: statusIcon(info.status))
                    .foregroundStyle(statusColor(info.status))
                    .font(.subheadline)

                // Source name
                Text(sourceName)
                    .font(.subheadline)
                    .foregroundStyle(isExcluded ? .secondary : .primary)
                    .lineLimit(1)

                Spacer()

                // Reported value
                if let snowfall = info.snowfall24hCm {
                    Text(WeatherCondition.formatSnow(snowfall, prefs: prefs))
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(isExcluded ? .secondary : .primary)
                        .strikethrough(info.status == "outlier", color: .orange.opacity(0.6))
                } else {
                    Text(info.status == "no_data" ? "N/A" : "No data")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }

                // Status label
                Text(statusLabel(info.status))
                    .font(.caption2)
                    .fontWeight(.medium)
                    .foregroundStyle(statusColor(info.status))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(
                        Capsule()
                            .fill(statusColor(info.status).opacity(0.1))
                    )
            }

            // Reason text — always show for excluded sources
            if let reason = info.reason {
                Text(reason)
                    .font(.caption2)
                    .foregroundStyle(isExcluded ? .orange : .secondary)
                    .padding(.leading, 26)
            }
        }
        .padding(.vertical, 2)
    }

    private func formatMergeMethod(_ method: String) -> String {
        switch method {
        case "outlier_detection": return "Outlier Detection"
        case "weighted_average": return "Weighted Average"
        case "simple_average": return "Simple Average"
        case "single_source": return "Single Source"
        default: return method.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private func sourceStatusOrder(_ status: String) -> Int {
        switch status {
        case "consensus": return 0
        case "included": return 1
        case "outlier": return 2
        case "no_data": return 3
        default: return 4
        }
    }

    private func statusIcon(_ status: String) -> String {
        switch status {
        case "consensus": return "checkmark.circle.fill"
        case "outlier": return "xmark.circle.fill"
        case "included": return "circle.fill"
        case "no_data": return "minus.circle"
        default: return "circle"
        }
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "consensus": return "Consensus"
        case "outlier": return "Excluded"
        case "included": return "Included"
        case "no_data": return "Unavailable"
        default: return status.capitalized
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "consensus": return .green
        case "outlier": return .orange
        case "included": return .blue
        case "no_data": return .gray
        default: return .secondary
        }
    }

    // MARK: - Run Difficulty

    @ViewBuilder
    private var runDifficultySection: some View {
        // Show if we have at least two trail percentages
        let green = resort.greenRunsPct
        let blue = resort.blueRunsPct
        let black = resort.blackRunsPct
        let hasEnoughData = [green != nil, blue != nil, black != nil].filter { $0 }.count >= 2

        if hasEnoughData {
            VStack(alignment: .leading, spacing: 8) {
                Text("Run Difficulty")
                    .font(.headline)

                VStack(spacing: 6) {
                    GeometryReader { geometry in
                        let total = Double(green ?? 0) + Double(blue ?? 0) + Double(black ?? 0)
                        let greenPct = total > 0 ? Double(green ?? 0) / total : 0
                        let bluePct = total > 0 ? Double(blue ?? 0) / total : 0
                        let blackPct = total > 0 ? Double(black ?? 0) / total : 0

                        HStack(spacing: 1) {
                            if greenPct > 0 {
                                Rectangle()
                                    .fill(.green)
                                    .frame(width: geometry.size.width * greenPct)
                            }
                            if bluePct > 0 {
                                Rectangle()
                                    .fill(.blue)
                                    .frame(width: geometry.size.width * bluePct)
                            }
                            if blackPct > 0 {
                                Rectangle()
                                    .fill(.primary)
                                    .frame(width: geometry.size.width * blackPct)
                            }
                        }
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                    .frame(height: 8)

                    HStack(spacing: 12) {
                        if let green = green {
                            Label("\(green)%", systemImage: "circle.fill")
                                .font(.caption2)
                                .foregroundStyle(.green)
                        }
                        if let blue = blue {
                            Label("\(blue)%", systemImage: "square.fill")
                                .font(.caption2)
                                .foregroundStyle(.blue)
                        }
                        if let black = black {
                            Label("\(black)%", systemImage: "diamond.fill")
                                .font(.caption2)
                                .foregroundStyle(.primary)
                        }
                        Spacer()
                    }
                }
            }
            .cardStyle()
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Run difficulty: \(green.map { "\($0)% beginner" } ?? ""), \(blue.map { "\($0)% intermediate" } ?? ""), \(black.map { "\($0)% advanced" } ?? "")")
        }
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
                            Text(point.formattedElevation(prefs: userPreferencesManager.preferredUnits))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        VStack(alignment: .trailing, spacing: 4) {
                            HStack(spacing: 4) {
                                Image(systemName: condition.snowQuality.icon)
                                    .foregroundStyle(condition.snowQuality.color)
                                Text(condition.snowQuality.displayName)
                                    .foregroundStyle(condition.snowQuality.color)
                            }
                            .font(.subheadline)

                            HStack(spacing: 8) {
                                Text(condition.formattedTemperature(userPreferencesManager.preferredUnits))
                                if condition.freshSnowCm > 0 {
                                    HStack(spacing: 2) {
                                        Image(systemName: "snowflake")
                                            .font(.caption2)
                                        Text(WeatherCondition.formatSnowShort(condition.freshSnowCm, prefs: userPreferencesManager.preferredUnits))
                                    }
                                    .foregroundStyle(.cyan)
                                }
                            }
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
            if snowConditionsManager.isLoading {
                ProgressView()
                    .controlSize(.large)
                Text("Loading conditions...")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                Image(systemName: "exclamationmark.triangle")
                    .font(.largeTitle)
                    .foregroundStyle(.orange)

                Text("No Data Available")
                    .font(.headline)

                Text("Weather conditions for this elevation are not currently available.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Button {
                    isRetrying = true
                    Task {
                        await snowConditionsManager.fetchConditionsForResort(resort.id, forceRefresh: true)
                        isRetrying = false
                    }
                } label: {
                    if isRetrying {
                        ProgressView()
                            .controlSize(.small)
                        Text("Retrying...")
                    } else {
                        Label("Retry", systemImage: "arrow.clockwise")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isRetrying)
            }
        }
        .frame(maxWidth: .infinity)
        .cardStyle()
    }
}

// MARK: - Safari Overlay

struct IdentifiableURL: Identifiable {
    let id = UUID()
    let url: URL
}

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        SFSafariViewController(url: url)
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

extension View {
    func safariOverlay(url: Binding<IdentifiableURL?>) -> some View {
        self.sheet(item: url) { identifiableURL in
            SafariView(url: identifiableURL.url)
                .ignoresSafeArea()
        }
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
