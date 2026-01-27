import WidgetKit
import SwiftUI
import os.log

private let logger = Logger(subsystem: "com.snowtracker.app.widget", category: "BestResorts")

// MARK: - Best Resorts Widget

struct BestResortsWidget: Widget {
    let kind: String = "BestResortsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: BestResortsProvider()) { entry in
            BestResortsWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Best Snow Right Now")
        .description("Top 2 resorts with the best snow conditions.")
        .supportedFamilies([.systemMedium, .systemLarge])
    }
}

// MARK: - Timeline Provider

struct BestResortsProvider: TimelineProvider {
    func placeholder(in context: Context) -> BestResortsEntry {
        BestResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ]
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (BestResortsEntry) -> Void) {
        let entry = BestResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ]
        )
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping @Sendable (Timeline<BestResortsEntry>) -> Void) {
        logger.info("BestResortsWidget: Getting timeline...")
        Task { @MainActor in
            do {
                let resorts = try await WidgetDataService.shared.fetchBestResorts()
                logger.info("BestResortsWidget: Got \(resorts.count) resorts")
                let entry = BestResortsEntry(date: Date(), resorts: resorts)
                let nextUpdate = Calendar.current.date(byAdding: .hour, value: 1, to: Date())!
                let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
                completion(timeline)
            } catch {
                logger.error("BestResortsWidget: Error fetching data: \(error.localizedDescription)")
                let entry = BestResortsEntry(date: Date(), resorts: [])
                let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
                let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
                completion(timeline)
            }
        }
    }
}

// MARK: - Timeline Entry

struct BestResortsEntry: TimelineEntry {
    let date: Date
    let resorts: [ResortConditionData]
}

// MARK: - Widget View

struct BestResortsWidgetView: View {
    var entry: BestResortsEntry
    private let unitPreferences = WidgetUnitPreferences.load()

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "trophy.fill")
                    .foregroundColor(.yellow)
                    .font(.caption)
                Text("Best Snow Right Now")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                Spacer()
            }

            if entry.resorts.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "cloud.snow")
                            .font(.title2)
                            .foregroundColor(.secondary)
                        Text("No data available")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(Array(entry.resorts.prefix(2).enumerated()), id: \.element.resortId) { index, resort in
                    HStack(spacing: 8) {
                        // Rank badge
                        ZStack {
                            Circle()
                                .fill(index == 0 ? Color.yellow : Color.gray.opacity(0.3))
                                .frame(width: 24, height: 24)
                            Text("\(index + 1)")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundColor(index == 0 ? .black : .primary)
                        }

                        ResortConditionRow(resort: resort, unitPreferences: unitPreferences)
                    }

                    if index < entry.resorts.prefix(2).count - 1 {
                        Divider()
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding()
    }
}

// MARK: - Preview

#Preview(as: .systemMedium) {
    BestResortsWidget()
} timeline: {
    BestResortsEntry(date: .now, resorts: [
        ResortConditionData.sample,
        ResortConditionData.sample2
    ])
}
