"""Tests for geographic utility functions."""

import pytest

from utils.geo_utils import (
    bounding_box,
    decode_geohash,
    encode_geohash,
    get_geohashes_for_radius,
    get_neighboring_geohashes,
    haversine_distance,
)


class TestHaversineDistance:
    """Test cases for haversine distance calculation."""

    def test_same_point_zero_distance(self):
        """Test that same point returns zero distance."""
        distance = haversine_distance(49.0, -120.0, 49.0, -120.0)
        assert distance == 0.0

    def test_known_distance_vancouver_whistler(self):
        """Test distance calculation between Vancouver and Whistler (~115km)."""
        # Vancouver: 49.2827, -123.1207
        # Whistler: 50.1163, -122.9574
        distance = haversine_distance(49.2827, -123.1207, 50.1163, -122.9574)
        # Actual road distance is ~125km, but straight-line is ~93km
        assert 90 < distance < 100

    def test_known_distance_los_angeles_san_francisco(self):
        """Test distance calculation between LA and San Francisco (~559km)."""
        # LA: 34.0522, -118.2437
        # SF: 37.7749, -122.4194
        distance = haversine_distance(34.0522, -118.2437, 37.7749, -122.4194)
        assert 540 < distance < 580

    def test_north_south_hemisphere(self):
        """Test distance calculation across hemispheres."""
        # Equator point and point in southern hemisphere
        distance = haversine_distance(0.0, 0.0, -45.0, 0.0)
        # 45 degrees at equator is about 5000km
        assert 4900 < distance < 5100

    def test_symmetric_calculation(self):
        """Test that distance is the same regardless of point order."""
        d1 = haversine_distance(49.0, -120.0, 50.0, -119.0)
        d2 = haversine_distance(50.0, -119.0, 49.0, -120.0)
        assert abs(d1 - d2) < 0.001

    def test_antipodal_points(self):
        """Test distance between antipodal points (opposite sides of Earth)."""
        # Should be close to half Earth's circumference (~20,000 km)
        distance = haversine_distance(0.0, 0.0, 0.0, 180.0)
        assert 19900 < distance < 20100


class TestBoundingBox:
    """Test cases for bounding box calculation."""

    def test_bounding_box_basic(self):
        """Test basic bounding box calculation."""
        min_lat, max_lat, min_lon, max_lon = bounding_box(49.0, -120.0, 100.0)

        # Box should be centered on the point
        assert min_lat < 49.0 < max_lat
        assert min_lon < -120.0 < max_lon

    def test_bounding_box_size(self):
        """Test that bounding box has approximately correct size."""
        radius = 100.0  # km
        min_lat, max_lat, min_lon, max_lon = bounding_box(49.0, -120.0, radius)

        # At ~49 degrees latitude, 1 degree latitude ~ 111 km
        # So 100km should be roughly 0.9 degrees
        lat_span = max_lat - min_lat
        assert 1.6 < lat_span < 2.0  # Should be close to 1.8 (2 * 100/111)

    def test_bounding_box_symmetric(self):
        """Test that bounding box is symmetric around center point."""
        lat, lon = 49.0, -120.0
        min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, 50.0)

        lat_diff_low = lat - min_lat
        lat_diff_high = max_lat - lat
        assert abs(lat_diff_low - lat_diff_high) < 0.001

        lon_diff_low = lon - min_lon
        lon_diff_high = max_lon - lon
        assert abs(lon_diff_low - lon_diff_high) < 0.001

    def test_bounding_box_near_equator(self):
        """Test bounding box near equator (where lon degrees are larger)."""
        min_lat, max_lat, min_lon, max_lon = bounding_box(0.0, 0.0, 100.0)

        # Near equator, lon and lat should span similar ranges
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        assert abs(lat_span - lon_span) < 0.5

    def test_bounding_box_high_latitude(self):
        """Test bounding box at high latitude (where lon degrees are smaller)."""
        min_lat, max_lat, min_lon, max_lon = bounding_box(70.0, 0.0, 100.0)

        # At high latitude, longitude span should be larger than latitude span
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        assert lon_span > lat_span

    def test_bounding_box_small_radius(self):
        """Test bounding box with small radius."""
        min_lat, max_lat, min_lon, max_lon = bounding_box(49.0, -120.0, 1.0)

        # 1km radius should give very small box
        lat_span = max_lat - min_lat
        assert lat_span < 0.1


class TestGeohashEncoding:
    """Test cases for geohash encoding."""

    def test_encode_known_location_whistler(self):
        """Test encoding Whistler's coordinates."""
        # Whistler: ~50.1163, -122.9574
        geohash = encode_geohash(50.1163, -122.9574, precision=5)
        assert len(geohash) == 5
        # Whistler should start with 'c2' (northern BC region)
        assert geohash.startswith("c2")

    def test_encode_known_location_chamonix(self):
        """Test encoding Chamonix's coordinates."""
        # Chamonix: ~45.9237, 6.8694
        geohash = encode_geohash(45.9237, 6.8694, precision=5)
        assert len(geohash) == 5
        # Chamonix should start with 'u0' (Alps region)
        assert geohash.startswith("u0")

    def test_encode_precision_increases_specificity(self):
        """Test that higher precision gives more specific geohash."""
        lat, lon = 49.0, -120.0
        gh3 = encode_geohash(lat, lon, precision=3)
        gh5 = encode_geohash(lat, lon, precision=5)
        gh7 = encode_geohash(lat, lon, precision=7)

        assert len(gh3) == 3
        assert len(gh5) == 5
        assert len(gh7) == 7
        # Lower precision should be prefix of higher precision
        assert gh5.startswith(gh3)
        assert gh7.startswith(gh5)

    def test_encode_nearby_points_share_prefix(self):
        """Test that nearby points share geohash prefix."""
        # Two points ~1km apart
        gh1 = encode_geohash(49.0, -120.0, precision=5)
        gh2 = encode_geohash(49.01, -120.0, precision=5)

        # Should share at least 4 characters (possibly all 5)
        common = 0
        for c1, c2 in zip(gh1, gh2, strict=False):
            if c1 == c2:
                common += 1
            else:
                break
        assert common >= 4

    def test_encode_distant_points_different_prefix(self):
        """Test that distant points have different geohash prefixes."""
        # Vancouver vs Sydney
        gh_vancouver = encode_geohash(49.2827, -123.1207, precision=3)
        gh_sydney = encode_geohash(-33.8688, 151.2093, precision=3)

        # First character should be different
        assert gh_vancouver[0] != gh_sydney[0]


class TestGeohashDecoding:
    """Test cases for geohash decoding."""

    def test_decode_returns_center(self):
        """Test that decoding returns approximate center of cell."""
        original_lat, original_lon = 49.0, -120.0
        geohash = encode_geohash(original_lat, original_lon, precision=5)
        decoded_lat, decoded_lon = decode_geohash(geohash)

        # Decoded should be close to original (within cell size)
        # Precision 5 has cell size ~5km, so ~0.05 degrees
        assert abs(decoded_lat - original_lat) < 0.1
        assert abs(decoded_lon - original_lon) < 0.1

    def test_encode_decode_roundtrip(self):
        """Test that encode/decode roundtrip maintains location."""
        test_points = [
            (0.0, 0.0),
            (49.0, -120.0),
            (-45.0, 170.0),
            (70.0, 25.0),
        ]

        for lat, lon in test_points:
            geohash = encode_geohash(lat, lon, precision=7)
            decoded_lat, decoded_lon = decode_geohash(geohash)

            # Precision 7 gives ~150m accuracy
            assert abs(decoded_lat - lat) < 0.01
            assert abs(decoded_lon - lon) < 0.02


class TestGeohashNeighbors:
    """Test cases for geohash neighbor calculation."""

    def test_neighbors_returns_8_hashes(self):
        """Test that get_neighboring_geohashes returns 8 neighbors."""
        geohash = encode_geohash(49.0, -120.0, precision=4)
        neighbors = get_neighboring_geohashes(geohash)

        assert len(neighbors) == 8

    def test_neighbors_same_precision(self):
        """Test that neighbors have same precision as input."""
        geohash = encode_geohash(49.0, -120.0, precision=4)
        neighbors = get_neighboring_geohashes(geohash)

        for neighbor in neighbors:
            assert len(neighbor) == len(geohash)

    def test_neighbors_different_from_center(self):
        """Test that neighbors are different from center."""
        geohash = encode_geohash(49.0, -120.0, precision=4)
        neighbors = get_neighboring_geohashes(geohash)

        for neighbor in neighbors:
            # All neighbors should differ from center
            assert neighbor != geohash

    def test_empty_geohash_returns_empty(self):
        """Test that empty geohash returns empty list."""
        neighbors = get_neighboring_geohashes("")
        assert neighbors == []


class TestGeohashesForRadius:
    """Test cases for radius-based geohash calculation."""

    def test_returns_center_and_neighbors(self):
        """Test that get_geohashes_for_radius returns center + neighbors."""
        hashes = get_geohashes_for_radius(49.0, -120.0, 100.0, precision=4)

        # Should return up to 9 hashes (center + 8 neighbors)
        assert 1 <= len(hashes) <= 9

    def test_no_duplicates(self):
        """Test that returned geohashes are unique."""
        hashes = get_geohashes_for_radius(49.0, -120.0, 100.0, precision=4)

        assert len(hashes) == len(set(hashes))

    def test_all_same_precision(self):
        """Test that all returned hashes have same precision."""
        precision = 4
        hashes = get_geohashes_for_radius(49.0, -120.0, 100.0, precision=precision)

        for h in hashes:
            assert len(h) == precision
