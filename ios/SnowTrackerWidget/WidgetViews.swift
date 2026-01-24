import SwiftUI

// MARK: - Resort Condition Row (Shared Component)

struct ResortConditionRow: View {
    let resort: ResortConditionData

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(resort.resortName)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .lineLimit(1)

                Text(resort.location)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                HStack(spacing: 4) {
                    Image(systemName: resort.snowQuality.icon)
                        .foregroundColor(resort.snowQuality.color)
                        .font(.caption)
                    Text(resort.snowQuality.displayName)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(resort.snowQuality.color)
                }

                HStack(spacing: 8) {
                    // Temperature
                    HStack(spacing: 2) {
                        Image(systemName: "thermometer")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text("\(Int(resort.temperature))°")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }

                    // Fresh snow
                    HStack(spacing: 2) {
                        Image(systemName: "snowflake")
                            .font(.caption2)
                            .foregroundColor(.cyan)
                        Text("\(Int(resort.freshSnow))cm")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    ResortConditionRow(resort: .sample)
        .padding()
        .background(Color(.systemBackground))
}
