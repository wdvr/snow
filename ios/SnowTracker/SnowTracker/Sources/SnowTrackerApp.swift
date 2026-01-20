import SwiftUI
import FirebaseCore
import FirebaseAuth

@main
struct SnowTrackerApp: App {
    @StateObject private var authenticationManager = AuthenticationManager()
    @StateObject private var snowConditionsManager = SnowConditionsManager()
    @StateObject private var userPreferencesManager = UserPreferencesManager()

    init() {
        // Configure Firebase
        FirebaseApp.configure()

        // Configure API client
        APIClient.configure()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authenticationManager)
                .environmentObject(snowConditionsManager)
                .environmentObject(userPreferencesManager)
                .onAppear {
                    authenticationManager.checkAuthenticationStatus()
                }
        }
    }
}

struct ContentView: View {
    @EnvironmentObject private var authManager: AuthenticationManager

    var body: some View {
        Group {
            if authManager.isAuthenticated {
                MainTabView()
            } else {
                WelcomeView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: authManager.isAuthenticated)
    }
}

struct MainTabView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

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

            ProfileView()
                .tabItem {
                    Image(systemName: "person")
                    Text("Profile")
                }
        }
        .tint(.blue)
        .onAppear {
            snowConditionsManager.loadInitialData()
        }
    }
}

#Preview("Main App") {
    ContentView()
        .environmentObject(AuthenticationManager())
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager())
}