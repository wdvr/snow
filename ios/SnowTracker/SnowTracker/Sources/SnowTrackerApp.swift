import SwiftUI

@main
struct SnowTrackerApp: App {
    @StateObject private var snowConditionsManager = SnowConditionsManager()

    init() {
        // Configure API client
        APIClient.configure()
    }

    var body: some Scene {
        WindowGroup {
            MainTabView()
                .environmentObject(snowConditionsManager)
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
    var body: some View {
        NavigationStack {
            List {
                Section("Units") {
                    Picker("Temperature", selection: .constant("celsius")) {
                        Text("Celsius").tag("celsius")
                        Text("Fahrenheit").tag("fahrenheit")
                    }

                    Picker("Distance", selection: .constant("metric")) {
                        Text("Metric (m)").tag("metric")
                        Text("Imperial (ft)").tag("imperial")
                    }
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview("Main App") {
    MainTabView()
        .environmentObject(SnowConditionsManager())
}
