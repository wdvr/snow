import SwiftUI

struct FavoritesView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @StateObject private var userPreferencesManager = UserPreferencesManager()

    private var favoriteResorts: [Resort] {
        snowConditionsManager.resorts.filter { resort in
            userPreferencesManager.favoriteResorts.contains(resort.id)
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
            .refreshable {
                await snowConditionsManager.refreshConditions()
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

    private var topCondition: WeatherCondition? {
        snowConditionsManager.conditions[resort.id]?.first { $0.elevationLevel == "top" }
    }

    var body: some View {
        HStack(spacing: 12) {
            // Snow quality indicator
            if let condition = topCondition {
                ZStack {
                    Circle()
                        .fill(condition.snowQuality.color.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: condition.snowQuality.icon)
                        .font(.title2)
                        .foregroundColor(condition.snowQuality.color)
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
                        Label("\(Int(condition.currentTempCelsius))°C", systemImage: "thermometer")
                        Label(condition.formattedFreshSnow, systemImage: "snowflake")
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
}
