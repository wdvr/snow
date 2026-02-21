import SwiftUI

/// Visual elevation profile showing conditions mapped to elevation bands
struct ElevationProfileView: View {
    let resort: Resort
    let conditions: [WeatherCondition]
    let prefs: UnitPreferences

    private var baseCondition: WeatherCondition? {
        conditions.first { $0.elevationLevel == "base" }
    }

    private var midCondition: WeatherCondition? {
        conditions.first { $0.elevationLevel == "mid" }
    }

    private var topCondition: WeatherCondition? {
        conditions.first { $0.elevationLevel == "top" }
    }

    private var elevationBands: [(level: String, elevation: ElevationPoint?, condition: WeatherCondition?)] {
        [
            ("top", resort.topElevation, topCondition),
            ("mid", resort.midElevation, midCondition),
            ("base", resort.baseElevation, baseCondition),
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Elevation Profile")
                .font(.headline)

            HStack(alignment: .bottom, spacing: 0) {
                // Mountain shape with elevation bands
                mountainProfile

                // Legend
                Spacer()
            }
        }
        .padding()
        .cardStyle()
    }

    private var mountainProfile: some View {
        HStack(spacing: 0) {
            // Mountain silhouette with colored bands
            VStack(spacing: 0) {
                ForEach(elevationBands, id: \.level) { band in
                    elevationBand(
                        level: band.level,
                        elevation: band.elevation,
                        condition: band.condition
                    )
                }
            }
            .clipShape(ElevationMountainShape())
            .frame(width: 120, height: 160)

            // Data labels
            VStack(spacing: 0) {
                ForEach(elevationBands, id: \.level) { band in
                    dataLabel(
                        level: band.level,
                        elevation: band.elevation,
                        condition: band.condition
                    )
                    .frame(height: 160.0 / 3.0)
                }
            }
            .padding(.leading, 12)
        }
    }

    private func elevationBand(level: String, elevation: ElevationPoint?, condition: WeatherCondition?) -> some View {
        let quality = condition?.snowQuality ?? .unknown
        return Rectangle()
            .fill(quality.color.opacity(0.3))
            .overlay(
                Rectangle()
                    .fill(quality.color.opacity(0.15))
            )
            .frame(height: 160.0 / 3.0)
    }

    private func dataLabel(level: String, elevation: ElevationPoint?, condition: WeatherCondition?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text(level.capitalized)
                    .font(.caption)
                    .fontWeight(.semibold)

                if let elevation {
                    Text(prefs.distance == .metric ? elevation.formattedMeters : elevation.formattedFeet)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            if let condition {
                HStack(spacing: 6) {
                    Image(systemName: condition.snowQuality.icon)
                        .font(.caption2)
                        .foregroundStyle(condition.snowQuality.color)

                    Text(condition.formattedTemperature(prefs))
                        .font(.caption2)

                    Text(WeatherCondition.formatSnow(condition.freshSnowCm, prefs: prefs))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            } else {
                Text("No data")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Mountain Shape

private struct ElevationMountainShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let w = rect.width
        let h = rect.height

        // Simple mountain silhouette: peak at top-center, widens toward base
        path.move(to: CGPoint(x: w * 0.5, y: 0)) // Peak
        path.addLine(to: CGPoint(x: w * 0.65, y: h * 0.15))
        path.addLine(to: CGPoint(x: w * 0.55, y: h * 0.2)) // Small notch
        path.addLine(to: CGPoint(x: w * 0.75, y: h * 0.35))
        path.addLine(to: CGPoint(x: w * 0.85, y: h * 0.5))
        path.addLine(to: CGPoint(x: w * 0.95, y: h * 0.7))
        path.addLine(to: CGPoint(x: w, y: h)) // Base right
        path.addLine(to: CGPoint(x: 0, y: h)) // Base left
        path.addLine(to: CGPoint(x: w * 0.05, y: h * 0.7))
        path.addLine(to: CGPoint(x: w * 0.15, y: h * 0.5))
        path.addLine(to: CGPoint(x: w * 0.25, y: h * 0.35))
        path.addLine(to: CGPoint(x: w * 0.45, y: h * 0.2))
        path.addLine(to: CGPoint(x: w * 0.35, y: h * 0.15))
        path.closeSubpath()

        return path
    }
}

// MARK: - Preview

#Preview("Elevation Profile") {
    ElevationProfileView(
        resort: Resort.sampleResorts[0],
        conditions: [],
        prefs: UnitPreferences()
    )
    .padding()
}
