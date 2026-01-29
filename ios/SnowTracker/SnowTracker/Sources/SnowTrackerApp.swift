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
                    WelcomeView()
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
            .onOpenURL { url in
                // Handle Google Sign-In callback URL
                _ = authService.handleURL(url)
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

            BestSnowNearYouView()
                .tabItem {
                    Image(systemName: "star.fill")
                    Text("Best Snow")
                }

            TripsListView()
                .tabItem {
                    Image(systemName: "calendar")
                    Text("Trips")
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
