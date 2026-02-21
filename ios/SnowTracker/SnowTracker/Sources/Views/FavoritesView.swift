import SwiftUI

struct FavoritesView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

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
                .foregroundColor(.gray)

            Text("No Favorites Yet")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Tap the heart icon on any resort to add it to your favorites for quick access.")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            NavigationLink(destination: ResortListView()) {
                Label("Browse Resorts", systemImage: "mountain.2")
                    .font(.headline)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(12)
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
            }
            .onDelete(perform: removeFavorites)
        }
        .listStyle(PlainListStyle())
    }

    private func removeFavorites(at offsets: IndexSet) {
        for index in offsets {
            let resort = favoriteResorts[index]
            userPreferencesManager.toggleFavorite(resortId: resort.id)
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
                        .foregroundColor(displayQuality.color)
                }
            } else {
                ZStack {
                    Circle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: "questionmark")
                        .font(.title2)
                        .foregroundColor(.gray)
                }
            }

            // Resort info
            VStack(alignment: .leading, spacing: 4) {
                Text(resort.name)
                    .font(.headline)

                Text(resort.displayLocation)
                    .font(.caption)
                    .foregroundColor(.secondary)

                if let condition = topCondition {
                    HStack(spacing: 8) {
                        Label(condition.formattedTemperature(userPreferencesManager.preferredUnits), systemImage: "thermometer")
                        Label(condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits), systemImage: "snowflake")
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
            }

            Spacer()

            // Arrow indicator
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
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
