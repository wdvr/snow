import ActivityKit
import Foundation

/// Attributes for the Snow Resort Live Activity.
/// Shared between the main app and the widget extension.
struct SnowActivityAttributes: ActivityAttributes {
    /// Dynamic content that updates over time.
    struct ContentState: Codable, Hashable {
        let freshSnowCm: Double
        let temperatureCelsius: Double
        let snowQuality: String
        let snowScore: Int?
        let lastUpdated: Date
    }

    /// Static data set when the activity starts.
    let resortId: String
    let resortName: String
    let resortLocation: String
}
