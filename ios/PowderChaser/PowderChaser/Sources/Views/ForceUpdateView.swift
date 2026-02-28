import SwiftUI

/// Full-screen overlay shown when the app version is below the required minimum.
///
/// When `forceUpdate` is true the view cannot be dismissed — the user must update.
/// When `forceUpdate` is false a "Not Now" button lets the user continue.
struct ForceUpdateView: View {
    let updateInfo: AppUpdateInfo
    let onDismiss: (() -> Void)?

    var body: some View {
        ZStack {
            // Background gradient matching the splash screen style
            LinearGradient(
                gradient: Gradient(colors: [
                    Color(red: 0.1, green: 0.2, blue: 0.4),
                    Color(red: 0.2, green: 0.4, blue: 0.6),
                    Color(red: 0.4, green: 0.6, blue: 0.8),
                ]),
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 32) {
                Spacer()

                // App icon
                VStack(spacing: 20) {
                    ZStack {
                        Circle()
                            .fill(.white.opacity(0.15))
                            .frame(width: 130, height: 130)
                            .blur(radius: 8)

                        Image(systemName: "snowflake")
                            .font(.system(size: 64, weight: .light))
                            .foregroundStyle(.white)
                    }

                    Text("Powder Chaser")
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                }

                // Update message
                VStack(spacing: 12) {
                    Text("Update Required")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)

                    Text(updateInfo.updateMessage)
                        .font(.body)
                        .foregroundStyle(.white.opacity(0.85))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)

                    Text("Version \(updateInfo.latestVersion) is now available")
                        .font(.footnote)
                        .foregroundStyle(.white.opacity(0.6))
                        .padding(.top, 4)
                }

                Spacer()

                // Action buttons
                VStack(spacing: 14) {
                    Button {
                        UIApplication.shared.open(updateInfo.updateURL)
                    } label: {
                        Text("Update Now")
                            .font(.headline)
                            .foregroundStyle(Color(red: 0.1, green: 0.2, blue: 0.4))
                            .frame(maxWidth: .infinity)
                            .frame(height: 54)
                            .background(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    .padding(.horizontal, 40)

                    if !updateInfo.forceUpdate, let dismiss = onDismiss {
                        Button {
                            dismiss()
                        } label: {
                            Text("Not Now")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundStyle(.white.opacity(0.8))
                        }
                        .padding(.top, 4)
                    }
                }
                .padding(.bottom, 60)
            }
        }
        .interactiveDismissDisabled(updateInfo.forceUpdate)
    }
}

#Preview("Force Update") {
    ForceUpdateView(
        updateInfo: AppUpdateInfo(
            minimumVersion: "3.0.0",
            latestVersion: "3.0.0",
            updateMessage: "A new version of Powder Chaser is available with important improvements to snow quality tracking.",
            updateURL: URL(string: "https://apps.apple.com/app/id6758333173")!,
            forceUpdate: true
        ),
        onDismiss: nil
    )
}

#Preview("Optional Update") {
    ForceUpdateView(
        updateInfo: AppUpdateInfo(
            minimumVersion: "2.0.0",
            latestVersion: "3.0.0",
            updateMessage: "A new version of Powder Chaser is available with exciting new features.",
            updateURL: URL(string: "https://apps.apple.com/app/id6758333173")!,
            forceUpdate: false
        ),
        onDismiss: {}
    )
}
