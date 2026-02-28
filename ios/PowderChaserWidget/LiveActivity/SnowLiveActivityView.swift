import ActivityKit
import SwiftUI
import WidgetKit

/// Live Activity configuration for snow resort conditions.
struct SnowLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SnowActivityAttributes.self) { context in
            // Lock Screen / StandBy banner
            lockScreenView(context: context)
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded regions
                DynamicIslandExpandedRegion(.leading) {
                    expandedLeading(context: context)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    expandedTrailing(context: context)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    expandedBottom(context: context)
                }
                DynamicIslandExpandedRegion(.center) {
                    expandedCenter(context: context)
                }
            } compactLeading: {
                // Compact leading - quality icon
                qualityIcon(for: context.state.snowQuality)
                    .font(.caption2)
            } compactTrailing: {
                // Compact trailing - fresh snow
                HStack(spacing: 2) {
                    Image(systemName: "snowflake")
                        .font(.caption2)
                    Text(formatSnow(context.state.freshSnowCm))
                        .font(.caption2)
                        .fontWeight(.medium)
                }
                .foregroundStyle(.cyan)
            } minimal: {
                // Minimal - just the quality icon
                qualityIcon(for: context.state.snowQuality)
                    .font(.caption2)
            }
        }
    }

    // MARK: - Lock Screen View

    @ViewBuilder
    private func lockScreenView(context: ActivityViewContext<SnowActivityAttributes>) -> some View {
        let prefs = WidgetUnitPreferences.load()

        HStack(spacing: 12) {
            // Left: resort info
            VStack(alignment: .leading, spacing: 4) {
                Text(context.attributes.resortName)
                    .font(.headline)
                    .fontWeight(.bold)
                    .lineLimit(1)

                Text(context.attributes.resortLocation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            // Right: conditions
            VStack(alignment: .trailing, spacing: 4) {
                // Quality badge
                HStack(spacing: 4) {
                    if let score = context.state.snowScore {
                        Text("\(score)")
                            .font(.subheadline.weight(.bold))
                            .fontDesign(.rounded)
                    }
                    qualityIcon(for: context.state.snowQuality)
                    Text(qualityDisplayName(context.state.snowQuality))
                        .font(.caption)
                        .fontWeight(.semibold)
                }
                .foregroundStyle(qualityColor(context.state.snowQuality))

                // Stats row
                HStack(spacing: 10) {
                    // Temperature
                    HStack(spacing: 2) {
                        Image(systemName: "thermometer")
                            .font(.caption2)
                        Text(prefs.formatTemperature(context.state.temperatureCelsius))
                            .font(.caption)
                    }
                    .foregroundStyle(.secondary)

                    // Fresh snow
                    HStack(spacing: 2) {
                        Image(systemName: "snowflake")
                            .font(.caption2)
                        Text(prefs.formatSnow(context.state.freshSnowCm))
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .foregroundStyle(.cyan)
                }
            }
        }
        .padding()
        .activityBackgroundTint(.black.opacity(0.6))
        .activitySystemActionForegroundColor(.white)
    }

    // MARK: - Dynamic Island Expanded

    @ViewBuilder
    private func expandedLeading(context: ActivityViewContext<SnowActivityAttributes>) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            qualityIcon(for: context.state.snowQuality)
                .font(.title3)
                .foregroundStyle(qualityColor(context.state.snowQuality))

            if let score = context.state.snowScore {
                Text("\(score)")
                    .font(.caption.weight(.bold))
                    .fontDesign(.rounded)
                    .foregroundStyle(qualityColor(context.state.snowQuality))
            }
        }
    }

    @ViewBuilder
    private func expandedTrailing(context: ActivityViewContext<SnowActivityAttributes>) -> some View {
        let prefs = WidgetUnitPreferences.load()

        VStack(alignment: .trailing, spacing: 2) {
            HStack(spacing: 2) {
                Image(systemName: "thermometer")
                    .font(.caption2)
                Text(prefs.formatTemperature(context.state.temperatureCelsius))
                    .font(.caption)
            }
            .foregroundStyle(.secondary)

            HStack(spacing: 2) {
                Image(systemName: "snowflake")
                    .font(.caption2)
                Text(prefs.formatSnow(context.state.freshSnowCm))
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundStyle(.cyan)
        }
    }

    @ViewBuilder
    private func expandedCenter(context: ActivityViewContext<SnowActivityAttributes>) -> some View {
        Text(context.attributes.resortName)
            .font(.subheadline)
            .fontWeight(.semibold)
            .lineLimit(1)
    }

    @ViewBuilder
    private func expandedBottom(context: ActivityViewContext<SnowActivityAttributes>) -> some View {
        HStack {
            Text(qualityDisplayName(context.state.snowQuality))
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(qualityColor(context.state.snowQuality))

            Spacer()

            Text("Updated \(context.state.lastUpdated, style: .relative) ago")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Helpers

    private func formatSnow(_ cm: Double) -> String {
        if cm >= 1 {
            return "\(Int(cm))cm"
        }
        return "0cm"
    }

    private func qualityIcon(for quality: String) -> Image {
        switch quality {
        case "champagne_powder": Image(systemName: "sparkles")
        case "powder_day": Image(systemName: "snowflake.circle")
        case "excellent": Image(systemName: "snowflake")
        case "great": Image(systemName: "cloud.snow")
        case "good": Image(systemName: "sun.max")
        case "decent", "fair": Image(systemName: "cloud.sun")
        case "mediocre", "slushy": Image(systemName: "cloud")
        case "poor": Image(systemName: "cloud.sleet")
        case "bad": Image(systemName: "exclamationmark.triangle")
        case "horrible": Image(systemName: "xmark.octagon.fill")
        default: Image(systemName: "questionmark.circle")
        }
    }

    private func qualityColor(_ quality: String) -> Color {
        switch quality {
        case "champagne_powder": Color(red: 0.1, green: 0.2, blue: 0.7)
        case "powder_day": Color(red: 0.2, green: 0.4, blue: 0.9)
        case "excellent": Color(red: 0.0, green: 0.65, blue: 0.35)
        case "great": .green
        case "good": Color(red: 0.4, green: 0.75, blue: 0.3)
        case "decent", "fair": .yellow
        case "mediocre", "slushy": .orange
        case "poor": Color(red: 0.8, green: 0.3, blue: 0.1)
        case "bad": .red
        case "horrible": Color(.label)
        default: .gray
        }
    }

    private func qualityDisplayName(_ quality: String) -> String {
        switch quality {
        case "champagne_powder": "Champagne Powder"
        case "powder_day": "Powder Day"
        case "excellent": "Excellent"
        case "great": "Great"
        case "good": "Good"
        case "decent", "fair": "Decent"
        case "mediocre", "slushy": "Mediocre"
        case "poor": "Poor"
        case "bad": "Bad"
        case "horrible": "Not Skiable"
        default: "Unknown"
        }
    }
}
