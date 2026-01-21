import SwiftUI

@main
struct SnowTrackerApp: App {
    @StateObject private var snowConditionsManager = SnowConditionsManager()
    @ObservedObject private var authService = AuthenticationService.shared

    init() {
        // Configure API client
        APIClient.configure()
    }

    var body: some Scene {
        WindowGroup {
            if authService.isAuthenticated {
                MainTabView()
                    .environmentObject(snowConditionsManager)
            } else {
                // For now, skip auth and go directly to main app
                // Uncomment WelcomeView when ready to enable auth
                // WelcomeView()
                MainTabView()
                    .environmentObject(snowConditionsManager)
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
}
