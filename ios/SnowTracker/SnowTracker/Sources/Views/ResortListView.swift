import SwiftUI

struct ResortListView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @State private var searchText = ""
    @State private var selectedCountry: String? = nil

    var filteredResorts: [Resort] {
        let resorts = snowConditionsManager.resorts

        // Apply country filter
        let countryFiltered = selectedCountry == nil ? resorts : resorts.filter { $0.country == selectedCountry }

        // Apply search filter
        if searchText.isEmpty {
            return countryFiltered
        } else {
            return countryFiltered.filter { resort in
                resort.name.localizedCaseInsensitiveContains(searchText) ||
                resort.region.localizedCaseInsensitiveContains(searchText)
            }
        }
    }

    var availableCountries: [String] {
        Array(Set(snowConditionsManager.resorts.map { $0.country })).sorted()
    }

    var body: some View {
        NavigationStack {
            VStack {
                // Country filter
                if !availableCountries.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            FilterChip(
                                title: "All",
                                isSelected: selectedCountry == nil
                            ) {
                                selectedCountry = nil
                            }

                            ForEach(availableCountries, id: \.self) { country in
                                FilterChip(
                                    title: Resort.countryName(for: country),
                                    isSelected: selectedCountry == country
                                ) {
                                    selectedCountry = selectedCountry == country ? nil : country
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
            .refreshable {
                await snowConditionsManager.refreshData()
            }
            .overlay {
                if snowConditionsManager.isLoading && snowConditionsManager.resorts.isEmpty {
                    ProgressView("Loading resorts...")
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
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.caption)
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

// Extension for Resort model
extension Resort {
    static func countryName(for code: String) -> String {
        switch code.uppercased() {
        case "CA": return "Canada"
        case "US": return "United States"
        default: return code
        }
    }
}

#Preview("Resort List") {
    ResortListView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
