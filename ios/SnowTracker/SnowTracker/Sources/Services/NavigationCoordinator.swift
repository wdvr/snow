import SwiftUI

@MainActor
final class NavigationCoordinator: ObservableObject {
    @Published var selectedTab: Int = 0
    @Published var mapTargetResort: Resort?

    func showOnMap(_ resort: Resort) {
        mapTargetResort = resort
        selectedTab = 1 // Map tab
    }
}
