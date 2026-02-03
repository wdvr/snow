"""Geographic utility functions for distance calculations and geohashing."""

import math

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0

# Geohash base32 alphabet (standard geohash encoding, excludes a, i, l, o)
GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"
GEOHASH_DECODE_MAP = {c: i for i, c in enumerate(GEOHASH_ALPHABET)}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the haversine formula to calculate the shortest distance over
    the earth's surface between two points.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance in kilometers
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def bounding_box(
    lat: float, lon: float, radius_km: float
) -> tuple[float, float, float, float]:
    """
    Calculate a bounding box around a point for quick filtering.

    This is an approximation that works well for typical radii.

    Args:
        lat: Center latitude in degrees
        lon: Center longitude in degrees
        radius_km: Radius in kilometers

    Returns:
        Tuple of (min_lat, max_lat, min_lon, max_lon) in degrees
    """
    # Approximate degrees per km
    # At the equator, 1 degree = 111 km
    km_per_degree_lat = 111.0
    km_per_degree_lon = 111.0 * math.cos(math.radians(lat))

    delta_lat = radius_km / km_per_degree_lat
    delta_lon = radius_km / km_per_degree_lon if km_per_degree_lon > 0 else 180.0

    return (
        lat - delta_lat,
        lat + delta_lat,
        lon - delta_lon,
        lon + delta_lon,
    )


def encode_geohash(latitude: float, longitude: float, precision: int = 5) -> str:
    """
    Encode lat/lon to geohash string.

    Precision levels and approximate cell sizes:
        1: ~5,000 km
        2: ~1,250 km
        3: ~156 km
        4: ~39 km
        5: ~5 km (good for ski resort queries)
        6: ~1.2 km

    Args:
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)
        precision: Number of characters in the geohash (default 5)

    Returns:
        Geohash string of specified precision
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]

    geohash = []
    bits = 0
    bit_count = 0
    is_longitude = True

    while len(geohash) < precision:
        if is_longitude:
            mid = (lon_range[0] + lon_range[1]) / 2
            if longitude >= mid:
                bits = (bits << 1) | 1
                lon_range[0] = mid
            else:
                bits = bits << 1
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if latitude >= mid:
                bits = (bits << 1) | 1
                lat_range[0] = mid
            else:
                bits = bits << 1
                lat_range[1] = mid

        is_longitude = not is_longitude
        bit_count += 1

        if bit_count == 5:
            geohash.append(GEOHASH_ALPHABET[bits])
            bits = 0
            bit_count = 0

    return "".join(geohash)


def decode_geohash(geohash: str) -> tuple[float, float]:
    """
    Decode geohash to approximate lat/lon center.

    Args:
        geohash: Geohash string

    Returns:
        Tuple of (latitude, longitude) as the center of the geohash cell
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_longitude = True

    for char in geohash.lower():
        if char not in GEOHASH_DECODE_MAP:
            continue

        bits = GEOHASH_DECODE_MAP[char]

        for i in range(4, -1, -1):
            bit = (bits >> i) & 1
            if is_longitude:
                mid = (lon_range[0] + lon_range[1]) / 2
                if bit:
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if bit:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            is_longitude = not is_longitude

    return (
        (lat_range[0] + lat_range[1]) / 2,
        (lon_range[0] + lon_range[1]) / 2,
    )


def get_neighboring_geohashes(geohash: str) -> list[str]:
    """
    Get the 8 neighboring geohashes for bounding box queries.

    Uses a simple approach: decode the center, compute the 8 cardinal/diagonal
    neighbors, and re-encode them.

    Args:
        geohash: The center geohash

    Returns:
        List of 8 neighboring geohash strings (N, NE, E, SE, S, SW, W, NW)
    """
    if not geohash:
        return []

    precision = len(geohash)

    # Calculate the approximate size of a geohash cell at this precision
    # Each character adds ~5 bits, alternating lat/lon
    # Precision 4 = ~39km, Precision 5 = ~5km
    lat_bits = (precision * 5) // 2
    lon_bits = precision * 5 - lat_bits

    lat_delta = 180.0 / (2**lat_bits)
    lon_delta = 360.0 / (2**lon_bits)

    # Decode center
    center_lat, center_lon = decode_geohash(geohash)

    # Calculate 8 neighbors
    neighbors = []
    directions = [
        (1, 0),  # N
        (1, 1),  # NE
        (0, 1),  # E
        (-1, 1),  # SE
        (-1, 0),  # S
        (-1, -1),  # SW
        (0, -1),  # W
        (1, -1),  # NW
    ]

    for lat_dir, lon_dir in directions:
        neighbor_lat = center_lat + (lat_dir * lat_delta)
        neighbor_lon = center_lon + (lon_dir * lon_delta)

        # Handle latitude bounds
        neighbor_lat = max(-90.0, min(90.0, neighbor_lat))

        # Handle longitude wrap-around
        if neighbor_lon > 180.0:
            neighbor_lon -= 360.0
        elif neighbor_lon < -180.0:
            neighbor_lon += 360.0

        neighbor_hash = encode_geohash(neighbor_lat, neighbor_lon, precision)
        neighbors.append(neighbor_hash)

    return neighbors


def get_geohashes_for_radius(
    latitude: float, longitude: float, radius_km: float, precision: int = 4
) -> list[str]:
    """
    Get all geohashes that might contain points within a radius.

    This returns the center geohash and its neighbors, which should cover
    most typical search radii when using precision 4 (~39km cells).

    For larger radii (>100km), consider using precision 3.
    For smaller radii (<20km), consider using precision 5.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_km: Search radius in kilometers
        precision: Geohash precision (default 4 for ~39km cells)

    Returns:
        List of unique geohash strings to query
    """
    center_hash = encode_geohash(latitude, longitude, precision)
    neighbors = get_neighboring_geohashes(center_hash)

    # Combine center + 8 neighbors and deduplicate
    all_hashes = [center_hash] + neighbors
    unique_hashes = list(dict.fromkeys(all_hashes))  # Preserve order, remove dupes

    # Remove any empty strings (edge cases near poles)
    return [h for h in unique_hashes if h]
