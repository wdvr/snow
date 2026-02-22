import WidgetKit
import SwiftUI
import AppIntents
import os.log

private let logger = Logger(subsystem: "com.snowtracker.app.widget", category: "BestResorts")

// MARK: - Region Selection Intent

enum WidgetRegion: String, CaseIterable, AppEnum {
    case all = "all"
    case naWest = "na_west"
    case naRockies = "na_rockies"
    case naEast = "na_east"
    case alps = "alps"
    case scandinavia = "scandinavia"
    case japan = "japan"
    case oceania = "oceania"
    case southAmerica = "south_america"

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Region"

    static let caseDisplayRepresentations: [WidgetRegion: DisplayRepresentation] = [
        .all: "All Regions",
        .naWest: "NA West Coast",
        .naRockies: "NA Rockies",
        .naEast: "NA East Coast",
        .alps: "Alps",
        .scandinavia: "Scandinavia",
        .japan: "Japan",
        .oceania: "Oceania",
        .southAmerica: "South America"
    ]

    var displayName: String {
        switch self {
        case .all: return "All Regions"
        case .naWest: return "NA West Coast"
        case .naRockies: return "NA Rockies"
        case .naEast: return "NA East Coast"
        case .alps: return "Alps"
        case .scandinavia: return "Scandinavia"
        case .japan: return "Japan"
        case .oceania: return "Oceania"
        case .southAmerica: return "South America"
        }
    }
}

struct BestResortsIntent: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "Best Snow Resorts"
    static let description = IntentDescription("Shows the top resorts with best snow conditions in your selected region.")

    @Parameter(title: "Region", default: .all)
    var region: WidgetRegion
}

// MARK: - Best Resorts Widget

struct BestResortsWidget: Widget {
    let kind: String = "BestResortsWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: BestResortsIntent.self, provider: BestResortsProvider()) { entry in
            BestResortsWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Best Snow Right Now")
        .description("Top resorts with the best snow conditions. Configure to filter by region.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

// MARK: - Timeline Provider

struct BestResortsProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> BestResortsEntry {
        BestResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ],
            region: .all
        )
    }

    func snapshot(for configuration: BestResortsIntent, in context: Context) async -> BestResortsEntry {
        BestResortsEntry(
            date: Date(),
            resorts: [
                ResortConditionData.sample,
                ResortConditionData.sample2
            ],
            region: configuration.region
        )
    }

    func timeline(for configuration: BestResortsIntent, in context: Context) async -> Timeline<BestResortsEntry> {
        logger.info("BestResortsWidget: Getting timeline for region: \(configuration.region.rawValue)")

        do {
            let regionParam = configuration.region == .all ? nil : configuration.region.rawValue
            let resorts = try await WidgetDataService.shared.fetchBestResorts(region: regionParam)
            logger.info("BestResortsWidget: Got \(resorts.count) resorts")
            let entry = BestResortsEntry(date: Date(), resorts: resorts, region: configuration.region)
            let nextUpdate = Calendar.current.date(byAdding: .hour, value: 1, to: Date())!
            return Timeline(entries: [entry], policy: .after(nextUpdate))
        } catch {
            logger.error("BestResortsWidget: Error fetching data: \(error.localizedDescription)")
            let entry = BestResortsEntry(date: Date(), resorts: [], region: configuration.region)
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
            return Timeline(entries: [entry], policy: .after(nextUpdate))
        }
    }
}

// MARK: - Timeline Entry

struct BestResortsEntry: TimelineEntry {
    let date: Date
    let resorts: [ResortConditionData]
    let region: WidgetRegion
}

// MARK: - Widget View

struct BestResortsWidgetView: View {
    @Environment(\.widgetFamily) var widgetFamily
    var entry: BestResortsEntry
    private let unitPreferences = WidgetUnitPreferences.load()

    private var regionTitle: String {
        if entry.region == .all {
            return "Best Snow Right Now"
        } else {
            return "Best in \(entry.region.displayName)"
        }
    }

    private var smallRegionTitle: String {
        if entry.region == .all {
            return "Best Snow"
        } else {
            return entry.region.displayName
        }
    }

    private var resortCount: Int {
        switch widgetFamily {
        case .systemLarge: return 5
        case .systemMedium: return 2
        default: return 1
        }
    }

    var body: some View {
        switch widgetFamily {
        case .systemSmall:
            smallView
        case .systemLarge:
            largeView
        default:
            mediumView
        }
    }

    private var smallView: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.yellow)
                    .font(.caption2)
                Text(smallRegionTitle)
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
            }

            if let resort = entry.resorts.first {
                Text(resort.resortName)
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .lineLimit(1)

                Text(resort.location)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)

                HStack(spacing: 4) {
                    if let score = resort.snowScore {
                        Text("\(score)")
                            .font(.title2.weight(.bold))
                            .fontDesign(.rounded)
                            .foregroundStyle(resort.snowQuality.color)
                    } else {
                        Image(systemName: resort.snowQuality.icon)
                            .foregroundStyle(resort.snowQuality.color)
                            .font(.title2)
                    }
                    Text(resort.snowQuality.displayName)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(resort.snowQuality.color)
                }

                Spacer(minLength: 0)

                HStack(spacing: 12) {
                    Label(unitPreferences.formatTemperature(resort.temperature), systemImage: "thermometer")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Label(unitPreferences.formatSnow(resort.freshSnow), systemImage: "snowflake")
                        .font(.caption2)
                        .foregroundStyle(.cyan)
                }
            } else {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "cloud.snow")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                        Text("No data")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                Spacer()
            }
        }
        .padding()
    }

    private var mediumView: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.yellow)
                    .font(.caption)
                Text(regionTitle)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
            }

            if entry.resorts.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "cloud.snow")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                        Text("No data available")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(Array(entry.resorts.prefix(2).enumerated()), id: \.element.resortId) { index, resort in
                    HStack(spacing: 8) {
                        rankBadge(index: index)
                        ResortConditionRow(resort: resort, unitPreferences: unitPreferences)
                    }

                    if index < 1 {
                        Divider()
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding()
    }

    private var largeView: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "trophy.fill")
                    .foregroundStyle(.yellow)
                    .font(.caption)
                Text(regionTitle)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
            }

            if entry.resorts.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "cloud.snow")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                        Text("No data available")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(Array(entry.resorts.prefix(5).enumerated()), id: \.element.resortId) { index, resort in
                    HStack(spacing: 8) {
                        rankBadge(index: index)
                        ResortConditionRow(resort: resort, unitPreferences: unitPreferences)
                    }

                    if index < entry.resorts.prefix(5).count - 1 {
                        Divider()
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding()
    }

    private func rankBadge(index: Int) -> some View {
        ZStack {
            Circle()
                .fill(index == 0 ? Color.yellow : Color.gray.opacity(0.3))
                .frame(width: 24, height: 24)
            Text("\(index + 1)")
                .font(.caption)
                .fontWeight(.bold)
                .foregroundStyle(index == 0 ? .black : .primary)
        }
    }
}

// MARK: - Preview

#Preview(as: .systemLarge) {
    BestResortsWidget()
} timeline: {
    BestResortsEntry(date: .now, resorts: [
        ResortConditionData.sample,
        ResortConditionData.sample2,
        ResortConditionData.sample3,
        ResortConditionData.sample4,
        ResortConditionData.sample5
    ], region: .all)
}
