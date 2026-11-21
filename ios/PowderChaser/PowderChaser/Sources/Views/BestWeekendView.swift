import SwiftUI
import CoreLocation
import os.log

private let weekendLog = Logger(subsystem: "com.snowtracker.app", category: "BestWeekend")

// MARK: - Scope

/// Which resorts to rank: favorites first, the home region, or everything.
enum WeekendScope: Hashable {
    case favorites
    case region(SkiRegion)
    case global

    var label: String {
        switch self {
        case .favorites: return "Favorites"
        case .region(let region): return region.displayName
        case .global: return "Global"
        }
    }

    var icon: String {
        switch self {
        case .favorites: return "heart.fill"
        case .region(let region): return region.icon
        case .global: return "globe"
        }
    }
}

/// Pass products the backend understands, in display order.
enum WeekendPassProduct: String, CaseIterable, Identifiable {
    case ikon
    case epic
    case mountainCollective = "mountain_collective"
    case indy

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .ikon: return "Ikon Pass"
        case .epic: return "Epic Pass"
        case .mountainCollective: return "Mountain Collective"
        case .indy: return "Indy Pass"
        }
    }
}

// MARK: - Manager

@MainActor
final class BestWeekendManager: ObservableObject {
    @Published var response: WeekendRankingsResponse?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?

    private let apiClient = APIClient.shared

    func load(
        scope: WeekendScope,
        favoriteIds: [String],
        start: Date?,
        end: Date?,
        passes: [String]
    ) async {
        isLoading = true
        errorMessage = nil

        var resortIds: [String]?
        var region: String?
        switch scope {
        case .favorites:
            resortIds = favoriteIds
        case .region(let skiRegion):
            region = skiRegion.rawValue
        case .global:
            break
        }

        do {
            response = try await apiClient.getWeekendRankings(
                resortIds: resortIds,
                region: region,
                start: start.map(WeekendDateFormat.string),
                end: end.map(WeekendDateFormat.string),
                passes: passes
            )
            lastUpdated = Date()
        } catch {
            errorMessage = error.localizedDescription
            weekendLog.error("Failed to load weekend rankings: \(error)")
        }

        isLoading = false
    }
}

// MARK: - Best This Weekend

/// "I want to ski this weekend, where is predicted best?" Ranked list for the
/// coming Fri-Sun (or a chosen range), favorites/home region first.
struct BestWeekendContent: View {
    @StateObject private var manager = BestWeekendManager()
    @StateObject private var locationManager = LocationManager.shared
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator

    @AppStorage("weekendPasses") private var passesRaw: String = ""
    @State private var scope: WeekendScope?
    @State private var useCustomRange = false
    @State private var customStart = Date()
    @State private var customEnd = Calendar.current.date(byAdding: .day, value: 2, to: Date()) ?? Date()
    @State private var showingDatePicker = false

    private static let maxRangeDays = 10
    private static let maxDaysAhead = 15

    private var favoriteIds: [String] {
        userPreferencesManager.favoriteResorts.sorted()
    }

    private var selectedPasses: Set<String> {
        Set(passesRaw.split(separator: ",").map { String($0) }.filter { !$0.isEmpty })
    }

    private var favoriteResorts: [Resort] {
        let ids = userPreferencesManager.favoriteResorts
        return snowConditionsManager.resorts
            .filter { ids.contains($0.id) }
            .sorted { $0.name < $1.name }
    }

    /// Home region: most common region among favorites, else the region of the
    /// nearest resort to the user, else nil.
    private var homeRegion: SkiRegion? {
        let favorites = favoriteResorts
        if !favorites.isEmpty {
            let counts = Dictionary(grouping: favorites, by: { $0.inferredRegion }).mapValues(\.count)
            return counts.max { $0.value < $1.value }?.key
        }
        guard let location = locationManager.userLocation else { return nil }
        let nearest = snowConditionsManager.resorts.min { lhs, rhs in
            distance(from: location, to: lhs) < distance(from: location, to: rhs)
        }
        return nearest?.inferredRegion
    }

    private var defaultScope: WeekendScope {
        if !favoriteIds.isEmpty { return .favorites }
        if let homeRegion { return .region(homeRegion) }
        return .global
    }

    private var effectiveScope: WeekendScope { scope ?? defaultScope }

    private var availableScopes: [WeekendScope] {
        var scopes: [WeekendScope] = []
        if !favoriteIds.isEmpty { scopes.append(.favorites) }
        if let homeRegion { scopes.append(.region(homeRegion)) }
        scopes.append(.global)
        return scopes
    }

    var body: some View {
        Group {
            if manager.isLoading && manager.response == nil {
                VStack(spacing: 16) {
                    ProgressView()
                    Text("Ranking resorts for the weekend...")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let response = manager.response, !response.rankings.isEmpty {
                rankingsList(response)
            } else {
                ContentUnavailableView {
                    Label("No Ranking Yet", systemImage: "calendar.badge.exclamationmark")
                } description: {
                    Text(manager.errorMessage ?? "No resorts to rank for this window. Try another scope or date range.")
                } actions: {
                    Button("Refresh") {
                        Task { await reload() }
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
        }
        .refreshable {
            AnalyticsService.shared.trackPullToRefresh(screen: "BestWeekend")
            await reload()
        }
        .task {
            if manager.response == nil {
                await reload()
            }
        }
        .sheet(isPresented: $showingDatePicker) {
            dateRangeSheet
        }
    }

    // MARK: - List

    private func rankingsList(_ response: WeekendRankingsResponse) -> some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                controls(window: response.window)

                ForEach(response.rankings) { ranking in
                    if let resort = resort(for: ranking.resortId) {
                        NavigationLink(value: resort) {
                            WeekendRankingCard(ranking: ranking)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .contextMenu {
                            Button {
                                navigationCoordinator.showOnMap(resort)
                            } label: {
                                Label("Show on Map", systemImage: "map.fill")
                            }
                        }
                    } else {
                        WeekendRankingCard(ranking: ranking)
                    }
                }

                Text("Ranked by forecast snow in the window (35%), last 7 days (25%), base depth (20%) and terrain open (20%). Days you can't ski lower the score; passholder-only and closed resorts are listed last.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            }
            .padding()
        }
    }

    private func controls(window: WeekendWindow) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(window.isDefaultWeekend ? "This weekend" : "Your dates")
                        .font(.headline)
                    Text(window.displayRange)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if manager.isLoading {
                    ProgressView()
                }
            }

            HStack(spacing: 8) {
                Menu {
                    ForEach(availableScopes, id: \.self) { option in
                        Button {
                            scope = option
                            AnalyticsService.shared.trackFilterApplied(filterType: "weekend_scope", filterValue: option.label)
                            Task { await reload() }
                        } label: {
                            Label(option.label, systemImage: option.icon)
                        }
                    }
                } label: {
                    chip(effectiveScope.label, icon: effectiveScope.icon)
                }

                Menu {
                    Button {
                        useCustomRange = false
                        Task { await reload() }
                    } label: {
                        Label("This weekend (Fri–Sun)", systemImage: useCustomRange ? "calendar" : "checkmark")
                    }
                    Button {
                        showingDatePicker = true
                    } label: {
                        Label("Choose dates…", systemImage: useCustomRange ? "checkmark" : "calendar.badge.plus")
                    }
                } label: {
                    chip(useCustomRange ? "Custom dates" : "Fri–Sun", icon: "calendar")
                }

                Menu {
                    Section("Pass products") {
                        ForEach(WeekendPassProduct.allCases) { pass in
                            Button {
                                togglePass(pass.rawValue)
                            } label: {
                                Label(pass.displayName, systemImage: selectedPasses.contains(pass.rawValue) ? "checkmark.circle.fill" : "circle")
                            }
                        }
                    }
                    if !favoriteResorts.isEmpty {
                        Section("Season pass at") {
                            ForEach(favoriteResorts) { resort in
                                Button {
                                    togglePass(resort.id)
                                } label: {
                                    Label(resort.name, systemImage: selectedPasses.contains(resort.id) ? "checkmark.circle.fill" : "circle")
                                }
                            }
                        }
                    }
                } label: {
                    chip(selectedPasses.isEmpty ? "My passes" : "\(selectedPasses.count) pass\(selectedPasses.count == 1 ? "" : "es")", icon: "ticket")
                }

                Spacer()
            }
        }
    }

    private func chip(_ text: String, icon: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
            Text(text)
                .lineLimit(1)
            Image(systemName: "chevron.down")
                .font(.caption2)
        }
        .font(.caption.weight(.medium))
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color(.tertiarySystemFill))
        .clipShape(Capsule())
    }

    // MARK: - Date range

    private var dateRangeSheet: some View {
        let today = Calendar.current.startOfDay(for: Date())
        let lastDay = Calendar.current.date(byAdding: .day, value: Self.maxDaysAhead, to: today) ?? today
        return NavigationStack {
            Form {
                DatePicker("From", selection: $customStart, in: today...lastDay, displayedComponents: .date)
                DatePicker("To", selection: $customEnd, in: customStart...lastDay, displayedComponents: .date)
                Text("Up to \(Self.maxRangeDays) days, within the \(Self.maxDaysAhead)-day forecast.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .navigationTitle("Ski dates")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { showingDatePicker = false }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Rank") {
                        clampCustomRange()
                        useCustomRange = true
                        showingDatePicker = false
                        AnalyticsService.shared.trackFilterApplied(filterType: "weekend_range", filterValue: "custom")
                        Task { await reload() }
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func clampCustomRange() {
        let calendar = Calendar.current
        let start = calendar.startOfDay(for: customStart)
        var end = calendar.startOfDay(for: customEnd)
        if end < start {
            end = start
        }
        if let maxEnd = calendar.date(byAdding: .day, value: Self.maxRangeDays - 1, to: start), end > maxEnd {
            end = maxEnd
        }
        customStart = start
        customEnd = end
    }

    // MARK: - Helpers

    private func reload() async {
        await manager.load(
            scope: effectiveScope,
            favoriteIds: favoriteIds,
            start: useCustomRange ? customStart : nil,
            end: useCustomRange ? customEnd : nil,
            passes: selectedPasses.sorted()
        )
    }

    private func togglePass(_ pass: String) {
        var passes = selectedPasses
        if passes.contains(pass) {
            passes.remove(pass)
        } else {
            passes.insert(pass)
        }
        passesRaw = passes.sorted().joined(separator: ",")
        AnalyticsService.shared.trackFilterApplied(filterType: "weekend_passes", filterValue: passesRaw)
        Task { await reload() }
    }

    private func resort(for id: String) -> Resort? {
        snowConditionsManager.resorts.first { $0.id == id }
    }

    private func distance(from location: CLLocation, to resort: Resort) -> CLLocationDistance {
        guard let coordinate = resort.elevationPoints.first?.coordinate else {
            return .greatestFiniteMagnitude
        }
        return location.distance(from: CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude))
    }
}

// MARK: - Card

struct WeekendRankingCard: View {
    let ranking: WeekendRanking
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                Text("\(ranking.rank)")
                    .font(.headline.weight(.bold))
                    .fontDesign(.rounded)
                    .frame(width: 32, height: 32)
                    .background(rankColor.opacity(0.15))
                    .foregroundStyle(rankColor)
                    .clipShape(Circle())
                    .accessibilityLabel("Rank \(ranking.rank)")

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(ranking.name)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        if ranking.passes.contains("epic") {
                            PassBadge(passName: "Epic", color: .indigo)
                        }
                        if ranking.passes.contains("ikon") {
                            PassBadge(passName: "Ikon", color: .orange)
                        }
                        if ranking.passes.contains("indy") {
                            PassBadge(passName: "Indy", color: .green)
                        }
                    }
                    if let bestDayText = ranking.bestDayText {
                        Text(bestDayText)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.blue)
                    } else if ranking.isPassholderOnly {
                        Text("Passholders only")
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.orange)
                    } else if ranking.isInaccessible {
                        Text("Closed for these dates")
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                if let score = ranking.score {
                    VStack(spacing: 0) {
                        Text("\(score)")
                            .font(.title3.weight(.bold))
                            .fontDesign(.rounded)
                        Text("score")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Weekend score \(score) out of 100")
                }
            }

            // The deciding numbers
            LazyVGrid(columns: [GridItem(.flexible(), alignment: .leading), GridItem(.flexible(), alignment: .leading)], spacing: 6) {
                StatItem(
                    icon: "cloud.snow.fill",
                    value: ranking.forecastWindowCm.map { "+\(formatSnow($0)) forecast" } ?? "No forecast",
                    color: .purple
                )
                StatItem(
                    icon: "snowflake",
                    value: ranking.snowfall7dCm.map { "\(formatSnow($0)) last 7d" } ?? "7d unknown",
                    color: .cyan
                )
                StatItem(
                    icon: "ruler",
                    value: ranking.baseDepthCm.map { "\(formatSnow($0)) base" } ?? "Base unknown",
                    color: .blue
                )
                StatItem(
                    icon: "figure.skiing.downhill",
                    value: ranking.terrainText ?? "Terrain unknown",
                    color: .green
                )
            }

            if ranking.days.count > 1 {
                HStack(spacing: 6) {
                    ForEach(ranking.days) { day in
                        dayChip(day)
                    }
                }
            }

            ForEach(ranking.flags, id: \.self) { flag in
                Label(flag, systemImage: flagIcon(flag))
                    .font(.caption)
                    .foregroundStyle(flag.hasPrefix("No ") ? Color.secondary : Color.orange)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(radius: 2)
        .opacity(ranking.isInaccessible ? 0.7 : 1.0)
        .accessibilityElement(children: .contain)
    }

    private var rankColor: Color {
        if ranking.isInaccessible { return .gray }
        switch ranking.rank {
        case 1: return .yellow
        case 2: return .blue
        case 3: return .orange
        default: return .secondary
        }
    }

    private func dayChip(_ day: WeekendDay) -> some View {
        VStack(spacing: 2) {
            Text(day.weekday)
                .font(.caption2.weight(.semibold))
            switch day.access {
            case .open, .unknown:
                Text(day.forecastSnowCm.map { formatSnow($0) } ?? "–")
                    .font(.caption2)
            case .passholderOnly:
                Image(systemName: "lock.fill")
                    .font(.caption2)
            case .closed:
                Image(systemName: "xmark")
                    .font(.caption2)
            }
        }
        .frame(minWidth: 44)
        .padding(.vertical, 4)
        .background(dayColor(day).opacity(0.15))
        .foregroundStyle(dayColor(day))
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(dayAccessibilityLabel(day))
    }

    private func dayColor(_ day: WeekendDay) -> Color {
        switch day.access {
        case .open, .unknown:
            return day.date == ranking.bestDay ? .blue : .primary
        case .passholderOnly:
            return .orange
        case .closed:
            return .gray
        }
    }

    private func dayAccessibilityLabel(_ day: WeekendDay) -> String {
        switch day.access {
        case .open, .unknown:
            let snow = day.forecastSnowCm.map { formatSnow($0) } ?? "unknown"
            return "\(day.weekday): \(snow) forecast"
        case .passholderOnly:
            return "\(day.weekday): passholders only"
        case .closed:
            return "\(day.weekday): closed"
        }
    }

    private func flagIcon(_ flag: String) -> String {
        if flag.hasPrefix("Passholders") { return "lock.fill" }
        if flag.hasPrefix("No ") { return "questionmark.circle" }
        return "exclamationmark.triangle.fill"
    }

    private func formatSnow(_ cm: Double) -> String {
        if userPreferencesManager.preferredUnits.snowDepth == .centimeters {
            return String(format: "%.0f cm", cm)
        } else {
            return String(format: "%.0f\"", cm / 2.54)
        }
    }
}
