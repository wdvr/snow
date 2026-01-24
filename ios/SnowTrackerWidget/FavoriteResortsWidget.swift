import WidgetKit
import SwiftUI
import os.log

private let logger = Logger(subsystem: "com.snowtracker.app.widget", category: "FavoriteResorts")

// MARK: - Favorite Resorts Widget

struct FavoriteResortsWidget: Widget {
    let kind: String = "FavoriteResortsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: FavoriteResortsProvider()) { entry in
            FavoriteResortsWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Favorite Resorts")
        .description("Snow conditions at your top 2 favorite resorts.")
        .supportedFamilies([.systemMedium, .systemLarge])
    }
}

// MARK: - Timeline Provider

struct FavoriteResortsProvider: TimelineProvider {
    func placeholder(in context: Context) -> FavoriteResortsEntry {
        FavoriteResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ]
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (FavoriteResortsEntry) -> Void) {
        let entry = FavoriteResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ]
        )
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<FavoriteResortsEntry>) -> Void) {
        logger.info("FavoriteResortsWidget: Getting timeline...")
        Task {
            do {
                let resorts = try await WidgetDataService.shared.fetchFavoriteResorts()
                logger.info("FavoriteResortsWidget: Got \(resorts.count) resorts")
                let entry = FavoriteResortsEntry(date: Date(), resorts: resorts)
                let nextUpdate = Calendar.current.date(byAdding: .hour, value: 1, to: Date())!
                let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
                completion(timeline)
            } catch {
                logger.error("FavoriteResortsWidget: Error fetching data: \(error.localizedDescription)")
                let entry = FavoriteResortsEntry(date: Date(), resorts: [])
                let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
                let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
                completion(timeline)
            }
        }
    }
}

// MARK: - Timeline Entry

struct FavoriteResortsEntry: TimelineEntry {
    let date: Date
    let resorts: [ResortConditionData]
}

// MARK: - Widget View

struct FavoriteResortsWidgetView: View {
    var entry: FavoriteResortsEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "heart.fill")
                    .foregroundColor(.red)
                    .font(.caption)
                Text("Favorite Resorts")
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
                        Image(systemName: "heart.slash")
                            .font(.title2)
                            .foregroundColor(.secondary)
                        Text("No favorites yet")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(entry.resorts.prefix(2), id: \.resortId) { resort in
                    ResortConditionRow(resort: resort)
                    if resort.resortId != entry.resorts.prefix(2).last?.resortId {
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
    FavoriteResortsWidget()
} timeline: {
    FavoriteResortsEntry(date: .now, resorts: [
        ResortConditionData.sample,
        ResortConditionData.sample2
    ])
}
