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
                // NOW Alerts Section
                Section {
                    Toggle("New Snow Alerts", isOn: $viewModel.freshSnowAlerts)
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

                                Text(formatThreshold(viewModel.snowThresholdCm))
                                    .frame(width: 55, alignment: .trailing)
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

                    Toggle("Powder Day Alerts", isOn: $viewModel.powderAlerts)
                        .onChange(of: viewModel.powderAlerts) { _, newValue in
                            viewModel.saveSettings()
                            AnalyticsService.shared.trackNotificationSettingChanged(setting: "powder_alerts", enabled: newValue)
                        }

                    if viewModel.powderAlerts {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Powder Day Threshold")
                                .font(.subheadline)

                            HStack {
                                Slider(
                                    value: $viewModel.powderThreshold,
                                    in: 15...50,
                                    step: 1
                                )
                                .onChange(of: viewModel.powderThreshold) { _, _ in
                                    viewModel.saveSettings()
                                }

                                Text(formatThreshold(viewModel.powderThreshold))
                                    .frame(width: 55, alignment: .trailing)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                } header: {
                    Label("Now", systemImage: "bolt.fill")
                } footer: {
                    Text("Get notified about current conditions at your favorite resorts.")
                }

                // SOON Alerts Section
                Section {
                    Toggle("Snowfall Forecast", isOn: $viewModel.forecastAlerts)
                        .onChange(of: viewModel.forecastAlerts) { _, newValue in
                            viewModel.saveSettings()
                            AnalyticsService.shared.trackNotificationSettingChanged(setting: "forecast_alerts", enabled: newValue)
                        }

                    if viewModel.forecastAlerts {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Minimum Predicted Snowfall (3 days)")
                                .font(.subheadline)

                            HStack {
                                Slider(
                                    value: $viewModel.forecastThreshold,
                                    in: 5...50,
                                    step: 5
                                )
                                .onChange(of: viewModel.forecastThreshold) { _, _ in
                                    viewModel.saveSettings()
                                }

                                Text(formatThreshold(viewModel.forecastThreshold))
                                    .frame(width: 55, alignment: .trailing)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                } header: {
                    Label("Soon", systemImage: "clock.fill")
                } footer: {
                    Text("Get notified about predicted conditions over the next 3 days.")
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

                // Debug Section (debug/TestFlight builds + admin users in production)
                if AppEnvironment.isDebugOrTestFlight || AppConfiguration.shared.showDeveloperSettings {
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

                        // Show current API environment
                        HStack {
                            Text("API")
                            Spacer()
                            Text(AppConfiguration.shared.apiBaseURL.host ?? "unknown")
                                .foregroundStyle(.secondary)
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

                                if !testResult.success {
                                    Button("Retry") {
                                        viewModel.testResult = nil
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

    private func formatThreshold(_ cm: Double) -> String {
        if userPreferencesManager.preferredUnits.snowDepth == .inches {
            let inches = cm / 2.54
            return String(format: "%.0f\"", inches)
        }
        return "\(Int(cm)) cm"
    }
}

// MARK: - Resort Notification Row

struct ResortNotificationRow: View {
    let resortId: String
    @ObservedObject var viewModel: NotificationSettingsViewModel
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
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

                            Text(formatThreshold(viewModel.getResortSetting(resortId)?.freshSnowThresholdCm ?? viewModel.snowThresholdCm))
                                .frame(width: 55, alignment: .trailing)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Toggle("Event Alerts", isOn: binding(for: \.eventNotificationsEnabled))
                    .font(.subheadline)

                Toggle("Powder Day Alerts", isOn: binding(for: \.powderAlertsEnabled))
                    .font(.subheadline)

                if viewModel.getResortSetting(resortId)?.powderAlertsEnabled ?? true {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Powder Threshold")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        HStack {
                            Slider(
                                value: powderThresholdBinding,
                                in: 15...50,
                                step: 1
                            )

                            Text(formatThreshold(viewModel.getResortSetting(resortId)?.powderThresholdCm ?? viewModel.powderThreshold))
                                .frame(width: 55, alignment: .trailing)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
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

    private var powderThresholdBinding: Binding<Double> {
        Binding(
            get: {
                viewModel.getResortSetting(resortId)?.powderThresholdCm ?? viewModel.powderThreshold
            },
            set: { newValue in
                viewModel.updateResortSetting(resortId: resortId, powderThresholdCm: newValue)
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
                case \.powderAlertsEnabled:
                    return viewModel.powderAlerts
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
                case \.powderAlertsEnabled:
                    viewModel.updateResortSetting(resortId: resortId, powderAlertsEnabled: newValue)
                default:
                    break
                }
            }
        )
    }

    private func formatThreshold(_ cm: Double) -> String {
        if userPreferencesManager.preferredUnits.snowDepth == .inches {
            let inches = cm / 2.54
            return String(format: "%.0f\"", inches)
        }
        return "\(Int(cm)) cm"
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
    @Published var powderAlerts = true
    @Published var forecastAlerts = true
    @Published var weeklySummary = false
    @Published var snowThresholdCm: Double = 1.0
    @Published var powderThreshold: Double = 15.0
    @Published var forecastThreshold: Double = 10.0
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
            powderAlerts = settings.powderAlerts
            forecastAlerts = settings.forecastAlerts
            weeklySummary = settings.weeklySummary
            snowThresholdCm = settings.defaultSnowThresholdCm
            powderThreshold = settings.powderSnowThresholdCm
            forecastThreshold = settings.forecastSnowThresholdCm
            gracePeriodHours = settings.gracePeriodHours
            resortSettings = settings.resortSettings
        } catch {
            notifSettingsLog.error("Failed to load notification settings: \(error)")
            // Use defaults if loading fails
        }
    }

    func saveSettings() {
        // Track global notification setting changes
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "notifications_enabled", enabled: notificationsEnabled)
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "fresh_snow_alerts", enabled: freshSnowAlerts)
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "powder_alerts", enabled: powderAlerts)
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "event_alerts", enabled: eventAlerts)
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "thaw_freeze_alerts", enabled: thawFreezeAlerts)
        AnalyticsService.shared.trackNotificationSettingChanged(setting: "forecast_alerts", enabled: forecastAlerts)

        Task {
            do {
                let update = NotificationSettingsUpdate(
                    notificationsEnabled: notificationsEnabled,
                    freshSnowAlerts: freshSnowAlerts,
                    eventAlerts: eventAlerts,
                    thawFreezeAlerts: thawFreezeAlerts,
                    powderAlerts: powderAlerts,
                    forecastAlerts: forecastAlerts,
                    weeklySummary: weeklySummary,
                    defaultSnowThresholdCm: snowThresholdCm,
                    powderSnowThresholdCm: powderThreshold,
                    forecastSnowThresholdCm: forecastThreshold,
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
        eventNotificationsEnabled: Bool? = nil,
        powderAlertsEnabled: Bool? = nil,
        powderThresholdCm: Double? = nil
    ) {
        // Create or update resort settings
        var settings = resortSettings[resortId] ?? ResortNotificationSettings(
            resortId: resortId,
            freshSnowEnabled: freshSnowAlerts,
            freshSnowThresholdCm: snowThresholdCm,
            eventNotificationsEnabled: eventAlerts,
            powderAlertsEnabled: powderAlerts
        )

        if let freshSnowEnabled {
            settings.freshSnowEnabled = freshSnowEnabled
            AnalyticsService.shared.trackResortAlertChanged(
                resortId: resortId, resortName: resortId, alertType: "fresh_snow", enabled: freshSnowEnabled
            )
        }
        if let freshSnowThresholdCm {
            settings.freshSnowThresholdCm = freshSnowThresholdCm
            AnalyticsService.shared.trackResortAlertThresholdChanged(
                resortId: resortId, alertType: "fresh_snow", thresholdCm: freshSnowThresholdCm
            )
        }
        if let eventNotificationsEnabled {
            settings.eventNotificationsEnabled = eventNotificationsEnabled
            AnalyticsService.shared.trackResortAlertChanged(
                resortId: resortId, resortName: resortId, alertType: "events", enabled: eventNotificationsEnabled
            )
        }
        if let powderAlertsEnabled {
            settings.powderAlertsEnabled = powderAlertsEnabled
            AnalyticsService.shared.trackResortAlertChanged(
                resortId: resortId, resortName: resortId, alertType: "powder", enabled: powderAlertsEnabled
            )
        }
        if let powderThresholdCm {
            settings.powderThresholdCm = powderThresholdCm
            AnalyticsService.shared.trackResortAlertThresholdChanged(
                resortId: resortId, alertType: "powder", thresholdCm: powderThresholdCm
            )
        }

        resortSettings[resortId] = settings

        // Save to backend
        Task {
            do {
                let update = ResortNotificationSettingsUpdate(
                    freshSnowEnabled: settings.freshSnowEnabled,
                    freshSnowThresholdCm: settings.freshSnowThresholdCm,
                    eventNotificationsEnabled: settings.eventNotificationsEnabled,
                    powderAlertsEnabled: settings.powderAlertsEnabled,
                    powderThresholdCm: settings.powderThresholdCm
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

        isSendingTest = true
        testResult = nil

        Task {
            do {
                let result = try await apiClient.sendTestPushNotification()
                var msg = result.message
                if let tokensFound = result.tokensFound {
                    msg += " (\(tokensFound) token(s))"
                }
                if let results = result.results {
                    let failures = results.filter { $0.status == "failed" }
                    for f in failures {
                        msg += "\nFailed: \(f.error ?? "unknown error")"
                    }
                }
                testResult = TestResult(success: true, message: msg)
                // Refresh bell badge after backend stores the notification
                try? await Task.sleep(for: .seconds(1))
                NotificationCenter.default.post(name: .didReceiveForegroundNotification, object: nil)
            } catch {
                testResult = TestResult(success: false, message: error.localizedDescription)
            }
            isSendingTest = false
        }
    }

    func triggerNotificationProcessor() {
        guard !isSendingTest else { return }

        isSendingTest = true
        testResult = nil

        Task {
            do {
                let result = try await apiClient.triggerNotificationProcessor()
                testResult = TestResult(success: true, message: result.message)
            } catch {
                testResult = TestResult(success: false, message: error.localizedDescription)
            }
            isSendingTest = false
        }
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
            .environmentObject(UserPreferencesManager.shared)
    }
}
