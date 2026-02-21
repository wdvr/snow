import Foundation
import Network
import os.log

private let networkLog = Logger(subsystem: "com.snowtracker.app", category: "NetworkMonitor")

/// Monitors network connectivity using NWPathMonitor.
/// Publishes connection status changes on the main actor so SwiftUI views
/// can react immediately (e.g. showing an offline banner).
@MainActor
final class NetworkMonitor: ObservableObject {
    static let shared = NetworkMonitor()

    @Published var isConnected: Bool = true
    @Published var isExpensive: Bool = false

    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "com.snowtracker.networkmonitor")

    private init() {
        startMonitoring()
    }

    private func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                guard let self else { return }
                let wasConnected = self.isConnected
                self.isConnected = path.status == .satisfied
                self.isExpensive = path.isExpensive

                if wasConnected != self.isConnected {
                    networkLog.debug("Network status changed: connected=\(self.isConnected), expensive=\(self.isExpensive)")
                }
            }
        }
        monitor.start(queue: monitorQueue)
        networkLog.debug("NetworkMonitor started")
    }
}
