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
                    .foregroundColor(.primary)
                    .cornerRadius(12)
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
                    if let termsURL = URL(string: "https://snow-tracker.com/terms") {
                        Link("Terms of Service", destination: termsURL)
                    }
                    Text("and")
                        .foregroundColor(.secondary)
                    if let privacyURL = URL(string: "https://snow-tracker.com/privacy") {
                        Link("Privacy Policy", destination: privacyURL)
                    }
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

                                // Always show email or a placeholder
                                Text(user.emailDisplay)
                                    .font(.caption)
                                    .foregroundColor(.secondary)

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
            .task {
                // Refresh user info from backend to get latest email
                await authService.refreshUserInfo()
            }
        }
    }
}

// NotificationSettingsView moved to NotificationSettingsView.swift

// MARK: - Google Logo View

struct GoogleLogoView: View {
    // Official Google brand colors
    private let googleBlue = Color(red: 66/255, green: 133/255, blue: 244/255)
    private let googleGreen = Color(red: 52/255, green: 168/255, blue: 83/255)
    private let googleYellow = Color(red: 251/255, green: 188/255, blue: 5/255)
    private let googleRed = Color(red: 234/255, green: 67/255, blue: 53/255)

    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let radius = min(size.width, size.height) / 2
            let strokeWidth = radius * 0.35
            let innerRadius = radius - strokeWidth / 2

            // Green arc (bottom, from 45° to 135°)
            var greenPath = Path()
            greenPath.addArc(center: center, radius: innerRadius,
                            startAngle: .degrees(45), endAngle: .degrees(135),
                            clockwise: false)
            context.stroke(greenPath, with: .color(googleGreen), lineWidth: strokeWidth)

            // Yellow arc (bottom left, from 135° to 225°)
            var yellowPath = Path()
            yellowPath.addArc(center: center, radius: innerRadius,
                             startAngle: .degrees(135), endAngle: .degrees(225),
                             clockwise: false)
            context.stroke(yellowPath, with: .color(googleYellow), lineWidth: strokeWidth)

            // Red arc (top left, from 225° to 315° - stops before horizontal bar)
            var redPath = Path()
            redPath.addArc(center: center, radius: innerRadius,
                          startAngle: .degrees(225), endAngle: .degrees(315),
                          clockwise: false)
            context.stroke(redPath, with: .color(googleRed), lineWidth: strokeWidth)

            // Blue arc (right side only, from -45° to 45°)
            var bluePath = Path()
            bluePath.addArc(center: center, radius: innerRadius,
                           startAngle: .degrees(-45), endAngle: .degrees(45),
                           clockwise: false)
            context.stroke(bluePath, with: .color(googleBlue), lineWidth: strokeWidth)

            // Blue horizontal bar extending from center to right (the G opening)
            let barHeight = strokeWidth
            let barRect = CGRect(
                x: center.x,
                y: center.y - barHeight / 2,
                width: radius * 0.6,
                height: barHeight
            )
            context.fill(Path(barRect), with: .color(googleBlue))
        }
        .frame(width: 20, height: 20)
    }
}

#Preview("Welcome") {
    WelcomeView()
}

#Preview("Profile") {
    ProfileView()
}
