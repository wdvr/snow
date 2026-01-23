import SwiftUI
import Combine

// MARK: - Authentication Manager

@MainActor
class AuthenticationManager: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?

    func checkAuthenticationStatus() {
        // TODO: Implement Firebase Auth check
        isLoading = true
        // Simulate auth check
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            self.isAuthenticated = false // Set to true when implementing
            self.isLoading = false
        }
    }

    func signInWithApple() async {
        // TODO: Implement Apple Sign In
        isLoading = true
        defer { isLoading = false }

        // Simulate sign in
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        isAuthenticated = true
    }

    func signOut() {
        // TODO: Implement sign out
        isAuthenticated = false
        currentUser = nil
    }
}

// MARK: - Snow Conditions Manager

@MainActor
class SnowConditionsManager: ObservableObject {
    @Published var resorts: [Resort] = []
    @Published var conditions: [String: [WeatherCondition]] = [:]
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?

    private let apiClient = APIClient.shared

    func loadInitialData() {
        Task {
            await fetchResorts()
            await fetchAllConditions()
        }
    }

    func refreshData() async {
        await fetchAllConditions()
    }

    func refreshConditions() async {
        await fetchAllConditions()
    }

    func fetchResorts() async {
        isLoading = true
        defer { isLoading = false }

        do {
            // Try to fetch from API
            resorts = try await apiClient.getResorts()
            print("Loaded \(resorts.count) resorts from API")
            errorMessage = nil
        } catch {
            // Show error - don't fall back to fake data
            print("API error: \(error.localizedDescription)")
            resorts = []
            errorMessage = "Unable to load resorts - API unavailable"
        }
    }

    func fetchAllConditions() async {
        isLoading = true
        defer { isLoading = false }

        for resort in resorts {
            do {
                // Try to fetch from API
                let resortConditions = try await apiClient.getConditions(for: resort.id)
                conditions[resort.id] = resortConditions
            } catch {
                // Don't fall back to fake data - just leave empty
                print("API error for \(resort.id): \(error.localizedDescription)")
                conditions[resort.id] = []
            }
        }

        lastUpdated = Date()
    }

    func getLatestCondition(for resortId: String) -> WeatherCondition? {
        conditions[resortId]?.first
    }

    func getConditions(for resortId: String, at elevation: ElevationLevel) -> WeatherCondition? {
        conditions[resortId]?.first { $0.elevationLevel == elevation.rawValue }
    }
}

// MARK: - User Preferences Manager

@MainActor
class UserPreferencesManager: ObservableObject {
    static let shared = UserPreferencesManager()

    @Published var favoriteResorts: Set<String> = []
    @Published var preferredUnits: UnitPreferences = UnitPreferences()
    @Published var notificationSettings: NotificationSettings = NotificationSettings()

    private let apiClient = APIClient.shared
    private let favoritesKey = "com.snowtracker.favoriteResorts"

    init() {
        loadLocalPreferences()
    }

    func loadPreferences() async {
        loadLocalPreferences()
    }

    private func loadLocalPreferences() {
        // Load favorites from UserDefaults
        if let savedFavorites = UserDefaults.standard.array(forKey: favoritesKey) as? [String] {
            favoriteResorts = Set(savedFavorites)
        }
    }

    func toggleFavorite(resortId: String) {
        if favoriteResorts.contains(resortId) {
            favoriteResorts.remove(resortId)
        } else {
            favoriteResorts.insert(resortId)
        }

        saveLocalPreferences()
    }

    func isFavorite(resortId: String) -> Bool {
        favoriteResorts.contains(resortId)
    }

    private func saveLocalPreferences() {
        // Save favorites to UserDefaults
        UserDefaults.standard.set(Array(favoriteResorts), forKey: favoritesKey)
    }

    func savePreferences() async {
        saveLocalPreferences()
    }
}

// MARK: - Supporting Types

struct User: Codable {
    let id: String
    let email: String?
    let firstName: String?
    let lastName: String?
    let createdAt: String
}

struct UnitPreferences: Codable {
    var temperature: TemperatureUnit = .celsius
    var distance: DistanceUnit = .metric
    var snowDepth: SnowDepthUnit = .centimeters

    enum TemperatureUnit: String, CaseIterable, Codable {
        case celsius = "celsius"
        case fahrenheit = "fahrenheit"
    }

    enum DistanceUnit: String, CaseIterable, Codable {
        case metric = "metric"
        case imperial = "imperial"
    }

    enum SnowDepthUnit: String, CaseIterable, Codable {
        case centimeters = "cm"
        case inches = "inches"
    }
}

struct NotificationSettings: Codable {
    var snowAlerts: Bool = true
    var conditionUpdates: Bool = true
    var weeklySummary: Bool = false
}
