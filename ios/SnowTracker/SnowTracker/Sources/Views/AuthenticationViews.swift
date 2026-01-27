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
                    .foregroundColor(.blue)

                Text("Snow Tracker")
                    .font(.largeTitle)
                    .fontWeight(.bold)

                Text("Track snow conditions at your favorite ski resorts")
                    .font(.body)
                    .foregroundColor(.secondary)
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
                .cornerRadius(12)
                .padding(.horizontal, 40)
                .onTapGesture {
                    authService.signInWithApple()
                }

                // Sign in with Google - using official Google Sign-In button
                GoogleSignInButton(scheme: .light, style: .wide, state: .normal) {
                    authService.signInWithGoogle()
                }
                .frame(height: 50)
                .cornerRadius(12)
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
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }

                // Skip button
                Button {
                    authService.continueWithoutSignIn()
                } label: {
                    Text("Continue without signing in")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 8)
            }

            Spacer()

            // Terms
            VStack(spacing: 4) {
                Text("By signing in, you agree to our")
                    .font(.caption)
                    .foregroundColor(.secondary)

                HStack {
                    Link("Terms of Service", destination: URL(string: "https://snow-tracker.com/terms")!)
                    Text("and")
                        .foregroundColor(.secondary)
                    Link("Privacy Policy", destination: URL(string: "https://snow-tracker.com/privacy")!)
                }
                .font(.caption)
            }
            .padding(.bottom, 20)
        }
    }
}

struct ProfileView: View {
    @ObservedObject private var authService = AuthenticationService.shared

    var body: some View {
        NavigationStack {
            List {
                if let user = authService.currentUser {
                    Section {
                        HStack {
                            // User avatar
                            ZStack {
                                Circle()
                                    .fill(Color.blue.opacity(0.2))
                                    .frame(width: 60, height: 60)

                                Text(user.initials)
                                    .font(.title2)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.blue)
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text(user.displayName)
                                    .font(.headline)

                                if let email = user.email {
                                    Text(email)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }

                                // Show auth provider
                                HStack(spacing: 4) {
                                    Image(systemName: user.provider == .apple ? "apple.logo" : "g.circle.fill")
                                        .font(.caption2)
                                    Text("Signed in with \(user.provider == .apple ? "Apple" : "Google")")
                                        .font(.caption2)
                                }
                                .foregroundColor(.secondary)
                            }
                            .padding(.leading, 8)
                        }
                        .padding(.vertical, 8)
                    }
                }

                Section("Preferences") {
                    NavigationLink {
                        SettingsView()
                    } label: {
                        Label("Settings", systemImage: "gear")
                    }

                    NavigationLink {
                        NotificationSettingsView()
                    } label: {
                        Label("Notifications", systemImage: "bell")
                    }
                }

                Section("Account") {
                    Button(role: .destructive) {
                        authService.signOut()
                    } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Profile")
        }
    }
}

struct NotificationSettingsView: View {
    @State private var snowAlerts = true
    @State private var conditionUpdates = true
    @State private var weeklySummary = false

    var body: some View {
        List {
            Section("Alerts") {
                Toggle("Snow Alerts", isOn: $snowAlerts)
                Toggle("Condition Updates", isOn: $conditionUpdates)
            }

            Section("Summaries") {
                Toggle("Weekly Summary", isOn: $weeklySummary)
            }

            Section(footer: Text("Snow alerts notify you when conditions at your favorite resorts improve. Condition updates provide real-time information about snow quality changes.")) {
                EmptyView()
            }
        }
        .navigationTitle("Notifications")
    }
}

#Preview("Welcome") {
    WelcomeView()
}

#Preview("Profile") {
    ProfileView()
}
