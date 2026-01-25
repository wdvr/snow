import SwiftUI

struct ResortListView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @State private var searchText = ""
    @State private var selectedRegion: SkiRegion? = nil
    @AppStorage("selectedRegionFilter") private var savedRegionFilter: String = ""

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
        if searchText.isEmpty {
            return regionFiltered
        } else {
            return regionFiltered.filter { resort in
                resort.name.localizedCaseInsensitiveContains(searchText) ||
                resort.countryName.localizedCaseInsensitiveContains(searchText) ||
                resort.region.localizedCaseInsensitiveContains(searchText)
            }
        }
    }

    var availableRegions: [SkiRegion] {
        let resortRegions = Set(snowConditionsManager.resorts.map { $0.inferredRegion })
        return SkiRegion.allCases.filter { resortRegions.contains($0) }
    }

    var body: some View {
        NavigationStack {
            VStack {
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

                // Resort list
                List {
                    ForEach(filteredResorts) { resort in
                        NavigationLink(destination: ResortDetailView(resort: resort)) {
                            ResortRowView(resort: resort)
                        }
                    }
                }
                .listStyle(PlainListStyle())
                .searchable(text: $searchText, prompt: "Search resorts...")
            }
            .navigationTitle("Snow Resorts")
            .onAppear {
                // Restore saved region filter
                if !savedRegionFilter.isEmpty, let region = SkiRegion(rawValue: savedRegionFilter) {
                    selectedRegion = region
                }
            }
            .refreshable {
                await snowConditionsManager.refreshData()
            }
            .overlay {
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

struct ResortRowView: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

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

                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundColor(.secondary)

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
