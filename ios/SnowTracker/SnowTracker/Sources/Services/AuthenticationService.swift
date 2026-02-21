import Foundation
import AuthenticationServices
import GoogleSignIn
import KeychainSwift
import UIKit
import os.log

private let authLog = Logger(subsystem: "com.snowtracker.app", category: "Auth")

// MARK: - Authentication Provider

enum AuthProvider: String, Codable {
    case apple
    case google
    case guest
}

// MARK: - Authentication Service

@MainActor
class AuthenticationService: NSObject, ObservableObject {
    static let shared = AuthenticationService()

    @Published private(set) var isAuthenticated = false
    @Published private(set) var currentUser: AuthenticatedUser?
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    private let keychain = KeychainSwift()

    // Google Sign-In Client ID from Google Cloud Console
    static let googleClientID = "269334695221-p2i31pdp3n7ms7o7rpf6cb3vsdmc4ohs.apps.googleusercontent.com"

    private enum Keys {
        static let userIdentifier = "com.snowtracker.userIdentifier"
        static let authToken = "com.snowtracker.authToken"
        static let refreshToken = "com.snowtracker.refreshToken"
        static let userEmail = "com.snowtracker.userEmail"
        static let userName = "com.snowtracker.userName"
        static let authProvider = "com.snowtracker.authProvider"
    }

    private override init() {
        super.init()
        configureGoogleSignIn()
        checkExistingCredentials()
    }

    // MARK: - Google Sign-In Configuration

    private func configureGoogleSignIn() {
        guard Self.googleClientID != "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com" else {
            authLog.warning("Google Sign-In: Client ID not configured")
            return
        }
        // Google Sign-In is configured via Info.plist URL schemes
    }

    // MARK: - Sign In with Apple

    func signInWithApple() {
        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.email, .fullName]

        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.performRequests()

        isLoading = true
        errorMessage = nil
    }

    // MARK: - Sign In with Google

    func signInWithGoogle() {
        guard Self.googleClientID != "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com" else {
            errorMessage = "Google Sign-In not configured. Please contact support."
            return
        }

        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let rootViewController = windowScene.windows.first?.rootViewController else {
            errorMessage = "Unable to get root view controller"
            return
        }

        isLoading = true
        errorMessage = nil

        GIDSignIn.sharedInstance.signIn(withPresenting: rootViewController) { [weak self] result, error in
            // Extract values before entering Task to avoid sending non-Sendable types
            let errorMessage = error?.localizedDescription
            let isCanceled = (error as? NSError)?.code == GIDSignInError.canceled.rawValue
            let userID = result?.user.userID ?? UUID().uuidString
            let email = result?.user.profile?.email
            let fullName = result?.user.profile?.name
            let idToken = result?.user.idToken?.tokenString

            Task { @MainActor in
                self?.isLoading = false

                if let errorMessage = errorMessage {
                    if isCanceled {
                        // User canceled, not an error
                        return
                    }
                    self?.errorMessage = "Google Sign-In failed: \(errorMessage)"
                    return
                }

                guard let idToken = idToken else {
                    self?.errorMessage = "Failed to get Google user info"
                    return
                }

                self?.handleSuccessfulGoogleSignIn(
                    userID: userID,
                    email: email,
                    fullName: fullName,
                    idToken: idToken
                )
            }
        }
    }

    // MARK: - Continue Without Sign In

    func continueWithoutSignIn() {
        // Set as authenticated but with a guest user
        currentUser = AuthenticatedUser(
            id: "guest",
            email: nil,
            fullName: "Guest",
            provider: .guest
        )
        isAuthenticated = true
        keychain.set("guest", forKey: Keys.userIdentifier)
        keychain.set(AuthProvider.guest.rawValue, forKey: Keys.authProvider)
    }

    // MARK: - Sign Out

    func signOut() {
        // Get the provider to sign out from the correct service
        if let providerString = keychain.get(Keys.authProvider),
           let provider = AuthProvider(rawValue: providerString) {
            switch provider {
            case .google:
                GIDSignIn.sharedInstance.signOut()
            case .apple, .guest:
                // Apple/Guest don't have a sign out API - just clear local credentials
                break
            }
        }

        // Clear keychain
        keychain.delete(Keys.userIdentifier)
        keychain.delete(Keys.authToken)
        keychain.delete(Keys.refreshToken)
        keychain.delete(Keys.userEmail)
        keychain.delete(Keys.userName)
        keychain.delete(Keys.authProvider)

        currentUser = nil
        isAuthenticated = false
    }

    // MARK: - Token Access (for API calls)

    nonisolated func getAuthToken() -> String? {
        KeychainSwift().get(Keys.authToken)
    }

    // MARK: - Credential Checking

    func checkExistingCredentials() {
        guard let userIdentifier = keychain.get(Keys.userIdentifier),
              let providerString = keychain.get(Keys.authProvider),
              let provider = AuthProvider(rawValue: providerString) else {
            isAuthenticated = false
            return
        }

        switch provider {
        case .apple:
            checkAppleCredentialState(userIdentifier: userIdentifier)
        case .google:
            checkGoogleCredentialState()
        case .guest:
            restoreUserSession(userIdentifier: userIdentifier, provider: .guest)
        }
    }

    private func checkAppleCredentialState(userIdentifier: String) {
        let provider = ASAuthorizationAppleIDProvider()
        provider.getCredentialState(forUserID: userIdentifier) { [weak self] state, _ in
            Task { @MainActor in
                switch state {
                case .authorized:
                    self?.restoreUserSession(userIdentifier: userIdentifier, provider: .apple)
                case .revoked, .notFound, .transferred:
                    self?.signOut()
                @unknown default:
                    self?.signOut()
                }
            }
        }
    }

    private func checkGoogleCredentialState() {
        // Try to restore previous Google sign-in
        GIDSignIn.sharedInstance.restorePreviousSignIn { [weak self] user, error in
            // Extract values before entering Task to avoid sending non-Sendable types
            let userID = user?.userID ?? ""
            let hasError = error != nil || user == nil

            Task { @MainActor in
                if !hasError && !userID.isEmpty {
                    self?.restoreUserSession(
                        userIdentifier: userID,
                        provider: .google
                    )
                } else {
                    self?.signOut()
                }
            }
        }
    }

    // MARK: - Private Methods

    private func restoreUserSession(userIdentifier: String, provider: AuthProvider) {
        let email = keychain.get(Keys.userEmail)
        let name = keychain.get(Keys.userName)

        currentUser = AuthenticatedUser(
            id: userIdentifier,
            email: email,
            fullName: name,
            provider: provider
        )
        isAuthenticated = true
    }

    private func handleSuccessfulAppleSignIn(credential: ASAuthorizationAppleIDCredential) {
        let userIdentifier = credential.user

        // Store user identifier and provider
        keychain.set(userIdentifier, forKey: Keys.userIdentifier)
        keychain.set(AuthProvider.apple.rawValue, forKey: Keys.authProvider)

        // Store email from credential (only provided on first sign in)
        // This is critical - Apple only sends email once!
        if let email = credential.email, !email.isEmpty {
            keychain.set(email, forKey: Keys.userEmail)
        }

        // Extract name components (only provided on first sign in)
        var firstName: String?
        var lastName: String?
        if let fullName = credential.fullName {
            firstName = fullName.givenName
            lastName = fullName.familyName
            let name = PersonNameComponentsFormatter().string(from: fullName)
            if !name.isEmpty {
                keychain.set(name, forKey: Keys.userName)
            }
        }

        // Get identity token and authorization code for backend authentication
        if let identityTokenData = credential.identityToken,
           let identityToken = String(data: identityTokenData, encoding: .utf8) {
            let authCode = credential.authorizationCode.flatMap { String(data: $0, encoding: .utf8) }
            Task {
                await authenticateWithAppleBackend(
                    identityToken: identityToken,
                    authorizationCode: authCode,
                    firstName: firstName,
                    lastName: lastName,
                    userIdentifier: userIdentifier
                )
            }
        } else {
            restoreUserSession(userIdentifier: userIdentifier, provider: .apple)
            isLoading = false
        }
    }

    private func handleSuccessfulGoogleSignIn(userID: String, email: String?, fullName: String?, idToken: String) {
        // Store user identifier and provider
        keychain.set(userID, forKey: Keys.userIdentifier)
        keychain.set(AuthProvider.google.rawValue, forKey: Keys.authProvider)

        // Store email and name
        if let email = email {
            keychain.set(email, forKey: Keys.userEmail)
        }
        if let fullName = fullName {
            keychain.set(fullName, forKey: Keys.userName)
        }

        Task {
            await authenticateWithBackend(token: idToken, provider: .google, userIdentifier: userID)
        }
    }

    private func authenticateWithAppleBackend(
        identityToken: String,
        authorizationCode: String?,
        firstName: String?,
        lastName: String?,
        userIdentifier: String
    ) async {
        defer { isLoading = false }

        do {
            let response = try await APIClient.shared.authenticateWithApple(
                identityToken: identityToken,
                authorizationCode: authorizationCode,
                firstName: firstName,
                lastName: lastName
            )

            // Store tokens from backend
            keychain.set(response.accessToken, forKey: Keys.authToken)
            keychain.set(response.refreshToken, forKey: Keys.refreshToken)

            // Store user info from backend (includes private relay email!)
            if let email = response.user.email {
                keychain.set(email, forKey: Keys.userEmail)
            }
            if let name = [response.user.firstName, response.user.lastName]
                .compactMap({ $0 })
                .joined(separator: " ") as String?,
               !name.isEmpty {
                keychain.set(name, forKey: Keys.userName)
            }

            // Create user from backend response
            currentUser = AuthenticatedUser(
                id: response.user.userId,
                email: response.user.email,
                fullName: [response.user.firstName, response.user.lastName].compactMap { $0 }.joined(separator: " "),
                provider: .apple
            )
            isAuthenticated = true

        } catch {
            authLog.warning("Backend auth failed: \(error.localizedDescription). Using local auth.")
            // Fallback to local-only authentication - notifications still work without backend auth
            keychain.set(identityToken, forKey: Keys.authToken)

            // Read any previously stored email (from credential or prior backend auth)
            let storedEmail = keychain.get(Keys.userEmail)
            let storedName = keychain.get(Keys.userName)

            currentUser = AuthenticatedUser(
                id: userIdentifier,
                email: storedEmail,
                fullName: storedName,
                provider: .apple
            )
            isAuthenticated = true
        }
    }

    private func authenticateWithBackend(token: String, provider: AuthProvider, userIdentifier: String) async {
        defer { isLoading = false }

        // For Google, just store the token locally for now
        // TODO: Implement Google backend auth when needed
        keychain.set(token, forKey: Keys.authToken)
        restoreUserSession(userIdentifier: userIdentifier, provider: provider)
    }

    // MARK: - Refresh User Info

    /// Fetch current user info from backend and update local state
    /// Call this to refresh email and validate token
    func refreshUserInfo() async -> Bool {
        guard isAuthenticated else { return false }

        do {
            let userInfo = try await APIClient.shared.getCurrentUser()

            // Update stored email if available
            if let email = userInfo.email {
                keychain.set(email, forKey: Keys.userEmail)
            }
            if let firstName = userInfo.firstName {
                let fullName = [firstName, userInfo.lastName].compactMap { $0 }.joined(separator: " ")
                if !fullName.isEmpty {
                    keychain.set(fullName, forKey: Keys.userName)
                }
            }

            // Update current user
            currentUser = AuthenticatedUser(
                id: userInfo.userId,
                email: userInfo.email,
                fullName: [userInfo.firstName, userInfo.lastName].compactMap { $0 }.joined(separator: " "),
                provider: currentUser?.provider ?? .apple
            )

            return true
        } catch {
            authLog.error("Failed to refresh user info: \(error)")
            return false
        }
    }

    /// Check if the current auth token is valid
    var hasValidToken: Bool {
        guard let token = keychain.get(Keys.authToken), !token.isEmpty else {
            return false
        }
        // Check if it looks like a JWT (has 3 parts separated by dots)
        // Apple identity tokens and Google ID tokens are JWTs but may not be valid for our API
        return true
    }

    // MARK: - Handle URL (for Google Sign-In callback)

    func handleURL(_ url: URL) -> Bool {
        return GIDSignIn.sharedInstance.handle(url)
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
                handleSuccessfulAppleSignIn(credential: appleIDCredential)
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
                default:
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
    let provider: AuthProvider

    init(id: String, email: String?, fullName: String?, provider: AuthProvider = .apple) {
        self.id = id
        self.email = email
        self.fullName = fullName
        self.provider = provider
    }

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

    /// Display string for email, with appropriate placeholder for Apple users
    var emailDisplay: String {
        if let email = email, !email.isEmpty {
            return email
        }
        // For Apple users without email, show Apple ID reference
        if provider == .apple {
            // The user ID for Apple is their Apple user identifier
            // Show a truncated version or a friendly message
            let shortId = String(id.prefix(8))
            return "Apple ID (\(shortId)...)"
        }
        return "Email not available"
    }
}
