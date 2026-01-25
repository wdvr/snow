import Foundation
import CoreLocation
import Combine

// MARK: - Location Manager

@MainActor
class LocationManager: NSObject, ObservableObject {
    static let shared = LocationManager()

    @Published var userLocation: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let locationManager = CLLocationManager()

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyKilometer
        authorizationStatus = locationManager.authorizationStatus
    }

    // MARK: - Authorization

    var isAuthorized: Bool {
        authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways
    }

    var needsAuthorization: Bool {
        authorizationStatus == .notDetermined
    }

    func requestAuthorization() {
        locationManager.requestWhenInUseAuthorization()
    }

    // MARK: - Location Updates

    func requestLocation() {
        guard isAuthorized else {
            if needsAuthorization {
                requestAuthorization()
            } else {
                errorMessage = "Location access denied. Enable in Settings."
            }
            return
        }

        isLoading = true
        errorMessage = nil
        locationManager.requestLocation()
    }

    func startUpdatingLocation() {
        guard isAuthorized else {
            if needsAuthorization {
                requestAuthorization()
            }
            return
        }

        locationManager.startUpdatingLocation()
    }

    func stopUpdatingLocation() {
        locationManager.stopUpdatingLocation()
    }

    // MARK: - Distance Calculations

    func distance(to coordinate: CLLocationCoordinate2D) -> CLLocationDistance? {
        guard let userLocation = userLocation else { return nil }
        let location = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        return userLocation.distance(from: location)
    }

    func distance(to resort: Resort) -> CLLocationDistance? {
        guard let basePoint = resort.baseElevation else { return nil }
        return distance(to: basePoint.coordinate)
    }

    func formattedDistance(to resort: Resort) -> String? {
        guard let meters = distance(to: resort) else { return nil }
        let km = meters / 1000
        let miles = meters / 1609.34

        if km < 100 {
            return String(format: "%.0f km", km)
        } else {
            return String(format: "%.0f km", km)
        }
    }

    func formattedDistanceMiles(to resort: Resort) -> String? {
        guard let meters = distance(to: resort) else { return nil }
        let miles = meters / 1609.34
        return String(format: "%.0f mi", miles)
    }
}

// MARK: - CLLocationManagerDelegate

extension LocationManager: CLLocationManagerDelegate {
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }

        Task { @MainActor in
            self.userLocation = location
            self.isLoading = false
            self.errorMessage = nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            self.isLoading = false

            if let clError = error as? CLError {
                switch clError.code {
                case .denied:
                    self.errorMessage = "Location access denied"
                case .locationUnknown:
                    self.errorMessage = "Unable to determine location"
                default:
                    self.errorMessage = "Location error: \(clError.localizedDescription)"
                }
            } else {
                self.errorMessage = error.localizedDescription
            }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            self.authorizationStatus = manager.authorizationStatus

            if self.isAuthorized && self.userLocation == nil {
                self.requestLocation()
            }
        }
    }
}

// MARK: - Resort Distance Extension

extension Resort {
    func distance(from location: CLLocation) -> CLLocationDistance? {
        guard let basePoint = baseElevation else { return nil }
        let resortLocation = CLLocation(latitude: basePoint.latitude, longitude: basePoint.longitude)
        return location.distance(from: resortLocation)
    }
}
