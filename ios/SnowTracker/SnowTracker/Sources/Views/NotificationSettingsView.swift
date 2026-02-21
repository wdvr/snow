import SwiftUI
import os.log

private let notifSettingsLog = Logger(subsystem: "com.snowtracker.app", category: "NotificationSettings")

struct NotificationSettingsView: View {
    @StateObject private var viewModel = NotificationSettingsViewModel()
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    var body: some View {
        Form {
            // System Permission Section
            Section {
                HStack {
                    Image(systemName: viewModel.isAuthorized ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(viewModel.isAuthorized ? .green : .red)

                    Text(viewModel.isAuthorized ? "Notifications Enabled" : "Notifications Disabled")

                    Spacer()

                    if !viewModel.isAuthorized {
                        Button("Enable") {
                            viewModel.openSystemSettings()
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                    }
                }
            } header: {
                Text("System Permissions")
            } footer: {
                if !viewModel.isAuthorized {
                    Text("Enable notifications in System Settings to receive alerts about snow conditions and resort events.")
                }
            }

            // Global Settings Section
            Section {
                Toggle("All Notifications", isOn: $viewModel.notificationsEnabled)
                    .onChange(of: viewModel.notificationsEnabled) { _, newValue in
                        viewModel.saveSettings()
                        AnalyticsService.shared.trackNotificationSettingChanged(setting: "all_notifications", enabled: newValue)
                    }
            } header: {
                Text("Master Switch")
            } footer: {
                Text("Turn off to disable all push notifications from Powder Chaser.")
            }

            // Notification Types Section
            if viewModel.notificationsEnabled {
                Section {
                    Toggle("Fresh Snow Alerts", isOn: $viewModel.freshSnowAlerts)
                        .onChange(of: viewModel.freshSnowAlerts) { _, newValue in
                            viewModel.saveSettings()
                            AnalyticsService.shared.trackNotificationSettingChanged(setting: "fresh_snow_alerts", enabled: newValue)
                        }

                    if viewModel.freshSnowAlerts {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Minimum Snow Threshold")
                                .font(.subheadline)

                            HStack {
                                Slider(
                                    value: $viewModel.snowThresholdCm,
                                    in: 1...30,
                                    step: 1
                                )
                                .onChange(of: viewModel.snowThresholdCm) { _, _ in
                                    viewModel.saveSettings()
                                }

                                Text("\(Int(viewModel.snowThresholdCm)) cm")
                                    .frame(width: 50, alignment: .trailing)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }

                    Toggle("Resort Event Alerts", isOn: $viewModel.eventAlerts)
                        .onChange(of: viewModel.eventAlerts) { _, newValue in
                            viewModel.saveSettings()
                            AnalyticsService.shared.trackNotificationSettingChanged(setting: "event_alerts", enabled: newValue)
                        }

                    Toggle("Thaw/Freeze Alerts", isOn: $viewModel.thawFreezeAlerts)
                        .onChange(of: viewModel.thawFreezeAlerts) { _, newValue in
                            viewModel.saveSettings()
                            AnalyticsService.shared.trackNotificationSettingChanged(setting: "thaw_freeze_alerts", enabled: newValue)
                        }
                } header: {
                    Text("Alert Types")
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Fresh Snow Alerts: Get notified when fresh snow falls at your favorite resorts.")
                        Text("Resort Events: Get notified about special events and offers at your favorite resorts.")
                        Text("Thaw/Freeze Alerts: Get notified when temperatures rise above 0°C for 4+ hours (thawing) or drop below 0°C (freezing) - indicates icy conditions ahead.")
                    }
                }

                // Notification Frequency Section
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Notification Cooldown")
                            .font(.subheadline)

                        Picker("", selection: $viewModel.gracePeriodHours) {
                            Text("12 hours").tag(12)
                            Text("24 hours").tag(24)
                            Text("48 hours").tag(48)
                        }
                        .pickerStyle(.segmented)
                        .onChange(of: viewModel.gracePeriodHours) { _, _ in
                            viewModel.saveSettings()
                        }
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("Frequency")
                } footer: {
                    Text("Maximum one notification per resort within this time period to avoid notification overload.")
                }

                // Favorite Resorts Section
                if !userPreferencesManager.favoriteResorts.isEmpty {
                    Section {
                        ForEach(Array(userPreferencesManager.favoriteResorts), id: \.self) { resortId in
                            ResortNotificationRow(
                                resortId: resortId,
                                viewModel: viewModel
                            )
                        }
                    } header: {
                        Text("Favorite Resorts")
                    } footer: {
                        Text("Customize notification settings for individual resorts. These override the global settings above.")
                    }
                }

                // Debug Section (only in staging/debug/TestFlight builds)
                if AppEnvironment.isDebugOrTestFlight {
                    Section {
                        // Auth status
                        HStack {
                            Text("Auth Status")
                            Spacer()
                            if AuthenticationService.shared.currentUser?.provider == .guest {
                                Text("Guest")
                                    .foregroundStyle(.orange)
                            } else if AuthenticationService.shared.isAuthenticated {
                                Text("Signed In")
                                    .foregroundStyle(.green)
                            } else {
                                Text("Not Signed In")
                                    .foregroundStyle(.red)
                            }
                        }
                        .font(.subheadline)

                        Button {
                            viewModel.sendTestNotification()
                        } label: {
                            HStack {
                                Image(systemName: "bell.badge")
                                Text("Send Test Notification")
                            }
                        }
                        .disabled(viewModel.isSendingTest)

                        Button {
                            viewModel.triggerNotificationProcessor()
                        } label: {
                            HStack {
                                Image(systemName: "arrow.clockwise")
                                Text("Trigger Notification Check")
                            }
                        }
                        .disabled(viewModel.isSendingTest)

                        if let testResult = viewModel.testResult {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Image(systemName: testResult.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                                        .foregroundStyle(testResult.success ? .green : .red)
                                    Text(testResult.message)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }

                                if !testResult.success && testResult.message.contains("Session expired") {
                                    Button("Sign out and re-authenticate") {
                                        AuthenticationService.shared.signOut()
                                    }
                                    .font(.caption)
                                    .foregroundStyle(.blue)
                                }
                            }
                        }
                    } header: {
                        Text("Debug")
                    } footer: {
                        Text("Test notification features. Only visible in debug/TestFlight builds.")
                    }
                }
            }
        }
        .navigationTitle("Notifications")
        .onAppear {
            AnalyticsService.shared.trackScreen("NotificationSettings", screenClass: "NotificationSettingsView")
        }
        .task {
            await viewModel.loadSettings()
        }
    }
}

// MARK: - Resort Notification Row

struct ResortNotificationRow: View {
    let resortId: String
    @ObservedObject var viewModel: NotificationSettingsViewModel
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 12) {
                Toggle("Snow Alerts", isOn: binding(for: \.freshSnowEnabled))
                    .font(.subheadline)

                if viewModel.getResortSetting(resortId)?.freshSnowEnabled ?? true {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Snow Threshold")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        HStack {
                            Slider(
                                value: thresholdBinding,
                                in: 1...30,
                                step: 1
                            )

                            Text("\(Int(viewModel.getResortSetting(resortId)?.freshSnowThresholdCm ?? viewModel.snowThresholdCm)) cm")
                                .frame(width: 50, alignment: .trailing)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Toggle("Event Alerts", isOn: binding(for: \.eventNotificationsEnabled))
                    .font(.subheadline)
            }
            .padding(.vertical, 8)
        } label: {
            HStack {
                Text(resortDisplayName)
                    .font(.body)

                Spacer()

                if hasCustomSettings {
                    Text("Custom")
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color.blue.opacity(0.1))
                        .clipShape(Capsule())
                }
            }
        }
    }

    private var resortDisplayName: String {
        // Format resort ID to display name (e.g., "whistler-blackcomb" -> "Whistler Blackcomb")
        resortId
            .split(separator: "-")
            .map { $0.capitalized }
            .joined(separator: " ")
    }

    private var hasCustomSettings: Bool {
        viewModel.getResortSetting(resortId) != nil
    }

    private var thresholdBinding: Binding<Double> {
        Binding(
            get: {
                viewModel.getResortSetting(resortId)?.freshSnowThresholdCm ?? viewModel.snowThresholdCm
            },
            set: { newValue in
                viewModel.updateResortSetting(resortId: resortId, freshSnowThresholdCm: newValue)
            }
        )
    }

    private func binding(for keyPath: WritableKeyPath<ResortNotificationSettings, Bool>) -> Binding<Bool> {
        Binding(
            get: {
                if let settings = viewModel.getResortSetting(resortId) {
                    return settings[keyPath: keyPath]
                }
                // Return global default
                switch keyPath {
                case \.freshSnowEnabled:
                    return viewModel.freshSnowAlerts
                case \.eventNotificationsEnabled:
                    return viewModel.eventAlerts
                default:
                    return true
                }
            },
            set: { newValue in
                switch keyPath {
                case \.freshSnowEnabled:
                    viewModel.updateResortSetting(resortId: resortId, freshSnowEnabled: newValue)
                case \.eventNotificationsEnabled:
                    viewModel.updateResortSetting(resortId: resortId, eventNotificationsEnabled: newValue)
                default:
                    break
                }
            }
        )
    }
}

// MARK: - View Model

struct TestResult {
    let success: Bool
    let message: String
}

@MainActor
class NotificationSettingsViewModel: ObservableObject {
    @Published var isAuthorized = false
    @Published var notificationsEnabled = true
    @Published var freshSnowAlerts = true
    @Published var eventAlerts = true
    @Published var thawFreezeAlerts = true
    @Published var weeklySummary = false
    @Published var snowThresholdCm: Double = 1.0
    @Published var gracePeriodHours = 24
    @Published var isLoading = false
    @Published var isSendingTest = false
    @Published var testResult: TestResult?

    private var resortSettings: [String: ResortNotificationSettings] = [:]
    private let apiClient = APIClient.shared
    private let pushService = PushNotificationService.shared

    init() {
        Task {
            await checkAuthorization()
        }
    }

    func checkAuthorization() async {
        await pushService.checkAuthorizationStatus()
        isAuthorized = pushService.isAuthorized
    }

    func openSystemSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
    }

    func loadSettings() async {
        isLoading = true
        defer { isLoading = false }

        await checkAuthorization()

        do {
            let settings = try await apiClient.getNotificationSettings()
            notificationsEnabled = settings.notificationsEnabled
            freshSnowAlerts = settings.freshSnowAlerts
            eventAlerts = settings.eventAlerts
            thawFreezeAlerts = settings.thawFreezeAlerts
            weeklySummary = settings.weeklySummary
            snowThresholdCm = settings.defaultSnowThresholdCm
            gracePeriodHours = settings.gracePeriodHours
            resortSettings = settings.resortSettings
        } catch {
            notifSettingsLog.error("Failed to load notification settings: \(error)")
            // Use defaults if loading fails
        }
    }

    func saveSettings() {
        Task {
            do {
                let update = NotificationSettingsUpdate(
                    notificationsEnabled: notificationsEnabled,
                    freshSnowAlerts: freshSnowAlerts,
                    eventAlerts: eventAlerts,
                    thawFreezeAlerts: thawFreezeAlerts,
                    weeklySummary: weeklySummary,
                    defaultSnowThresholdCm: snowThresholdCm,
                    gracePeriodHours: gracePeriodHours
                )
                try await apiClient.updateNotificationSettings(update)
            } catch {
                notifSettingsLog.error("Failed to save notification settings: \(error)")
            }
        }
    }

    func getResortSetting(_ resortId: String) -> ResortNotificationSettings? {
        resortSettings[resortId]
    }

    func updateResortSetting(
        resortId: String,
        freshSnowEnabled: Bool? = nil,
        freshSnowThresholdCm: Double? = nil,
        eventNotificationsEnabled: Bool? = nil
    ) {
        // Create or update resort settings
        var settings = resortSettings[resortId] ?? ResortNotificationSettings(
            resortId: resortId,
            freshSnowEnabled: freshSnowAlerts,
            freshSnowThresholdCm: snowThresholdCm,
            eventNotificationsEnabled: eventAlerts
        )

        if let freshSnowEnabled {
            settings.freshSnowEnabled = freshSnowEnabled
        }
        if let freshSnowThresholdCm {
            settings.freshSnowThresholdCm = freshSnowThresholdCm
        }
        if let eventNotificationsEnabled {
            settings.eventNotificationsEnabled = eventNotificationsEnabled
        }

        resortSettings[resortId] = settings

        // Save to backend
        Task {
            do {
                let update = ResortNotificationSettingsUpdate(
                    freshSnowEnabled: settings.freshSnowEnabled,
                    freshSnowThresholdCm: settings.freshSnowThresholdCm,
                    eventNotificationsEnabled: settings.eventNotificationsEnabled
                )
                try await apiClient.updateResortNotificationSettings(
                    resortId: resortId,
                    settings: update
                )
            } catch {
                notifSettingsLog.error("Failed to save resort notification settings: \(error)")
            }
        }
    }

    // MARK: - Debug Methods

    func sendTestNotification() {
        guard !isSendingTest else { return }

        // Check authentication first
        let authService = AuthenticationService.shared
        guard authService.isAuthenticated else {
            testResult = TestResult(success: false, message: "Please sign in first")
            return
        }

        if authService.currentUser?.provider == .guest {
            testResult = TestResult(success: false, message: "Debug features require signing in with Apple or Google")
            return
        }

        isSendingTest = true
        testResult = nil

        Task {
            do {
                let result = try await apiClient.sendTestPushNotification()
                testResult = TestResult(success: true, message: result.message)
            } catch let error as APIError {
                testResult = TestResult(success: false, message: formatAuthError(error))
            } catch {
                testResult = TestResult(success: false, message: error.localizedDescription)
            }
            isSendingTest = false
        }
    }

    func triggerNotificationProcessor() {
        guard !isSendingTest else { return }

        // Check authentication first
        let authService = AuthenticationService.shared
        guard authService.isAuthenticated else {
            testResult = TestResult(success: false, message: "Please sign in first")
            return
        }

        if authService.currentUser?.provider == .guest {
            testResult = TestResult(success: false, message: "Debug features require signing in with Apple or Google")
            return
        }

        isSendingTest = true
        testResult = nil

        Task {
            do {
                let result = try await apiClient.triggerNotificationProcessor()
                testResult = TestResult(success: true, message: result.message)
            } catch let error as APIError {
                testResult = TestResult(success: false, message: formatAuthError(error))
            } catch {
                testResult = TestResult(success: false, message: error.localizedDescription)
            }
            isSendingTest = false
        }
    }

    private func formatAuthError(_ error: APIError) -> String {
        switch error {
        case .unauthorized:
            return "Session expired. Please sign out and sign in again."
        case .forbidden:
            return "Debug features not available in this environment."
        default:
            return error.localizedDescription ?? "An error occurred"
        }
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
            .environmentObject(UserPreferencesManager.shared)
    }
}
