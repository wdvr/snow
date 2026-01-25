import SwiftUI

@main
struct SnowTrackerApp: App {
    @StateObject private var snowConditionsManager = SnowConditionsManager()
    @ObservedObject private var authService = AuthenticationService.shared
    @ObservedObject private var userPreferencesManager = UserPreferencesManager.shared
    @State private var showSplash = true

    init() {
        // Configure API client
        APIClient.configure()
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                if authService.isAuthenticated {
                    MainTabView()
                        .environmentObject(snowConditionsManager)
                        .environmentObject(userPreferencesManager)
                } else {
                    // For now, skip auth and go directly to main app
                    // Uncomment WelcomeView when ready to enable auth
                    // WelcomeView()
                    MainTabView()
                        .environmentObject(snowConditionsManager)
                        .environmentObject(userPreferencesManager)
                }

                if showSplash {
                    SplashView()
                        .transition(.opacity)
                        .zIndex(1)
                }
            }
            .onAppear {
                // Show splash for minimum duration while data loads
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                    withAnimation(.easeOut(duration: 0.5)) {
                        showSplash = false
                    }
                }
            }
        }
    }
}

struct MainTabView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @ObservedObject private var authService = AuthenticationService.shared

    var body: some View {
        TabView {
            ResortListView()
                .tabItem {
                    Image(systemName: "mountain.2")
                    Text("Resorts")
                }

            ResortMapView()
                .tabItem {
                    Image(systemName: "map")
                    Text("Map")
                }

            ConditionsView()
                .tabItem {
                    Image(systemName: "snowflake")
                    Text("Conditions")
                }

            FavoritesView()
                .tabItem {
                    Image(systemName: "heart")
                    Text("Favorites")
                }

            SettingsView()
                .environmentObject(authService)
                .tabItem {
                    Image(systemName: "gear")
                    Text("Settings")
                }
        }
        .tint(.blue)
        .onAppear {
            snowConditionsManager.loadInitialData()
        }
    }
}

#Preview("Main App") {
    MainTabView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
