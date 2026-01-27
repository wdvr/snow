"""Tests for geographic utility functions."""

import pytest

from utils.geo_utils import bounding_box, haversine_distance


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
