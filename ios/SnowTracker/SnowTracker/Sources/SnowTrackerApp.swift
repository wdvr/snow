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
                // Check if onboarding is needed
                showOnboarding = !userPreferencesManager.hasCompletedOnboarding

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
                    // Check if onboarding is needed when user signs in
                    showOnboarding = !userPreferencesManager.hasCompletedOnboarding

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

    var body: some View {
        TabView {
            ResortListView()
                .tabItem {
                    Image(systemName: "mountain.2")
                    Text("Resorts")
                }

            ResortMapView()
                .tabItem {
                    Image(systemName: "map.fill")
                    Text("Map")
                }

            BestSnowNearYouView()
                .tabItem {
                    Image(systemName: "star.fill")
                    Text("Best Snow")
                }

            FavoritesView()
                .tabItem {
                    Image(systemName: "heart")
                    Text("Favorites")
                }

            SettingsView()
                .environmentObject(authService)
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

#Preview("Main App") {
    MainTabView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
