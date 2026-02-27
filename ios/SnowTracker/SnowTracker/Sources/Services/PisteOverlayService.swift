import Foundation
import MapKit

// MARK: - Piste Color Scheme

/// Regional color conventions for piste difficulty markings.
/// NA uses green circle / blue square / black diamond.
/// EU uses green / blue / red / black.
enum PisteColorScheme {
    case northAmerican  // US, CA
    case european       // Default for all other countries

    init(country: String) {
        switch country.uppercased() {
        case "US", "CA": self = .northAmerican
        default: self = .european
        }
    }
}

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

    func color(scheme: PisteColorScheme) -> UIColor {
        switch scheme {
        case .northAmerican:
            switch self {
            case .novice, .easy: UIColor.systemGreen
            case .intermediate: UIColor.systemBlue
            case .advanced, .expert: UIColor.black
            case .freeride: UIColor.systemOrange
            case .unknown: UIColor.systemGray
            }
        case .european:
            switch self {
            case .novice: UIColor.systemGreen
            case .easy: UIColor.systemBlue
            case .intermediate: UIColor.systemRed
            case .advanced, .expert: UIColor.black
            case .freeride: UIColor.systemOrange
            case .unknown: UIColor.systemGray
            }
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

    /// High-contrast color for text labels on white/light backgrounds.
    func labelColor(scheme: PisteColorScheme) -> UIColor {
        switch scheme {
        case .northAmerican:
            switch self {
            case .novice, .easy: UIColor(red: 0, green: 0.55, blue: 0, alpha: 1)
            case .intermediate: UIColor(red: 0, green: 0.25, blue: 0.75, alpha: 1)
            case .advanced, .expert: UIColor.black
            case .freeride: UIColor(red: 0.7, green: 0.4, blue: 0, alpha: 1)
            case .unknown: UIColor.darkGray
            }
        case .european:
            switch self {
            case .novice: UIColor(red: 0, green: 0.55, blue: 0, alpha: 1)
            case .easy: UIColor(red: 0, green: 0.25, blue: 0.75, alpha: 1)
            case .intermediate: UIColor(red: 0.75, green: 0, blue: 0, alpha: 1)
            case .advanced, .expert: UIColor.black
            case .freeride: UIColor(red: 0.7, green: 0.4, blue: 0, alpha: 1)
            case .unknown: UIColor.darkGray
            }
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
    private(set) var colorScheme: PisteColorScheme = .european

    /// Create a PistePolyline from coordinates, difficulty, and optional name.
    static func create(
        coordinates: [CLLocationCoordinate2D],
        difficulty: PisteDifficulty,
        name: String?,
        colorScheme: PisteColorScheme = .european
    ) -> PistePolyline {
        var coords = coordinates
        let polyline = PistePolyline(coordinates: &coords, count: coords.count)
        polyline.difficulty = difficulty
        polyline.pisteName = name
        polyline.colorScheme = colorScheme
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

/// Fetches piste/ski run data for native rendering on MKMapView.
///
/// **Data flow**: Try pre-cached S3 JSON first → fall back to live Overpass API query.
/// Pre-cached data is generated by `backend/scripts/precache_pistes.py`.
///
/// **Caching**: Results are cached in memory per resort slug with LRU eviction at 50 entries.
actor PisteOverlayService {
    static let shared = PisteOverlayService()

    /// S3 pre-cache URL template. Resort piste data is pre-generated and uploaded here.
    private static let s3URLTemplate = "https://powderchaserapp.com/data/pistes/%@.json"

    /// Bounding box padding in degrees (~5km at mid-latitudes) for Overpass fallback.
    private static let bboxPadding: Double = 0.05

    /// Overpass API endpoint (fallback when S3 cache miss)
    private static let overpassURL = "https://overpass-api.de/api/interpreter"

    /// Cache: resort slug → overlay result
    private var cache: [String: PisteOverlayResult] = [:]
    private var cacheOrder: [String] = []  // LRU tracking
    private static let maxCacheSize = 50

    /// In-flight requests to avoid duplicate fetches
    private var inFlight: [String: Task<PisteOverlayResult, Error>] = [:]

    // MARK: - Public API

    /// Fetch piste + lift overlays for a resort.
    /// Tries S3 pre-cache first, falls back to live Overpass API query.
    func overlays(
        for resortSlug: String,
        coordinate: CLLocationCoordinate2D,
        colorScheme: PisteColorScheme = .european,
        boundingBoxPadding: Double? = nil
    ) async throws -> PisteOverlayResult {
        // Check memory cache
        if let cached = cache[resortSlug] {
            touchCache(resortSlug)
            return cached
        }

        // Deduplicate in-flight requests
        if let existing = inFlight[resortSlug] {
            return try await existing.value
        }

        let task = Task<PisteOverlayResult, Error> {
            // Try S3 pre-cache first
            if let s3Result = try? await fetchFromS3(resortSlug: resortSlug, colorScheme: colorScheme), !s3Result.isEmpty {
                return s3Result
            }

            // Fall back to live Overpass query
            let padding = boundingBoxPadding ?? Self.bboxPadding
            return try await fetchFromOverpass(
                coordinate: coordinate,
                padding: padding,
                colorScheme: colorScheme
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

    // MARK: - S3 Pre-Cache Fetch

    private func fetchFromS3(resortSlug: String, colorScheme: PisteColorScheme) async throws -> PisteOverlayResult {
        let urlString = String(format: Self.s3URLTemplate, resortSlug)
        guard let url = URL(string: urlString) else { throw PisteOverlayError.parseError }

        var request = URLRequest(url: url)
        request.timeoutInterval = 10

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw PisteOverlayError.networkError
        }

        return try parseS3Response(data, colorScheme: colorScheme)
    }

    private func parseS3Response(_ data: Data, colorScheme: PisteColorScheme) throws -> PisteOverlayResult {
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw PisteOverlayError.parseError
        }

        var pistes: [PistePolyline] = []
        var lifts: [LiftPolyline] = []

        if let pisteArray = json["pistes"] as? [[String: Any]] {
            for item in pisteArray {
                guard let coords = item["coords"] as? [[Double]], coords.count >= 2 else { continue }
                let coordinates = coords.map {
                    CLLocationCoordinate2D(latitude: $0[0], longitude: $0[1])
                }
                let diffStr = item["difficulty"] as? String ?? "unknown"
                let difficulty = PisteDifficulty(osmValue: diffStr)
                let name = item["name"] as? String
                pistes.append(PistePolyline.create(
                    coordinates: coordinates, difficulty: difficulty, name: name, colorScheme: colorScheme
                ))
            }
        }

        if let liftArray = json["lifts"] as? [[String: Any]] {
            for item in liftArray {
                guard let coords = item["coords"] as? [[Double]], coords.count >= 2 else { continue }
                let coordinates = coords.map {
                    CLLocationCoordinate2D(latitude: $0[0], longitude: $0[1])
                }
                let typeStr = item["type"] as? String ?? "other"
                let liftType = LiftType(osmValue: typeStr)
                let name = item["name"] as? String
                lifts.append(LiftPolyline.create(
                    coordinates: coordinates, liftType: liftType, name: name
                ))
            }
        }

        return PisteOverlayResult(pistes: pistes, lifts: lifts)
    }

    // MARK: - Overpass Query

    private func fetchFromOverpass(
        coordinate: CLLocationCoordinate2D,
        padding: Double,
        colorScheme: PisteColorScheme
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

        return try parseOverpassResponse(data, colorScheme: colorScheme)
    }

    private func parseOverpassResponse(_ data: Data, colorScheme: PisteColorScheme) throws -> PisteOverlayResult {
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
                    name: name,
                    colorScheme: colorScheme
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
