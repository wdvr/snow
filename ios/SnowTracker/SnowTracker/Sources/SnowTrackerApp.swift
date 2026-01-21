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

struct SettingsView: View {
    @State private var temperatureUnit = "celsius"
    @State private var distanceUnit = "metric"
    @ObservedObject private var authService = AuthenticationService.shared

    var body: some View {
        NavigationStack {
            List {
                Section("Units") {
                    Picker("Temperature", selection: $temperatureUnit) {
                        Text("Celsius").tag("celsius")
                        Text("Fahrenheit").tag("fahrenheit")
                    }

                    Picker("Distance", selection: $distanceUnit) {
                        Text("Metric (m)").tag("metric")
                        Text("Imperial (ft)").tag("imperial")
                    }
                }

                if authService.isAuthenticated, let user = authService.currentUser {
                    Section("Account") {
                        HStack {
                            ZStack {
                                Circle()
                                    .fill(Color.blue.opacity(0.2))
                                    .frame(width: 40, height: 40)

                                Text(user.initials)
                                    .font(.headline)
                                    .foregroundColor(.blue)
                            }

                            VStack(alignment: .leading) {
                                Text(user.displayName)
                                    .font(.body)
                                if let email = user.email {
                                    Text(email)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }

                        Button(role: .destructive) {
                            authService.signOut()
                        } label: {
                            Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    }
                } else {
                    Section("Account") {
                        Button {
                            authService.signInWithApple()
                        } label: {
                            Label("Sign in with Apple", systemImage: "apple.logo")
                        }
                    }
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")
                            .foregroundColor(.secondary)
                    }

                    HStack {
                        Text("Environment")
                        Spacer()
                        Text(AppConfiguration.shared.isDebug ? "Development" : "Production")
                            .foregroundColor(.secondary)
                    }
                }

                #if DEBUG
                Section("Debug") {
                    HStack {
                        Text("API Base URL")
                        Spacer()
                        Text(AppConfiguration.shared.apiBaseURL.absoluteString)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
                #endif
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview("Main App") {
    MainTabView()
        .environmentObject(SnowConditionsManager())
}

#Preview("Settings") {
    SettingsView()
}
