import SwiftUI
import CoreLocation

enum ResortSortOption: String, CaseIterable {
    case name = "Name"
    case distance = "Distance"
    case snowQuality = "Snow Quality"
    case freshSnow = "New Snow"
    case snowDepth = "Snow Depth"
    case predictedSnow = "Predicted Snow"
    case temperature = "Temperature"

    var icon: String {
        switch self {
        case .name: return "textformat.abc"
        case .distance: return "location"
        case .snowQuality: return "snowflake"
        case .freshSnow: return "cloud.snow"
        case .snowDepth: return "mountain.2.fill"
        case .predictedSnow: return "cloud.snow.fill"
        case .temperature: return "thermometer.snowflake"
        }
    }
}

enum PassFilter: String, CaseIterable {
    case all = "All"
    case epic = "Epic"
    case ikon = "Ikon"
    case indy = "Indy"

    var icon: String {
        switch self {
        case .all: return "creditcard"
        case .epic: return "star.fill"
        case .ikon: return "mountain.2.fill"
        case .indy: return "figure.skiing.downhill"
        }
    }

    var chipColor: Color {
        switch self {
        case .all: return .blue
        case .epic: return .indigo
        case .ikon: return .orange
        case .indy: return .green
        }
    }
}

struct ResortListView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator
    @ObservedObject private var locationManager = LocationManager.shared
    @Binding var deepLinkResort: Resort?

    init(deepLinkResort: Binding<Resort?> = .constant(nil)) {
        _deepLinkResort = deepLinkResort
    }
    @State private var searchText = ""
    @State private var selectedRegion: SkiRegion? = nil
    @State private var sortOption: ResortSortOption = .name
    @State private var passFilter: PassFilter = .all
    @State private var visibleResortIds: Set<String> = []
    @AppStorage("selectedRegionFilter") private var savedRegionFilter: String = ""
    @AppStorage("resortSortOption") private var savedSortOption: String = "Name"
    @AppStorage("selectedPassFilter") private var savedPassFilter: String = "All"

    private var useMetricDistance: Bool {
        userPreferencesManager.preferredUnits.distance == .metric
    }

    private var visibleResorts: [Resort] {
        userPreferencesManager.filterByVisibleRegions(snowConditionsManager.resorts)
    }

    var filteredAndSortedResorts: [Resort] {
        // Apply region filter (selected chip filter)
        let regionFiltered: [Resort]
        if let region = selectedRegion {
            regionFiltered = visibleResorts.filter { $0.inferredRegion == region }
        } else {
            regionFiltered = visibleResorts
        }

        // Apply pass filter
        let passFiltered: [Resort]
        switch passFilter {
        case .all:
            passFiltered = regionFiltered
        case .epic:
            passFiltered = regionFiltered.filter { $0.epicPass != nil }
        case .ikon:
            passFiltered = regionFiltered.filter { $0.ikonPass != nil }
        case .indy:
            passFiltered = regionFiltered.filter { $0.indyPass != nil }
        }

        // Apply search filter
        let searchFiltered: [Resort]
        if searchText.isEmpty {
            searchFiltered = passFiltered
        } else {
            searchFiltered = passFiltered.filter { resort in
                resort.name.localizedCaseInsensitiveContains(searchText) ||
                resort.countryName.localizedCaseInsensitiveContains(searchText) ||
                resort.country.localizedCaseInsensitiveContains(searchText) ||
                resort.region.localizedCaseInsensitiveContains(searchText) ||
                (resort.epicPass != nil && "epic".localizedCaseInsensitiveContains(searchText)) ||
                (resort.ikonPass != nil && "ikon".localizedCaseInsensitiveContains(searchText)) ||
                (resort.indyPass != nil && "indy".localizedCaseInsensitiveContains(searchText))
            }
        }

        // Apply sorting
        return sortResorts(searchFiltered)
    }

    private func sortResorts(_ resorts: [Resort]) -> [Resort] {
        switch sortOption {
        case .name:
            return resorts.sorted { $0.name < $1.name }
        case .distance:
            guard let userLocation = locationManager.userLocation else {
                return resorts.sorted { $0.name < $1.name }
            }
            // Pre-compute distances to avoid O(n log n) distance calculations during sort
            let distances = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, $0.distance(from: userLocation))
            })
            return resorts.sorted {
                (distances[$0.id] ?? .infinity) < (distances[$1.id] ?? .infinity)
            }
        case .snowQuality:
            // Pre-compute quality to avoid O(n log n) lookups during sort
            let qualities = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, snowConditionsManager.getSnowQuality(for: $0.id).sortOrder)
            })
            return resorts.sorted {
                (qualities[$0.id] ?? 99) < (qualities[$1.id] ?? 99)
            }
        case .freshSnow:
            // Sort by fresh snow amount (most snow first)
            let freshSnow = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, snowConditionsManager.snowQualitySummaries[$0.id]?.snowfallFreshCm ?? -1)
            })
            return resorts.sorted {
                (freshSnow[$0.id] ?? -1) > (freshSnow[$1.id] ?? -1)
            }
        case .snowDepth:
            // Sort by snow depth (deepest first)
            let depths = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, snowConditionsManager.snowQualitySummaries[$0.id]?.snowDepthCm ?? -1)
            })
            return resorts.sorted {
                (depths[$0.id] ?? -1) > (depths[$1.id] ?? -1)
            }
        case .predictedSnow:
            // Sort by predicted snowfall in next 48h (most first)
            let predicted = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, snowConditionsManager.snowQualitySummaries[$0.id]?.predictedSnow48hCm ?? -1)
            })
            return resorts.sorted {
                (predicted[$0.id] ?? -1) > (predicted[$1.id] ?? -1)
            }
        case .temperature:
            // Sort by temperature (coldest first - better for snow preservation)
            let temps = Dictionary(uniqueKeysWithValues: resorts.map {
                ($0.id, snowConditionsManager.snowQualitySummaries[$0.id]?.temperatureC ?? 999)
            })
            return resorts.sorted {
                (temps[$0.id] ?? 999) < (temps[$1.id] ?? 999)
            }
        }
    }

    // Legacy computed property for compatibility
    var filteredResorts: [Resort] {
        filteredAndSortedResorts
    }

    var availableRegions: [SkiRegion] {
        let resortRegions = Set(visibleResorts.map { $0.inferredRegion })
        return SkiRegion.allCases.filter { resortRegions.contains($0) }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Filter and sort controls
                VStack(spacing: 8) {
                    // Region filter
                    if !availableRegions.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack {
                                FilterChip(
                                    title: "All Regions",
                                    icon: "globe",
                                    isSelected: selectedRegion == nil
                                ) {
                                    selectedRegion = nil
                                    savedRegionFilter = ""
                                }

                                ForEach(availableRegions, id: \.self) { region in
                                    FilterChip(
                                        title: region.displayName,
                                        icon: region.icon,
                                        isSelected: selectedRegion == region
                                    ) {
                                        if selectedRegion == region {
                                            selectedRegion = nil
                                            savedRegionFilter = ""
                                        } else {
                                            selectedRegion = region
                                            savedRegionFilter = region.rawValue
                                        }
                                    }
                                }
                            }
                            .padding(.horizontal)
                        }
                    }

                    // Pass filter
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            Text("Pass:")
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            ForEach(PassFilter.allCases, id: \.self) { filter in
                                FilterChip(
                                    title: filter.rawValue,
                                    icon: filter.icon,
                                    isSelected: passFilter == filter,
                                    selectedColor: filter.chipColor
                                ) {
                                    passFilter = filter
                                    savedPassFilter = filter.rawValue
                                }
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Sort options
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            Text("Sort:")
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            ForEach(ResortSortOption.allCases, id: \.self) { option in
                                // Only show distance option if location is available
                                if option != .distance || locationManager.isLocationAvailable {
                                    FilterChip(
                                        title: option.rawValue,
                                        icon: option.icon,
                                        isSelected: sortOption == option
                                    ) {
                                        sortOption = option
                                        savedSortOption = option.rawValue
                                        // Request location when switching to distance sort
                                        if option == .distance && locationManager.userLocation == nil {
                                            locationManager.requestLocationPermission()
                                        }
                                    }
                                }
                            }
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.vertical, 8)

                // Resort list
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(filteredResorts) { resort in
                            NavigationLink(value: resort) {
                                ResortRowView(
                                    resort: resort,
                                    showDistance: sortOption == .distance,
                                    userLocation: locationManager.userLocation,
                                    useMetric: useMetricDistance
                                )
                            }
                            .buttonStyle(PlainButtonStyle())
                            .onAppear {
                                visibleResortIds.insert(resort.id)
                                snowConditionsManager.onResortAppeared(resort.id)
                            }
                            .onDisappear {
                                visibleResortIds.remove(resort.id)
                            }
                            .contextMenu {
                                Button {
                                    navigationCoordinator.showOnMap(resort)
                                } label: {
                                    Label("Show on Map", systemImage: "map.fill")
                                }

                                Button {
                                    userPreferencesManager.toggleFavorite(resortId: resort.id)
                                } label: {
                                    Label(
                                        userPreferencesManager.isFavorite(resortId: resort.id) ? "Remove Favorite" : "Add to Favorites",
                                        systemImage: userPreferencesManager.isFavorite(resortId: resort.id) ? "heart.slash" : "heart"
                                    )
                                }

                                if let website = resort.officialWebsite, let url = URL(string: website) {
                                    Link(destination: url) {
                                        Label("Visit Website", systemImage: "safari")
                                    }
                                }
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                .searchable(text: $searchText, prompt: "Search resorts...")
                .refreshable {
                    NSLog("[Refresh] .refreshable closure START")
                    AnalyticsService.shared.trackPullToRefresh(screen: "ResortList")
                    let topIds = Array(filteredResorts.prefix(max(visibleResortIds.count + 20, 30)).map(\.id))
                    await snowConditionsManager.refreshData(visibleResortIds: topIds)
                    NSLog("[Refresh] .refreshable closure END — spinner should dismiss now")
                }
                .overlay {
                    if filteredResorts.isEmpty && !snowConditionsManager.resorts.isEmpty {
                        if !searchText.isEmpty {
                            ContentUnavailableView.search(text: searchText)
                        } else if passFilter != .all {
                            ContentUnavailableView(
                                "No \(passFilter.rawValue) Pass Resorts",
                                systemImage: "creditcard.trianglebadge.exclamationmark",
                                description: Text("No resorts found with \(passFilter.rawValue) pass in the selected region.")
                            )
                        }
                    }
                }
            }
            .navigationTitle("Snow Resorts")
            .onAppear {
                // Restore saved region filter
                if !savedRegionFilter.isEmpty, let region = SkiRegion(rawValue: savedRegionFilter) {
                    selectedRegion = region
                }
                // Restore saved sort option
                if let option = ResortSortOption(rawValue: savedSortOption) {
                    sortOption = option
                }
                // Restore saved pass filter
                if let filter = PassFilter(rawValue: savedPassFilter) {
                    passFilter = filter
                }
                // Track screen view
                AnalyticsService.shared.trackScreen("ResortList", screenClass: "ResortListView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("ResortList")
            }
            .onChange(of: searchText) { _, newValue in
                // Track search when user stops typing (debounced by SwiftUI)
                if !newValue.isEmpty {
                    AnalyticsService.shared.trackSearch(query: newValue, resultsCount: filteredResorts.count)
                }
            }
            .onChange(of: selectedRegion) { oldValue, newValue in
                AnalyticsService.shared.trackRegionFilterChanged(
                    region: newValue?.rawValue,
                    previousRegion: oldValue?.rawValue
                )
            }
            .onChange(of: sortOption) { _, newValue in
                AnalyticsService.shared.trackSortChanged(sortOption: newValue.rawValue)
            }
            .navigationDestination(for: Resort.self) { resort in
                ResortDetailView(resort: resort)
            }
            .navigationDestination(item: $deepLinkResort) { resort in
                ResortDetailView(resort: resort)
            }
            .overlay {
                if snowConditionsManager.resorts.isEmpty {
                    if snowConditionsManager.isLoading {
                        VStack(spacing: 16) {
                            ProgressView()
                                .controlSize(.large)
                            Text("Loading resorts...")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    } else if let errorMessage = snowConditionsManager.errorMessage {
                        VStack(spacing: 16) {
                            Image(systemName: "wifi.exclamationmark")
                                .font(.system(size: 50))
                                .foregroundStyle(.orange)
                            Text("Unable to Load Resorts")
                                .font(.headline)
                            Text(errorMessage)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                            Button {
                                Task {
                                    await snowConditionsManager.fetchResorts()
                                }
                            } label: {
                                Label("Try Again", systemImage: "arrow.clockwise")
                            }
                            .buttonStyle(.borderedProminent)
                        }
                        .padding()
                    } else {
                        VStack(spacing: 16) {
                            Image(systemName: "mountain.2")
                                .font(.system(size: 50))
                                .foregroundStyle(.gray)
                            Text("No Resorts Found")
                                .font(.headline)
                            Text("Pull to refresh")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}

struct ResortRowView: View {
    let resort: Resort
    var showDistance: Bool = false
    var userLocation: CLLocation? = nil
    var useMetric: Bool = true
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    private var latestCondition: WeatherCondition? {
        snowConditionsManager.getLatestCondition(for: resort.id)
    }

    private var snowQualitySummary: SnowQualitySummaryLight? {
        snowConditionsManager.snowQualitySummaries[resort.id]
    }

    private var formattedDistance: String? {
        guard showDistance, let location = userLocation else { return nil }
        let distance = resort.distance(from: location)
        if useMetric {
            let km = distance / 1000
            if km < 1 {
                return String(format: "%.0f m", distance)
            } else if km < 10 {
                return String(format: "%.1f km", km)
            } else {
                return String(format: "%.0f km", km)
            }
        } else {
            let miles = distance / 1609.344
            if miles < 1 {
                return String(format: "%.1f mi", miles)
            } else if miles < 10 {
                return String(format: "%.1f mi", miles)
            } else {
                return String(format: "%.0f mi", miles)
            }
        }
    }

    private var displayQuality: SnowQuality {
        snowConditionsManager.getSnowQuality(for: resort.id)
    }

    private var snowScore: Int? {
        snowConditionsManager.getSnowScore(for: resort.id)
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

            // Stats row using StatItem components
            HStack(spacing: 12) {
                // Temperature
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

                // Fresh snow
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

                // Forecast (predicted snow)
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

                // Distance
                if let distance = formattedDistance {
                    StatItem(
                        icon: "location.fill",
                        value: distance,
                        color: .blue
                    )
                }

                Spacer()
            }

            // Quality explanation
            if let explanation = snowConditionsManager.getExplanation(for: resort.id) {
                Text(explanation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            }
        }
        .cardStyle()
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

struct FilterChip: View {
    let title: String
    var icon: String? = nil
    let isSelected: Bool
    var selectedColor: Color = .blue
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                if let icon = icon {
                    Image(systemName: icon)
                        .font(.caption)
                }
                Text(title)
                    .font(.caption)
                    .fontWeight(isSelected ? .semibold : .regular)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(isSelected ? selectedColor : Color.gray.opacity(0.2))
            )
            .foregroundStyle(isSelected ? .white : .primary)
        }
        .buttonStyle(PlainButtonStyle())
        .scaleEffect(isSelected ? 1.0 : 0.95)
        .animation(.easeInOut(duration: 0.15), value: isSelected)
        .sensoryFeedback(.selection, trigger: isSelected)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityLabel("\(title)\(isSelected ? ", selected" : "")")
    }
}


#Preview("Resort List") {
    ResortListView(deepLinkResort: .constant(nil))
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
        .environmentObject(NavigationCoordinator())
}
