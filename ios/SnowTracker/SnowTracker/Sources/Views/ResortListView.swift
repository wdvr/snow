import SwiftUI
import CoreLocation

enum ResortViewMode: String, CaseIterable {
    case list = "list"
    case map = "map"

    var icon: String {
        switch self {
        case .list: return "list.bullet"
        case .map: return "map"
        }
    }
}

enum ResortSortOption: String, CaseIterable {
    case name = "name"
    case nearMe = "near_me"
    case snowQuality = "snow_quality"

    var displayName: String {
        switch self {
        case .name: return "Name"
        case .nearMe: return "Near Me"
        case .snowQuality: return "Snow Quality"
        }
    }

    var icon: String {
        switch self {
        case .name: return "textformat"
        case .nearMe: return "location"
        case .snowQuality: return "snowflake"
        }
    }
}

struct ResortListView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @ObservedObject private var locationManager = LocationManager.shared
    @State private var searchText = ""
    @State private var selectedRegion: SkiRegion? = nil
    @State private var viewMode: ResortViewMode = .list
    @State private var sortOption: ResortSortOption = .name
    @AppStorage("selectedRegionFilter") private var savedRegionFilter: String = ""
    @AppStorage("resortViewMode") private var savedViewMode: String = "list"

    var filteredResorts: [Resort] {
        let resorts = snowConditionsManager.resorts

        // Apply region filter
        let regionFiltered: [Resort]
        if let region = selectedRegion {
            regionFiltered = resorts.filter { $0.inferredRegion == region }
        } else {
            regionFiltered = resorts
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
        return sortedResorts(searchFiltered)
    }

    private func sortedResorts(_ resorts: [Resort]) -> [Resort] {
        switch sortOption {
        case .name:
            return resorts.sorted { $0.name < $1.name }
        case .nearMe:
            guard let userLocation = locationManager.userLocation else {
                return resorts.sorted { $0.name < $1.name }
            }
            return resorts.sorted { resort1, resort2 in
                let dist1 = resort1.distance(from: userLocation) ?? .infinity
                let dist2 = resort2.distance(from: userLocation) ?? .infinity
                return dist1 < dist2
            }
        case .snowQuality:
            return resorts.sorted { resort1, resort2 in
                let quality1 = snowConditionsManager.getLatestCondition(for: resort1.id)?.snowQuality ?? .unknown
                let quality2 = snowConditionsManager.getLatestCondition(for: resort2.id)?.snowQuality ?? .unknown
                return quality1.sortOrder < quality2.sortOrder
            }
        }
    }

    var availableRegions: [SkiRegion] {
        let resortRegions = Set(snowConditionsManager.resorts.map { $0.inferredRegion })
        return SkiRegion.allCases.filter { resortRegions.contains($0) }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
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
                    .padding(.vertical, 8)
                }

                // Content based on view mode
                if viewMode == .map {
                    ResortMapView(selectedRegion: $selectedRegion)
                } else {
                    // Resort list
                    List {
                        ForEach(filteredResorts) { resort in
                            NavigationLink(destination: ResortDetailView(resort: resort)) {
                                ResortRowView(
                                    resort: resort,
                                    showDistance: sortOption == .nearMe
                                )
                            }
                        }
                    }
                    .listStyle(PlainListStyle())
                    .searchable(text: $searchText, prompt: "Search resorts...")
                }
            }
            .navigationTitle("Snow Resorts")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    // Sort menu (only in list view)
                    if viewMode == .list {
                        Menu {
                            ForEach(ResortSortOption.allCases, id: \.self) { option in
                                Button {
                                    withAnimation {
                                        sortOption = option
                                        if option == .nearMe {
                                            requestLocationIfNeeded()
                                        }
                                    }
                                } label: {
                                    Label(option.displayName, systemImage: option.icon)
                                    if sortOption == option {
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        } label: {
                            Image(systemName: sortOption.icon)
                        }
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    // View mode toggle
                    Picker("View Mode", selection: $viewMode) {
                        ForEach(ResortViewMode.allCases, id: \.self) { mode in
                            Image(systemName: mode.icon)
                                .tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 100)
                }
            }
            .onAppear {
                // Restore saved region filter
                if !savedRegionFilter.isEmpty, let region = SkiRegion(rawValue: savedRegionFilter) {
                    selectedRegion = region
                }
                // Restore saved view mode
                if let mode = ResortViewMode(rawValue: savedViewMode) {
                    viewMode = mode
                }
            }
            .onChange(of: viewMode) { _, newValue in
                savedViewMode = newValue.rawValue
            }
            .onChange(of: sortOption) { _, newValue in
                if newValue == .nearMe {
                    requestLocationIfNeeded()
                }
            }
            .refreshable {
                await snowConditionsManager.refreshData()
            }
            .overlay {
                if viewMode == .list {
                    if snowConditionsManager.isLoading && snowConditionsManager.resorts.isEmpty {
                        ProgressView("Loading resorts...")
                    } else if let errorMessage = snowConditionsManager.errorMessage, snowConditionsManager.resorts.isEmpty {
                        VStack(spacing: 16) {
                            Image(systemName: "wifi.exclamationmark")
                                .font(.system(size: 50))
                                .foregroundColor(.orange)
                            Text("Unable to Load Resorts")
                                .font(.headline)
                            Text(errorMessage)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                            Button("Try Again") {
                                Task {
                                    await snowConditionsManager.fetchResorts()
                                }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                        .padding()
                    } else if snowConditionsManager.resorts.isEmpty && !snowConditionsManager.isLoading {
                        VStack(spacing: 16) {
                            Image(systemName: "mountain.2")
                                .font(.system(size: 50))
                                .foregroundColor(.gray)
                            Text("No Resorts Found")
                                .font(.headline)
                            Text("Pull to refresh")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
    }

    private func requestLocationIfNeeded() {
        if locationManager.needsAuthorization {
            locationManager.requestAuthorization()
        } else if locationManager.isAuthorized && locationManager.userLocation == nil {
            locationManager.requestLocation()
        }
    }
}

struct ResortRowView: View {
    let resort: Resort
    var showDistance: Bool = false
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @ObservedObject private var locationManager = LocationManager.shared

    private var latestCondition: WeatherCondition? {
        snowConditionsManager.getLatestCondition(for: resort.id)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(resort.name)
                        .font(.headline)
                        .foregroundColor(.primary)

                    HStack(spacing: 4) {
                        Text(resort.displayLocation)
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        // Show distance when sorting by Near Me
                        if showDistance, let distance = locationManager.formattedDistance(to: resort) {
                            Text("•")
                                .foregroundColor(.secondary)
                            Label(distance, systemImage: "location")
                                .font(.subheadline)
                                .foregroundColor(.blue)
                        }
                    }

                    Text(resort.elevationRange)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Snow quality indicator
                if let condition = latestCondition {
                    VStack {
                        Image(systemName: condition.snowQuality.icon)
                            .foregroundColor(condition.snowQuality.color)
                            .font(.title2)

                        Text(condition.snowQuality.displayName)
                            .font(.caption)
                            .foregroundColor(condition.snowQuality.color)
                    }
                } else {
                    VStack {
                        Image(systemName: "questionmark.circle")
                            .foregroundColor(.gray)
                            .font(.title2)

                        Text("No data")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
            }

            // Quick stats
            if let condition = latestCondition {
                HStack {
                    Label(condition.formattedCurrentTemp, systemImage: "thermometer")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Spacer()

                    Label(condition.formattedSnowfall24h, systemImage: "snowflake")
                        .font(.caption)
                        .foregroundColor(.blue)

                    Spacer()

                    Label(condition.formattedTimestamp, systemImage: "clock")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
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
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(isSelected ? Color.blue : Color.gray.opacity(0.2))
            )
            .foregroundColor(isSelected ? .white : .primary)
        }
        .buttonStyle(PlainButtonStyle())
    }
}


#Preview("Resort List") {
    ResortListView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
