import SwiftUI

struct SuggestEditView: View {
    let resortId: String
    let resortName: String

    @Environment(\.dismiss) private var dismiss
    @State private var section: String = ""
    @State private var suggestion: String = ""
    @State private var isSubmitting: Bool = false
    @State private var showingSuccessAlert: Bool = false
    @State private var showingErrorAlert: Bool = false
    @State private var errorMessage: String = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Text("Resort")
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text(resortName)
                            .foregroundStyle(.primary)
                    }
                }

                Section {
                    TextField("e.g. Elevation, Lift count, Trail map", text: $section)
                        .textInputAutocapitalization(.sentences)
                } header: {
                    Text("What needs updating?")
                } footer: {
                    Text("Which section or field has incorrect information?")
                }

                Section {
                    TextEditor(text: $suggestion)
                        .frame(minHeight: 120)
                } header: {
                    Text("Suggested Correction")
                } footer: {
                    if suggestion.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 && !suggestion.isEmpty {
                        Text("Please provide at least 10 characters")
                            .foregroundStyle(.red)
                    } else {
                        Text("Describe the correct information as you know it.")
                    }
                }

                Section {
                    Button(action: submitSuggestion) {
                        HStack {
                            Spacer()
                            if isSubmitting {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle())
                            } else {
                                Text("Submit Suggestion")
                            }
                            Spacer()
                        }
                    }
                    .disabled(!isValid || isSubmitting)
                    .accessibilityIdentifier(AccessibilityID.SuggestEdit.submitButton)
                }
            }
            .navigationTitle("Suggest an Edit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                AnalyticsService.shared.trackScreen("SuggestEdit", screenClass: "SuggestEditView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("SuggestEdit")
            }
            .alert("Suggestion Sent!", isPresented: $showingSuccessAlert) {
                Button("OK") {
                    dismiss()
                }
            } message: {
                Text("Thank you for helping us keep resort information accurate!")
            }
            .alert("Error", isPresented: $showingErrorAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(errorMessage)
            }
        }
    }

    private var isValid: Bool {
        !section.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        suggestion.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
    }

    private func submitSuggestion() {
        isSubmitting = true

        let formattedMessage = """
        [Resort Edit Suggestion]
        Resort: \(resortName) (\(resortId))
        Section: \(section.trimmingCharacters(in: .whitespacesAndNewlines))

        Suggested correction:
        \(suggestion.trimmingCharacters(in: .whitespacesAndNewlines))
        """

        Task {
            do {
                try await APIClient.shared.submitFeedback(
                    FeedbackSubmission(
                        subject: "Resort Edit: \(resortName) - \(section.trimmingCharacters(in: .whitespacesAndNewlines))",
                        message: formattedMessage,
                        email: nil,
                        appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
                        buildNumber: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1",
                        deviceModel: getDeviceModel(),
                        iosVersion: UIDevice.current.systemVersion
                    )
                )
                await MainActor.run {
                    isSubmitting = false
                    showingSuccessAlert = true
                    AnalyticsService.shared.trackFeedbackSubmitted(type: "resort_edit")
                }
            } catch {
                await MainActor.run {
                    isSubmitting = false
                    errorMessage = "Failed to submit suggestion: \(error.localizedDescription)"
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
    SuggestEditView(resortId: "whistler-blackcomb", resortName: "Whistler Blackcomb")
}
