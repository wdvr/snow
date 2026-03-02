import SwiftUI

// MARK: - Daily Forecast Summary

/// Summarizes timeline data for a single day from hourly TimelinePoints
struct DailyForecastSummary: Identifiable {
    let id: String // date string yyyy-MM-dd
    let date: Date
    let dayLabel: String // "Now", "Thu", "Fri", etc.
    let minTempC: Double
    let maxTempC: Double
    let totalSnowfallCm: Double
    let weatherDescription: String?
    let snowQuality: SnowQuality?
    let snowScore: Int?
    let explanation: String?
    let isToday: Bool
}

struct FavoritesView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator
    @EnvironmentObject private var notificationHistoryVM: NotificationHistoryViewModel
    @State private var showingNotifications = false
    @State private var resortToRemove: Resort?
    @State private var showingGroupManager = false
    @State private var showingMoveSheet = false
    @State private var resortToMove: Resort?
    @State private var selectedDayIndex: Int = 0
    @State private var timelineData: [String: [DailyForecastSummary]] = [:]
    @State private var isLoadingTimelines = false

    private var favoriteResorts: [Resort] {
        snowConditionsManager.resorts
            .filter { userPreferencesManager.favoriteResorts.contains($0.id) }
            .sorted { resort1, resort2 in
                let q1 = snowConditionsManager.getSnowQuality(for: resort1.id).sortOrder
                let q2 = snowConditionsManager.getSnowQuality(for: resort2.id).sortOrder
                if q1 != q2 { return q1 < q2 }
                return resort1.name < resort2.name
            }
    }

    /// Generate the next 10 days for the date selector
    private var forecastDays: [ForecastDayOption] {
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        let dayFormatter = DateFormatter()
        dayFormatter.dateFormat = "EEE"

        return (0..<10).map { offset in
            let date = calendar.date(byAdding: .day, value: offset, to: today)!
            let label = offset == 0 ? "Now" : dayFormatter.string(from: date)
            return ForecastDayOption(index: offset, date: date, label: label)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if favoriteResorts.isEmpty {
                    emptyStateView
                } else {
                    favoritesList
                }
            }
            .navigationTitle("Favorites")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    if !favoriteResorts.isEmpty {
                        Button {
                            showingGroupManager = true
                        } label: {
                            Label("Groups", systemImage: "folder")
                        }
                    }
                }
                if favoriteResorts.count >= 2 {
                    ToolbarItem(placement: .topBarTrailing) {
                        NavigationLink {
                            ResortComparisonView(initialResorts: favoriteResorts)
                                .environmentObject(snowConditionsManager)
                                .environmentObject(userPreferencesManager)
                        } label: {
                            Label("Compare", systemImage: "rectangle.split.3x1")
                        }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    NotificationBellButton(viewModel: notificationHistoryVM, showingSheet: $showingNotifications)
                }
            }
            .sheet(isPresented: $showingNotifications) {
                NotificationHistoryView(viewModel: notificationHistoryVM)
            }
            .onAppear {
                AnalyticsService.shared.trackScreen("Favorites", screenClass: "FavoritesView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("Favorites")
            }
            .refreshable {
                AnalyticsService.shared.trackPullToRefresh(screen: "Favorites")
                await snowConditionsManager.fetchConditionsForFavorites()
                await fetchTimelines()
            }
            .task {
                await snowConditionsManager.fetchConditionsForFavorites()
                await fetchTimelines()
            }
            .navigationDestination(for: Resort.self) { resort in
                ResortDetailView(resort: resort)
            }
            .sheet(isPresented: $showingGroupManager) {
                FavoriteGroupsManagerView()
                    .environmentObject(userPreferencesManager)
            }
            .sheet(isPresented: $showingMoveSheet) {
                if let resort = resortToMove {
                    MoveToGroupSheet(resort: resort)
                        .environmentObject(userPreferencesManager)
                }
            }
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Image(systemName: "heart.slash")
                .font(.system(size: 60))
                .foregroundStyle(.gray)

            Text("No Favorites Yet")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Tap the heart icon on any resort to add it to your favorites for quick access.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            NavigationLink(destination: ResortListView()) {
                Label("Browse Resorts", systemImage: "mountain.2")
                    .font(.headline)
                    .padding()
                    .background(Color.blue)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }

    private var favoritesList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                // Conditions summary card
                if favoriteResorts.count >= 2 {
                    FavoritesSummaryCard(
                        resorts: favoriteResorts,
                        snowConditionsManager: snowConditionsManager,
                        userPreferencesManager: userPreferencesManager
                    )
                }

                // Date selector
                dateSelector

                // Show grouped sections if any groups exist
                if !userPreferencesManager.favoriteGroups.isEmpty {
                    // Grouped resorts
                    ForEach(userPreferencesManager.favoriteGroups) { group in
                        let groupResorts = favoriteResorts.filter { group.resortIds.contains($0.id) }
                        if !groupResorts.isEmpty {
                            sectionHeader(group.name)
                            resortCards(groupResorts)
                        }
                    }

                    // Ungrouped resorts
                    let ungroupedIds = userPreferencesManager.ungroupedFavoriteResortIds()
                    let ungrouped = favoriteResorts.filter { ungroupedIds.contains($0.id) }
                    if !ungrouped.isEmpty {
                        sectionHeader("Other")
                        resortCards(ungrouped)
                    }
                } else {
                    // No groups - flat list
                    resortCards(favoriteResorts)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 16)
        }
        .alert("Remove Favorite?", isPresented: Binding(
            get: { resortToRemove != nil },
            set: { if !$0 { resortToRemove = nil } }
        )) {
            Button("Cancel", role: .cancel) { resortToRemove = nil }
            Button("Remove", role: .destructive) {
                if let resort = resortToRemove {
                    userPreferencesManager.toggleFavorite(resortId: resort.id)
                }
                resortToRemove = nil
            }
        } message: {
            if let resort = resortToRemove {
                Text("Remove \(resort.name) from your favorites?")
            }
        }
    }

    // MARK: - Date Selector

    private var dateSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(forecastDays) { day in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedDayIndex = day.index
                        }
                    } label: {
                        VStack(spacing: 4) {
                            Text(day.label)
                                .font(.caption.weight(selectedDayIndex == day.index ? .bold : .medium))

                            if day.index > 0 {
                                Text(day.shortDate)
                                    .font(.caption2)
                            }
                        }
                        .frame(minWidth: 44, minHeight: 40)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            Capsule()
                                .fill(selectedDayIndex == day.index ? Color.accentColor : Color.gray.opacity(0.15))
                        )
                        .foregroundStyle(selectedDayIndex == day.index ? .white : .primary)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .sensoryFeedback(.selection, trigger: selectedDayIndex)
                }
            }
            .padding(.vertical, 4)
        }
    }

    // MARK: - Section Header

    private func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            Spacer()
        }
        .padding(.top, 8)
    }

    // MARK: - Resort Cards

    private func resortCards(_ resorts: [Resort]) -> some View {
        ForEach(resorts) { resort in
            NavigationLink(value: resort) {
                FavoriteResortCard(
                    resort: resort,
                    selectedDayIndex: selectedDayIndex,
                    dailyForecast: forecastForResort(resort.id)
                )
            }
            .buttonStyle(PlainButtonStyle())
            .accessibilityLabel("\(resort.name), \(snowConditionsManager.getSnowQuality(for: resort.id).displayName)")
            .contextMenu {
                Button {
                    navigationCoordinator.showOnMap(resort)
                } label: {
                    Label("Show on Map", systemImage: "map.fill")
                }

                if !userPreferencesManager.favoriteGroups.isEmpty {
                    Button {
                        resortToMove = resort
                        showingMoveSheet = true
                    } label: {
                        Label("Move to Group", systemImage: "folder")
                    }
                }

                Button(role: .destructive) {
                    resortToRemove = resort
                } label: {
                    Label("Remove Favorite", systemImage: "heart.slash")
                }
            }
        }
    }

    // MARK: - Timeline Fetching

    private func forecastForResort(_ resortId: String) -> DailyForecastSummary? {
        guard selectedDayIndex > 0,
              let days = timelineData[resortId],
              selectedDayIndex < days.count else {
            return nil
        }
        return days[selectedDayIndex]
    }

    private func fetchTimelines() async {
        let favoriteIds = favoriteResorts.map { $0.id }
        guard !favoriteIds.isEmpty else { return }

        isLoadingTimelines = true
        defer { isLoadingTimelines = false }

        let apiClient = APIClient.shared
        let cacheService = CacheService.shared

        // Check cache on the main actor first, then only fetch stale/missing ones
        var cachedResponses: [String: TimelineResponse] = [:]
        var idsToFetch: [String] = []
        for resortId in favoriteIds {
            if let cached = cacheService.getCachedTimeline(for: resortId), !cached.isStale {
                cachedResponses[resortId] = cached.data
            } else {
                idsToFetch.append(resortId)
            }
        }

        // Fetch missing/stale timelines in parallel
        let fetched: [(String, TimelineResponse?)] = await withTaskGroup(
            of: (String, TimelineResponse?).self,
            returning: [(String, TimelineResponse?)].self
        ) { group in
            for resortId in idsToFetch {
                group.addTask {
                    do {
                        let timeline = try await apiClient.getTimeline(for: resortId)
                        return (resortId, timeline)
                    } catch {
                        return (resortId, nil)
                    }
                }
            }
            var results: [(String, TimelineResponse?)] = []
            for await result in group {
                results.append(result)
            }
            return results
        }

        // Cache fetched results on main actor and build summaries
        var results: [String: [DailyForecastSummary]] = [:]
        for (resortId, response) in cachedResponses {
            results[resortId] = summarizeTimeline(response)
        }
        for (resortId, response) in fetched {
            if let response {
                cacheService.cacheTimeline(response, for: resortId)
                results[resortId] = summarizeTimeline(response)
            }
        }

        timelineData = results
    }

    /// Summarize hourly timeline points into daily summaries
    private func summarizeTimeline(_ response: TimelineResponse) -> [DailyForecastSummary] {
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        let dateParser = DateFormatter()
        dateParser.dateFormat = "yyyy-MM-dd"
        let dayFormatter = DateFormatter()
        dayFormatter.dateFormat = "EEE"

        // Group timeline points by date
        var pointsByDate: [String: [TimelinePoint]] = [:]
        for point in response.timeline {
            pointsByDate[point.date, default: []].append(point)
        }

        // Build daily summaries for the next 10 days
        return (0..<10).compactMap { offset -> DailyForecastSummary? in
            let targetDate = calendar.date(byAdding: .day, value: offset, to: today)!
            let dateStr = dateParser.string(from: targetDate)
            guard let points = pointsByDate[dateStr], !points.isEmpty else { return nil }

            let label = offset == 0 ? "Now" : dayFormatter.string(from: targetDate)
            let minTemp = points.map(\.temperatureC).min() ?? 0
            let maxTemp = points.map(\.temperatureC).max() ?? 0
            let totalSnow = points.map(\.snowfallCm).reduce(0, +)

            // Most common weather description
            let descriptions = points.compactMap(\.weatherDescription)
            let descCounts = Dictionary(grouping: descriptions, by: { $0 }).mapValues(\.count)
            let topDescription = descCounts.max(by: { $0.value < $1.value })?.key

            // Use the midday point for quality if available, else the latest
            let representativePoint = points.first { $0.hour >= 10 && $0.hour <= 14 } ?? points.last
            let quality = representativePoint?.snowQuality
            let score = representativePoint?.snowScore
            let explanation = representativePoint?.explanation

            return DailyForecastSummary(
                id: dateStr,
                date: targetDate,
                dayLabel: label,
                minTempC: minTemp,
                maxTempC: maxTemp,
                totalSnowfallCm: totalSnow,
                weatherDescription: topDescription,
                snowQuality: quality,
                snowScore: score,
                explanation: explanation,
                isToday: offset == 0
            )
        }
    }
}

// MARK: - Forecast Day Option

private struct ForecastDayOption: Identifiable {
    let index: Int
    let date: Date
    let label: String

    var id: Int { index }

    private static let shortDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "d MMM"
        return f
    }()

    var shortDate: String {
        Self.shortDateFormatter.string(from: date)
    }
}

// MARK: - Favorite Resort Card

struct FavoriteResortCard: View {
    let resort: Resort
    let selectedDayIndex: Int
    let dailyForecast: DailyForecastSummary?
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    private var latestCondition: WeatherCondition? {
        snowConditionsManager.getLatestCondition(for: resort.id)
    }

    private var snowQualitySummary: SnowQualitySummaryLight? {
        snowConditionsManager.snowQualitySummaries[resort.id]
    }

    private var displayQuality: SnowQuality {
        if selectedDayIndex > 0, let forecast = dailyForecast, let quality = forecast.snowQuality {
            return quality
        }
        return snowConditionsManager.getSnowQuality(for: resort.id)
    }

    private var snowScore: Int? {
        if selectedDayIndex > 0, let forecast = dailyForecast {
            return forecast.snowScore
        }
        return snowConditionsManager.getSnowScore(for: resort.id)
    }

    /// Whether showing forecast data vs. current conditions
    private var isShowingForecast: Bool {
        selectedDayIndex > 0 && dailyForecast != nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Header row: Logo + name + pass badges + quality badge
            HStack(alignment: .top, spacing: 10) {
                ResortLogoView(resort: resort, size: 40)

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(resort.name)
                            .font(.headline)
                            .foregroundStyle(.primary)
                            .lineLimit(1)

                        if resort.epicPass != nil {
                            PassBadge(passName: "Epic", color: .indigo)
                        }
                        if resort.ikonPass != nil {
                            PassBadge(passName: "Ikon", color: .orange)
                        }
                        if resort.indyPass != nil {
                            PassBadge(passName: "Indy", color: .green)
                        }
                    }

                    Text(resort.displayLocation)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                // Quality badge
                if displayQuality != .unknown {
                    QualityBadge(quality: displayQuality, snowScore: snowScore)
                } else if snowConditionsManager.isLoadingSnowQuality {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }

            // Stats row
            HStack(spacing: 12) {
                if isShowingForecast, let forecast = dailyForecast {
                    // Forecast: show min/max temperature range
                    StatItem(
                        icon: "thermometer.medium",
                        value: forecastTempRange(min: forecast.minTempC, max: forecast.maxTempC),
                        color: tempColor((forecast.minTempC + forecast.maxTempC) / 2)
                    )

                    // Forecast: total snowfall for the day
                    StatItem(
                        icon: "snowflake",
                        value: formatSnow(forecast.totalSnowfallCm),
                        color: .cyan
                    )

                    // Forecast: weather description
                    if let weather = forecast.weatherDescription {
                        StatItem(
                            icon: "cloud",
                            value: weather,
                            color: .secondary
                        )
                    }
                } else {
                    // Current conditions
                    if let condition = latestCondition {
                        StatItem(
                            icon: "thermometer.medium",
                            value: condition.formattedTemperature(userPreferencesManager.preferredUnits),
                            color: tempColor(condition.currentTempCelsius)
                        )
                    } else if let summary = snowQualitySummary,
                              let temp = summary.formattedTemperature(userPreferencesManager.preferredUnits) {
                        StatItem(
                            icon: "thermometer.medium",
                            value: temp,
                            color: summary.temperatureC.map { tempColor($0) } ?? .secondary
                        )
                    }

                    if let condition = latestCondition {
                        StatItem(
                            icon: "snowflake",
                            value: condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits),
                            color: .cyan
                        )
                    } else if let summary = snowQualitySummary,
                              let snow = summary.formattedFreshSnow(userPreferencesManager.preferredUnits) {
                        StatItem(
                            icon: "snowflake",
                            value: snow,
                            color: .cyan
                        )
                    }

                    // Predicted snow (only for current/today view)
                    if let condition = latestCondition,
                       let predicted = condition.predictedSnow48hCm, predicted >= 5 {
                        StatItem(
                            icon: "cloud.snow.fill",
                            value: "+\(WeatherCondition.formatSnowShort(predicted, prefs: userPreferencesManager.preferredUnits))",
                            color: .purple
                        )
                    } else if let summary = snowQualitySummary,
                              let predicted = summary.predictedSnow48hCm, predicted >= 5 {
                        StatItem(
                            icon: "cloud.snow.fill",
                            value: "+\(WeatherCondition.formatSnowShort(predicted, prefs: userPreferencesManager.preferredUnits))",
                            color: .purple
                        )
                    }
                }

                Spacer()
            }

            // Quality explanation
            if isShowingForecast, let forecast = dailyForecast, let explanation = forecast.explanation {
                Text(explanation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            } else if let explanation = snowConditionsManager.getExplanation(for: resort.id) {
                Text(explanation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            }
        }
        .cardStyle()
    }

    // MARK: - Helpers

    private func forecastTempRange(min: Double, max: Double) -> String {
        switch userPreferencesManager.preferredUnits.temperature {
        case .celsius:
            return "\(Int(min))°/\(Int(max))°C"
        case .fahrenheit:
            let minF = min * 9.0 / 5.0 + 32.0
            let maxF = max * 9.0 / 5.0 + 32.0
            return "\(Int(minF))°/\(Int(maxF))°F"
        }
    }

    private func formatSnow(_ cm: Double) -> String {
        if cm < 0.1 {
            return "No snow"
        }
        return WeatherCondition.formatSnowShort(cm, prefs: userPreferencesManager.preferredUnits)
    }

    private func tempColor(_ celsius: Double) -> Color {
        if celsius < -10 {
            return .blue
        } else if celsius < 0 {
            return .cyan
        } else if celsius < 5 {
            return .yellow
        } else {
            return .orange
        }
    }
}

// MARK: - Favorite Groups Manager

struct FavoriteGroupsManagerView: View {
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss
    @State private var newGroupName = ""
    @State private var editingGroup: FavoriteGroup?
    @State private var editName = ""

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        TextField("New group name", text: $newGroupName)
                            .textInputAutocapitalization(.words)
                        Button {
                            guard !newGroupName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                            userPreferencesManager.createGroup(name: newGroupName.trimmingCharacters(in: .whitespaces))
                            newGroupName = ""
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .foregroundStyle(.blue)
                        }
                        .disabled(newGroupName.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                } header: {
                    Text("Create Group")
                }

                if !userPreferencesManager.favoriteGroups.isEmpty {
                    Section {
                        ForEach(userPreferencesManager.favoriteGroups) { group in
                            HStack {
                                Image(systemName: "folder.fill")
                                    .foregroundStyle(.blue)
                                VStack(alignment: .leading) {
                                    Text(group.name)
                                        .font(.body)
                                    Text("\(group.resortIds.count) resorts")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    userPreferencesManager.deleteGroup(id: group.id)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                                Button {
                                    editingGroup = group
                                    editName = group.name
                                } label: {
                                    Label("Rename", systemImage: "pencil")
                                }
                                .tint(.orange)
                            }
                        }
                        .onMove { from, to in
                            userPreferencesManager.favoriteGroups.move(fromOffsets: from, toOffset: to)
                            userPreferencesManager.saveFavoriteGroups()
                        }
                    } header: {
                        Text("Your Groups")
                    }
                }
            }
            .navigationTitle("Manage Groups")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .topBarLeading) {
                    EditButton()
                }
            }
            .alert("Rename Group", isPresented: Binding(
                get: { editingGroup != nil },
                set: { if !$0 { editingGroup = nil } }
            )) {
                TextField("Group name", text: $editName)
                Button("Cancel", role: .cancel) { editingGroup = nil }
                Button("Save") {
                    if let group = editingGroup {
                        userPreferencesManager.renameGroup(id: group.id, name: editName)
                    }
                    editingGroup = nil
                }
            }
        }
    }
}

// MARK: - Move to Group Sheet

struct MoveToGroupSheet: View {
    let resort: Resort
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss

    private var currentGroup: FavoriteGroup? {
        userPreferencesManager.groupForResort(resort.id)
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button {
                        if let group = currentGroup {
                            userPreferencesManager.removeResortFromGroup(resortId: resort.id, groupId: group.id)
                        }
                        dismiss()
                    } label: {
                        HStack {
                            Label("No Group", systemImage: "tray")
                            Spacer()
                            if currentGroup == nil {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(.blue)
                            }
                        }
                    }
                    .foregroundStyle(.primary)

                    ForEach(userPreferencesManager.favoriteGroups) { group in
                        Button {
                            userPreferencesManager.addResortToGroup(resortId: resort.id, groupId: group.id)
                            dismiss()
                        } label: {
                            HStack {
                                Label(group.name, systemImage: "folder.fill")
                                Spacer()
                                if currentGroup?.id == group.id {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.blue)
                                }
                            }
                        }
                        .foregroundStyle(.primary)
                    }
                } header: {
                    Text("Move \"\(resort.name)\" to:")
                }
            }
            .navigationTitle("Move to Group")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Favorites Summary Card

struct FavoritesSummaryCard: View {
    let resorts: [Resort]
    let snowConditionsManager: SnowConditionsManager
    let userPreferencesManager: UserPreferencesManager

    private var qualityCounts: [(quality: SnowQuality, count: Int)] {
        var counts: [SnowQuality: Int] = [:]
        for resort in resorts {
            let quality = snowConditionsManager.getSnowQuality(for: resort.id)
            if quality != .unknown {
                counts[quality, default: 0] += 1
            }
        }
        return counts.sorted { $0.key.sortOrder < $1.key.sortOrder }
            .map { (quality: $0.key, count: $0.value) }
    }

    private var bestResort: (resort: Resort, score: Int)? {
        resorts.compactMap { resort -> (Resort, Int)? in
            guard let score = snowConditionsManager.getSnowScore(for: resort.id) else { return nil }
            return (resort, score)
        }
        .max { $0.1 < $1.1 }
    }

    private var averageScore: Int? {
        let scores = resorts.compactMap { snowConditionsManager.getSnowScore(for: $0.id) }
        guard !scores.isEmpty else { return nil }
        return scores.reduce(0, +) / scores.count
    }

    private var totalFreshSnow: Double {
        resorts.compactMap { snowConditionsManager.snowQualitySummaries[$0.id]?.snowfallFreshCm }
            .reduce(0, +)
    }

    private var stormsIncoming: [(resort: Resort, cm: Double)] {
        resorts.compactMap { resort -> (Resort, Double)? in
            guard let predicted = snowConditionsManager.snowQualitySummaries[resort.id]?.predictedSnow48hCm,
                  predicted >= 10 else { return nil }
            return (resort, predicted)
        }
        .sorted { $0.1 > $1.1 }
    }

    var body: some View {
        VStack(spacing: 12) {
            // Header row
            HStack {
                Label("Conditions Overview", systemImage: "chart.bar.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.primary)
                Spacer()
            }

            // Best resort highlight
            if let best = bestResort {
                let quality = snowConditionsManager.getSnowQuality(for: best.resort.id)
                HStack(spacing: 10) {
                    ZStack {
                        Circle()
                            .fill(quality.color.opacity(0.15))
                            .frame(width: 36, height: 36)
                        Text("\(best.score)")
                            .font(.caption.weight(.bold))
                            .fontDesign(.rounded)
                            .foregroundStyle(quality.color)
                    }

                    VStack(alignment: .leading, spacing: 1) {
                        Text("Best conditions")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(best.resort.name)
                            .font(.caption.weight(.medium))
                    }

                    Spacer()

                    if let avg = averageScore {
                        VStack(alignment: .trailing, spacing: 1) {
                            Text("Avg score")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("\(avg)")
                                .font(.caption.weight(.medium))
                                .fontDesign(.rounded)
                        }
                    }
                }
            }

            // Quality distribution bar
            if !qualityCounts.isEmpty {
                let total = qualityCounts.reduce(0) { $0 + $1.count }
                VStack(spacing: 4) {
                    GeometryReader { geometry in
                        HStack(spacing: 1) {
                            ForEach(qualityCounts, id: \.quality) { item in
                                let width = max(8, geometry.size.width * CGFloat(item.count) / CGFloat(total))
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(item.quality.color)
                                    .frame(width: width, height: 8)
                            }
                        }
                    }
                    .frame(height: 8)

                    // Legend
                    HStack(spacing: 8) {
                        ForEach(qualityCounts, id: \.quality) { item in
                            HStack(spacing: 3) {
                                Circle()
                                    .fill(item.quality.color)
                                    .frame(width: 6, height: 6)
                                Text("\(item.count) \(item.quality.displayName)")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                }
            }

            // Storms incoming
            if !stormsIncoming.isEmpty {
                Divider()

                VStack(alignment: .leading, spacing: 6) {
                    Label(
                        stormsIncoming.count == 1 ? "Storm incoming" : "\(stormsIncoming.count) storms incoming",
                        systemImage: "cloud.snow.fill"
                    )
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.cyan)

                    ForEach(stormsIncoming.prefix(3), id: \.resort.id) { item in
                        HStack(spacing: 6) {
                            Text(item.resort.name)
                                .font(.caption)
                            Spacer()
                            ForecastBadge(hours: 48, cm: item.cm, prefs: userPreferencesManager.preferredUnits)
                        }
                    }
                }
            }
        }
        .cardStyle()
    }
}

#Preview("Favorites") {
    FavoritesView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
        .environmentObject(NavigationCoordinator())
}
