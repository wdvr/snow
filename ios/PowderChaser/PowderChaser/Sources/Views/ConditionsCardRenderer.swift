import SwiftUI

/// Generates a branded shareable image card showing resort conditions
struct ConditionsCardRenderer {

    /// Render a conditions card image for sharing
    @MainActor
    static func render(
        resort: Resort,
        condition: WeatherCondition?,
        quality: SnowQuality,
        snowScore: Int?,
        prefs: UnitPreferences
    ) -> UIImage {
        let view = ConditionsCardView(
            resortName: resort.name,
            location: resort.displayLocation,
            condition: condition,
            quality: quality,
            snowScore: snowScore,
            prefs: prefs
        )

        let renderer = ImageRenderer(content: view.frame(width: 400))
        renderer.scale = 3.0 // Retina quality
        return renderer.uiImage ?? UIImage()
    }
}

// MARK: - Card View (rendered to image)

private struct ConditionsCardView: View {
    let resortName: String
    let location: String
    let condition: WeatherCondition?
    let quality: SnowQuality
    let snowScore: Int?
    let prefs: UnitPreferences

    var body: some View {
        VStack(spacing: 0) {
            // Header with gradient
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "mountain.2.fill")
                        .font(.title3)
                    Text(resortName)
                        .font(.title2)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)

                Text(location)
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.8))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .padding(.horizontal, 16)
            .background(
                LinearGradient(
                    colors: [Color.blue, Color.blue.opacity(0.7)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )

            // Quality badge
            HStack(spacing: 12) {
                VStack(spacing: 4) {
                    Image(systemName: quality.icon)
                        .font(.title)
                        .foregroundStyle(quality.color)
                    Text(quality.displayName)
                        .font(.headline)
                        .foregroundStyle(quality.color)
                }

                if let score = snowScore {
                    Divider()
                        .frame(height: 40)

                    VStack(spacing: 4) {
                        Text("\(score)")
                            .font(.system(size: 32, weight: .bold))
                        Text("/ 100")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color(.systemBackground))

            // Conditions grid
            if let condition {
                Divider()

                HStack(spacing: 0) {
                    statCell(
                        icon: "thermometer",
                        label: "Temp",
                        value: condition.formattedTemperature(prefs)
                    )

                    Divider()
                        .frame(height: 50)

                    statCell(
                        icon: "snowflake",
                        label: "Fresh Snow",
                        value: condition.formattedFreshSnowWithPrefs(prefs)
                    )
                }
                .padding(.vertical, 12)
                .background(Color(.systemBackground))

                Divider()

                HStack(spacing: 0) {
                    if let depth = condition.snowDepthCm, depth > 0 {
                        statCell(
                            icon: "mountain.2.fill",
                            label: "Snow Depth",
                            value: WeatherCondition.formatSnow(depth, prefs: prefs)
                        )
                    } else {
                        statCell(
                            icon: "cloud.snow",
                            label: "24h Snowfall",
                            value: condition.formattedSnowfall24hWithPrefs(prefs)
                        )
                    }

                    Divider()
                        .frame(height: 50)

                    if let predicted = condition.predictedSnow48hCm, predicted >= 5 {
                        statCell(
                            icon: "cloud.snow.fill",
                            label: "48h Forecast",
                            value: "+\(WeatherCondition.formatSnow(predicted, prefs: prefs))"
                        )
                    } else {
                        statCell(
                            icon: "wind",
                            label: "Wind",
                            value: condition.formattedWindSpeedWithPrefs(prefs)
                        )
                    }
                }
                .padding(.vertical, 12)
                .background(Color(.systemBackground))
            }

            // Footer branding
            HStack {
                Image(systemName: "snowflake.circle.fill")
                    .foregroundStyle(.blue)
                Text("Powder Chaser")
                    .font(.caption)
                    .fontWeight(.medium)
                Spacer()
                Text(formattedDate)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(.secondarySystemBackground))
        }
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(.separator), lineWidth: 0.5)
        )
        .padding(16)
        .background(Color(.systemBackground))
    }

    private func statCell(icon: String, label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Label(value, systemImage: icon)
                .font(.subheadline)
                .fontWeight(.medium)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: Date())
    }
}
