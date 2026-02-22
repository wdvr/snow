import SwiftUI

// MARK: - Timeline Card (Self-contained with loading)

struct TimelineCard: View {
    let resortId: String
    let elevation: ElevationLevel
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var timelineResponse: TimelineResponse?
    @State private var isLoading = true
    @State private var error: Error?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "calendar.badge.clock")
                    .foregroundStyle(.blue)
                Text("Conditions Timeline")
                    .font(.headline)
                Spacer()
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }

            if let response = timelineResponse {
                TimelineView(points: response.timeline, prefs: userPreferencesManager.preferredUnits)
            } else if isLoading {
                timelineLoadingSkeleton
            } else if error != nil {
                Text("Unable to load timeline")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(radius: 2)
        .task(id: "\(resortId)-\(elevation.rawValue)") {
            await loadTimeline()
        }
    }

    private var timelineLoadingSkeleton: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(0..<7, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(.systemGray5))
                        .frame(width: 72, height: 140)
                }
            }
        }
    }

    private func loadTimeline() async {
        isLoading = true
        error = nil
        do {
            timelineResponse = try await APIClient.shared.getTimeline(for: resortId, elevation: elevation)
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

// MARK: - Timeline View (Horizontal scrollable)

struct TimelineView: View {
    let points: [TimelinePoint]
    let prefs: UnitPreferences

    /// Group points by date for day headers
    private var groupedPoints: [(date: String, dayLabel: String, points: [TimelinePoint])] {
        var result: [(date: String, dayLabel: String, points: [TimelinePoint])] = []
        var currentDate = ""
        var currentPoints: [TimelinePoint] = []

        for point in points {
            if point.date != currentDate {
                if !currentPoints.isEmpty {
                    let label = dayLabel(for: currentDate, points: currentPoints)
                    result.append((date: currentDate, dayLabel: label, points: currentPoints))
                }
                currentDate = point.date
                currentPoints = [point]
            } else {
                currentPoints.append(point)
            }
        }
        if !currentPoints.isEmpty {
            let label = dayLabel(for: currentDate, points: currentPoints)
            result.append((date: currentDate, dayLabel: label, points: currentPoints))
        }
        return result
    }

    private func dayLabel(for date: String, points: [TimelinePoint]) -> String {
        if points.first?.isToday == true {
            return "Today"
        }
        return points.first?.dayOfWeek ?? ""
    }

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    /// Find the current time slot index for "Now" indicator
    private var currentPointIndex: Int? {
        let now = Date()
        let calendar = Calendar.current
        let currentHour = calendar.component(.hour, from: now)
        let todayStr = Self.dateFormatter.string(from: now)

        // Find the closest time slot to now
        for (index, point) in points.enumerated() {
            if point.date == todayStr {
                if currentHour < 10 && point.timeLabel == "morning" { return index }
                if currentHour >= 10 && currentHour < 14 && point.timeLabel == "midday" { return index }
                if currentHour >= 14 && point.timeLabel == "afternoon" { return index }
            }
        }
        return nil
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 0) {
                    ForEach(groupedPoints, id: \.date) { group in
                        VStack(alignment: .leading, spacing: 4) {
                            // Day header
                            Text(group.dayLabel)
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .foregroundStyle(group.points.first?.isToday == true ? .blue : .secondary)
                                .padding(.leading, 4)

                            HStack(spacing: 6) {
                                ForEach(group.points) { point in
                                    let isCurrentSlot = currentPointIndex.map { points[$0].id == point.id } ?? false
                                    TimelinePointCard(
                                        point: point,
                                        prefs: prefs,
                                        isCurrentSlot: isCurrentSlot
                                    )
                                    .id(point.id)
                                }
                            }
                        }
                        .padding(.trailing, 4)
                    }
                }
                .padding(.horizontal, 4)
            }
            .onAppear {
                // Scroll to "now" or today
                if let idx = currentPointIndex {
                    proxy.scrollTo(points[idx].id, anchor: .center)
                }
            }
        }
    }
}

// MARK: - Individual Timeline Point Card

struct TimelinePointCard: View {
    let point: TimelinePoint
    let prefs: UnitPreferences
    let isCurrentSlot: Bool
    @State private var showExplanation = false

    var body: some View {
        VStack(spacing: 4) {
            // Snow score + quality icon
            if let score = point.snowScore {
                Text("\(score)")
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                    .foregroundStyle(point.snowQuality.color)
            }

            Image(systemName: point.snowQuality.icon)
                .font(.title3)
                .foregroundStyle(point.snowQuality.color)

            Text(point.snowQuality.displayName)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundStyle(point.snowQuality.color)
                .lineLimit(1)

            Divider()
                .frame(width: 40)

            // Temperature
            Text(point.formattedTemperature(prefs))
                .font(.caption)
                .fontWeight(.semibold)

            // Wind
            if let wind = point.windSpeedKmh {
                HStack(spacing: 2) {
                    Image(systemName: "wind")
                        .font(.system(size: 9))
                    if prefs.distance == .metric {
                        Text("\(Int(wind))")
                            .font(.caption2)
                    } else {
                        Text("\(Int(wind * 0.621371))")
                            .font(.caption2)
                    }
                }
                .foregroundStyle(.secondary)
            }

            // Snowfall
            if point.snowfallCm > 0.1 {
                HStack(spacing: 2) {
                    Image(systemName: "snowflake")
                        .font(.system(size: 9))
                    Text(WeatherCondition.formatSnowShort(point.snowfallCm, prefs: prefs))
                        .font(.caption2)
                }
                .foregroundStyle(.cyan)
            }

            Divider()
                .frame(width: 40)

            // Time label
            Text(point.timeDisplay)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)

            // "Now" indicator
            if isCurrentSlot {
                Text("Now")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Color.blue))
            }

            // Explanation info button
            if point.explanation != nil {
                Button {
                    showExplanation = true
                } label: {
                    Image(systemName: "eye.fill")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Show conditions explanation")
            }
        }
        .frame(width: 68)
        .padding(.vertical, 8)
        .padding(.horizontal, 2)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(point.snowQuality.color.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(
                    isCurrentSlot ? Color.blue :
                        (point.isToday ? Color.blue.opacity(0.3) : Color.clear),
                    lineWidth: isCurrentSlot ? 2 : 1
                )
        )
        .opacity(point.isForecast ? 0.85 : 1.0)
        .popover(isPresented: $showExplanation) {
            if let explanation = point.explanation {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: point.snowQuality.icon)
                            .foregroundStyle(point.snowQuality.color)
                        Text(point.snowQuality.displayName)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundStyle(point.snowQuality.color)
                        if let score = point.snowScore {
                            Text("\(score)/100")
                                .font(.subheadline)
                                .fontWeight(.bold)
                                .foregroundStyle(point.snowQuality.color)
                        }
                    }
                    Text(explanation)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding()
                .frame(maxWidth: 260)
                .presentationCompactAdaptation(.popover)
            }
        }
    }
}

#Preview("Timeline Card") {
    TimelineCard(resortId: "whistler-blackcomb", elevation: .mid)
        .environmentObject(UserPreferencesManager.shared)
        .padding()
}
