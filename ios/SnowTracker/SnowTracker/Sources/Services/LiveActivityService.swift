import ActivityKit
import Foundation
import os.log

/// Manages Live Activities for snow resort conditions.
/// Starts, updates, and ends activities from the main app.
@MainActor
final class LiveActivityService: ObservableObject {
    static let shared = LiveActivityService()

    @Published private(set) var activeResortId: String?

    private let logger = Logger(subsystem: "com.snowtracker.app", category: "LiveActivity")

    private init() {
        // Clean up any stale activities on launch
        cleanupStaleActivities()
    }

    /// Whether Live Activities are supported on this device.
    var isSupported: Bool {
        ActivityAuthorizationInfo().areActivitiesEnabled
    }

    /// Whether a Live Activity is currently running for the given resort.
    func isActive(for resortId: String) -> Bool {
        activeResortId == resortId
    }

    /// Start a Live Activity for a resort.
    func start(
        resortId: String,
        resortName: String,
        resortLocation: String,
        freshSnowCm: Double,
        temperatureCelsius: Double,
        snowQuality: String,
        snowScore: Int?
    ) {
        guard isSupported else {
            logger.warning("Live Activities not supported on this device")
            return
        }

        // End any existing activity first
        if activeResortId != nil {
            endAll()
        }

        let attributes = SnowActivityAttributes(
            resortId: resortId,
            resortName: resortName,
            resortLocation: resortLocation
        )

        let state = SnowActivityAttributes.ContentState(
            freshSnowCm: freshSnowCm,
            temperatureCelsius: temperatureCelsius,
            snowQuality: snowQuality,
            snowScore: snowScore,
            lastUpdated: Date()
        )

        let content = ActivityContent(state: state, staleDate: Date().addingTimeInterval(3600))

        do {
            _ = try Activity.request(
                attributes: attributes,
                content: content,
                pushType: nil
            )
            activeResortId = resortId
            logger.info("Started Live Activity for \(resortName)")
        } catch {
            logger.error("Failed to start Live Activity: \(error.localizedDescription)")
        }
    }

    /// Update the Live Activity with new conditions.
    func update(
        freshSnowCm: Double,
        temperatureCelsius: Double,
        snowQuality: String,
        snowScore: Int?
    ) {
        guard let activity = currentActivity() else { return }

        let state = SnowActivityAttributes.ContentState(
            freshSnowCm: freshSnowCm,
            temperatureCelsius: temperatureCelsius,
            snowQuality: snowQuality,
            snowScore: snowScore,
            lastUpdated: Date()
        )

        let content = ActivityContent(state: state, staleDate: Date().addingTimeInterval(3600))

        Task {
            await activity.update(content)
            logger.info("Updated Live Activity")
        }
    }

    /// End the Live Activity for a specific resort.
    func end(resortId: String) {
        guard activeResortId == resortId else { return }
        endAll()
    }

    /// End all Live Activities.
    func endAll() {
        Task {
            for activity in Activity<SnowActivityAttributes>.activities {
                await activity.end(nil, dismissalPolicy: .immediate)
            }
            activeResortId = nil
            logger.info("Ended all Live Activities")
        }
    }

    // MARK: - Private

    private func currentActivity() -> Activity<SnowActivityAttributes>? {
        Activity<SnowActivityAttributes>.activities.first
    }

    private func cleanupStaleActivities() {
        Task {
            let activities = Activity<SnowActivityAttributes>.activities
            if !activities.isEmpty {
                logger.info("Cleaning up \(activities.count) stale activities on launch")
                for activity in activities {
                    await activity.end(nil, dismissalPolicy: .immediate)
                }
            }
        }
    }
}
