import SwiftUI

struct RegionFilterSettingsView: View {
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

    var body: some View {
        Form {
            Section {
                Text("Choose which regions to show in the app. Hidden regions will not appear in the resort list, map, or recommendations.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            // North America Section
            Section {
                ForEach([SkiRegion.naWest, .naRockies, .naEast], id: \.self) { region in
                    RegionToggleRow(
                        region: region,
                        resortCount: resortCount(for: region)
                    )
                }
            } header: {
                Text("North America")
            }

            // Europe Section
            Section {
                ForEach([SkiRegion.alps, .scandinavia], id: \.self) { region in
                    RegionToggleRow(
                        region: region,
                        resortCount: resortCount(for: region)
                    )
                }
            } header: {
                Text("Europe")
            }

            // Asia Pacific Section
            Section {
                ForEach([SkiRegion.japan, .oceania], id: \.self) { region in
                    RegionToggleRow(
                        region: region,
                        resortCount: resortCount(for: region)
                    )
                }
            } header: {
                Text("Asia Pacific")
            } footer: {
                Text("Japan and Oceania (Australia & New Zealand) are hidden by default as they have opposite ski seasons.")
            }

            // South America Section
            Section {
                RegionToggleRow(
                    region: .southAmerica,
                    resortCount: resortCount(for: .southAmerica)
                )
            } header: {
                Text("South America")
            }

            // Quick Actions Section
            Section {
                Button("Show All Regions") {
                    withAnimation {
                        userPreferencesManager.hiddenRegions = []
                    }
                }
                .disabled(userPreferencesManager.hiddenRegions.isEmpty)

                Button("Show Northern Hemisphere Only") {
                    withAnimation {
                        userPreferencesManager.hiddenRegions = Set(
                            SkiRegion.allCases
                                .filter { $0.hemisphere == .southern }
                                .map { $0.rawValue }
                        )
                    }
                }

                Button("Reset to Defaults") {
                    withAnimation {
                        userPreferencesManager.hiddenRegions = Set(["oceania", "japan"])
                    }
                }
            } header: {
                Text("Quick Actions")
            }
        }
        .navigationTitle("Regions")
    }

    private func resortCount(for region: SkiRegion) -> Int {
        snowConditionsManager.resorts.filter { $0.inferredRegion == region }.count
    }
}

// MARK: - Region Toggle Row

struct RegionToggleRow: View {
    let region: SkiRegion
    let resortCount: Int
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    private var isVisible: Bool {
        userPreferencesManager.isRegionVisible(region)
    }

    var body: some View {
        Toggle(isOn: Binding(
            get: { isVisible },
            set: { _ in
                withAnimation {
                    userPreferencesManager.toggleRegionVisibility(region)
                }
            }
        )) {
            HStack(spacing: 12) {
                Image(systemName: region.icon)
                    .font(.title3)
                    .foregroundStyle(isVisible ? .blue : .secondary)
                    .frame(width: 28)

                VStack(alignment: .leading, spacing: 2) {
                    Text(region.displayName)
                        .font(.body)

                    HStack(spacing: 8) {
                        Text("\(resortCount) resort\(resortCount == 1 ? "" : "s")")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        Text(region.seasonMonths)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .tint(.blue)
    }
}

#Preview {
    NavigationStack {
        RegionFilterSettingsView()
            .environmentObject(UserPreferencesManager.shared)
            .environmentObject(SnowConditionsManager())
    }
}
