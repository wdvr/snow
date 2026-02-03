import SwiftUI
import MapKit
import Combine

// MARK: - Resort Annotation

struct ResortAnnotation: Identifiable, Hashable {
    let id: String
    let resort: Resort
    let coordinate: CLLocationCoordinate2D
    let snowQuality: SnowQuality
    let condition: WeatherCondition?

    init(resort: Resort, condition: WeatherCondition?, fallbackQuality: SnowQuality? = nil) {
        self.id = resort.id
        self.resort = resort
        self.coordinate = resort.primaryCoordinate
        self.condition = condition
        // Use condition's quality if available, otherwise use fallback, otherwise unknown
        self.snowQuality = condition?.snowQuality ?? fallbackQuality ?? .unknown
    }

    var markerTint: Color {
        snowQuality.color
    }

    var markerIcon: String {
        snowQuality.icon
    }

    // Hashable conformance
    static func == (lhs: ResortAnnotation, rhs: ResortAnnotation) -> Bool {
        lhs.id == rhs.id
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
}

// MARK: - Map Filter Options

enum MapFilterOption: String, CaseIterable, Identifiable {
    case all = "All"
    case excellent = "Excellent"
    case good = "Good"
    case fair = "Fair"
    case poor = "Poor & Below"

    var id: String { rawValue }

    var qualities: [SnowQuality] {
        switch self {
        case .all:
            return SnowQuality.allCases
        case .excellent:
            return [.excellent]
        case .good:
            return [.good]
        case .fair:
            return [.fair]
        case .poor:
            return [.poor, .bad, .horrible]
        }
    }

    var color: Color {
        switch self {
        case .all: return .blue
        case .excellent: return .green
        case .good: return Color(.systemGreen)
        case .fair: return .orange
        case .poor: return .red
        }
    }
}

// MARK: - Map Region Presets

enum MapRegionPreset: String, CaseIterable, Identifiable {
    case userLocation = "My Location"
    case naWest = "NA West Coast"
    case naRockies = "NA Rockies"
    case alps = "Alps"
    case japan = "Japan"
    case oceania = "Oceania"

    var id: String { rawValue }

    var region: MKCoordinateRegion {
        switch self {
        case .userLocation:
            // Default to North America if no location
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 45.0, longitude: -110.0),
                span: MKCoordinateSpan(latitudeDelta: 30, longitudeDelta: 40)
            )
        case .naWest:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 47.0, longitude: -121.0),
                span: MKCoordinateSpan(latitudeDelta: 12, longitudeDelta: 15)
            )
        case .naRockies:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.5, longitude: -106.5),
                span: MKCoordinateSpan(latitudeDelta: 10, longitudeDelta: 12)
            )
        case .alps:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 46.5, longitude: 8.5),
                span: MKCoordinateSpan(latitudeDelta: 5, longitudeDelta: 8)
            )
        case .japan:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 36.5, longitude: 138.0),
                span: MKCoordinateSpan(latitudeDelta: 5, longitudeDelta: 6)
            )
        case .oceania:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: -40.0, longitude: 165.0),
                span: MKCoordinateSpan(latitudeDelta: 20, longitudeDelta: 25)
            )
        }
    }

    var icon: String {
        switch self {
        case .userLocation: return "location.fill"
        case .naWest: return "sun.max"
        case .naRockies: return "mountain.2.fill"
        case .alps: return "flag.fill"
        case .japan: return "globe.asia.australia.fill"
        case .oceania: return "globe"
        }
    }
}

// MARK: - Map View Model

@MainActor
class MapViewModel: ObservableObject {
    @Published var annotations: [ResortAnnotation] = []
    @Published var selectedAnnotation: ResortAnnotation?
    @Published var selectedFilter: MapFilterOption = .all
    @Published var selectedRegionPreset: MapRegionPreset = .naRockies
    @Published var cameraPosition: MapCameraPosition = .automatic
    @Published var sortByDistance: Bool = false

    private let locationManager = LocationManager.shared
    private var cancellables = Set<AnyCancellable>()

    init() {
        setupLocationObserver()
    }

    private func setupLocationObserver() {
        locationManager.$userLocation
            .receive(on: DispatchQueue.main)
            .sink { [weak self] location in
                guard let self = self, let location = location else { return }
                if self.selectedRegionPreset == .userLocation {
                    self.centerOnUserLocation(location)
                }
            }
            .store(in: &cancellables)
    }

    // MARK: - Public Methods

    func updateAnnotations(
        resorts: [Resort],
        conditions: [String: [WeatherCondition]],
        snowQualitySummaries: [String: SnowQualitySummaryLight] = [:]
    ) {
        let allAnnotations = resorts.map { resort in
            let condition = conditions[resort.id]?.first
            // Use snow quality summary as fallback if no full condition available
            let fallbackQuality = snowQualitySummaries[resort.id]?.overallSnowQuality
            return ResortAnnotation(resort: resort, condition: condition, fallbackQuality: fallbackQuality)
        }

        // Apply filter
        annotations = allAnnotations.filter { annotation in
            selectedFilter.qualities.contains(annotation.snowQuality)
        }

        // Sort by distance if enabled and location available
        if sortByDistance, let userLocation = locationManager.userLocation {
            annotations.sort { a, b in
                let distA = a.resort.distance(from: userLocation)
                let distB = b.resort.distance(from: userLocation)
                return distA < distB
            }
        }
    }

    func selectAnnotation(_ annotation: ResortAnnotation?) {
        selectedAnnotation = annotation
    }

    func centerOnUserLocation(_ location: CLLocation? = nil) {
        let loc = location ?? locationManager.userLocation
        guard let userLoc = loc else {
            locationManager.requestLocationPermission()
            return
        }

        cameraPosition = .region(MKCoordinateRegion(
            center: userLoc.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 8, longitudeDelta: 10)
        ))
    }

    func setRegion(_ preset: MapRegionPreset) {
        selectedRegionPreset = preset
        if preset == .userLocation {
            centerOnUserLocation()
        } else {
            cameraPosition = .region(preset.region)
        }
    }

    func fitAllAnnotations() {
        guard !annotations.isEmpty else { return }

        let coordinates = annotations.map { $0.coordinate }
        let minLat = coordinates.map { $0.latitude }.min() ?? 0
        let maxLat = coordinates.map { $0.latitude }.max() ?? 0
        let minLon = coordinates.map { $0.longitude }.min() ?? 0
        let maxLon = coordinates.map { $0.longitude }.max() ?? 0

        let center = CLLocationCoordinate2D(
            latitude: (minLat + maxLat) / 2,
            longitude: (minLon + maxLon) / 2
        )

        // Calculate span with bounds validation to prevent crash
        var latDelta = (maxLat - minLat) * 1.3 + 2
        var lonDelta = (maxLon - minLon) * 1.3 + 2

        // Clamp to valid MapKit region bounds
        latDelta = min(max(latDelta, 0.01), 170.0)
        lonDelta = min(max(lonDelta, 0.01), 350.0)

        // Validate center coordinates
        guard center.latitude.isFinite && center.longitude.isFinite &&
              center.latitude >= -90 && center.latitude <= 90 &&
              center.longitude >= -180 && center.longitude <= 180 else {
            // Fallback to default region
            cameraPosition = .region(MapRegionPreset.naRockies.region)
            return
        }

        let span = MKCoordinateSpan(latitudeDelta: latDelta, longitudeDelta: lonDelta)
        cameraPosition = .region(MKCoordinateRegion(center: center, span: span))
    }

    func requestLocationPermission() {
        locationManager.requestLocationPermission()
    }

    // MARK: - Distance Helpers

    func formattedDistance(to resort: Resort) -> String? {
        guard let userLocation = locationManager.userLocation else { return nil }
        let distance = resort.distance(from: userLocation)
        return String(format: "%.0f km", distance / 1000)
    }

    // MARK: - Nearby Resorts

    func nearbyResorts(limit: Int = 5) -> [ResortAnnotation] {
        guard let userLocation = locationManager.userLocation else { return [] }

        return annotations
            .sorted { $0.resort.distance(from: userLocation) < $1.resort.distance(from: userLocation) }
            .prefix(limit)
            .map { $0 }
    }

    // MARK: - Quality Statistics

    var qualityStats: [SnowQuality: Int] {
        var stats: [SnowQuality: Int] = [:]
        for annotation in annotations {
            stats[annotation.snowQuality, default: 0] += 1
        }
        return stats
    }
}
