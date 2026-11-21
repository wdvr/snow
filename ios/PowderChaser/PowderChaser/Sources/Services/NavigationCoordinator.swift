import SwiftUI

@MainActor
final class NavigationCoordinator: ObservableObject {
    @Published var selectedTab: Int = 0
    @Published var mapTargetResort: Resort?
    /// Presents the AI chat sheet (from the floating button or a toolbar button)
    @Published var showingChat = false

    func showOnMap(_ resort: Resort) {
        selectedTab = 1 // Switch to Map tab first
        // Delay setting the target so the map view is rendered and ready
        Task {
            try? await Task.sleep(nanoseconds: 100_000_000) // 100ms
            mapTargetResort = resort
        }
    }
}
