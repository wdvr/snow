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
struct SnowTrackerApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var snowConditionsManager = SnowConditionsManager()
    @StateObject private var pushNotificationService = PushNotificationService.shared
    @ObservedObject private var authService = AuthenticationService.shared
    @ObservedObject private var userPreferencesManager = UserPreferencesManager.shared
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
                // Auto-authenticate in screenshot/demo mode
                if ProcessInfo.processInfo.arguments.contains("SCREENSHOT_MODE") ||
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
            .onOpenURL { url in
                // Handle Google Sign-In callback URL
                _ = authService.handleURL(url)
            }
            .onChange(of: authService.isAuthenticated) { _, isAuthenticated in
                if isAuthenticated {
                    // Skip onboarding in screenshot/demo mode
                    let isTestMode = ProcessInfo.processInfo.arguments.contains("SCREENSHOT_MODE") ||
                                     ProcessInfo.processInfo.arguments.contains("DEMO_DATA")
                    showOnboarding = isTestMode ? false : !userPreferencesManager.hasCompletedOnboarding

                    // Request notification permissions when user is authenticated
                    Task {
                        await pushNotificationService.requestAuthorization()
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
    @ObservedObject private var authService = AuthenticationService.shared
    @ObservedObject private var pushService = PushNotificationService.shared
    @ObservedObject private var networkMonitor = NetworkMonitor.shared
    @State private var selectedTab = 0
    @State private var deepLinkResort: Resort?

    var body: some View {
        VStack(spacing: 0) {
            if !networkMonitor.isConnected {
                OfflineBanner(cachedDataAge: snowConditionsManager.cachedDataAge)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            TabView(selection: $selectedTab) {
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

                ChatView()
                    .tabItem {
                        Image(systemName: "bubble.left.and.text.bubble.right")
                        Text("Ask AI")
                    }
                    .tag(4)

                SettingsView()
                    .environmentObject(authService)
                    .tabItem {
                        Image(systemName: "gear")
                        Text("Settings")
                    }
                    .tag(5)
            }
            .tint(.blue)
        }
        .animation(.easeInOut(duration: 0.3), value: networkMonitor.isConnected)
        .onAppear {
            snowConditionsManager.loadInitialData()
        }
        .onChange(of: pushService.pendingResortId) { _, resortId in
            guard let resortId else { return }
            // Find the resort and navigate to it
            if let resort = snowConditionsManager.resorts.first(where: { $0.id == resortId }) {
                selectedTab = 0
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
}
