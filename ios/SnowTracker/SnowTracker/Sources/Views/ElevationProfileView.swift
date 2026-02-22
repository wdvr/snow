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
                    Text(elevation.formattedElevation(prefs: prefs))
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
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription(level: level, elevation: elevation, condition: condition))
    }

    private func accessibilityDescription(level: String, elevation: ElevationPoint?, condition: WeatherCondition?) -> String {
        var parts = ["\(level.capitalized) elevation"]
        if let elevation {
            parts.append(elevation.formattedElevation(prefs: prefs))
        }
        if let condition {
            parts.append(condition.snowQuality.displayName)
            parts.append(condition.formattedTemperature(prefs))
            parts.append("fresh snow \(WeatherCondition.formatSnow(condition.freshSnowCm, prefs: prefs))")
        } else {
            parts.append("no data available")
        }
        return parts.joined(separator: ", ")
    }
}

// MARK: - Mountain Shape

private struct ElevationMountainShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let w = rect.width
        let h = rect.height

        // Natural mountain silhouette: asymmetric with smooth curves
        path.move(to: CGPoint(x: w * 0.45, y: 0)) // Peak (slightly left of center)

        // Right slope — steeper face with gentle curve
        path.addQuadCurve(
            to: CGPoint(x: w * 0.72, y: h * 0.4),
            control: CGPoint(x: w * 0.58, y: h * 0.15)
        )
        // Right shoulder — subtle ridge
        path.addQuadCurve(
            to: CGPoint(x: w * 0.88, y: h * 0.65),
            control: CGPoint(x: w * 0.78, y: h * 0.48)
        )
        // Right foot — gentle runout
        path.addQuadCurve(
            to: CGPoint(x: w, y: h),
            control: CGPoint(x: w * 0.95, y: h * 0.82)
        )

        // Base
        path.addLine(to: CGPoint(x: 0, y: h))

        // Left slope — gentler, longer approach
        path.addQuadCurve(
            to: CGPoint(x: w * 0.18, y: h * 0.55),
            control: CGPoint(x: w * 0.06, y: h * 0.78)
        )
        path.addQuadCurve(
            to: CGPoint(x: w * 0.45, y: 0),
            control: CGPoint(x: w * 0.3, y: h * 0.18)
        )

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
