import SwiftUI
import MapKit

struct ResortMapView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @StateObject private var mapViewModel = MapViewModel()
    @ObservedObject private var locationManager = LocationManager.shared

    @State private var selectedResort: Resort?
    @State private var showResortDetail: Bool = false
    @State private var showLegend: Bool = false
    @State private var mapStyle: MapStyle = .standard
    @State private var clusterResorts: [Resort] = []
    @State private var showClusterList: Bool = false

    var body: some View {
        NavigationStack {
            mainMapContent
        }
    }

    private var mainMapContent: some View {
        mapZStackContent
            .navigationTitle("Map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { mapToolbarItems }
            .sheet(isPresented: $showResortDetail) { resortDetailSheet }
            .sheet(isPresented: $showClusterList) { clusterListSheet }
            .onAppear { handleAppear() }
            .onDisappear { handleDisappear() }
            .modifier(MapChangeHandlers(
                resorts: snowConditionsManager.resorts,
                conditions: snowConditionsManager.conditions,
                summaryCount: snowConditionsManager.snowQualitySummaries.count,
                selectedFilter: mapViewModel.selectedFilter,
                hiddenRegions: userPreferencesManager.hiddenRegions,
                onAnnotationsUpdate: updateAnnotations,
                onFilterChange: handleFilterChange
            ))
    }

    private var mapZStackContent: some View {
        ZStack {
            mapContent
            mapOverlays

            // Loading overlay when resorts are loading
            if snowConditionsManager.isLoading && mapViewModel.annotations.isEmpty {
                VStack(spacing: 12) {
                    ProgressView()
                        .controlSize(.large)
                    Text("Loading resorts...")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.ultraThinMaterial)
            }
        }
    }

    @ViewBuilder
    private var mapOverlays: some View {
        VStack {
            filterBar
                .padding(.horizontal)
                .padding(.top, 8)
            Spacer()
            bottomOverlays
        }
    }

    @ViewBuilder
    private var bottomOverlays: some View {
        VStack(spacing: 12) {
            if showLegend {
                qualityLegend
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            if locationManager.isLocationAvailable && !mapViewModel.nearbyResorts().isEmpty {
                nearbyResortsCarousel
            }
        }
        .padding(.horizontal)
        .padding(.bottom, 8)
    }

    @ToolbarContentBuilder
    private var mapToolbarItems: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) { mapStyleMenu }
        ToolbarItem(placement: .topBarTrailing) { trailingToolbarItems }
    }

    @ViewBuilder
    private var resortDetailSheet: some View {
        if let resort = selectedResort {
            ResortMapDetailSheet(resort: resort)
                .environmentObject(snowConditionsManager)
                .environmentObject(userPreferencesManager)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
    }

    @ViewBuilder
    private var clusterListSheet: some View {
        ClusterResortListSheet(
            resorts: clusterResorts,
            onResortSelected: { resort in
                showClusterList = false
                selectedResort = resort
                showResortDetail = true
            }
        )
        .environmentObject(snowConditionsManager)
        .environmentObject(userPreferencesManager)
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private func handleAppear() {
        updateAnnotations()
        locationManager.requestOneTimeLocation()
        AnalyticsService.shared.trackScreen("Map", screenClass: "ResortMapView")
    }

    private func handleDisappear() {
        AnalyticsService.shared.trackScreenExit("Map")
    }

    private func handleFilterChange(_ newValue: MapFilterOption) {
        updateAnnotations()
        AnalyticsService.shared.trackFilterApplied(filterType: "map_filter", filterValue: newValue.rawValue)
    }

    private func handleMapStyleChange(_ newValue: MapStyle) {
        // MapStyle doesn't conform to Equatable, so use string representation
        let styleName = String(describing: newValue)
        AnalyticsService.shared.trackMapStyleChanged(style: styleName)
    }

    // MARK: - Map Content

    @ViewBuilder
    private var mapContent: some View {
        ClusteredMapView(
            cameraPosition: $mapViewModel.cameraPosition,
            annotations: mapViewModel.annotations,
            mapStyle: mapStyle,
            showUserLocation: true,
            onAnnotationTap: { resort in
                selectedResort = resort
                showResortDetail = true
                AnalyticsService.shared.trackResortClicked(
                    resortId: resort.id,
                    resortName: resort.name,
                    source: "map"
                )
            },
            onClusterTap: { resorts in
                // Show a list of resorts in the cluster
                clusterResorts = resorts
                showClusterList = true
                AnalyticsService.shared.trackMapInteraction(action: "cluster_tap")
            }
        )
        .ignoresSafeArea(edges: .bottom)
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(MapFilterOption.allCases) { filter in
                    MapFilterChip(
                        title: filter.rawValue,
                        isSelected: mapViewModel.selectedFilter == filter,
                        color: filter.color,
                        count: countForFilter(filter)
                    ) {
                        withAnimation {
                            mapViewModel.selectedFilter = filter
                        }
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 4)
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Quality Legend

    private var qualityLegend: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Snow Quality Legend")
                .font(.headline)
                .padding(.bottom, 4)

            ForEach([SnowQuality.excellent, .good, .fair, .poor, .bad, .horrible], id: \.self) { quality in
                HStack(spacing: 12) {
                    Circle()
                        .fill(quality.color)
                        .frame(width: 16, height: 16)

                    Text(quality.displayName)
                        .font(.subheadline)

                    Spacer()

                    Text(quality.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Nearby Resorts Carousel

    private var nearbyResortsCarousel: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "location.fill")
                    .foregroundStyle(.blue)
                Text("Nearby")
                    .font(.headline)

                if mapViewModel.selectedForecastDate != nil {
                    Text("Forecast")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if mapViewModel.isFetchingTimelines {
                    ProgressView()
                        .controlSize(.small)
                }
            }
            .padding(.horizontal, 4)

            dateSelector

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(mapViewModel.nearbyResorts(limit: 5)) { annotation in
                        NearbyResortCard(
                            annotation: annotation,
                            distance: mapViewModel.formattedDistance(to: annotation.resort, prefs: userPreferencesManager.preferredUnits)
                        ) {
                            selectedResort = annotation.resort
                            showResortDetail = true
                        }
                    }
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var dateSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(mapViewModel.forecastDates, id: \.self) { date in
                    let isToday = Calendar.current.isDateInToday(date)
                    let isSelected = isToday
                        ? mapViewModel.selectedForecastDate == nil
                        : Calendar.current.isDate(date, inSameDayAs: mapViewModel.selectedForecastDate ?? .distantPast)

                    Button {
                        mapViewModel.selectForecastDate(isToday ? nil : date)
                    } label: {
                        Text(isToday ? "Today" : dayAbbreviation(date))
                            .font(.caption)
                            .fontWeight(isSelected ? .semibold : .regular)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(isSelected ? Color.blue : Color.clear)
                            .foregroundStyle(isSelected ? .white : .primary)
                            .clipShape(Capsule())
                            .overlay(Capsule().strokeBorder(isSelected ? .clear : Color.blue.opacity(0.4)))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE"
        return formatter
    }()

    private func dayAbbreviation(_ date: Date) -> String {
        Self.dayFormatter.string(from: date)
    }

    // MARK: - Helpers

    // MARK: - Toolbar Items

    private var mapStyleMenu: some View {
        Menu {
            Button("Standard") { mapStyle = .standard }
            Button("Satellite") { mapStyle = .imagery }
            Button("Hybrid") { mapStyle = .hybrid }
        } label: {
            Image(systemName: "map")
        }
    }

    private var trailingToolbarItems: some View {
        HStack(spacing: 16) {
            Button {
                withAnimation {
                    showLegend.toggle()
                }
            } label: {
                Image(systemName: showLegend ? "info.circle.fill" : "info.circle")
            }
            .accessibilityLabel(showLegend ? "Hide legend" : "Show legend")

            regionMenu
        }
    }

    private var regionMenu: some View {
        Menu {
            ForEach(MapRegionPreset.allCases) { preset in
                Button {
                    mapViewModel.setRegion(preset)
                } label: {
                    Label(preset.rawValue, systemImage: preset.icon)
                }
            }

            Divider()

            Button {
                mapViewModel.fitAllAnnotations()
            } label: {
                Label("Show All Resorts", systemImage: "rectangle.expand.vertical")
            }
        } label: {
            Image(systemName: "globe")
        }
    }

    // MARK: - Private Methods

    private func updateAnnotations() {
        mapViewModel.updateAnnotations(
            resorts: snowConditionsManager.resorts,
            conditions: snowConditionsManager.conditions,
            snowQualitySummaries: snowConditionsManager.snowQualitySummaries,
            hiddenRegions: userPreferencesManager.hiddenRegions
        )
    }

    private func countForFilter(_ filter: MapFilterOption) -> Int {
        // Filter by visible regions first
        let visibleResorts = userPreferencesManager.filterByVisibleRegions(snowConditionsManager.resorts)
        let allAnnotations = visibleResorts.map { resort in
            // Use the manager's getSnowQuality which checks summaries first
            snowConditionsManager.getSnowQuality(for: resort.id)
        }
        return allAnnotations.filter { filter.qualities.contains($0) }.count
    }
}

// MARK: - Filter Chip

struct MapFilterChip: View {
    let title: String
    let isSelected: Bool
    let color: Color
    let count: Int
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(isSelected ? .semibold : .regular)

                if count > 0 {
                    Text("\(count)")
                        .font(.caption)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(isSelected ? .white.opacity(0.3) : Color.secondary.opacity(0.2))
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(isSelected ? color : Color.clear)
            .foregroundStyle(isSelected ? .white : .primary)
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .strokeBorder(isSelected ? Color.clear : color.opacity(0.5), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .sensoryFeedback(.selection, trigger: isSelected)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityLabel("\(title), \(count) resorts\(isSelected ? ", selected" : "")")
    }
}

// MARK: - Resort Map Marker

struct ResortMapMarker: View {
    let annotation: ResortAnnotation

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                Circle()
                    .fill(annotation.markerTint)
                    .frame(width: 36, height: 36)
                    .shadow(color: annotation.markerTint.opacity(0.5), radius: 4, y: 2)

                Image(systemName: annotation.markerIcon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
            }

            // Pin pointer
            Triangle()
                .fill(annotation.markerTint)
                .frame(width: 12, height: 8)
                .offset(y: -1)
        }
        .accessibilityLabel("\(annotation.resort.name), \(annotation.snowQuality.displayName)")
    }
}

struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        path.closeSubpath()
        return path
    }
}

// MARK: - Nearby Resort Card

struct NearbyResortCard: View {
    let annotation: ResortAnnotation
    let distance: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Circle()
                        .fill(annotation.snowQuality.color)
                        .frame(width: 10, height: 10)

                    Text(annotation.resort.name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(1)
                }

                HStack {
                    if let distance = distance {
                        Text(distance)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Text(annotation.snowQuality.displayName)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(annotation.snowQuality.color)
                }
            }
            .padding(12)
            .frame(width: 160)
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(annotation.resort.name), \(annotation.snowQuality.displayName)\(distance.map { ", \($0) away" } ?? "")")
    }
}

// MARK: - Resort Map Detail Sheet

struct ResortMapDetailSheet: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss
    @State private var isLoadingConditions = true

    private var condition: WeatherCondition? {
        snowConditionsManager.getLatestCondition(for: resort.id)
    }

    private var knownQuality: SnowQuality {
        snowConditionsManager.getSnowQuality(for: resort.id)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Header
                    headerSection

                    Divider()

                    // Current conditions
                    if let condition = condition {
                        conditionsSection(condition)
                    } else if isLoadingConditions {
                        loadingConditionsView
                    } else {
                        noConditionsView
                    }

                    Divider()

                    // Quick actions
                    actionsSection
                }
                .padding()
            }
            .navigationTitle(resort.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .task {
                if condition == nil {
                    isLoadingConditions = true
                }
                defer { isLoadingConditions = false }
                await snowConditionsManager.fetchConditionsForResort(resort.id)
            }
        }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text(resort.elevationRange(prefs: userPreferencesManager.preferredUnits))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Favorite button
                Button {
                    userPreferencesManager.toggleFavorite(resortId: resort.id)
                } label: {
                    Image(systemName: userPreferencesManager.isFavorite(resortId: resort.id) ? "heart.fill" : "heart")
                        .font(.title2)
                        .foregroundStyle(userPreferencesManager.isFavorite(resortId: resort.id) ? .red : .secondary)
                }
                .sensoryFeedback(.impact(weight: .light), trigger: userPreferencesManager.isFavorite(resortId: resort.id))
                .accessibilityLabel(userPreferencesManager.isFavorite(resortId: resort.id) ? "Remove from favorites" : "Add to favorites")
            }

            HStack(spacing: 12) {
                // Snow quality badge - show from summary even before conditions load
                let quality = condition?.snowQuality ?? knownQuality
                if quality != .unknown {
                    Label(quality.displayName, systemImage: quality.icon)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(quality.color, in: Capsule())
                }

                // Temperature (only when full conditions are loaded)
                if let condition = condition {
                    Label(condition.formattedTemperature(userPreferencesManager.preferredUnits), systemImage: "thermometer.medium")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else if isLoadingConditions {
                    ProgressView()
                        .controlSize(.small)
                }
            }
        }
    }

    @ViewBuilder
    private func conditionsSection(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Current Conditions")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ConditionCard(
                    title: "Fresh Snow",
                    value: condition.formattedSnowSinceFreezeWithPrefs(userPreferencesManager.preferredUnits),
                    icon: "snowflake",
                    color: .cyan
                )

                ConditionCard(
                    title: "24h Snowfall",
                    value: condition.formattedSnowfall24hWithPrefs(userPreferencesManager.preferredUnits),
                    icon: "cloud.snow",
                    color: .blue
                )

                ConditionCard(
                    title: "Surface",
                    value: condition.surfaceType.rawValue,
                    icon: condition.surfaceType.icon,
                    color: condition.surfaceType.color
                )

                ConditionCard(
                    title: "Last Freeze",
                    value: condition.formattedTimeSinceFreeze,
                    icon: "thermometer.snowflake",
                    color: .indigo
                )
            }

            // Predictions
            if let pred24 = condition.predictedSnow24hCm, pred24 > 0 {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Forecast")
                        .font(.subheadline)
                        .fontWeight(.medium)

                    HStack(spacing: 16) {
                        ForecastBadge(hours: 24, cm: pred24, prefs: userPreferencesManager.preferredUnits)
                        if let pred48 = condition.predictedSnow48hCm, pred48 > 0 {
                            ForecastBadge(hours: 48, cm: pred48, prefs: userPreferencesManager.preferredUnits)
                        }
                        if let pred72 = condition.predictedSnow72hCm, pred72 > 0 {
                            ForecastBadge(hours: 72, cm: pred72, prefs: userPreferencesManager.preferredUnits)
                        }
                    }
                }
                .padding(.top, 8)
            }
        }
    }

    private var loadingConditionsView: some View {
        VStack(spacing: 12) {
            ProgressView()
                .controlSize(.large)
            Text("Loading conditions...")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }

    private var noConditionsView: some View {
        VStack(spacing: 12) {
            Image(systemName: "cloud.sun")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No conditions data available")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }

    private var actionsSection: some View {
        VStack(spacing: 12) {
            NavigationLink {
                ResortDetailView(resort: resort)
                    .environmentObject(snowConditionsManager)
                    .environmentObject(userPreferencesManager)
            } label: {
                HStack {
                    Text("View Full Details")
                    Spacer()
                    Image(systemName: "chevron.right")
                }
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)

            if let website = resort.officialWebsite, let url = URL(string: website) {
                Link(destination: url) {
                    HStack {
                        Text("Visit Resort Website")
                        Spacer()
                        Image(systemName: "arrow.up.right")
                    }
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

// MARK: - Condition Card

struct ConditionCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(color)
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

// MARK: - Forecast Badge

struct ForecastBadge: View {
    let hours: Int
    let cm: Double
    let prefs: UnitPreferences

    var body: some View {
        VStack(spacing: 2) {
            Text("\(hours)h")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(WeatherCondition.formatSnowShort(cm, prefs: prefs))
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.cyan)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.cyan.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Cluster Resort List Sheet

struct ClusterResortListSheet: View {
    let resorts: [Resort]
    let onResortSelected: (Resort) -> Void
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss
    @State private var isLoadingConditions = false

    var body: some View {
        NavigationStack {
            Group {
                if isLoadingConditions && sortedResorts.isEmpty {
                    VStack(spacing: 12) {
                        ProgressView()
                            .controlSize(.large)
                        Text("Loading conditions...")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if sortedResorts.isEmpty {
                    VStack(spacing: 16) {
                        ContentUnavailableView(
                            "No Data Available",
                            systemImage: "snowflake.slash",
                            description: Text("Could not load conditions for these resorts.")
                        )

                        Button {
                            Task {
                                isLoadingConditions = true
                                let resortIds = resorts.map { $0.id }
                                await snowConditionsManager.fetchConditionsForResorts(resortIds: resortIds)
                                isLoadingConditions = false
                            }
                        } label: {
                            Label("Try Again", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    List {
                        ForEach(sortedResorts) { resort in
                            ClusterResortRow(
                                resort: resort,
                                condition: snowConditionsManager.getLatestCondition(for: resort.id),
                                snowQuality: snowConditionsManager.getSnowQuality(for: resort.id)
                            )
                            .contentShape(Rectangle())
                            .onTapGesture {
                                onResortSelected(resort)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .overlay {
                        if isLoadingConditions {
                            VStack {
                                Spacer()
                                HStack(spacing: 8) {
                                    ProgressView()
                                        .controlSize(.small)
                                    Text("Updating conditions...")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                .padding(8)
                                .background(.regularMaterial, in: Capsule())
                                .padding(.bottom, 8)
                            }
                        }
                    }
                }
            }
            .navigationTitle("\(resorts.count) Resorts")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .task {
                let resortIds = resorts.map { $0.id }
                let needsFetch = resortIds.contains { id in
                    snowConditionsManager.getLatestCondition(for: id) == nil
                }
                if needsFetch {
                    isLoadingConditions = true
                    await snowConditionsManager.fetchConditionsForResorts(resortIds: resortIds)
                    isLoadingConditions = false
                }
            }
        }
    }

    private var sortedResorts: [Resort] {
        resorts.sorted { resort1, resort2 in
            let quality1 = snowConditionsManager.getSnowQuality(for: resort1.id)
            let quality2 = snowConditionsManager.getSnowQuality(for: resort2.id)
            if quality1.sortOrder != quality2.sortOrder {
                return quality1.sortOrder < quality2.sortOrder
            }
            return resort1.name < resort2.name
        }
    }
}

struct ClusterResortRow: View {
    let resort: Resort
    let condition: WeatherCondition?
    let snowQuality: SnowQuality
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    var body: some View {
        HStack(spacing: 12) {
            // Quality indicator
            Circle()
                .fill(snowQuality.color)
                .frame(width: 12, height: 12)

            VStack(alignment: .leading, spacing: 2) {
                Text(resort.name)
                    .font(.body)
                    .fontWeight(.medium)

                Text(resort.displayLocation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(snowQuality.displayName)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(snowQuality.color)

                if let temp = condition?.formattedTemperature(userPreferencesManager.preferredUnits) {
                    Text(temp)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Map Change Handlers Modifier

private struct MapChangeHandlers: ViewModifier {
    let resorts: [Resort]
    let conditions: [String: [WeatherCondition]]
    let summaryCount: Int
    let selectedFilter: MapFilterOption
    let hiddenRegions: Set<String>
    let onAnnotationsUpdate: () -> Void
    let onFilterChange: (MapFilterOption) -> Void

    /// Content-aware hash that detects quality changes, not just count changes
    private var contentHash: Int {
        var hasher = Hasher()
        hasher.combine(resorts.count)
        hasher.combine(summaryCount)
        hasher.combine(hiddenRegions)
        for (key, conds) in conditions {
            hasher.combine(key)
            for c in conds {
                hasher.combine(c.snowQuality)
                hasher.combine(c.timestamp)
            }
        }
        return hasher.finalize()
    }

    func body(content: Content) -> some View {
        content
            .onChange(of: contentHash) { _, _ in onAnnotationsUpdate() }
            .onChange(of: selectedFilter) { _, newValue in onFilterChange(newValue) }
    }
}

// MARK: - Preview

#Preview {
    ResortMapView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
