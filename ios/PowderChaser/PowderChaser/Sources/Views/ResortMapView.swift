import SwiftUI
import MapKit

struct ResortMapView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator
    @StateObject private var mapViewModel = MapViewModel()
    @ObservedObject private var locationManager = LocationManager.shared

    @State private var selectedResort: Resort?
    @State private var showLegend: Bool = false
    @State private var mapStyle: MapDisplayStyle = .standard
    @State private var showPisteOverlay: Bool = true
    @State private var clusterResorts: [Resort] = []
    @State private var showClusterList: Bool = false
    @State private var regionChangeTask: Task<Void, Never>?
    @State private var isFetchingVisibleConditions: Bool = false
    @State private var nearbyCollapsed: Bool = false
    @State private var pisteOverlayResult: PisteOverlayResult?
    @State private var pisteLoadedForResorts: Set<String> = []
    @State private var pisteLoadTask: Task<Void, Never>?
    @State private var showMapSearch: Bool = false

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
            .sheet(item: $selectedResort) { resort in
                ResortMapDetailSheet(resort: resort)
                    .environmentObject(snowConditionsManager)
                    .environmentObject(userPreferencesManager)
                    .environmentObject(navigationCoordinator)
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
            }
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
            .onChange(of: mapViewModel.isFetchingTimelines) { _, newValue in
                if !newValue && mapViewModel.selectedForecastDate != nil {
                    updateAnnotations()
                }
            }
            .onChange(of: mapViewModel.timelineBatchCount) { _, _ in
                // Progressive update: refresh pins after each timeline batch completes
                if mapViewModel.selectedForecastDate != nil {
                    updateAnnotations()
                }
            }
            .onChange(of: mapViewModel.selectedForecastDate) { _, _ in
                updateAnnotations()
            }
            .onChange(of: showPisteOverlay) { _, _ in
                fetchPisteOverlaysForVisibleResorts()
            }
            .onChange(of: navigationCoordinator.mapTargetResort) { _, resort in
                guard let resort else { return }
                navigationCoordinator.mapTargetResort = nil
                mapViewModel.pendingRegion = MKCoordinateRegion(
                    center: resort.primaryCoordinate,
                    span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)
                )
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    selectedResort = resort
                }
            }
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

            // Piste overlay attribution
            if showPisteOverlay {
                pisteAttribution
                    .transition(.opacity)
            }

            // Forecast indicator when showing predicted quality
            if let forecastDate = mapViewModel.selectedForecastDate {
                forecastBanner(for: forecastDate)
            }

            // Date selector — always visible (controls all map pins)
            dateSelector
                .padding(8)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))

            nearbyAndSearchBar
        }
        .padding(.horizontal)
        .padding(.bottom, 8)
    }

    private func forecastBanner(for date: Date) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "calendar")
                .foregroundStyle(.blue)

            Text("Showing forecast for \(dayAbbreviation(date))")
                .font(.subheadline)
                .fontWeight(.medium)

            Spacer()

            if mapViewModel.isFetchingTimelines {
                ProgressView()
                    .controlSize(.small)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 10))
    }

    @ToolbarContentBuilder
    private var mapToolbarItems: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) { mapStyleMenu }
        ToolbarItem(placement: .topBarTrailing) { trailingToolbarItems }
    }

    @ViewBuilder
    private var clusterListSheet: some View {
        ClusterResortListSheet(
            resorts: clusterResorts,
            onResortSelected: { resort in
                showClusterList = false
                // Delay to let the cluster sheet dismiss before showing detail
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    selectedResort = resort
                }
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
        // Center on user location if available, otherwise keep default (NA Rockies)
        if let userLocation = locationManager.userLocation {
            mapViewModel.centerOnUserLocation(userLocation)
        }
        AnalyticsService.shared.trackScreen("Map", screenClass: "ResortMapView")

        // Proactively fetch conditions for all visible resorts in the background
        // so map icons show fresh quality data without needing to tap each one
        Task { await fetchConditionsForVisibleResorts() }

        // Fetch vector piste data for visible resorts
        fetchPisteOverlaysForVisibleResorts()
    }

    /// Debounce region-change fetches: cancel any pending fetch and start a new one
    /// after a 1.5-second pause so we don't fire on every tiny pan.
    private func debouncedFetchConditionsForVisibleResorts() {
        regionChangeTask?.cancel()
        regionChangeTask = Task {
            try? await Task.sleep(nanoseconds: 1_500_000_000) // 1.5 seconds
            guard !Task.isCancelled else { return }
            await fetchConditionsForVisibleResorts()

            // If forecast mode is active, also fetch timelines for newly visible resorts
            if mapViewModel.selectedForecastDate != nil {
                await mapViewModel.fetchTimelinesForVisible(resortIds: mapViewModel.visibleResortIds())
            }

            // Fetch vector piste data when zoomed in
            fetchPisteOverlaysForVisibleResorts()
        }
    }

    /// Fetch full conditions for resorts currently visible on the map.
    /// This runs in the background so icons update to show live quality data.
    /// Only fetches for resorts not already present in the conditions cache.
    @discardableResult
    private func fetchConditionsForVisibleResorts() async -> Bool {
        let visibleIds = mapViewModel.visibleResortIds()
        guard !visibleIds.isEmpty else { return false }

        // Only fetch for resorts whose conditions are not yet cached
        let uncachedIds = visibleIds.filter { snowConditionsManager.conditions[$0] == nil }
        guard !uncachedIds.isEmpty else { return false }

        isFetchingVisibleConditions = true
        defer { isFetchingVisibleConditions = false }

        // Fetch in batches to avoid overloading the API
        let batchSize = 30
        for batch in stride(from: 0, to: uncachedIds.count, by: batchSize) {
            guard !Task.isCancelled else { return false }
            let end = min(batch + batchSize, uncachedIds.count)
            let batchIds = Array(uncachedIds[batch..<end])
            await snowConditionsManager.fetchConditionsForResorts(resortIds: batchIds)
        }

        // Refresh annotations so pins update their quality display
        updateAnnotations()
        return true
    }

    /// Force-refresh conditions for all visible resorts (ignores cache).
    private func forceRefreshVisibleResorts() {
        regionChangeTask?.cancel()
        regionChangeTask = Task {
            let visibleIds = mapViewModel.annotations.map(\.resort.id)
            guard !visibleIds.isEmpty else { return }

            isFetchingVisibleConditions = true
            defer { isFetchingVisibleConditions = false }

            let batchSize = 30
            for batch in stride(from: 0, to: visibleIds.count, by: batchSize) {
                guard !Task.isCancelled else { return }
                let end = min(batch + batchSize, visibleIds.count)
                let batchIds = Array(visibleIds[batch..<end])
                await snowConditionsManager.fetchConditionsForResorts(resortIds: batchIds)
            }
        }
    }

    private func handleDisappear() {
        regionChangeTask?.cancel()
        regionChangeTask = nil
        pisteLoadTask?.cancel()
        pisteLoadTask = nil
        AnalyticsService.shared.trackScreenExit("Map")
    }

    /// Fetch vector piste overlays for resorts visible at high zoom levels.
    /// Only fetches when piste overlay is enabled and zoom is sufficient.
    private func fetchPisteOverlaysForVisibleResorts() {
        guard showPisteOverlay else {
            if pisteOverlayResult != nil {
                pisteOverlayResult = nil
            }
            return
        }

        // Check zoom level — only load vector pistes when zoomed in
        guard let region = mapViewModel.currentVisibleRegion,
              region.span.latitudeDelta < 0.5 else {
            // Zoomed out too far — clear vector overlays
            if pisteOverlayResult != nil {
                pisteOverlayResult = nil
                pisteLoadedForResorts = []
            }
            return
        }

        // Find resorts in the viewport
        let visibleResorts = snowConditionsManager.resorts.filter { resort in
            let coord = resort.primaryCoordinate
            let center = region.center
            let span = region.span
            return abs(coord.latitude - center.latitude) < span.latitudeDelta / 2
                && abs(coord.longitude - center.longitude) < span.longitudeDelta / 2
        }

        // Only fetch for resorts not yet loaded
        let newResorts = visibleResorts.filter { !pisteLoadedForResorts.contains($0.id) }
        guard !newResorts.isEmpty else { return }

        pisteLoadTask?.cancel()
        pisteLoadTask = Task {
            var allPistes: [PistePolyline] = []
            var allLifts: [LiftPolyline] = []

            // Keep existing data
            if let existing = pisteOverlayResult {
                allPistes = existing.pistes
                allLifts = existing.lifts
            }

            for resort in newResorts {
                guard !Task.isCancelled else { return }
                do {
                    let result = try await PisteOverlayService.shared.overlays(
                        for: resort.id,
                        coordinate: resort.primaryCoordinate,
                        colorScheme: PisteColorScheme(country: resort.country)
                    )
                    allPistes.append(contentsOf: result.pistes)
                    allLifts.append(contentsOf: result.lifts)
                    pisteLoadedForResorts.insert(resort.id)
                } catch {
                    // Silently skip — resort may not have OSM piste data
                    pisteLoadedForResorts.insert(resort.id) // don't retry
                }
            }

            guard !Task.isCancelled else { return }

            pisteOverlayResult = PisteOverlayResult(pistes: allPistes, lifts: allLifts)
        }
    }

    private func handleFilterChange(_ newValue: MapFilterOption) {
        updateAnnotations()
        AnalyticsService.shared.trackFilterApplied(filterType: "map_filter", filterValue: newValue.rawValue)
    }

    private func handleMapStyleChange(_ newValue: MapDisplayStyle) {
        AnalyticsService.shared.trackMapStyleChanged(style: newValue.rawValue)
    }

    // MARK: - Map Content

    @ViewBuilder
    private var mapContent: some View {
        ClusteredMapView(
            cameraPosition: $mapViewModel.cameraPosition,
            pendingRegion: $mapViewModel.pendingRegion,
            annotations: mapViewModel.annotations,
            mapStyle: mapStyle,
            showUserLocation: true,
            showPisteOverlay: showPisteOverlay,
            pisteOverlayResult: pisteOverlayResult,
            onAnnotationTap: { resort in
                selectedResort = resort
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
            },
            onRegionChange: { region in
                mapViewModel.currentVisibleRegion = region
                debouncedFetchConditionsForVisibleResorts()
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

            ForEach([SnowQuality.champagnePowder, .powderDay, .excellent, .great, .good, .decent, .mediocre, .poor, .bad, .horrible], id: \.self) { quality in
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

    // MARK: - Piste Attribution

    private var pisteAttribution: some View {
        HStack(spacing: 6) {
            Image(systemName: "figure.skiing.downhill")
                .font(.caption2)
                .foregroundStyle(.blue)

            Text("Ski trails: © OpenStreetMap contributors")
                .font(.caption2)
                .foregroundStyle(.secondary)

            Spacer()

            if pisteOverlayResult == nil || pisteOverlayResult?.isEmpty == true {
                Text("Zoom in to see trails")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
    }

    // MARK: - Nearby + Search Bar

    private var nearbyAndSearchBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header row with Nearby + Search
            HStack {
                if locationManager.isLocationAvailable && !mapViewModel.nearbyResorts().isEmpty {
                    Button {
                        withAnimation(.easeInOut(duration: 0.25)) {
                            nearbyCollapsed.toggle()
                        }
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "location.fill")
                                .foregroundStyle(.blue)
                            Text("Nearby")
                                .font(.headline)
                                .foregroundStyle(.primary)

                            Image(systemName: "chevron.down")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .rotationEffect(.degrees(nearbyCollapsed ? -90 : 0))
                        }
                    }
                    .buttonStyle(.plain)
                }

                Spacer()

                Button {
                    showMapSearch = true
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "magnifyingglass")
                        Text("Search")
                            .font(.subheadline)
                    }
                    .foregroundStyle(.blue)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 4)

            // Nearby cards
            if locationManager.isLocationAvailable
                && !mapViewModel.nearbyResorts().isEmpty
                && !nearbyCollapsed {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(mapViewModel.nearbyResorts(limit: 5)) { annotation in
                            NearbyResortCard(
                                annotation: annotation,
                                distance: mapViewModel.formattedDistance(to: annotation.resort, prefs: userPreferencesManager.preferredUnits)
                            ) {
                                // Zoom to resort first, then show detail after delay to avoid race condition
                                mapViewModel.pendingRegion = MKCoordinateRegion(
                                    center: annotation.resort.primaryCoordinate,
                                    span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)
                                )
                                let resort = annotation.resort
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                    selectedResort = resort
                                }
                            }
                        }
                    }
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
        .sheet(isPresented: $showMapSearch) {
            MapSearchSheet { region in
                mapViewModel.pendingRegion = region
            }
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
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
            ForEach(MapDisplayStyle.allCases) { style in
                Button {
                    mapStyle = style
                } label: {
                    Label(style.displayName, systemImage: style.icon)
                }
            }
        } label: {
            Image(systemName: "map")
        }
    }

    private var trailingToolbarItems: some View {
        HStack(spacing: 16) {
            Button {
                forceRefreshVisibleResorts()
            } label: {
                if isFetchingVisibleConditions {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Image(systemName: "arrow.clockwise")
                }
            }
            .disabled(isFetchingVisibleConditions)
            .accessibilityLabel("Refresh conditions")

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
        .accessibilityLabel("Region")
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

// MARK: - Map Search Sheet

struct MapSearchSheet: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var searchCompleter = MapSearchCompleter()
    @State private var searchText = ""
    let onSelect: (MKCoordinateRegion) -> Void

    var body: some View {
        NavigationStack {
            List {
                if searchCompleter.results.isEmpty && !searchText.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    ForEach(searchCompleter.results, id: \.self) { completion in
                        Button {
                            selectCompletion(completion)
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(completion.title)
                                    .font(.body)
                                    .foregroundStyle(.primary)
                                if !completion.subtitle.isEmpty {
                                    Text(completion.subtitle)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search for a place")
            .onChange(of: searchText) { _, newValue in
                searchCompleter.search(query: newValue)
            }
            .navigationTitle("Search Map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func selectCompletion(_ completion: MKLocalSearchCompletion) {
        let request = MKLocalSearch.Request(completion: completion)
        let search = MKLocalSearch(request: request)
        search.start { response, _ in
            guard let mapItem = response?.mapItems.first else { return }
            let region = MKCoordinateRegion(
                center: mapItem.placemark.coordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.5, longitudeDelta: 0.5)
            )
            onSelect(region)
            dismiss()
        }
    }
}

/// Search completer that provides autocomplete suggestions.
final class MapSearchCompleter: NSObject, ObservableObject, MKLocalSearchCompleterDelegate {
    @Published var results: [MKLocalSearchCompletion] = []
    private let completer = MKLocalSearchCompleter()

    override init() {
        super.init()
        completer.delegate = self
        completer.resultTypes = [.address, .pointOfInterest]
    }

    func search(query: String) {
        guard !query.isEmpty else {
            results = []
            return
        }
        completer.queryFragment = query
    }

    func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        results = completer.results
    }

    func completer(_ completer: MKLocalSearchCompleter, didFailWithError error: Error) {
        // Silently handle — user keeps typing
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
    @EnvironmentObject private var navigationCoordinator: NavigationCoordinator
    @Environment(\.dismiss) private var dismiss
    @State private var isLoadingConditions = true
    @State private var safariURL: IdentifiableURL?
    @State private var showingTrailMap = false

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

                    // Current conditions - show summary immediately while full conditions load
                    if let condition = condition {
                        conditionsSection(condition)
                    } else if let summary = snowConditionsManager.snowQualitySummaries[resort.id],
                              summary.temperatureC != nil || summary.snowfallFreshCm != nil {
                        summaryFallbackSection(summary)
                        if isLoadingConditions {
                            HStack(spacing: 8) {
                                ProgressView()
                                    .controlSize(.small)
                                Text("Loading full conditions...")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
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
            .safariOverlay(url: $safariURL)
            .fullScreenCover(isPresented: $showingTrailMap) {
                if let urlStr = resort.trailMapUrl, let url = URL(string: urlStr) {
                    TrailMapView(url: url, resortName: resort.name)
                }
            }
        }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                ResortLogoView(resort: resort, size: 36)

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
                    HStack(spacing: 6) {
                        if let score = snowConditionsManager.getSnowScore(for: resort.id) {
                            Text("\(score)")
                                .font(.subheadline.weight(.bold))
                                .fontDesign(.rounded)
                        }
                        Label(quality.displayName, systemImage: quality.icon)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                    }
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

    @ViewBuilder
    private func summaryFallbackSection(_ summary: SnowQualitySummaryLight) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Conditions Summary")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let temp = summary.formattedTemperature(userPreferencesManager.preferredUnits) {
                    ConditionCard(title: "Temperature", value: temp, icon: "thermometer.medium", color: .orange)
                }

                if let snow = summary.formattedFreshSnow(userPreferencesManager.preferredUnits) {
                    ConditionCard(title: "Fresh Snow", value: snow, icon: "snowflake", color: .cyan)
                }

                if let snow24 = summary.snowfall24hCm {
                    ConditionCard(
                        title: "24h Snowfall",
                        value: WeatherCondition.formatSnowShort(snow24, prefs: userPreferencesManager.preferredUnits),
                        icon: "cloud.snow",
                        color: .blue
                    )
                }

                if let depth = summary.snowDepthCm {
                    ConditionCard(
                        title: "Snow Depth",
                        value: WeatherCondition.formatSnowShort(depth, prefs: userPreferencesManager.preferredUnits),
                        icon: "mountain.2.fill",
                        color: .purple
                    )
                }
            }

            if let pred48 = summary.predictedSnow48hCm, pred48 >= 5 {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Forecast")
                        .font(.subheadline)
                        .fontWeight(.medium)

                    ForecastBadge(hours: 48, cm: pred48, prefs: userPreferencesManager.preferredUnits)
                }
                .padding(.top, 8)
            }
        }
    }

    @ViewBuilder
    private var webcamSection: some View {
        if let webcamUrlStr = resort.webcamUrl, let webcamUrl = URL(string: webcamUrlStr) {
            Button {
                safariURL = IdentifiableURL(url: webcamUrl)
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "web.camera.fill")
                        .font(.title3)
                        .foregroundStyle(.white)
                        .frame(width: 40, height: 40)
                        .background(.blue.gradient, in: RoundedRectangle(cornerRadius: 10))

                    VStack(alignment: .leading, spacing: 2) {
                        Text("View Live Webcams")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundStyle(.primary)
                        Text(resort.name)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                .padding(12)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)
        }
    }

    private var actionsSection: some View {
        VStack(spacing: 12) {
            // Webcam card
            webcamSection

            NavigationLink {
                ResortDetailView(resort: resort)
                    .environmentObject(snowConditionsManager)
                    .environmentObject(userPreferencesManager)
                    .environmentObject(navigationCoordinator)
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

            // Quick links row
            HStack(spacing: 12) {
                if let website = resort.officialWebsite, let url = URL(string: website) {
                    Button {
                        safariURL = IdentifiableURL(url: url)
                    } label: {
                        Label("Website", systemImage: "safari")
                            .font(.subheadline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(Color(.secondarySystemBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }

                if let mapUrlStr = resort.trailMapUrl, let mapUrl = URL(string: mapUrlStr) {
                    Button {
                        if mapUrlStr.hasSuffix(".jpg") || mapUrlStr.hasSuffix(".jpeg") || mapUrlStr.hasSuffix(".png") {
                            showingTrailMap = true
                        } else {
                            safariURL = IdentifiableURL(url: mapUrl)
                        }
                    } label: {
                        Label("Trail Map", systemImage: "map")
                            .font(.subheadline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(Color(.secondarySystemBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }
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
        .environmentObject(NavigationCoordinator())
}
