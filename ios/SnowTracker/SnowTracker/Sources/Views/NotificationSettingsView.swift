import SwiftUI

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
                    }
            } header: {
                Text("Master Switch")
            } footer: {
                Text("Turn off to disable all push notifications from Snow Tracker.")
            }

            // Notification Types Section
            if viewModel.notificationsEnabled {
                Section {
                    Toggle("Fresh Snow Alerts", isOn: $viewModel.freshSnowAlerts)
                        .onChange(of: viewModel.freshSnowAlerts) { _, _ in
                            viewModel.saveSettings()
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
                        .onChange(of: viewModel.eventAlerts) { _, _ in
                            viewModel.saveSettings()
                        }
                } header: {
                    Text("Alert Types")
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Fresh Snow Alerts: Get notified when fresh snow falls at your favorite resorts.")
                        Text("Resort Events: Get notified about special events and offers at your favorite resorts.")
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
                            HStack {
                                Image(systemName: testResult.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                                    .foregroundStyle(testResult.success ? .green : .red)
                                Text(testResult.message)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
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

@MainActor
class NotificationSettingsViewModel: ObservableObject {
    @Published var isAuthorized = false
    @Published var notificationsEnabled = true
    @Published var freshSnowAlerts = true
    @Published var eventAlerts = true
    @Published var weeklySummary = false
    @Published var snowThresholdCm: Double = 1.0
    @Published var gracePeriodHours = 24
    @Published var isLoading = false

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
            weeklySummary = settings.weeklySummary
            snowThresholdCm = settings.defaultSnowThresholdCm
            gracePeriodHours = settings.gracePeriodHours
            resortSettings = settings.resortSettings
        } catch {
            print("Failed to load notification settings: \(error)")
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
                    weeklySummary: weeklySummary,
                    defaultSnowThresholdCm: snowThresholdCm,
                    gracePeriodHours: gracePeriodHours
                )
                try await apiClient.updateNotificationSettings(update)
            } catch {
                print("Failed to save notification settings: \(error)")
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
                print("Failed to save resort notification settings: \(error)")
            }
        }
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
            .environmentObject(UserPreferencesManager.shared)
    }
}
