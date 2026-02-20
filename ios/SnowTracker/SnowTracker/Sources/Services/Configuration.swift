import Foundation

/// Environment configuration for the Snow Tracker app
/// Maps to Pulumi stacks: dev, staging, prod
enum AppEnvironment: String, CaseIterable {
    case development = "dev"
    case staging = "staging"
    case production = "prod"

    /// Whether this is a debug or TestFlight build (for showing debug UI)
    /// TestFlight builds have a sandbox receipt, App Store builds have a production receipt
    static var isDebugOrTestFlight: Bool {
        #if DEBUG
        return true
        #else
        // TestFlight builds have a receipt file named "sandboxReceipt"
        // App Store builds have a receipt file named "receipt"
        return Bundle.main.appStoreReceiptURL?.lastPathComponent == "sandboxReceipt"
        #endif
    }

    var displayName: String {
        switch self {
        case .development: return "Development"
        case .staging: return "Staging"
        case .production: return "Production"
        }
    }

    /// API base URL for each environment
    /// Using custom subdomains of powderchaserapp.com
    var apiBaseURL: URL {
        switch self {
        case .development:
            // Dev environment - use dev subdomain
            return URL(string: "https://dev.api.powderchaserapp.com")!
        case .staging:
            // Staging subdomain
            return URL(string: "https://staging.api.powderchaserapp.com")!
        case .production:
            // Production API
            return URL(string: "https://api.powderchaserapp.com")!
        }
    }

    var cognitoUserPoolId: String {
        switch self {
        case .development:
            return "us-west-2_dev" // Replace with actual dev pool ID after Pulumi deployment
        case .staging:
            return "us-west-2_staging" // Replace with actual staging pool ID
        case .production:
            return "us-west-2_prod" // Replace with actual prod pool ID
        }
    }

    var cognitoClientId: String {
        switch self {
        case .development:
            return "dev-client-id" // Replace after Pulumi deployment
        case .staging:
            return "staging-client-id"
        case .production:
            return "prod-client-id"
        }
    }
}

/// App configuration singleton
/// Handles environment selection and custom API URL overrides
@MainActor
class AppConfiguration: ObservableObject {
    static let shared = AppConfiguration()

    // UserDefaults keys
    private let customAPIURLKey = "com.snowtracker.customAPIURL"
    private let useCustomAPIKey = "com.snowtracker.useCustomAPI"
    private let selectedEnvironmentKey = "com.snowtracker.selectedEnvironment"

    /// The default environment based on build configuration
    let defaultEnvironment: AppEnvironment

    /// Currently selected environment (can be changed in debug builds)
    @Published var selectedEnvironment: AppEnvironment {
        didSet {
            UserDefaults.standard.set(selectedEnvironment.rawValue, forKey: selectedEnvironmentKey)
        }
    }

    /// Whether to use a custom API URL instead of the environment URL
    @Published var useCustomAPI: Bool {
        didSet {
            UserDefaults.standard.set(useCustomAPI, forKey: useCustomAPIKey)
        }
    }

    /// Custom API URL string (for local development or testing)
    @Published var customAPIURLString: String {
        didSet {
            UserDefaults.standard.set(customAPIURLString, forKey: customAPIURLKey)
        }
    }

    private init() {
        // Determine default environment based on build configuration
        #if DEBUG
        // Use staging for debug builds since dev environment is not deployed
        self.defaultEnvironment = .staging
        #else
        // Both TestFlight and App Store builds use production
        self.defaultEnvironment = .production
        #endif

        // Load saved environment preference (debug builds only)
        #if DEBUG
        if let savedEnv = UserDefaults.standard.string(forKey: selectedEnvironmentKey),
           let env = AppEnvironment(rawValue: savedEnv) {
            self.selectedEnvironment = env
        } else {
            self.selectedEnvironment = defaultEnvironment
        }
        #else
        self.selectedEnvironment = defaultEnvironment
        #endif

        // Load custom API settings
        self.useCustomAPI = UserDefaults.standard.bool(forKey: useCustomAPIKey)
        self.customAPIURLString = UserDefaults.standard.string(forKey: customAPIURLKey) ?? ""
    }

    /// The current API base URL to use
    var apiBaseURL: URL {
        // Custom URL takes precedence if enabled and valid
        if useCustomAPI, !customAPIURLString.isEmpty, let customURL = URL(string: customAPIURLString) {
            return customURL
        }
        return selectedEnvironment.apiBaseURL
    }

    /// Whether this is a debug build
    var isDebug: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }

    /// Whether environment switching is allowed (debug builds only)
    var canSwitchEnvironment: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }

    /// Whether currently using a custom API URL
    var isUsingCustomAPI: Bool {
        useCustomAPI && !customAPIURLString.isEmpty
    }

    /// Display string for current configuration
    var currentConfigurationDisplay: String {
        if isUsingCustomAPI {
            return "Custom: \(customAPIURLString)"
        }
        return selectedEnvironment.displayName
    }

    /// Reset to default settings
    func resetToDefault() {
        selectedEnvironment = defaultEnvironment
        useCustomAPI = false
        customAPIURLString = ""
    }

    /// Validate a URL string
    func validateURL(_ urlString: String) -> Bool {
        guard let url = URL(string: urlString) else { return false }
        return url.scheme == "http" || url.scheme == "https"
    }

    /// Set environment (only works in debug builds)
    func setEnvironment(_ environment: AppEnvironment) {
        #if DEBUG
        selectedEnvironment = environment
        #endif
    }
}
