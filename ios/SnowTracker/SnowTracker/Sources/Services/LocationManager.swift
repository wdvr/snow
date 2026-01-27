import Foundation
import CoreLocation
import Combine

@MainActor
class LocationManager: NSObject, ObservableObject {
    static let shared = LocationManager()

    @Published var userLocation: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published var isLocationAvailable: Bool = false
    @Published var errorMessage: String?

    private let locationManager = CLLocationManager()

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyKilometer
        authorizationStatus = locationManager.authorizationStatus
        updateLocationAvailability()
    }

    func requestLocationPermission() {
        locationManager.requestWhenInUseAuthorization()
    }

    func startUpdatingLocation() {
        guard authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways else {
            requestLocationPermission()
            return
        }
        locationManager.startUpdatingLocation()
    }

    func stopUpdatingLocation() {
        locationManager.stopUpdatingLocation()
    }

    func requestOneTimeLocation() {
        guard authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways else {
            requestLocationPermission()
            return
        }
        locationManager.requestLocation()
    }

    private func updateLocationAvailability() {
        isLocationAvailable = (authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways)
    }

    // MARK: - Distance Calculations

    func distance(to coordinate: CLLocationCoordinate2D) -> CLLocationDistance? {
        guard let userLocation = userLocation else { return nil }
        let destination = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        return userLocation.distance(from: destination)
    }

    func formattedDistance(to coordinate: CLLocationCoordinate2D, useMetric: Bool = true) -> String? {
        guard let meters = distance(to: coordinate) else { return nil }

        if useMetric {
            if meters < 1000 {
                return "\(Int(meters)) m"
            } else {
                return String(format: "%.1f km", meters / 1000)
            }
        } else {
            let miles = meters / 1609.34
            if miles < 0.5 {
                let feet = meters * 3.28084
                return "\(Int(feet)) ft"
            } else {
                return String(format: "%.1f mi", miles)
            }
        }
    }
}

// MARK: - CLLocationManagerDelegate

extension LocationManager: CLLocationManagerDelegate {
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        Task { @MainActor in
            self.userLocation = location
            self.errorMessage = nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
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
                self.errorMessage = "Location error: \(error.localizedDescription)"
            }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            self.authorizationStatus = status
            self.updateLocationAvailability()

            if self.authorizationStatus == .authorizedWhenInUse || self.authorizationStatus == .authorizedAlways {
                self.locationManager.requestLocation()
            }
        }
    }
}

// MARK: - Resort Distance Extensions

extension Resort {
    /// Get the primary coordinate for the resort (uses mid elevation, falls back to base)
    var primaryCoordinate: CLLocationCoordinate2D {
        let point = midElevation ?? baseElevation ?? elevationPoints.first
        return point?.coordinate ?? CLLocationCoordinate2D(latitude: 0, longitude: 0)
    }

    /// Get distance from user to resort
    func distance(from location: CLLocation) -> CLLocationDistance {
        let resortLocation = CLLocation(latitude: primaryCoordinate.latitude, longitude: primaryCoordinate.longitude)
        return location.distance(from: resortLocation)
    }
}
