import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var selectedRegions: Set<String> = []
    var onComplete: () -> Void

    // Default regions (northern hemisphere) - selected by default
    private let northernHemisphereRegions: [SkiRegion] = [
        .naWest, .naRockies, .naEast, .alps, .scandinavia
    ]

    // Southern hemisphere regions - deselected by default
    private let southernHemisphereRegions: [SkiRegion] = [
        .japan, .oceania, .southAmerica
    ]

    init(onComplete: @escaping () -> Void) {
        self.onComplete = onComplete
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(spacing: 16) {
                Image(systemName: "snowflake")
                    .font(.system(size: 60))
                    .foregroundStyle(.blue)

                Text("Welcome to Powder Chaser")
                    .font(.largeTitle)
                    .fontWeight(.bold)

                // Algorithm value proposition
                VStack(spacing: 8) {
                    Text("Powered by our proprietary snow quality algorithm")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(.blue)

                    Text("We track fresh powder since the last ice layer, not just snowfall. Know the actual skiing conditions before you go.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }
                .padding(.vertical, 8)

                Text("Select the ski regions you want to track:")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            .padding(.top, 40)
            .padding(.bottom, 24)

            // Region selection
            ScrollView {
                VStack(spacing: 24) {
                    // Northern Hemisphere
                    RegionGroupView(
                        title: "Northern Hemisphere",
                        subtitle: "Season: November - April",
                        regions: northernHemisphereRegions,
                        selectedRegions: $selectedRegions
                    )

                    // Southern Hemisphere / Off-Season
                    RegionGroupView(
                        title: "Southern Hemisphere",
                        subtitle: "Season: June - October",
                        regions: southernHemisphereRegions,
                        selectedRegions: $selectedRegions
                    )
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 100) // Space for button
            }

            Spacer()

            // Continue button
            VStack(spacing: 12) {
                Button {
                    completeOnboarding()
                } label: {
                    Text("Continue")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .background(selectedRegions.isEmpty ? Color.gray : Color.blue)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(selectedRegions.isEmpty)
                .padding(.horizontal, 20)

                if selectedRegions.isEmpty {
                    Text("Select at least one region to continue")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.bottom, 40)
            .background(
                LinearGradient(
                    colors: [Color(.systemBackground).opacity(0), Color(.systemBackground)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .frame(height: 100)
                .allowsHitTesting(false),
                alignment: .top
            )
        }
        .onAppear {
            // Initialize with default selections (northern hemisphere regions)
            selectedRegions = Set(northernHemisphereRegions.map { $0.rawValue })
            AnalyticsService.shared.trackScreen("Onboarding", screenClass: "OnboardingView")
            AnalyticsService.shared.trackOnboardingStarted()
        }
    }

    private func completeOnboarding() {
        // Track onboarding completion
        AnalyticsService.shared.trackOnboardingCompleted(regionsSelected: selectedRegions.count)
        // Calculate hidden regions (inverse of selected)
        let allRegions = Set(SkiRegion.allCases.map { $0.rawValue })
        let hiddenRegions = allRegions.subtracting(selectedRegions)

        // Save to preferences
        userPreferencesManager.hiddenRegions = hiddenRegions
        userPreferencesManager.completeOnboarding()

        // Notify completion
        onComplete()
    }
}

// MARK: - Region Group View

struct RegionGroupView: View {
    let title: String
    let subtitle: String
    let regions: [SkiRegion]
    @Binding var selectedRegions: Set<String>

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)

                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 8) {
                ForEach(regions, id: \.self) { region in
                    RegionSelectionCard(
                        region: region,
                        isSelected: selectedRegions.contains(region.rawValue),
                        onTap: {
                            toggleRegion(region)
                        }
                    )
                }
            }
            .sensoryFeedback(.selection, trigger: selectionTrigger)
        }
    }

    @State private var selectionTrigger = false

    private func toggleRegion(_ region: SkiRegion) {
        let wasSelected = selectedRegions.contains(region.rawValue)
        withAnimation(.easeInOut(duration: 0.2)) {
            if wasSelected {
                selectedRegions.remove(region.rawValue)
            } else {
                selectedRegions.insert(region.rawValue)
            }
        }
        selectionTrigger.toggle()
        AnalyticsService.shared.trackOnboardingRegionToggled(region: region.rawValue, selected: !wasSelected)
    }
}

// MARK: - Region Selection Card

struct RegionSelectionCard: View {
    let region: SkiRegion
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                // Region icon
                Image(systemName: region.icon)
                    .font(.title2)
                    .foregroundStyle(isSelected ? .blue : .secondary)
                    .frame(width: 32)

                // Region info
                VStack(alignment: .leading, spacing: 2) {
                    Text(region.displayName)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundStyle(.primary)

                    Text(region.fullName)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Checkmark
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundStyle(isSelected ? .blue : Color(.systemGray4))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? Color.blue.opacity(0.1) : Color(.secondarySystemBackground))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(region.displayName), \(region.fullName)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityHint(isSelected ? "Double tap to deselect" : "Double tap to select")
    }
}

#Preview {
    OnboardingView {
        print("Onboarding completed")
    }
    .environmentObject(UserPreferencesManager.shared)
}
