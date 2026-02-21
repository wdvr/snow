import SwiftUI

struct FavoritesView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var resortToRemove: Resort?

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
            }
            .task {
                // Fetch conditions for favorites when view appears
                await snowConditionsManager.fetchConditionsForFavorites()
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
        List {
            ForEach(favoriteResorts) { resort in
                NavigationLink(destination: ResortDetailView(resort: resort)) {
                    FavoriteResortRow(resort: resort)
                }
                .simultaneousGesture(TapGesture().onEnded {
                    AnalyticsService.shared.trackResortClicked(
                        resortId: resort.id,
                        resortName: resort.name,
                        source: "favorites"
                    )
                })
                .accessibilityLabel("\(resort.name), \(snowConditionsManager.getSnowQuality(for: resort.id).displayName)")
            }
            .onDelete { offsets in
                if let index = offsets.first {
                    resortToRemove = favoriteResorts[index]
                }
            }
        }
        .listStyle(PlainListStyle())
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
}

struct FavoriteResortRow: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    private var topCondition: WeatherCondition? {
        snowConditionsManager.conditions[resort.id]?.first { $0.elevationLevel == "top" }
    }

    var body: some View {
        HStack(spacing: 12) {
            // Snow quality indicator - use overall quality for consistency
            let displayQuality = snowConditionsManager.getSnowQuality(for: resort.id)
            if displayQuality != .unknown {
                ZStack {
                    Circle()
                        .fill(displayQuality.color.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: displayQuality.icon)
                        .font(.title2)
                        .foregroundStyle(displayQuality.color)
                }
            } else {
                ZStack {
                    Circle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: "questionmark")
                        .font(.title2)
                        .foregroundStyle(.gray)
                }
            }

            // Resort info
            VStack(alignment: .leading, spacing: 4) {
                Text(resort.name)
                    .font(.headline)

                Text(resort.displayLocation)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                if let condition = topCondition {
                    HStack(spacing: 8) {
                        Label(condition.formattedTemperature(userPreferencesManager.preferredUnits), systemImage: "thermometer")
                        Label(condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits), systemImage: "snowflake")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Arrow indicator
            Image(systemName: "chevron.right")
                .foregroundStyle(.secondary)
                .font(.caption)
        }
        .padding(.vertical, 8)
    }
}

#Preview("Favorites") {
    FavoritesView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
