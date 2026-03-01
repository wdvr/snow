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

    // Calculate the date when the last ice crust formed (end of last thaw period).
    // `lastFreezeThawHoursAgo` tracks when the last sustained warm period ended —
    // after this point, any new snow is fresh powder on top of the ice crust.
    private var crustFormedDate: String? {
        guard let hoursAgo = condition.lastFreezeThawHoursAgo, hoursAgo > 0 else { return nil }
        let crustTime = Date().addingTimeInterval(-hoursAgo * 3600)
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: crustTime)
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
                    Text("Recent Snowfall")
                        .font(.headline)
                    Text("\(WeatherCondition.formatSnow(freshSnowTotal, prefs: prefs)) accumulated since last thaw")
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

                    // Ice crust line — marks when the last thaw ended and snow re-froze
                    if let crustDate = crustFormedDate,
                       let crustDay = dailyData.first(where: { $0.date == crustDate }),
                       let crustDateVal = crustDay.dateValue {
                        RuleMark(x: .value("Crust", crustDateVal, unit: .day))
                            .foregroundStyle(.orange)
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                            .annotation(position: .top, alignment: .leading) {
                                Text("Crust formed")
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
                .frame(height: 200)

                // Legend
                HStack(spacing: 16) {
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(.cyan.opacity(0.8))
                            .frame(width: 10, height: 10)
                        Text("Snowfall (\(prefs.snowDepth == .inches ? "in" : "cm"))")
                            .font(.caption2)
                    }
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(.red.opacity(0.2))
                            .frame(width: 10, height: 10)
                        Text("Temp range (\(prefs.temperature == .celsius ? "°C" : "°F"))")
                            .font(.caption2)
                    }
                }
                .foregroundStyle(.secondary)
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
