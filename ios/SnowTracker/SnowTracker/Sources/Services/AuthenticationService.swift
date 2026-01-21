import Foundation
import AuthenticationServices
import KeychainSwift

// MARK: - Authentication Service

@MainActor
class AuthenticationService: NSObject, ObservableObject {
    static let shared = AuthenticationService()

    @Published private(set) var isAuthenticated = false
    @Published private(set) var currentUser: AuthenticatedUser?
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    private let keychain = KeychainSwift()

    // Keychain keys
    private enum Keys {
        static let userIdentifier = "com.snowtracker.userIdentifier"
        static let authToken = "com.snowtracker.authToken"
        static let refreshToken = "com.snowtracker.refreshToken"
        static let userEmail = "com.snowtracker.userEmail"
        static let userName = "com.snowtracker.userName"
    }

    private override init() {
        super.init()
        checkExistingCredentials()
    }

    // MARK: - Public Methods

    func signInWithApple() {
        #if DEBUG
        // Check if Sign in with Apple is available (requires paid developer account)
        // Fall back to debug sign-in if not
        if !isSignInWithAppleAvailable {
            debugSignIn()
            return
        }
        #endif

        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.email, .fullName]

        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.performRequests()

        isLoading = true
        errorMessage = nil
    }

    #if DEBUG
    /// Check if Sign in with Apple is properly configured
    private var isSignInWithAppleAvailable: Bool {
        // Check if the entitlement exists
        guard let entitlements = Bundle.main.infoDictionary?["Entitlements"] as? [String: Any],
              let signInWithApple = entitlements["com.apple.developer.applesignin"] as? [String],
              !signInWithApple.isEmpty else {
            return false
        }
        return true
    }

    /// Debug-only sign in for development without paid Apple Developer account
    func debugSignIn(email: String = "developer@snowtracker.local", name: String = "Debug User") {
        isLoading = true
        errorMessage = nil

        let debugUserID = "debug-user-\(UUID().uuidString.prefix(8))"

        // Simulate network delay
        Task {
            try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

            keychain.set(debugUserID, forKey: Keys.userIdentifier)
            keychain.set(email, forKey: Keys.userEmail)
            keychain.set(name, forKey: Keys.userName)
            keychain.set("debug-token-\(debugUserID)", forKey: Keys.authToken)

            currentUser = AuthenticatedUser(
                id: debugUserID,
                email: email,
                fullName: name
            )
            isAuthenticated = true
            isLoading = false
        }
    }
    #endif

    func signOut() {
        // Clear keychain
        keychain.delete(Keys.userIdentifier)
        keychain.delete(Keys.authToken)
        keychain.delete(Keys.refreshToken)
        keychain.delete(Keys.userEmail)
        keychain.delete(Keys.userName)

        currentUser = nil
        isAuthenticated = false
    }

    // Nonisolated for use from APIClient
    nonisolated func getAuthToken() -> String? {
        KeychainSwift().get(Keys.authToken)
    }

    func checkExistingCredentials() {
        guard let userIdentifier = keychain.get(Keys.userIdentifier) else {
            isAuthenticated = false
            return
        }

        // Verify the credential is still valid
        let provider = ASAuthorizationAppleIDProvider()
        provider.getCredentialState(forUserID: userIdentifier) { [weak self] state, error in
            Task { @MainActor in
                switch state {
                case .authorized:
                    self?.restoreUserSession(userIdentifier: userIdentifier)
                case .revoked, .notFound:
                    self?.signOut()
                case .transferred:
                    // Handle account transfer between devices
                    self?.signOut()
                @unknown default:
                    self?.signOut()
                }
            }
        }
    }

    // MARK: - Private Methods

    private func restoreUserSession(userIdentifier: String) {
        let email = keychain.get(Keys.userEmail)
        let name = keychain.get(Keys.userName)

        currentUser = AuthenticatedUser(
            id: userIdentifier,
            email: email,
            fullName: name
        )
        isAuthenticated = true
    }

    private func handleSuccessfulSignIn(credential: ASAuthorizationAppleIDCredential) {
        let userIdentifier = credential.user

        // Store user identifier
        keychain.set(userIdentifier, forKey: Keys.userIdentifier)

        // Store email if provided (only on first sign in)
        if let email = credential.email {
            keychain.set(email, forKey: Keys.userEmail)
        }

        // Store full name if provided (only on first sign in)
        if let fullName = credential.fullName {
            let name = PersonNameComponentsFormatter().string(from: fullName)
            if !name.isEmpty {
                keychain.set(name, forKey: Keys.userName)
            }
        }

        // Get identity token for backend authentication
        if let identityTokenData = credential.identityToken,
           let identityToken = String(data: identityTokenData, encoding: .utf8) {
            // Send to backend for verification and get JWT
            Task {
                await authenticateWithBackend(appleToken: identityToken, userIdentifier: userIdentifier)
            }
        } else {
            // No token, but we can still proceed with local auth
            restoreUserSession(userIdentifier: userIdentifier)
            isLoading = false
        }
    }

    private func authenticateWithBackend(appleToken: String, userIdentifier: String) async {
        defer { isLoading = false }

        // TODO: Call backend /api/v1/auth/apple endpoint
        // For now, just store the Apple token as the auth token
        keychain.set(appleToken, forKey: Keys.authToken)
        restoreUserSession(userIdentifier: userIdentifier)
    }
}

// MARK: - ASAuthorizationControllerDelegate

extension AuthenticationService: ASAuthorizationControllerDelegate {
    nonisolated func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithAuthorization authorization: ASAuthorization
    ) {
        Task { @MainActor in
            isLoading = false

            switch authorization.credential {
            case let appleIDCredential as ASAuthorizationAppleIDCredential:
                handleSuccessfulSignIn(credential: appleIDCredential)
            default:
                errorMessage = "Unsupported credential type"
            }
        }
    }

    nonisolated func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithError error: Error
    ) {
        Task { @MainActor in
            isLoading = false

            if let authError = error as? ASAuthorizationError {
                switch authError.code {
                case .canceled:
                    // User canceled, not an error
                    break
                case .failed:
                    errorMessage = "Sign in failed. Please try again."
                case .invalidResponse:
                    errorMessage = "Invalid response from Apple. Please try again."
                case .notHandled:
                    errorMessage = "Sign in not handled. Please try again."
                case .notInteractive:
                    errorMessage = "Sign in requires interaction."
                case .unknown:
                    errorMessage = "An unknown error occurred."
                @unknown default:
                    errorMessage = "An error occurred: \(authError.localizedDescription)"
                }
            } else {
                errorMessage = error.localizedDescription
            }
        }
    }
}

// MARK: - Authenticated User Model

struct AuthenticatedUser: Identifiable, Codable {
    let id: String
    let email: String?
    let fullName: String?

    var displayName: String {
        if let name = fullName, !name.isEmpty {
            return name
        }
        if let email = email {
            return email
        }
        return "Snow Tracker User"
    }

    var initials: String {
        if let name = fullName, !name.isEmpty {
            let components = name.components(separatedBy: " ")
            let initials = components.compactMap { $0.first }.prefix(2)
            return String(initials).uppercased()
        }
        return "ST"
    }
}
