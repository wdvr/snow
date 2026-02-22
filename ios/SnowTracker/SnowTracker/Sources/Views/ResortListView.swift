import SwiftUI
import CoreLocation

enum ResortSortOption: String, CaseIterable {
    case name = "Name"
    case distance = "Distance"
    case snowQuality = "Snow Quality"

    var icon: String {
        switch self {
        case .name: return "textformat.abc"
        case .distance: return "location"
        case .snowQuality: return "snowflake"
        }
    }
}

struct ResortListView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @ObservedObject private var locationManager = LocationManager.shared
    @Binding var deepLinkResort: Resort?

    init(deepLinkResort: Binding<Resort?> = .constant(nil)) {
        _deepLinkResort = deepLinkResort
    }
    @State private var searchText = ""
    @State private var selectedRegion: SkiRegion? = nil
    @State private var sortOption: ResortSortOption = .name
    @AppStorage("selectedRegionFilter") private var savedRegionFilter: String = ""
    @AppStorage("resortSortOption") private var savedSortOption: String = "Name"

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

        // Apply search filter
        let searchFiltered: [Resort]
        if searchText.isEmpty {
            searchFiltered = regionFiltered
        } else {
            searchFiltered = regionFiltered.filter { resort in
                resort.name.localizedCaseInsensitiveContains(searchText) ||
                resort.countryName.localizedCaseInsensitiveContains(searchText) ||
                resort.region.localizedCaseInsensitiveContains(searchText)
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
                List {
                    ForEach(filteredResorts) { resort in
                        NavigationLink(value: resort) {
                            ResortRowView(
                                resort: resort,
                                showDistance: sortOption == .distance,
                                userLocation: locationManager.userLocation,
                                useMetric: useMetricDistance
                            )
                        }
                        .contextMenu {
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
                .listStyle(PlainListStyle())
                .searchable(text: $searchText, prompt: "Search resorts...")
                .overlay {
                    if !searchText.isEmpty && filteredResorts.isEmpty && !snowConditionsManager.resorts.isEmpty {
                        ContentUnavailableView.search(text: searchText)
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
                // Track screen view
                AnalyticsService.shared.trackScreen("ResortList", screenClass: "ResortListView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("ResortList")
            }
            .refreshable {
                AnalyticsService.shared.trackPullToRefresh(screen: "ResortList")
                await snowConditionsManager.refreshData()
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

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    HStack {
                        Text(resort.name)
                            .font(.headline)
                            .foregroundStyle(.primary)

                        // Distance badge when sorting by distance
                        if let distance = formattedDistance {
                            Text(distance)
                                .font(.caption)
                                .fontWeight(.medium)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.15))
                                .foregroundStyle(.blue)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }

                        // Pass affiliation badges
                        if resort.epicPass != nil {
                            Text("Epic")
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 2)
                                .foregroundStyle(.indigo)
                                .background(Color.indigo.opacity(0.12))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                        if resort.ikonPass != nil {
                            Text("Ikon")
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 2)
                                .foregroundStyle(.orange)
                                .background(Color.orange.opacity(0.12))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                    }

                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text(resort.elevationRange)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Snow quality indicator - always use summary/overall quality for consistency
                // (latestCondition is a single elevation which may differ from overall)
                let displayQuality = snowConditionsManager.getSnowQuality(for: resort.id)
                if displayQuality != .unknown {
                    VStack(spacing: 2) {
                        if let score = snowConditionsManager.getSnowScore(for: resort.id) {
                            Text("\(score)")
                                .font(.callout.weight(.bold))
                                .fontDesign(.rounded)
                                .foregroundStyle(displayQuality.color)
                        }
                        Image(systemName: displayQuality.icon)
                            .foregroundStyle(displayQuality.color)
                            .font(.title3)

                        Text(displayQuality.displayName)
                            .font(.caption2)
                            .foregroundStyle(displayQuality.color)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Snow quality: \(displayQuality.displayName)\(snowConditionsManager.getSnowScore(for: resort.id).map { ", score \($0)" } ?? "")")
                } else if snowConditionsManager.isLoadingSnowQuality {
                    VStack {
                        ProgressView()
                            .scaleEffect(0.8)

                        Text("Loading")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                } else {
                    VStack {
                        Image(systemName: "questionmark.circle")
                            .foregroundStyle(.gray)
                            .font(.title2)

                        Text("No data")
                            .font(.caption)
                            .foregroundStyle(.gray)
                    }
                }
            }

            // Quick stats - prefer full condition, fall back to summary
            if let condition = latestCondition {
                HStack {
                    Label(condition.formattedTemperature(userPreferencesManager.preferredUnits), systemImage: "thermometer")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Spacer()

                    // Use fresh snow (snowfall_after_freeze) which is more meaningful than 24h
                    Label(condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits), systemImage: "snowflake")
                        .font(.caption)
                        .foregroundStyle(.blue)

                    Spacer()

                    Label(condition.formattedTimestamp, systemImage: "clock")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } else if let summary = snowQualitySummary,
                      summary.temperatureC != nil || summary.snowfallFreshCm != nil {
                HStack {
                    if let temp = summary.formattedTemperature(userPreferencesManager.preferredUnits) {
                        Label(temp, systemImage: "thermometer")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    if let snow = summary.formattedFreshSnow(userPreferencesManager.preferredUnits) {
                        Label(snow, systemImage: "snowflake")
                            .font(.caption)
                            .foregroundStyle(.blue)
                    }

                    Spacer()

                    if let timestamp = summary.formattedTimestamp {
                        Label(timestamp, systemImage: "clock")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            } else {
                // Loading skeleton while weather data is being fetched
                HStack {
                    let tempUnit = userPreferencesManager.preferredUnits.temperature == .celsius ? "C" : "F"
                    Label("--\u{00B0}\(tempUnit)", systemImage: "thermometer")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Spacer()

                    let snowUnit = userPreferencesManager.preferredUnits.snowDepth == .centimeters ? "cm" : "\""
                    Label("-- \(snowUnit)", systemImage: "snowflake")
                        .font(.caption)
                        .foregroundStyle(.blue)

                    Spacer()

                    Label("--:--", systemImage: "clock")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .redacted(reason: .placeholder)
            }

            // Quality explanation (one-liner)
            if let explanation = snowConditionsManager.getExplanation(for: resort.id) {
                Text(explanation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            }
        }
        .padding(.vertical, 4)
    }
}

struct FilterChip: View {
    let title: String
    var icon: String? = nil
    let isSelected: Bool
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
                    .fill(isSelected ? Color.blue : Color.gray.opacity(0.2))
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
}
