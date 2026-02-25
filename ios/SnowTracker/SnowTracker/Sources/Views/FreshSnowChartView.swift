import Charts
import SwiftUI

struct FreshSnowChartView: View {
    let resortId: String
    let elevation: ElevationLevel
    let condition: WeatherCondition
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var timelineResponse: TimelineResponse?
    @State private var isLoading = true

    // Aggregate timeline points to daily
    private var dailyData: [DailySnowData] {
        guard let response = timelineResponse else { return [] }
        // Group by date, sum snowfall, get min/max temp
        var byDate: [String: (snowfall: Double, minTemp: Double, maxTemp: Double, isForecast: Bool)] = [:]
        for point in response.timeline {
            if var existing = byDate[point.date] {
                existing.snowfall += point.snowfallCm
                existing.minTemp = min(existing.minTemp, point.temperatureC)
                existing.maxTemp = max(existing.maxTemp, point.temperatureC)
                byDate[point.date] = existing
            } else {
                byDate[point.date] = (point.snowfallCm, point.temperatureC, point.temperatureC, point.isForecast)
            }
        }
        return byDate.sorted { $0.key < $1.key }.map { date, data in
            DailySnowData(date: date, snowfallCm: data.snowfall, minTempC: data.minTemp, maxTempC: data.maxTemp, isForecast: data.isForecast)
        }
    }

    // Calculate freeze line date from condition.lastFreezeThawHoursAgo
    private var freezeDate: String? {
        guard let hoursAgo = condition.lastFreezeThawHoursAgo, hoursAgo > 0 else { return nil }
        let freezeTime = Date().addingTimeInterval(-hoursAgo * 3600)
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: freezeTime)
    }

    private var freshSnowTotal: Double {
        condition.snowfallAfterFreezeCm ?? condition.freshSnowCm
    }

    private var prefs: UnitPreferences { userPreferencesManager.preferredUnits }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "snowflake.circle")
                    .foregroundStyle(.cyan)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Fresh Powder")
                        .font(.headline)
                    Text("\(WeatherCondition.formatSnow(freshSnowTotal, prefs: prefs)) since last freeze")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }

            if !dailyData.isEmpty {
                Chart {
                    // Snowfall bars
                    ForEach(dailyData) { day in
                        if let dateVal = day.dateValue {
                            BarMark(
                                x: .value("Date", dateVal, unit: .day),
                                y: .value("Snow", day.snowfallDisplay(prefs))
                            )
                            .foregroundStyle(day.isForecast ? Color.cyan.opacity(0.4) : Color.cyan.opacity(0.8))
                        }
                    }

                    // Temperature range area
                    ForEach(dailyData) { day in
                        if let dateVal = day.dateValue {
                            AreaMark(
                                x: .value("Date", dateVal, unit: .day),
                                yStart: .value("Min", day.minTempDisplay(prefs)),
                                yEnd: .value("Max", day.maxTempDisplay(prefs))
                            )
                            .foregroundStyle(.red.opacity(0.1))
                        }
                    }

                    // Freeze line
                    if let freezeDate = freezeDate,
                       let freezeDay = dailyData.first(where: { $0.date == freezeDate }),
                       let freezeDateVal = freezeDay.dateValue {
                        RuleMark(x: .value("Freeze", freezeDateVal, unit: .day))
                            .foregroundStyle(.orange)
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                            .annotation(position: .top, alignment: .leading) {
                                Text("Last freeze")
                                    .font(.caption2)
                                    .foregroundStyle(.orange)
                            }
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .day, count: 3)) { value in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxisLabel(prefs.temperature == .celsius ? "°C / cm" : "°F / in")
                .frame(height: 200)
            } else if !isLoading {
                Text("No timeline data available")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            }
        }
        .cardStyle()
        .task(id: "\(resortId)-\(elevation.rawValue)-fresh") {
            await loadTimeline()
        }
    }

    private func loadTimeline() async {
        isLoading = true
        do {
            timelineResponse = try await APIClient.shared.getTimeline(for: resortId, elevation: elevation)
        } catch {
            // Silently fail -- chart is supplementary
        }
        isLoading = false
    }
}

// MARK: - Daily Snow Data Model

struct DailySnowData: Identifiable {
    let date: String // yyyy-MM-dd
    let snowfallCm: Double
    let minTempC: Double
    let maxTempC: Double
    let isForecast: Bool

    var id: String { date }

    private static let dateParser: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let shortFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "MMM d"
        return f
    }()

    var dateValue: Date? {
        Self.dateParser.date(from: date)
    }

    var shortDate: String {
        guard let dateObj = dateValue else { return date }
        return Self.shortFormatter.string(from: dateObj)
    }

    func snowfallDisplay(_ prefs: UnitPreferences) -> Double {
        prefs.snowDepth == .inches ? snowfallCm / 2.54 : snowfallCm
    }

    func minTempDisplay(_ prefs: UnitPreferences) -> Double {
        prefs.temperature == .fahrenheit ? minTempC * 9.0 / 5.0 + 32.0 : minTempC
    }

    func maxTempDisplay(_ prefs: UnitPreferences) -> Double {
        prefs.temperature == .fahrenheit ? maxTempC * 9.0 / 5.0 + 32.0 : maxTempC
    }
}
