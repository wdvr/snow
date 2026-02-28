import SwiftUI
import UserNotifications
#if canImport(FirebaseCore)
import FirebaseCore
#endif

// MARK: - App Delegate for Push Notifications

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // Set up push notification delegate
        UNUserNotificationCenter.current().delegate = PushNotificationService.shared
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        PushNotificationService.shared.didRegisterForRemoteNotifications(withDeviceToken: deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        PushNotificationService.shared.didFailToRegisterForRemoteNotifications(withError: error)
    }
}

@main
struct PowderChaserApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var snowConditionsManager = SnowConditionsManager()
    @StateObject private var pushNotificationService = PushNotificationService.shared
    @ObservedObject private var authService = AuthenticationService.shared
    @ObservedObject private var userPreferencesManager = UserPreferencesManager.shared
    @StateObject private var navigationCoordinator = NavigationCoordinator()
    @StateObject private var updateService = AppUpdateService()
    @State private var showSplash = true
    @State private var showOnboarding = false

    init() {
        // Initialize Firebase Analytics & Crashlytics
        AnalyticsService.shared.configure()

        // Configure API client
        APIClient.configure()
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                if authService.isAuthenticated {
                    if showOnboarding {
                        OnboardingView {
                            withAnimation {
                                showOnboarding = false
                            }
                        }
                        .environmentObject(userPreferencesManager)
                    } else {
                        MainTabView()
                            .environmentObject(snowConditionsManager)
                            .environmentObject(userPreferencesManager)
                            .environmentObject(pushNotificationService)
                            .environmentObject(navigationCoordinator)
                    }
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
                // Auto-authenticate in UI testing/screenshot/demo mode
                if ProcessInfo.processInfo.arguments.contains("UI_TESTING") ||
                   ProcessInfo.processInfo.arguments.contains("SCREENSHOT_MODE") ||
                   ProcessInfo.processInfo.arguments.contains("DEMO_DATA") {
                    authService.continueWithoutSignIn()
                    showOnboarding = false
                } else {
                    // Check if onboarding is needed
                    showOnboarding = !userPreferencesManager.hasCompletedOnboarding
                }

                // Show splash for minimum duration while data loads
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                    withAnimation(.easeOut(duration: 0.5)) {
                        showSplash = false
                    }
                }
            }
            .task {
                // Check for required app updates once per launch
                await updateService.checkForUpdate()
            }
            .fullScreenCover(item: $updateService.updateInfo) { info in
                ForceUpdateView(updateInfo: info) {
                    updateService.updateInfo = nil
                }
            }
            .onOpenURL { url in
                // Handle Google Sign-In callback URL
                _ = authService.handleURL(url)
            }
            .onChange(of: authService.isAuthenticated) { _, isAuthenticated in
                if isAuthenticated {
                    // Skip onboarding in UI testing/screenshot/demo mode
                    let isTestMode = ProcessInfo.processInfo.arguments.contains("UI_TESTING") ||
                                     ProcessInfo.processInfo.arguments.contains("SCREENSHOT_MODE") ||
                                     ProcessInfo.processInfo.arguments.contains("DEMO_DATA")
                    showOnboarding = isTestMode ? false : !userPreferencesManager.hasCompletedOnboarding

                    // Request notification permissions when user is authenticated (skip in test mode)
                    if !ProcessInfo.processInfo.arguments.contains("UI_TESTING") {
                        Task {
                            await pushNotificationService.requestAuthorization()
                        }
                    }
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                AnalyticsService.shared.trackAppBackground()
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                AnalyticsService.shared.trackAppForeground()
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willTerminateNotification)) { _ in
                AnalyticsService.shared.endSession()
            }
        }
    }
}

struct MainTabView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator
    @ObservedObject private var authService = AuthenticationService.shared
    @ObservedObject private var pushService = PushNotificationService.shared
    @ObservedObject private var networkMonitor = NetworkMonitor.shared
    @State private var deepLinkResort: Resort?
    @State private var showingChat = false
    @ObservedObject private var userPrefs = UserPreferencesManager.shared

    /// Number of favorited resorts with significant predicted snow (≥10cm in 48h)
    private var favoritesStormCount: Int {
        userPrefs.favoriteResorts.filter { resortId in
            guard let predicted = snowConditionsManager.snowQualitySummaries[resortId]?.predictedSnow48hCm else {
                return false
            }
            return predicted >= 10
        }.count
    }

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            VStack(spacing: 0) {
                if !networkMonitor.isConnected {
                    OfflineBanner(cachedDataAge: snowConditionsManager.cachedDataAge)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }

                TabView(selection: $navigationCoordinator.selectedTab) {
                    ResortListView(deepLinkResort: $deepLinkResort)
                        .tabItem {
                            Image(systemName: "mountain.2")
                            Text("Resorts")
                        }
                        .tag(0)

                    ResortMapView()
                        .tabItem {
                            Image(systemName: "map.fill")
                            Text("Map")
                        }
                        .tag(1)

                    BestSnowNearYouView()
                        .tabItem {
                            Image(systemName: "star.fill")
                            Text("Best Snow")
                        }
                        .tag(2)

                    FavoritesView()
                        .tabItem {
                            Image(systemName: "heart")
                            Text("Favorites")
                        }
                        .tag(3)
                        .badge(favoritesStormCount)

                    SettingsView()
                        .environmentObject(authService)
                        .tabItem {
                            Image(systemName: "gear")
                            Text("Settings")
                        }
                        .tag(4)
                }
                .tint(.blue)
            }

            // Floating AI chat bubble
            Button {
                showingChat = true
            } label: {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 56, height: 56)
                        .shadow(color: .blue.opacity(0.3), radius: 8, x: 0, y: 4)

                    Image(systemName: "sparkles")
                        .font(.system(size: 24, weight: .medium))
                        .foregroundStyle(.white)
                }
            }
            .padding(.trailing, 16)
            .padding(.bottom, 72) // Above the tab bar
            .accessibilityLabel("Ask AI about snow conditions")
            .accessibilityIdentifier(AccessibilityID.Tab.chatFAB)
        }
        .sheet(isPresented: $showingChat) {
            NavigationStack {
                ChatView()
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button("Close") {
                                showingChat = false
                            }
                        }
                    }
            }
            .environmentObject(snowConditionsManager)
            .environmentObject(UserPreferencesManager.shared)
            .environmentObject(navigationCoordinator)
        }
        .animation(.easeInOut(duration: 0.3), value: networkMonitor.isConnected)
        .onAppear {
            snowConditionsManager.loadInitialData()
        }
        .onChange(of: pushService.pendingResortId) { _, resortId in
            guard let resortId else { return }
            // Find the resort and navigate to it
            if let resort = snowConditionsManager.resorts.first(where: { $0.id == resortId }) {
                navigationCoordinator.selectedTab = 0
                deepLinkResort = resort
            }
            pushService.pendingResortId = nil
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
            // Pre-fetch favorite data when returning to foreground
            if networkMonitor.isConnected {
                Task {
                    await snowConditionsManager.prefetchFavoriteData()
                }
            }
        }
    }
}

#Preview("Main App") {
    MainTabView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
        .environmentObject(NavigationCoordinator())
}
