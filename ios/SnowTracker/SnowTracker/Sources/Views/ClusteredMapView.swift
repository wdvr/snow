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
    @Binding var pendingRegion: MKCoordinateRegion?
    let annotations: [ResortAnnotation]
    let mapStyle: MapDisplayStyle
    let showUserLocation: Bool
    let showPisteOverlay: Bool
    let pisteOverlayResult: PisteOverlayResult?
    var onAnnotationTap: ((Resort) -> Void)?
    var onClusterTap: (([Resort]) -> Void)?
    var onRegionChange: ((MKCoordinateRegion) -> Void)?

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

        // Set initial region
        if let region = pendingRegion {
            mapView.setRegion(region, animated: false)
            DispatchQueue.main.async { self.pendingRegion = nil }
        } else {
            mapView.setRegion(MapRegionPreset.naRockies.region, animated: false)
        }

        // Register piste name annotation view
        mapView.register(
            PisteNameAnnotationView.self,
            forAnnotationViewWithReuseIdentifier: "pisteNameAnnotation"
        )

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        // Update map type
        updateMapType(mapView)

        // Update vector piste polylines + name labels
        updatePistePolylines(mapView, coordinator: context.coordinator)

        // Apply pending region change (from preset selection, fitAll, etc.)
        if let region = pendingRegion {
            context.coordinator.isProgrammaticRegionChange = true
            mapView.setRegion(region, animated: context.coordinator.hasInitialized)
            context.coordinator.hasInitialized = true
            DispatchQueue.main.async { self.pendingRegion = nil }
        }

        // Update annotations
        updateAnnotations(mapView)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Private Methods

    private func updateMapType(_ mapView: MKMapView) {
        mapView.mapType = mapStyle.mapType
    }

    private func updatePistePolylines(_ mapView: MKMapView, coordinator: Coordinator) {
        let newOverlays: [MKOverlay] = showPisteOverlay ? (pisteOverlayResult?.allOverlays ?? []) : []
        let currentIds = Set(coordinator.vectorOverlays.map { ObjectIdentifier($0) })
        let newIds = Set(newOverlays.map { ObjectIdentifier($0) })

        // Update polyline overlays if changed
        if currentIds != newIds {
            if !coordinator.vectorOverlays.isEmpty {
                mapView.removeOverlays(coordinator.vectorOverlays)
            }
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays, level: .aboveRoads)
            }
            coordinator.vectorOverlays = newOverlays
        }

        // Update piste name annotations
        let isZoomedIn = mapView.region.span.latitudeDelta < 0.04 // ~z14+
        let newNames: [PisteNameAnnotation] = (showPisteOverlay && isZoomedIn)
            ? buildPisteNameAnnotations()
            : []

        let currentNameIds = Set(coordinator.pisteNameAnnotations.map { $0.pisteId })
        let newNameIds = Set(newNames.map { $0.pisteId })

        if currentNameIds != newNameIds {
            if !coordinator.pisteNameAnnotations.isEmpty {
                mapView.removeAnnotations(coordinator.pisteNameAnnotations)
            }
            if !newNames.isEmpty {
                mapView.addAnnotations(newNames)
            }
            coordinator.pisteNameAnnotations = newNames
        }
    }

    private func buildPisteNameAnnotations() -> [PisteNameAnnotation] {
        guard let result = pisteOverlayResult else { return [] }

        var annotations: [PisteNameAnnotation] = []

        for piste in result.pistes {
            guard let name = piste.pisteName, !name.isEmpty else { continue }
            // Place label at midpoint of the piste
            let midIndex = piste.pointCount / 2
            guard midIndex < piste.pointCount else { continue }
            let points = piste.points()
            let midCoord = points[midIndex].coordinate

            let annotation = PisteNameAnnotation(
                pisteId: "\(name)-\(midCoord.latitude)-\(midCoord.longitude)",
                name: name,
                difficulty: piste.difficulty,
                colorScheme: piste.colorScheme,
                coordinate: midCoord
            )
            annotations.append(annotation)
        }

        for lift in result.lifts {
            guard let name = lift.liftName, !name.isEmpty else { continue }
            let midIndex = lift.pointCount / 2
            guard midIndex < lift.pointCount else { continue }
            let points = lift.points()
            let midCoord = points[midIndex].coordinate

            let annotation = PisteNameAnnotation(
                pisteId: "lift-\(name)-\(midCoord.latitude)-\(midCoord.longitude)",
                name: name,
                difficulty: nil,
                coordinate: midCoord
            )
            annotations.append(annotation)
        }

        return annotations
    }

    private func updateAnnotations(_ mapView: MKMapView) {
        let currentAnnotations = mapView.annotations.compactMap { $0 as? ResortPointAnnotation }
        let currentById = Dictionary(currentAnnotations.map { ($0.resort.id, $0) }, uniquingKeysWith: { first, _ in first })
        let newById = Dictionary(annotations.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })

        var toRemove: [MKAnnotation] = []
        var toAdd: [ResortPointAnnotation] = []

        // Annotations to remove: gone from new set, or quality changed
        for (id, current) in currentById {
            if let updated = newById[id] {
                if current.snowQuality != updated.snowQuality {
                    toRemove.append(current)
                    toAdd.append(ResortPointAnnotation(resort: updated.resort, condition: updated.condition, snowQuality: updated.snowQuality))
                }
            } else {
                toRemove.append(current)
            }
        }

        // Annotations to add: not in current set
        for (id, newAnnotation) in newById {
            if currentById[id] == nil {
                toAdd.append(ResortPointAnnotation(resort: newAnnotation.resort, condition: newAnnotation.condition, snowQuality: newAnnotation.snowQuality))
            }
        }

        // Batch operations — single remove then single add keeps MKMapView clustering consistent
        if !toRemove.isEmpty { mapView.removeAnnotations(toRemove) }
        if !toAdd.isEmpty { mapView.addAnnotations(toAdd) }
    }

    // MARK: - Coordinator

    final class Coordinator: NSObject, MKMapViewDelegate {
        var parent: ClusteredMapView
        var isProgrammaticRegionChange = false
        var hasInitialized = false
        var vectorOverlays: [MKOverlay] = []
        var pisteNameAnnotations: [PisteNameAnnotation] = []

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

            // Handle piste name annotations
            if let pisteAnnotation = annotation as? PisteNameAnnotation {
                let view = mapView.dequeueReusableAnnotationView(
                    withIdentifier: "pisteNameAnnotation",
                    for: annotation
                ) as? PisteNameAnnotationView ?? PisteNameAnnotationView(
                    annotation: annotation,
                    reuseIdentifier: "pisteNameAnnotation"
                )
                view.configure(with: pisteAnnotation)
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

            // Ignore piste name labels
            if annotation is PisteNameAnnotation { return }

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
                    isProgrammaticRegionChange = true
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
            let region = mapView.region
            // Skip binding update for programmatic changes (prevents feedback loop)
            if isProgrammaticRegionChange {
                isProgrammaticRegionChange = false
                // Still notify about region change so conditions get fetched for new area
                parent.onRegionChange?(region)
                return
            }
            // Update the binding when user interacts with map
            parent.cameraPosition = .region(region)
            parent.onRegionChange?(region)
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let pistePolyline = overlay as? PistePolyline {
                let renderer = MKPolylineRenderer(polyline: pistePolyline)
                renderer.strokeColor = pistePolyline.difficulty.color(scheme: pistePolyline.colorScheme)
                renderer.lineWidth = pistePolyline.difficulty.lineWidth
                renderer.alpha = 0.9
                renderer.lineCap = .round
                renderer.lineJoin = .round
                return renderer
            }

            if let liftPolyline = overlay as? LiftPolyline {
                let renderer = MKPolylineRenderer(polyline: liftPolyline)
                renderer.strokeColor = liftPolyline.liftType.color
                renderer.lineWidth = liftPolyline.liftType.lineWidth
                renderer.alpha = 0.6
                renderer.lineDashPattern = [8, 4]  // Dashed line for lifts
                renderer.lineCap = .butt
                return renderer
            }

            return MKOverlayRenderer(overlay: overlay)
        }
    }
}

// MARK: - Piste Name Annotation

/// Lightweight annotation placed at the midpoint of a piste/lift for labeling.
final class PisteNameAnnotation: NSObject, MKAnnotation {
    let pisteId: String
    let name: String
    let difficulty: PisteDifficulty?
    let colorScheme: PisteColorScheme
    let coordinate: CLLocationCoordinate2D

    init(pisteId: String, name: String, difficulty: PisteDifficulty?, colorScheme: PisteColorScheme = .european, coordinate: CLLocationCoordinate2D) {
        self.pisteId = pisteId
        self.name = name
        self.difficulty = difficulty
        self.colorScheme = colorScheme
        self.coordinate = coordinate
        super.init()
    }

    var title: String? { name }
}

// MARK: - Piste Name Annotation View

final class PisteNameAnnotationView: MKAnnotationView {
    private let nameLabel: UILabel = {
        let label = UILabel()
        label.font = .systemFont(ofSize: 10, weight: .semibold)
        label.textAlignment = .center
        label.numberOfLines = 1
        label.adjustsFontSizeToFitWidth = true
        label.minimumScaleFactor = 0.7
        return label
    }()

    override init(annotation: MKAnnotation?, reuseIdentifier: String?) {
        super.init(annotation: annotation, reuseIdentifier: reuseIdentifier)
        // Don't cluster piste names with resort pins
        clusteringIdentifier = nil
        collisionMode = .rectangle
        canShowCallout = false
        addSubview(nameLabel)
    }

    required init?(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func configure(with annotation: PisteNameAnnotation) {
        self.annotation = annotation
        clusteringIdentifier = nil
        nameLabel.text = annotation.name

        if let difficulty = annotation.difficulty {
            nameLabel.textColor = difficulty.labelColor(scheme: annotation.colorScheme)
        } else {
            // Lift
            nameLabel.textColor = .darkGray
        }

        // Size to fit the text
        nameLabel.sizeToFit()
        let padding: CGFloat = 6
        let width = min(nameLabel.frame.width + padding * 2, 120)
        let height = nameLabel.frame.height + 4
        frame = CGRect(x: 0, y: 0, width: width, height: height)
        nameLabel.frame = CGRect(x: padding, y: 2, width: width - padding * 2, height: height - 4)
        centerOffset = CGPoint(x: 0, y: -height / 2)

        // Semi-transparent background pill
        backgroundColor = UIColor.systemBackground.withAlphaComponent(0.8)
        layer.cornerRadius = height / 2
        layer.masksToBounds = true

        displayPriority = .defaultLow
        isAccessibilityElement = false
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
        clusteringIdentifier = Self.preferredClusteringIdentifier
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

        // Count by quality category
        var greenCount = 0
        var yellowCount = 0
        var orangeCount = 0
        var redCount = 0
        var blackCount = 0

        for annotation in memberAnnotations {
            switch annotation.snowQuality {
            case .champagnePowder, .powderDay, .excellent, .great, .good:
                greenCount += 1
            case .decent:
                yellowCount += 1
            case .mediocre, .poor:
                orangeCount += 1
            case .bad:
                redCount += 1
            case .horrible:
                blackCount += 1
            case .unknown:
                orangeCount += 1
            }
        }

        // Draw pie chart
        drawPieChart(green: greenCount, yellow: yellowCount, orange: orangeCount, red: redCount, black: blackCount, total: count)

        countLabel.text = count > 99 ? "99+" : "\(count)"

        // Accessibility
        isAccessibilityElement = true
        var qualityParts: [String] = []
        if greenCount > 0 { qualityParts.append("\(greenCount) excellent or good") }
        if yellowCount > 0 { qualityParts.append("\(yellowCount) decent") }
        if orangeCount > 0 { qualityParts.append("\(orangeCount) mediocre or poor") }
        if redCount > 0 { qualityParts.append("\(redCount) bad") }
        if blackCount > 0 { qualityParts.append("\(blackCount) horrible") }
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

    private func drawPieChart(green: Int, yellow: Int, orange: Int, red: Int, black: Int, total: Int) {
        // Remove old sublayers
        pieChartLayer.sublayers?.forEach { $0.removeFromSuperlayer() }

        let center = CGPoint(x: clusterSize / 2, y: clusterSize / 2)
        let radius = clusterSize / 2
        var startAngle: CGFloat = -.pi / 2  // Start from top

        let segments: [(count: Int, color: UIColor)] = [
            (green, UIColor.systemGreen),
            (yellow, UIColor.systemYellow),
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
