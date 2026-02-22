import Charts
import SwiftUI

struct SnowHistoryView: View {
    let resortId: String
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    @StateObject private var viewModel = SnowHistoryViewModel()

    private var prefs: UnitPreferences {
        userPreferencesManager.preferredUnits
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with season total
            headerRow

            if viewModel.isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else if viewModel.history.isEmpty {
                Text("No history data available yet")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 100)
            } else {
                // Snowfall bar chart
                snowfallChart

                // Season stats row
                if let summary = viewModel.seasonSummary {
                    seasonStatsRow(summary)
                }
            }
        }
        .padding()
        .cardStyle()
        .task {
            await viewModel.loadHistory(resortId: resortId)
        }
    }

    // MARK: - Header

    private var headerRow: some View {
        HStack {
            Text("Snow History")
                .font(.headline)
            Spacer()
            if let total = viewModel.seasonSummary?.totalSnowfallCm, total > 0 {
                Text(formatSnow(total))
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.blue)
                Text("this season")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Chart

    private var snowfallChart: some View {
        Chart(viewModel.history) { day in
            BarMark(
                x: .value("Date", day.chartDate, unit: .day),
                y: .value("Snowfall", snowValue(day.snowfall24hCm))
            )
            .foregroundStyle(
                day.snowfall24hCm >= 15
                    ? Color.blue
                    : Color.blue.opacity(0.6)
            )
        }
        .chartYAxisLabel(prefs.snowDepth == .centimeters ? "cm" : "in")
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day())
            }
        }
        .frame(height: 180)
    }

    // MARK: - Season Stats

    private func seasonStatsRow(_ summary: SeasonSummary) -> some View {
        HStack(spacing: 16) {
            statItem(title: "Snow Days", value: "\(summary.snowDays)")
            statItem(title: "Best Day", value: formatBestDay(summary.bestDay))
            if let avg = summary.avgQualityScore {
                statItem(title: "Avg Quality", value: String(format: "%.1f", avg))
            }
            statItem(title: "Days Tracked", value: "\(summary.daysTracked)")
        }
        .font(.caption)
    }

    private func statItem(title: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .fontWeight(.semibold)
                .foregroundStyle(.primary)
            Text(title)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value)")
    }

    // MARK: - Formatting Helpers

    private func formatSnow(_ cm: Double) -> String {
        WeatherCondition.formatSnow(cm, prefs: prefs)
    }

    private func snowValue(_ cm: Double) -> Double {
        switch prefs.snowDepth {
        case .centimeters:
            return cm
        case .inches:
            return cm / 2.54
        }
    }

    private func formatBestDay(_ day: DailySnowHistory?) -> String {
        guard let day else { return "-" }
        return formatSnow(day.snowfall24hCm)
    }
}
