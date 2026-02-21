import SwiftUI
import AuthenticationServices
import GoogleSignInSwift

struct WelcomeView: View {
    @ObservedObject private var authService = AuthenticationService.shared

    var body: some View {
        VStack(spacing: 30) {
            Spacer()

            // App icon and title
            VStack(spacing: 16) {
                Image(systemName: "snowflake")
                    .font(.system(size: 80))
                    .foregroundStyle(.blue)

                Text("Powder Chaser")
                    .font(.largeTitle)
                    .fontWeight(.bold)

                Text("Track snow conditions at your favorite ski resorts")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            Spacer()

            // Sign in buttons
            VStack(spacing: 16) {
                // Sign in with Apple
                SignInWithAppleButton(.signIn) { request in
                    request.requestedScopes = [.email, .fullName]
                } onCompletion: { result in
                    switch result {
                    case .success(let authorization):
                        if let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential {
                            // The AuthenticationService delegate handles this
                            _ = appleIDCredential
                        }
                    case .failure:
                        // Error is handled by AuthenticationService delegate
                        break
                    }
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 50)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.horizontal, 40)

                // Sign in with Google - using standard Google branding
                Button {
                    authService.signInWithGoogle()
                } label: {
                    HStack(spacing: 12) {
                        // Google "G" logo using the colored G
                        GoogleLogoView()
                            .frame(width: 20, height: 20)

                        Text("Sign in with Google")
                            .font(.system(size: 17, weight: .medium))
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Color(.systemBackground))
                    .foregroundStyle(.primary)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color(.systemGray4), lineWidth: 1)
                    )
                }
                .padding(.horizontal, 40)

                // Loading indicator
                if authService.isLoading {
                    ProgressView()
                        .padding(.top, 8)
                }

                // Error message
                if let error = authService.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }

                // Skip button
                Button {
                    authService.continueWithoutSignIn()
                } label: {
                    Text("Continue without signing in")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 8)
            }

            Spacer()
        }
    }
}

// NotificationSettingsView moved to NotificationSettingsView.swift

// MARK: - Google Logo View

struct GoogleLogoView: View {
    var body: some View {
        Image("GoogleLogo")
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: 20, height: 20)
    }
}

#Preview("Welcome") {
    WelcomeView()
}
