import SwiftUI
import CoreLocation

// MARK: - Recommendations Manager

@MainActor
class RecommendationsManager: ObservableObject {
    @Published var recommendations: [ResortRecommendation] = []
    @Published var bestConditions: [ResortRecommendation] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?

    private let apiClient = APIClient.shared

    func loadRecommendations(latitude: Double, longitude: Double, radiusKm: Double = 500) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiClient.getRecommendations(
                latitude: latitude,
                longitude: longitude,
                radiusKm: radiusKm,
                limit: 10
            )
            recommendations = response.recommendations
            lastUpdated = Date()
        } catch {
            errorMessage = error.localizedDescription
            print("Error loading recommendations: \(error)")
        }

        isLoading = false
    }

    func loadBestConditions() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiClient.getBestConditions(limit: 10)
            bestConditions = response.recommendations
            lastUpdated = Date()
        } catch {
            errorMessage = error.localizedDescription
            print("Error loading best conditions: \(error)")
        }

        isLoading = false
    }
}

// MARK: - Best Snow Near You View

struct BestSnowNearYouView: View {
    @StateObject private var recommendationsManager = RecommendationsManager()
    @StateObject private var locationManager = LocationManager.shared
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    @State private var selectedTab = 0
    @State private var searchRadius: Double = 500

    var useMetric: Bool {
        userPreferencesManager.preferredUnits.distance == .metric
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Tab Picker
                Picker("View", selection: $selectedTab) {
                    Text("Near You").tag(0)
                    Text("Best Globally").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()

                // Content
                if selectedTab == 0 {
                    nearYouContent
                } else {
                    bestGloballyContent
                }
            }
            .navigationTitle("Best Snow")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Section("Search Radius") {
                            Button("100 km / 62 mi") { searchRadius = 100; Task { await refreshNearby() } }
                            Button("250 km / 155 mi") { searchRadius = 250; Task { await refreshNearby() } }
                            Button("500 km / 310 mi") { searchRadius = 500; Task { await refreshNearby() } }
                        }
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                    }
                }
            }
        }
    }

    private var nearYouContent: some View {
        Group {
            if locationManager.authorizationStatus == .notDetermined {
                locationPermissionView
            } else if locationManager.authorizationStatus == .denied ||
                      locationManager.authorizationStatus == .restricted {
                locationDeniedView
            } else if recommendationsManager.isLoading && recommendationsManager.recommendations.isEmpty {
                loadingView
            } else if recommendationsManager.recommendations.isEmpty {
                emptyStateView
            } else {
                recommendationsList(recommendations: recommendationsManager.recommendations, showDistance: true)
            }
        }
        .refreshable {
            await refreshNearby()
        }
        .task {
            await loadNearbyIfNeeded()
        }
    }

    private var bestGloballyContent: some View {
        Group {
            if recommendationsManager.isLoading && recommendationsManager.bestConditions.isEmpty {
                loadingView
            } else if recommendationsManager.bestConditions.isEmpty {
                ContentUnavailableView(
                    "No Data Available",
                    systemImage: "snowflake.slash",
                    description: Text("Could not load best conditions. Pull to refresh.")
                )
            } else {
                recommendationsList(recommendations: recommendationsManager.bestConditions, showDistance: false)
            }
        }
        .refreshable {
            await recommendationsManager.loadBestConditions()
        }
        .task {
            if recommendationsManager.bestConditions.isEmpty {
                await recommendationsManager.loadBestConditions()
            }
        }
    }

    private var locationPermissionView: some View {
        ContentUnavailableView {
            Label("Location Access", systemImage: "location.circle")
        } description: {
            Text("Enable location access to see the best snow conditions near you.")
        } actions: {
            Button("Enable Location") {
                locationManager.requestLocationPermission()
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var locationDeniedView: some View {
        ContentUnavailableView {
            Label("Location Disabled", systemImage: "location.slash")
        } description: {
            Text("Location access is disabled. Enable it in Settings to see nearby recommendations.")
        } actions: {
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .buttonStyle(.bordered)
        }
    }

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Finding best snow near you...")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyStateView: some View {
        ContentUnavailableView {
            Label("No Recommendations", systemImage: "snowflake")
        } description: {
            if let error = recommendationsManager.errorMessage {
                Text(error)
            } else {
                Text("No resorts found within \(Int(searchRadius)) km. Try increasing the search radius.")
            }
        } actions: {
            Button("Refresh") {
                Task { await refreshNearby() }
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private func recommendationsList(recommendations: [ResortRecommendation], showDistance: Bool) -> some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                // Header
                if let lastUpdated = recommendationsManager.lastUpdated {
                    HStack {
                        Image(systemName: "clock")
                            .foregroundColor(.secondary)
                        Text("Updated \(lastUpdated.formatted(.relative(presentation: .named)))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 8)
                }

                // Recommendations
                ForEach(recommendations) { recommendation in
                    NavigationLink(destination: ResortDetailView(resort: recommendation.resort)) {
                        RecommendationCard(
                            recommendation: recommendation,
                            showDistance: showDistance,
                            useMetric: useMetric
                        )
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            .padding()
        }
    }

    private func loadNearbyIfNeeded() async {
        if recommendationsManager.recommendations.isEmpty,
           let location = locationManager.userLocation {
            await recommendationsManager.loadRecommendations(
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                radiusKm: searchRadius
            )
        }
    }

    private func refreshNearby() async {
        if let location = locationManager.userLocation {
            await recommendationsManager.loadRecommendations(
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                radiusKm: searchRadius
            )
        }
    }
}

// MARK: - Recommendation Card

struct RecommendationCard: View {
    let recommendation: ResortRecommendation
    let showDistance: Bool
    let useMetric: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with resort name and quality badge
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(recommendation.resort.name)
                        .font(.headline)
                        .foregroundColor(.primary)

                    Text(recommendation.resort.displayLocation)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Quality badge
                QualityBadge(quality: recommendation.quality)
            }

            // Reason text
            Text(recommendation.reason)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .lineLimit(2)

            // Stats row
            HStack(spacing: 16) {
                // Distance (if showing)
                if showDistance && recommendation.distanceKm > 0 {
                    StatItem(
                        icon: "location.fill",
                        value: recommendation.formattedDistance(useMetric: useMetric),
                        color: .blue
                    )
                }

                // Fresh snow
                if recommendation.freshSnowCm > 0 {
                    StatItem(
                        icon: "snowflake",
                        value: formatSnow(recommendation.freshSnowCm),
                        color: .cyan
                    )
                }

                // Predicted snow
                if recommendation.predictedSnow72hCm > 0 {
                    StatItem(
                        icon: "cloud.snow.fill",
                        value: "+\(formatSnow(recommendation.predictedSnow72hCm))",
                        color: .purple
                    )
                }

                // Temperature
                StatItem(
                    icon: "thermometer.medium",
                    value: formatTemp(recommendation.currentTempCelsius),
                    color: tempColor(recommendation.currentTempCelsius)
                )

                Spacer()

                // Score indicator
                ScoreIndicator(score: recommendation.combinedScore)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func formatSnow(_ cm: Double) -> String {
        if useMetric {
            return String(format: "%.0f cm", cm)
        } else {
            return String(format: "%.1f\"", cm / 2.54)
        }
    }

    private func formatTemp(_ celsius: Double) -> String {
        if useMetric {
            return String(format: "%.0f°C", celsius)
        } else {
            return String(format: "%.0f°F", celsius * 9/5 + 32)
        }
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

// MARK: - Supporting Views

struct QualityBadge: View {
    let quality: SnowQuality

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: quality.icon)
            Text(quality.displayName)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .foregroundColor(quality.color)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(quality.color.opacity(0.15))
        .cornerRadius(8)
    }
}

struct StatItem: View {
    let icon: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(color)
            Text(value)
                .font(.caption)
                .foregroundColor(.primary)
        }
    }
}

struct ScoreIndicator: View {
    let score: Double

    private var scoreColor: Color {
        if score >= 0.8 {
            return .green
        } else if score >= 0.6 {
            return .yellow
        } else if score >= 0.4 {
            return .orange
        } else {
            return .red
        }
    }

    var body: some View {
        VStack(spacing: 2) {
            Text(String(format: "%.0f", score * 100))
                .font(.caption)
                .fontWeight(.bold)
                .foregroundColor(scoreColor)
            Text("score")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Best Snow Card (for Home Screen)

struct BestSnowNearYouCard: View {
    @StateObject private var recommendationsManager = RecommendationsManager()
    @StateObject private var locationManager = LocationManager.shared
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    var useMetric: Bool {
        userPreferencesManager.preferredUnits.distance == .metric
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Label("Best Snow Near You", systemImage: "snowflake.circle.fill")
                    .font(.headline)
                Spacer()
                NavigationLink(destination: BestSnowNearYouView()) {
                    Text("See All")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }

            if recommendationsManager.isLoading {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
                .padding(.vertical, 20)
            } else if let topRecommendation = recommendationsManager.recommendations.first {
                // Show top recommendation
                NavigationLink(destination: ResortDetailView(resort: topRecommendation.resort)) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(topRecommendation.resort.name)
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.primary)

                            Text(topRecommendation.formattedDistance(useMetric: useMetric))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        QualityBadge(quality: topRecommendation.quality)
                    }
                }
                .buttonStyle(PlainButtonStyle())

                Text(topRecommendation.reason)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            } else if locationManager.authorizationStatus == .denied ||
                      locationManager.authorizationStatus == .restricted {
                HStack {
                    Image(systemName: "location.slash")
                        .foregroundColor(.orange)
                    Text("Enable location to see nearby recommendations")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            } else {
                HStack {
                    Image(systemName: "snowflake")
                        .foregroundColor(.secondary)
                    Text("Pull to load recommendations")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .task {
            await loadRecommendations()
        }
    }

    private func loadRecommendations() async {
        if let location = locationManager.userLocation {
            await recommendationsManager.loadRecommendations(
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                radiusKm: 300
            )
        }
    }
}

#Preview {
    BestSnowNearYouView()
        .environmentObject(UserPreferencesManager.shared)
}
