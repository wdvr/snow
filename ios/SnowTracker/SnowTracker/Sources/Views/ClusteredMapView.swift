import SwiftUI
import MapKit
import UIKit

// MARK: - Resort Point Annotation

final class ResortPointAnnotation: MKPointAnnotation {
    let resort: Resort
    let condition: WeatherCondition?
    let snowQuality: SnowQuality

    /// Initialize with a pre-computed snow quality (from ResortAnnotation which may have fallback from summary)
    init(resort: Resort, condition: WeatherCondition?, snowQuality: SnowQuality) {
        self.resort = resort
        self.condition = condition
        self.snowQuality = snowQuality
        super.init()
        self.coordinate = resort.primaryCoordinate
        self.title = resort.name
        self.subtitle = snowQuality.displayName
    }

    var markerColor: UIColor {
        UIColor(snowQuality.color)
    }
}

// MARK: - Clustered Map View (UIViewRepresentable)

struct ClusteredMapView: UIViewRepresentable {
    @Binding var cameraPosition: MapCameraPosition
    let annotations: [ResortAnnotation]
    let mapStyle: MapStyle
    let showUserLocation: Bool
    var onAnnotationTap: ((Resort) -> Void)?
    var onClusterTap: (([Resort]) -> Void)?

    // Cluster identifier
    private static let clusterIdentifier = "resortCluster"

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = showUserLocation
        mapView.showsCompass = true
        mapView.showsScale = true

        // Register annotation views
        mapView.register(
            ResortAnnotationView.self,
            forAnnotationViewWithReuseIdentifier: MKMapViewDefaultAnnotationViewReuseIdentifier
        )
        mapView.register(
            ResortClusterAnnotationView.self,
            forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier
        )

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        // Update map type
        updateMapType(mapView)

        // Update region from camera position
        updateRegion(mapView)

        // Update annotations
        updateAnnotations(mapView)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Private Methods

    private func updateMapType(_ mapView: MKMapView) {
        // MapStyle doesn't conform to Equatable, so we use String comparison
        let styleDescription = String(describing: mapStyle)
        if styleDescription.contains("imagery") {
            mapView.mapType = .satellite
        } else if styleDescription.contains("hybrid") {
            mapView.mapType = .hybrid
        } else {
            mapView.mapType = .standard
        }
    }

    private func updateRegion(_ mapView: MKMapView) {
        // MapCameraPosition doesn't expose its region directly in a pattern-matchable way
        // So we check its description or use a different approach
        let positionDescription = String(describing: cameraPosition)
        if positionDescription.contains("automatic") {
            if !annotations.isEmpty {
                fitAllAnnotations(mapView)
            }
        }
        // For region updates, we'll rely on the region passed through the binding
        // This is handled by SwiftUI's onChange in the parent view
    }

    private func updateAnnotations(_ mapView: MKMapView) {
        // Get current resort IDs
        let currentAnnotations = mapView.annotations.compactMap { $0 as? ResortPointAnnotation }
        let newIds = Set(annotations.map { $0.id })

        // Remove annotations that are no longer needed
        let toRemove = currentAnnotations.filter { !newIds.contains($0.resort.id) }
        mapView.removeAnnotations(toRemove)

        // Add new annotations
        let existingIds = Set(currentAnnotations.map { $0.resort.id })
        let toAdd = annotations.filter { !existingIds.contains($0.id) }
            .map { annotation in
                ResortPointAnnotation(resort: annotation.resort, condition: annotation.condition, snowQuality: annotation.snowQuality)
            }
        mapView.addAnnotations(toAdd)

        // Update existing annotations if condition changed
        for annotation in currentAnnotations {
            if let updatedData = annotations.first(where: { $0.id == annotation.resort.id }) {
                if annotation.snowQuality != updatedData.snowQuality {
                    // Need to remove and re-add to update the view
                    mapView.removeAnnotation(annotation)
                    mapView.addAnnotation(
                        ResortPointAnnotation(resort: updatedData.resort, condition: updatedData.condition, snowQuality: updatedData.snowQuality)
                    )
                }
            }
        }
    }

    private func fitAllAnnotations(_ mapView: MKMapView) {
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

        // Clamp to valid MapKit region bounds (max 180 lat, 360 lon)
        // Use slightly smaller values to avoid edge case issues
        latDelta = min(latDelta, 170.0)
        lonDelta = min(lonDelta, 350.0)

        // Ensure minimum reasonable zoom level
        latDelta = max(latDelta, 0.01)
        lonDelta = max(lonDelta, 0.01)

        // Validate center coordinates
        guard center.latitude.isFinite && center.longitude.isFinite &&
              center.latitude >= -90 && center.latitude <= 90 &&
              center.longitude >= -180 && center.longitude <= 180 else {
            // Fallback to a safe default region (North America)
            let defaultRegion = MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 45.0, longitude: -110.0),
                span: MKCoordinateSpan(latitudeDelta: 30, longitudeDelta: 40)
            )
            mapView.setRegion(defaultRegion, animated: false)
            return
        }

        let span = MKCoordinateSpan(latitudeDelta: latDelta, longitudeDelta: lonDelta)

        mapView.setRegion(MKCoordinateRegion(center: center, span: span), animated: false)
    }

    // MARK: - Coordinator

    final class Coordinator: NSObject, MKMapViewDelegate {
        var parent: ClusteredMapView

        init(_ parent: ClusteredMapView) {
            self.parent = parent
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            // Don't customize user location
            if annotation is MKUserLocation {
                return nil
            }

            // Handle cluster annotations
            if let cluster = annotation as? MKClusterAnnotation {
                let view = mapView.dequeueReusableAnnotationView(
                    withIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier,
                    for: annotation
                ) as? ResortClusterAnnotationView ?? ResortClusterAnnotationView(
                    annotation: annotation,
                    reuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier
                )
                view.configure(with: cluster)
                return view
            }

            // Handle resort annotations
            if let resortAnnotation = annotation as? ResortPointAnnotation {
                let view = mapView.dequeueReusableAnnotationView(
                    withIdentifier: MKMapViewDefaultAnnotationViewReuseIdentifier,
                    for: annotation
                ) as? ResortAnnotationView ?? ResortAnnotationView(
                    annotation: annotation,
                    reuseIdentifier: MKMapViewDefaultAnnotationViewReuseIdentifier
                )
                view.configure(with: resortAnnotation)
                return view
            }

            return nil
        }

        func mapView(_ mapView: MKMapView, didSelect annotation: MKAnnotation) {
            mapView.deselectAnnotation(annotation, animated: false)

            if let cluster = annotation as? MKClusterAnnotation {
                // Get all resorts in the cluster
                let resorts = cluster.memberAnnotations.compactMap { ($0 as? ResortPointAnnotation)?.resort }

                if resorts.count <= 10 {
                    // Zoom in to show individual pins
                    let region = MKCoordinateRegion(
                        center: cluster.coordinate,
                        span: MKCoordinateSpan(
                            latitudeDelta: mapView.region.span.latitudeDelta / 3,
                            longitudeDelta: mapView.region.span.longitudeDelta / 3
                        )
                    )
                    mapView.setRegion(region, animated: true)
                } else {
                    // Show cluster tap handler for larger clusters
                    parent.onClusterTap?(resorts)
                }
            } else if let resortAnnotation = annotation as? ResortPointAnnotation {
                parent.onAnnotationTap?(resortAnnotation.resort)
            }
        }

        func mapView(_ mapView: MKMapView, regionDidChangeAnimated animated: Bool) {
            // Update the binding when user interacts with map
            parent.cameraPosition = .region(mapView.region)
        }
    }
}

// MARK: - Resort Annotation View

final class ResortAnnotationView: MKAnnotationView {
    static let preferredClusteringIdentifier = "resortCluster"

    private let markerSize: CGFloat = 36
    private let pointerHeight: CGFloat = 8

    private lazy var markerImageView: UIImageView = {
        let imageView = UIImageView()
        imageView.contentMode = .scaleAspectFit
        return imageView
    }()

    override init(annotation: MKAnnotation?, reuseIdentifier: String?) {
        super.init(annotation: annotation, reuseIdentifier: reuseIdentifier)
        clusteringIdentifier = Self.preferredClusteringIdentifier
        collisionMode = .circle
        setupView()
    }

    required init?(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func setupView() {
        frame = CGRect(x: 0, y: 0, width: markerSize, height: markerSize + pointerHeight)
        centerOffset = CGPoint(x: 0, y: -frame.height / 2)
        addSubview(markerImageView)
        markerImageView.frame = bounds
    }

    func configure(with annotation: ResortPointAnnotation) {
        self.annotation = annotation
        let image = createMarkerImage(color: annotation.markerColor, quality: annotation.snowQuality)
        markerImageView.image = image

        // Accessibility
        isAccessibilityElement = true
        accessibilityLabel = "\(annotation.resort.name), \(annotation.snowQuality.displayName) snow quality"
        accessibilityTraits = .button
    }

    private func createMarkerImage(color: UIColor, quality: SnowQuality) -> UIImage {
        let size = CGSize(width: markerSize, height: markerSize + pointerHeight)

        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { context in
            let ctx = context.cgContext

            // Draw circle
            let circleRect = CGRect(x: 0, y: 0, width: markerSize, height: markerSize)
            ctx.setFillColor(color.cgColor)
            ctx.fillEllipse(in: circleRect)

            // Draw pointer triangle
            let pointerPath = UIBezierPath()
            pointerPath.move(to: CGPoint(x: markerSize / 2 - 6, y: markerSize - 2))
            pointerPath.addLine(to: CGPoint(x: markerSize / 2, y: markerSize + pointerHeight))
            pointerPath.addLine(to: CGPoint(x: markerSize / 2 + 6, y: markerSize - 2))
            pointerPath.close()

            ctx.setFillColor(color.cgColor)
            ctx.addPath(pointerPath.cgPath)
            ctx.fillPath()

            // Draw icon centered in the circle
            let iconSize: CGFloat = 18
            let iconConfig = UIImage.SymbolConfiguration(pointSize: iconSize, weight: .bold)
                .applying(UIImage.SymbolConfiguration(hierarchicalColor: .white))
            if let icon = UIImage(systemName: quality.icon, withConfiguration: iconConfig)?
                .withTintColor(.white, renderingMode: .alwaysOriginal) {
                // Calculate centered position
                let iconX = (markerSize - icon.size.width) / 2
                let iconY = (markerSize - icon.size.height) / 2
                let iconRect = CGRect(x: iconX, y: iconY, width: icon.size.width, height: icon.size.height)
                icon.draw(in: iconRect)
            }
        }
    }
}

// MARK: - Resort Cluster Annotation View

final class ResortClusterAnnotationView: MKAnnotationView {
    private let clusterSize: CGFloat = 44

    private lazy var pieChartLayer: CAShapeLayer = {
        let layer = CAShapeLayer()
        return layer
    }()

    private lazy var countLabel: UILabel = {
        let label = UILabel()
        label.font = .systemFont(ofSize: 14, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    override init(annotation: MKAnnotation?, reuseIdentifier: String?) {
        super.init(annotation: annotation, reuseIdentifier: reuseIdentifier)
        collisionMode = .circle
        setupView()
    }

    required init?(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func setupView() {
        frame = CGRect(x: 0, y: 0, width: clusterSize, height: clusterSize)
        centerOffset = CGPoint(x: 0, y: -clusterSize / 2)

        // Add pie chart sublayers
        layer.addSublayer(pieChartLayer)

        addSubview(countLabel)
        countLabel.frame = bounds
    }

    func configure(with cluster: MKClusterAnnotation) {
        self.annotation = cluster

        let memberAnnotations = cluster.memberAnnotations.compactMap { $0 as? ResortPointAnnotation }
        let count = memberAnnotations.count

        // Count by quality category (simplified: excellent/good = green, fair/poor = orange, bad/horrible = red)
        var greenCount = 0
        var orangeCount = 0
        var redCount = 0
        var blackCount = 0

        for annotation in memberAnnotations {
            switch annotation.snowQuality {
            case .excellent, .good:
                greenCount += 1
            case .fair, .poor, .slushy:
                orangeCount += 1
            case .bad:
                redCount += 1
            case .horrible:
                blackCount += 1
            case .unknown:
                orangeCount += 1  // Treat unknown as orange
            }
        }

        // Draw pie chart
        drawPieChart(green: greenCount, orange: orangeCount, red: redCount, black: blackCount, total: count)

        countLabel.text = count > 99 ? "99+" : "\(count)"

        // Accessibility
        isAccessibilityElement = true
        var qualityParts: [String] = []
        if greenCount > 0 { qualityParts.append("\(greenCount) excellent or good") }
        if orangeCount > 0 { qualityParts.append("\(orangeCount) fair or soft") }
        if redCount > 0 { qualityParts.append("\(redCount) icy") }
        if blackCount > 0 { qualityParts.append("\(blackCount) not skiable") }
        accessibilityLabel = "Cluster of \(count) resorts: \(qualityParts.joined(separator: ", "))"
        accessibilityTraits = .button

        // Add white border
        layer.cornerRadius = clusterSize / 2
        layer.borderWidth = 3
        layer.borderColor = UIColor.white.cgColor

        // Add shadow based on best quality
        let bestQuality = memberAnnotations
            .map { $0.snowQuality }
            .min(by: { $0.sortOrder < $1.sortOrder }) ?? .unknown
        layer.shadowColor = UIColor(bestQuality.color).cgColor
        layer.shadowOffset = CGSize(width: 0, height: 2)
        layer.shadowRadius = 4
        layer.shadowOpacity = 0.5
    }

    private func drawPieChart(green: Int, orange: Int, red: Int, black: Int, total: Int) {
        // Remove old sublayers
        pieChartLayer.sublayers?.forEach { $0.removeFromSuperlayer() }

        let center = CGPoint(x: clusterSize / 2, y: clusterSize / 2)
        let radius = clusterSize / 2
        var startAngle: CGFloat = -.pi / 2  // Start from top

        let segments: [(count: Int, color: UIColor)] = [
            (green, UIColor.systemGreen),
            (orange, UIColor.orange),
            (red, UIColor.red),
            (black, UIColor.black)
        ].filter { $0.count > 0 }

        // If all same category, just fill with that color
        if segments.count == 1 {
            backgroundColor = segments[0].color
            return
        }

        backgroundColor = .clear

        for (count, color) in segments {
            let proportion = CGFloat(count) / CGFloat(total)
            let endAngle = startAngle + (proportion * 2 * .pi)

            let path = UIBezierPath()
            path.move(to: center)
            path.addArc(withCenter: center, radius: radius, startAngle: startAngle, endAngle: endAngle, clockwise: true)
            path.close()

            let sliceLayer = CAShapeLayer()
            sliceLayer.path = path.cgPath
            sliceLayer.fillColor = color.cgColor
            pieChartLayer.addSublayer(sliceLayer)

            startAngle = endAngle
        }
    }
}
