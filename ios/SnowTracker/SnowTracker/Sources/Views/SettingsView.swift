import SwiftUI

struct SettingsView: View {
    @ObservedObject private var config = AppConfiguration.shared
    @EnvironmentObject var authService: AuthenticationService
    @Environment(\.dismiss) private var dismiss: DismissAction

    @State private var showingResetAlert = false
    @State private var showingSignOutAlert = false
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
                    if authService.isAuthenticated {
                        if let email = authService.currentUser?.email {
                            HStack {
                                Text("Signed in as")
                                Spacer()
                                Text(email)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        Button("Sign Out") {
                            showingSignOutAlert = true
                        }
                        .foregroundStyle(.red)
                    } else {
                        Text("Not signed in")
                            .foregroundStyle(.secondary)
                    }
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
}

// MARK: - Units Settings

struct UnitsSettingsView: View {
    @State private var temperatureUnit = "celsius"
    @State private var distanceUnit = "metric"
    @State private var snowDepthUnit = "cm"

    var body: some View {
        Form {
            Section {
                Picker("Temperature", selection: $temperatureUnit) {
                    Text("Celsius").tag("celsius")
                    Text("Fahrenheit").tag("fahrenheit")
                }

                Picker("Distance", selection: $distanceUnit) {
                    Text("Metric (km)").tag("metric")
                    Text("Imperial (mi)").tag("imperial")
                }

                Picker("Snow Depth", selection: $snowDepthUnit) {
                    Text("Centimeters").tag("cm")
                    Text("Inches").tag("in")
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
}
