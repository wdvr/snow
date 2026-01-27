import SwiftUI

struct SettingsView: View {
    @ObservedObject private var config = AppConfiguration.shared
    @EnvironmentObject var authService: AuthenticationService
    @EnvironmentObject var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss: DismissAction

    @State private var showingResetAlert = false
    @State private var showingSignOutAlert = false
    @State private var showingClearCacheAlert = false
    @State private var customURL: String = ""
    @State private var urlValidationError: String?

    var body: some View {
        NavigationStack {
            Form {
                // API Configuration Section (Debug only)
                #if DEBUG
                Section {
                    // Environment Picker
                    Picker("Environment", selection: $config.selectedEnvironment) {
                        ForEach(AppEnvironment.allCases, id: \.self) { env in
                            Text(env.displayName).tag(env)
                        }
                    }

                    Toggle("Use Custom API URL", isOn: $config.useCustomAPI)

                    if config.useCustomAPI {
                        TextField("API URL", text: $customURL)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .onChange(of: customURL) { _, newValue in
                                validateAndSaveURL(newValue)
                            }

                        if let error = urlValidationError {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                        }

                        Text("Example: http://localhost:8000 or https://your-api.ngrok.io")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("Current API")
                        Spacer()
                        Text(config.apiBaseURL.absoluteString)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }

                    if config.isUsingCustomAPI || config.selectedEnvironment != config.defaultEnvironment {
                        Button("Reset to Default") {
                            showingResetAlert = true
                        }
                        .foregroundStyle(.orange)
                    }
                } header: {
                    Text("Developer Settings")
                } footer: {
                    Text("Configure environment and API endpoint for testing. Only available in debug builds.")
                }
                #endif

                // Environment Info Section
                Section {
                    HStack {
                        Text("Environment")
                        Spacer()
                        Text(environmentName)
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("App Version")
                        Spacer()
                        Text(appVersion)
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("Build")
                        Spacer()
                        Text(buildNumber)
                            .foregroundStyle(.secondary)
                    }
                } header: {
                    Text("App Info")
                }

                // Account Section
                Section {
                    accountRow
                } header: {
                    Text("Account")
                }

                // Preferences Section
                Section {
                    NavigationLink {
                        Text("Notification settings coming soon")
                            .navigationTitle("Notifications")
                    } label: {
                        Label("Notifications", systemImage: "bell")
                    }

                    NavigationLink {
                        UnitsSettingsView()
                    } label: {
                        Label("Units", systemImage: "ruler")
                    }
                } header: {
                    Text("Preferences")
                }

                // Data & Storage Section
                Section {
                    Button {
                        showingClearCacheAlert = true
                    } label: {
                        Label("Clear Offline Cache", systemImage: "trash")
                    }
                    .foregroundStyle(.red)
                } header: {
                    Text("Data & Storage")
                } footer: {
                    if snowConditionsManager.isUsingCachedData {
                        Text("Currently showing cached data. Clear cache to force fresh data on next load.")
                    } else {
                        Text("Cached data allows the app to work offline. Clear cache to free up storage.")
                    }
                }

                // Support Section
                Section {
                    NavigationLink {
                        FeedbackView()
                    } label: {
                        Label("Send Feedback", systemImage: "envelope")
                    }
                } header: {
                    Text("Support")
                } footer: {
                    Text("Help us improve by sharing your feedback, reporting bugs, or suggesting features.")
                }

                // About Section
                Section {
                    Link(destination: URL(string: "https://snow-tracker.com/privacy")!) {
                        Label("Privacy Policy", systemImage: "hand.raised")
                    }

                    Link(destination: URL(string: "https://snow-tracker.com/terms")!) {
                        Label("Terms of Service", systemImage: "doc.text")
                    }

                    NavigationLink {
                        AboutView()
                    } label: {
                        Label("About", systemImage: "info.circle")
                    }
                } header: {
                    Text("Legal")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                customURL = config.customAPIURLString
            }
            .alert("Reset API URL?", isPresented: $showingResetAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Reset", role: .destructive) {
                    config.resetToDefault()
                    customURL = ""
                    urlValidationError = nil
                }
            } message: {
                Text("This will reset the API URL to the default endpoint.")
            }
            .alert("Sign Out?", isPresented: $showingSignOutAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Sign Out", role: .destructive) {
                    authService.signOut()
                }
            } message: {
                Text("Are you sure you want to sign out?")
            }
            .alert("Clear Cache?", isPresented: $showingClearCacheAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Clear", role: .destructive) {
                    snowConditionsManager.clearCache()
                }
            } message: {
                Text("This will delete all cached resort and weather data. The app will need to download fresh data.")
            }
        }
    }

    private func validateAndSaveURL(_ urlString: String) {
        if urlString.isEmpty {
            urlValidationError = nil
            config.customAPIURLString = ""
            return
        }

        if config.validateURL(urlString) {
            urlValidationError = nil
            config.customAPIURLString = urlString
        } else {
            urlValidationError = "Invalid URL format. Must start with http:// or https://"
        }
    }

    private var environmentName: String {
        config.currentConfigurationDisplay
    }

    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown"
    }

    private var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "Unknown"
    }

    @ViewBuilder
    private var accountRow: some View {
        if authService.isAuthenticated, let user = authService.currentUser {
            if user.provider == .guest {
                // Guest mode - show "Not logged in" and option to sign in
                HStack {
                    Image(systemName: "person.circle")
                        .foregroundColor(.secondary)

                    Text("Not logged in")
                        .font(.body)
                        .foregroundStyle(.secondary)

                    Spacer()
                }

                Button("Sign In") {
                    authService.signOut()  // This will return to login screen
                }
                .foregroundStyle(.blue)
            } else {
                // Signed in with Apple or Google
                HStack {
                    let isApple = user.provider == .apple
                    Image(systemName: isApple ? "apple.logo" : "g.circle.fill")
                        .foregroundColor(isApple ? .primary : .blue)
                        .font(.title3)

                    VStack(alignment: .leading, spacing: 2) {
                        if let email = user.email {
                            Text(email)
                                .font(.body)
                        } else {
                            Text(user.displayName)
                                .font(.body)
                        }

                        Text("Signed in with \(isApple ? "Apple" : "Google")")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()
                }

                Button("Sign Out") {
                    showingSignOutAlert = true
                }
                .foregroundStyle(.red)
            }
        } else {
            Text("Not signed in")
                .foregroundStyle(.secondary)
        }
    }
}

// MARK: - Units Settings

struct UnitsSettingsView: View {
    @EnvironmentObject var userPreferencesManager: UserPreferencesManager

    var body: some View {
        Form {
            Section {
                Picker("Temperature", selection: $userPreferencesManager.preferredUnits.temperature) {
                    Text("Celsius").tag(UnitPreferences.TemperatureUnit.celsius)
                    Text("Fahrenheit").tag(UnitPreferences.TemperatureUnit.fahrenheit)
                }

                Picker("Distance", selection: $userPreferencesManager.preferredUnits.distance) {
                    Text("Metric (km)").tag(UnitPreferences.DistanceUnit.metric)
                    Text("Imperial (mi)").tag(UnitPreferences.DistanceUnit.imperial)
                }

                Picker("Snow Depth", selection: $userPreferencesManager.preferredUnits.snowDepth) {
                    Text("Centimeters").tag(UnitPreferences.SnowDepthUnit.centimeters)
                    Text("Inches").tag(UnitPreferences.SnowDepthUnit.inches)
                }
            }
        }
        .navigationTitle("Units")
    }
}

// MARK: - About View

struct AboutView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Image(systemName: "snowflake")
                    .font(.system(size: 80))
                    .foregroundStyle(.blue)
                    .padding(.top, 40)

                Text("Snow Quality Tracker")
                    .font(.title)
                    .fontWeight(.bold)

                Text("Track snow conditions at your favorite ski resorts. Get real-time updates on snow quality, temperature, and fresh powder.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)

                Divider()
                    .padding(.horizontal)

                VStack(spacing: 8) {
                    Text("Initial Resorts")
                        .font(.headline)

                    Text("Big White, Lake Louise, Silver Star")
                        .foregroundStyle(.secondary)
                }

                Spacer()
            }
            .padding()
        }
        .navigationTitle("About")
    }
}

#Preview {
    SettingsView()
        .environmentObject(AuthenticationService.shared)
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
