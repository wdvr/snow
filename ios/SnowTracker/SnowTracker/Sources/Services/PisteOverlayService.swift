import Foundation
import MapKit

// MARK: - Piste Difficulty

/// OSM piste difficulty levels mapped to display colors and line widths.
enum PisteDifficulty: String, CaseIterable {
    case novice       // Green circle (NA) / Green (EU)
    case easy         // Green circle (NA) / Blue (EU)
    case intermediate // Blue square (NA) / Red (EU)
    case advanced     // Black diamond (NA) / Black (EU)
    case expert       // Double black (NA)
    case freeride     // Off-piste / backcountry
    case unknown

    init(osmValue: String) {
        switch osmValue {
        case "novice": self = .novice
        case "easy": self = .easy
        case "intermediate": self = .intermediate
        case "advanced": self = .advanced
        case "expert": self = .expert
        case "freeride": self = .freeride
        default: self = .unknown
        }
    }

    var color: UIColor {
        switch self {
        case .novice: UIColor.systemGreen
        case .easy: UIColor.systemBlue
        case .intermediate: UIColor.systemRed
        case .advanced, .expert: UIColor.black
        case .freeride: UIColor.systemOrange
        case .unknown: UIColor.systemGray
        }
    }

    var lineWidth: CGFloat {
        switch self {
        case .novice, .easy: 2.5
        case .intermediate: 2.5
        case .advanced, .expert: 2.5
        case .freeride: 2.0
        case .unknown: 1.5
        }
    }

    var sortOrder: Int {
        switch self {
        case .novice: 0
        case .easy: 1
        case .intermediate: 2
        case .advanced: 3
        case .expert: 4
        case .freeride: 5
        case .unknown: 6
        }
    }
}

// MARK: - Piste Polyline

/// MKPolyline subclass that carries difficulty metadata for the renderer.
final class PistePolyline: MKPolyline {
    private(set) var difficulty: PisteDifficulty = .unknown
    private(set) var pisteName: String?

    /// Create a PistePolyline from coordinates, difficulty, and optional name.
    static func create(
        coordinates: [CLLocationCoordinate2D],
        difficulty: PisteDifficulty,
        name: String?
    ) -> PistePolyline {
        var coords = coordinates
        let polyline = PistePolyline(coordinates: &coords, count: coords.count)
        polyline.difficulty = difficulty
        polyline.pisteName = name
        return polyline
    }
}

// MARK: - Lift Type

enum LiftType: String {
    case chairLift = "chair_lift"
    case gondola
    case cableCar = "cable_car"
    case dragLift = "drag_lift"
    case tBar = "t-bar"
    case platter
    case rope
    case other

    init(osmValue: String) {
        switch osmValue {
        case "chair_lift": self = .chairLift
        case "gondola": self = .gondola
        case "cable_car": self = .cableCar
        case "drag_lift", "j-bar", "magic_carpet": self = .dragLift
        case "t-bar": self = .tBar
        case "platter": self = .platter
        case "rope_tow": self = .rope
        default: self = .other
        }
    }

    var color: UIColor {
        UIColor.darkGray
    }

    var lineWidth: CGFloat {
        switch self {
        case .cableCar, .gondola: 2.0
        case .chairLift: 1.5
        default: 1.0
        }
    }
}

// MARK: - Lift Polyline

/// MKPolyline subclass for ski lift lines.
final class LiftPolyline: MKPolyline {
    private(set) var liftType: LiftType = .other
    private(set) var liftName: String?

    static func create(
        coordinates: [CLLocationCoordinate2D],
        liftType: LiftType,
        name: String?
    ) -> LiftPolyline {
        var coords = coordinates
        let polyline = LiftPolyline(coordinates: &coords, count: coords.count)
        polyline.liftType = liftType
        polyline.liftName = name
        return polyline
    }
}

// MARK: - Piste Overlay Result

struct PisteOverlayResult {
    let pistes: [PistePolyline]
    let lifts: [LiftPolyline]

    var allOverlays: [MKOverlay] {
        // Lifts first (below), pistes on top
        (lifts as [MKOverlay]) + (pistes as [MKOverlay])
    }

    var isEmpty: Bool { pistes.isEmpty && lifts.isEmpty }
}

// MARK: - Piste Overlay Service

/// Fetches piste/ski run data from OpenStreetMap via the Overpass API and converts
/// it into MKPolyline overlays for native rendering on MKMapView.
///
/// **Approach**: Query Overpass for `way["piste:type"="downhill"]` within a bounding box
/// around the resort, parse the GeoJSON-like response, and return typed polylines
/// grouped by difficulty.
///
/// **Caching**: Results are cached in memory per resort slug. The cache is bounded
/// to prevent unbounded growth (LRU eviction at 50 entries).
actor PisteOverlayService {
    static let shared = PisteOverlayService()

    /// Bounding box padding in degrees (~5km at mid-latitudes).
    /// Larger resorts (Vail, Chamonix) need ≥0.05° to capture all runs.
    private static let bboxPadding: Double = 0.05

    /// Overpass API endpoint
    private static let overpassURL = "https://overpass-api.de/api/interpreter"

    /// Cache: resort slug → overlay result
    private var cache: [String: PisteOverlayResult] = [:]
    private var cacheOrder: [String] = []  // LRU tracking
    private static let maxCacheSize = 50

    /// In-flight requests to avoid duplicate fetches
    private var inFlight: [String: Task<PisteOverlayResult, Error>] = [:]

    // MARK: - Public API

    /// Fetch piste + lift overlays for a resort. Returns cached data if available.
    func overlays(
        for resortSlug: String,
        coordinate: CLLocationCoordinate2D,
        boundingBoxPadding: Double? = nil
    ) async throws -> PisteOverlayResult {
        // Check cache
        if let cached = cache[resortSlug] {
            touchCache(resortSlug)
            return cached
        }

        // Deduplicate in-flight requests
        if let existing = inFlight[resortSlug] {
            return try await existing.value
        }

        let task = Task<PisteOverlayResult, Error> {
            let padding = boundingBoxPadding ?? Self.bboxPadding
            return try await fetchFromOverpass(
                coordinate: coordinate,
                padding: padding
            )
        }

        inFlight[resortSlug] = task

        do {
            let result = try await task.value
            inFlight[resortSlug] = nil
            storeInCache(resortSlug, result: result)
            return result
        } catch {
            inFlight[resortSlug] = nil
            throw error
        }
    }

    /// Clear cache for a specific resort or all resorts.
    func clearCache(for resortSlug: String? = nil) {
        if let slug = resortSlug {
            cache.removeValue(forKey: slug)
            cacheOrder.removeAll { $0 == slug }
        } else {
            cache.removeAll()
            cacheOrder.removeAll()
        }
    }

    // MARK: - Overpass Query

    private func fetchFromOverpass(
        coordinate: CLLocationCoordinate2D,
        padding: Double
    ) async throws -> PisteOverlayResult {
        let south = coordinate.latitude - padding
        let north = coordinate.latitude + padding
        let west = coordinate.longitude - padding
        let east = coordinate.longitude + padding

        // Overpass QL: fetch downhill pistes AND lifts in one query
        let query = """
        [out:json][timeout:20];
        (
          way["piste:type"="downhill"](\(south),\(west),\(north),\(east));
          way["aerialway"](\(south),\(west),\(north),\(east));
        );
        out body geom;
        """

        var request = URLRequest(url: URL(string: Self.overpassURL)!)
        request.httpMethod = "POST"
        request.httpBody = query.data(using: .utf8)
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 25

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw PisteOverlayError.networkError
        }

        return try parseOverpassResponse(data)
    }

    private func parseOverpassResponse(_ data: Data) throws -> PisteOverlayResult {
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let elements = json["elements"] as? [[String: Any]] else {
            throw PisteOverlayError.parseError
        }

        var pistes: [PistePolyline] = []
        var lifts: [LiftPolyline] = []

        for element in elements {
            guard let geometry = element["geometry"] as? [[String: Any]] else { continue }

            // Parse coordinates
            var coordinates: [CLLocationCoordinate2D] = []
            for node in geometry {
                guard let lat = node["lat"] as? Double,
                      let lon = node["lon"] as? Double else { continue }
                coordinates.append(CLLocationCoordinate2D(latitude: lat, longitude: lon))
            }

            guard coordinates.count >= 2 else { continue }

            let tags = element["tags"] as? [String: String] ?? [:]

            if let aerialway = tags["aerialway"] {
                // It's a lift
                let liftType = LiftType(osmValue: aerialway)
                let name = tags["name"]
                lifts.append(LiftPolyline.create(
                    coordinates: coordinates,
                    liftType: liftType,
                    name: name
                ))
            } else {
                // It's a piste
                let difficultyStr = tags["piste:difficulty"] ?? "unknown"
                let difficulty = PisteDifficulty(osmValue: difficultyStr)
                let name = tags["name"]
                pistes.append(PistePolyline.create(
                    coordinates: coordinates,
                    difficulty: difficulty,
                    name: name
                ))
            }
        }

        return PisteOverlayResult(pistes: pistes, lifts: lifts)
    }

    // MARK: - Cache Management

    private func touchCache(_ key: String) {
        cacheOrder.removeAll { $0 == key }
        cacheOrder.append(key)
    }

    private func storeInCache(_ key: String, result: PisteOverlayResult) {
        cache[key] = result
        touchCache(key)

        // Evict oldest if over limit
        while cacheOrder.count > Self.maxCacheSize {
            let evicted = cacheOrder.removeFirst()
            cache.removeValue(forKey: evicted)
        }
    }
}

// MARK: - Errors

enum PisteOverlayError: LocalizedError {
    case networkError
    case parseError

    var errorDescription: String? {
        switch self {
        case .networkError: "Failed to fetch piste data from OpenStreetMap"
        case .parseError: "Failed to parse piste data"
        }
    }
}
