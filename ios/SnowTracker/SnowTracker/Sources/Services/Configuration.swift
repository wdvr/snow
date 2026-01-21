import Foundation

enum Environment {
    case development
    case staging
    case production

    var apiBaseURL: URL {
        switch self {
        case .development:
            // Use localhost for simulator, or ngrok URL for device testing
            #if targetEnvironment(simulator)
            return URL(string: "http://localhost:8000")!
            #else
            return URL(string: "https://api-dev.snow-tracker.com")!
            #endif
        case .staging:
            return URL(string: "https://api-staging.snow-tracker.com")!
        case .production:
            return URL(string: "https://api.snow-tracker.com")!
        }
    }

    var cognitoUserPoolId: String {
        switch self {
        case .development:
            return "us-west-2_XXXXXXXXX" // Replace with actual dev pool ID
        case .staging:
            return "us-west-2_YYYYYYYYY" // Replace with actual staging pool ID
        case .production:
            return "us-west-2_ZZZZZZZZZ" // Replace with actual prod pool ID
        }
    }

    var cognitoClientId: String {
        switch self {
        case .development:
            return "dev-client-id"
        case .staging:
            return "staging-client-id"
        case .production:
            return "prod-client-id"
        }
    }
}

struct AppConfiguration {
    static var shared = AppConfiguration()

    let environment: Environment

    private init() {
        #if DEBUG
        self.environment = .development
        #else
        // Check for staging bundle ID or use production
        if Bundle.main.bundleIdentifier?.contains("staging") == true {
            self.environment = .staging
        } else {
            self.environment = .production
        }
        #endif
    }

    var apiBaseURL: URL {
        environment.apiBaseURL
    }

    var isDebug: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }
}
