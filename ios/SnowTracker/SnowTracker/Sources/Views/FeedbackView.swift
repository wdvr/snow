import SwiftUI

struct FeedbackView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var subject: String = ""
    @State private var message: String = ""
    @State private var email: String = ""
    @State private var isSubmitting: Bool = false
    @State private var showingSuccessAlert: Bool = false
    @State private var showingErrorAlert: Bool = false
    @State private var errorMessage: String = ""

    var body: some View {
        Form {
            Section {
                TextField("Subject", text: $subject)
                    .autocapitalization(.sentences)

                TextEditor(text: $message)
                    .frame(minHeight: 150)
            } header: {
                Text("Your Feedback")
            } footer: {
                if message.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 && !message.isEmpty {
                    Text("Message must be at least 10 characters")
                        .foregroundStyle(.red)
                } else {
                    Text("Please describe your feedback, bug report, or feature request in detail.")
                }
            }

            Section {
                TextField("Email (optional)", text: $email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            } header: {
                Text("Contact")
            } footer: {
                Text("Leave your email if you'd like us to follow up with you.")
            }

            Section {
                Button(action: submitFeedback) {
                    HStack {
                        Spacer()
                        if isSubmitting {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle())
                        } else {
                            Text("Submit Feedback")
                        }
                        Spacer()
                    }
                }
                .disabled(!isValid || isSubmitting)
            }
        }
        .navigationTitle("Send Feedback")
        .navigationBarTitleDisplayMode(.inline)
        .alert("Feedback Sent!", isPresented: $showingSuccessAlert) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text("Thank you for your feedback! We appreciate you taking the time to help us improve.")
        }
        .alert("Error", isPresented: $showingErrorAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage)
        }
    }

    private var isValid: Bool {
        !subject.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        message.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
    }

    private func submitFeedback() {
        isSubmitting = true

        Task {
            do {
                try await APIClient.shared.submitFeedback(
                    FeedbackSubmission(
                        subject: subject.trimmingCharacters(in: .whitespacesAndNewlines),
                        message: message.trimmingCharacters(in: .whitespacesAndNewlines),
                        email: email.isEmpty ? nil : email.trimmingCharacters(in: .whitespacesAndNewlines),
                        appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
                        buildNumber: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1",
                        deviceModel: getDeviceModel(),
                        iosVersion: UIDevice.current.systemVersion
                    )
                )
                await MainActor.run {
                    isSubmitting = false
                    showingSuccessAlert = true
                }
            } catch {
                await MainActor.run {
                    isSubmitting = false
                    errorMessage = "Failed to submit feedback: \(error.localizedDescription)"
                    showingErrorAlert = true
                }
            }
        }
    }

    private func getDeviceModel() -> String {
        var systemInfo = utsname()
        uname(&systemInfo)
        let modelCode = withUnsafePointer(to: &systemInfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) {
                String(validatingUTF8: $0)
            }
        }
        return modelCode ?? "Unknown"
    }
}

#Preview {
    NavigationStack {
        FeedbackView()
    }
}
