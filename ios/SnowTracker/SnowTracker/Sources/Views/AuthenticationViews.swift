import SwiftUI
import AuthenticationServices

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

            // Sign in button
            VStack(spacing: 16) {
                SignInWithAppleButton(.signIn) { request in
                    request.requestedScopes = [.email, .fullName]
                } onCompletion: { result in
                    // Handled by AuthenticationService
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 50)
                .cornerRadius(12)
                .padding(.horizontal, 40)

                // Skip button for development
                #if DEBUG
                Button("Continue as Guest") {
                    // Skip auth for testing
                }
                .foregroundColor(.secondary)
                #endif

                if let error = authService.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }
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
        .onTapGesture {
            authService.signInWithApple()
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
