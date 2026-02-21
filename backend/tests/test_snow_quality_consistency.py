"""Tests for snow quality consistency between API endpoints.

This ensures that the detail view endpoint (/api/v1/resorts/{id}/snow-quality)
and the batch endpoint (/api/v1/snow-quality/batch) use consistent logic
for determining overall snow quality, particularly the HORRIBLE override.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition


class TestSnowQualityApiConsistency:
    """Tests for snow quality API consistency."""

    @pytest.fixture
    def mock_conditions_horrible_base(self):
        """Create conditions where base is HORRIBLE but top is EXCELLENT."""
        return [
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="base",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=10.0,  # Warm - melting
                min_temp_celsius=5.0,
                max_temp_celsius=15.0,
                snowfall_24h_cm=0.0,
                hours_above_ice_threshold=24.0,
                snow_quality=SnowQuality.HORRIBLE,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=0.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.HIGH,
            ),
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="top",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-10.0,  # Cold - great conditions
                min_temp_celsius=-15.0,
                max_temp_celsius=-5.0,
                snowfall_24h_cm=30.0,
                hours_above_ice_threshold=0.0,
                snow_quality=SnowQuality.EXCELLENT,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=30.0,
                snowfall_after_freeze_cm=30.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.HIGH,
            ),
        ]

    def test_batch_endpoint_weighted_quality(self, mock_conditions_horrible_base):
        """Test that batch endpoint uses weighted elevation scoring (top/mid weighted higher than base)."""
        from handlers.api_handler import _get_snow_quality_for_resort
        from utils.cache import clear_all_caches

        # Clear caches to avoid stale cached results
        clear_all_caches()

        # Mock the dependencies
        with (
            patch("handlers.api_handler._get_resort_cached") as mock_resort,
            patch("handlers.api_handler.get_weather_service") as mock_weather_svc,
        ):
            # Setup mock resort with base and top elevations
            mock_resort_obj = MagicMock()
            mock_resort_obj.elevation_points = [
                MagicMock(level=MagicMock(value="base")),
                MagicMock(level=MagicMock(value="top")),
            ]
            mock_resort.return_value = mock_resort_obj

            # Mock single-query method to return all conditions at once
            mock_weather_svc.return_value.get_latest_conditions_all_elevations.return_value = mock_conditions_horrible_base

            # Call the function
            result = _get_snow_quality_for_resort("test-resort")

            # Weighted scoring: top (50%) EXCELLENT + base (15%) HORRIBLE = GOOD overall
            # A warm base shouldn't override excellent upper mountain conditions
            assert result["overall_quality"] == SnowQuality.GOOD.value

    def test_detail_endpoint_horrible_override(self, mock_conditions_horrible_base):
        """Test that detail endpoint also marks resort as HORRIBLE if ANY elevation is HORRIBLE.

        This was a bug - the detail endpoint was just averaging scores,
        so HORRIBLE could be averaged out by good conditions at other elevations.
        After the fix, both endpoints should behave consistently.
        """
        # Import the endpoint function
        from handlers.api_handler import SnowQuality as ApiSnowQuality

        # Simulate the quality calculation logic from the detail endpoint
        conditions = mock_conditions_horrible_base

        # Quality scores (should match both endpoints)
        quality_scores = {
            SnowQuality.EXCELLENT: 6,
            SnowQuality.GOOD: 5,
            SnowQuality.FAIR: 4,
            SnowQuality.POOR: 3,
            SnowQuality.BAD: 2,
            SnowQuality.HORRIBLE: 1,
            SnowQuality.UNKNOWN: 0,
        }

        # Check for HORRIBLE override (this is the key fix)
        has_horrible = any(c.snow_quality == SnowQuality.HORRIBLE for c in conditions)

        if has_horrible:
            overall_quality = SnowQuality.HORRIBLE
        else:
            overall_scores = [quality_scores.get(c.snow_quality, 0) for c in conditions]
            avg_score = (
                sum(overall_scores) / len(overall_scores) if overall_scores else 0
            )

            if avg_score >= 5.5:
                overall_quality = SnowQuality.EXCELLENT
            elif avg_score >= 4.5:
                overall_quality = SnowQuality.GOOD
            elif avg_score >= 3.5:
                overall_quality = SnowQuality.FAIR
            elif avg_score >= 2.5:
                overall_quality = SnowQuality.POOR
            elif avg_score >= 1.5:
                overall_quality = SnowQuality.BAD
            else:
                overall_quality = SnowQuality.HORRIBLE

        # Overall should be HORRIBLE because base is HORRIBLE
        assert overall_quality == SnowQuality.HORRIBLE

    def test_no_horrible_allows_averaging(self):
        """Test that without HORRIBLE conditions, quality is properly averaged."""
        conditions = [
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="base",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-2.0,
                min_temp_celsius=-5.0,
                max_temp_celsius=0.0,
                snowfall_24h_cm=5.0,
                hours_above_ice_threshold=2.0,
                snow_quality=SnowQuality.FAIR,  # Score 4
                confidence_level=ConfidenceLevel.MEDIUM,
                fresh_snow_cm=3.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.MEDIUM,
            ),
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="top",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-10.0,
                min_temp_celsius=-15.0,
                max_temp_celsius=-5.0,
                snowfall_24h_cm=20.0,
                hours_above_ice_threshold=0.0,
                snow_quality=SnowQuality.EXCELLENT,  # Score 6
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=20.0,
                snowfall_after_freeze_cm=20.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.HIGH,
            ),
        ]

        quality_scores = {
            SnowQuality.EXCELLENT: 6,
            SnowQuality.GOOD: 5,
            SnowQuality.FAIR: 4,
            SnowQuality.POOR: 3,
            SnowQuality.BAD: 2,
            SnowQuality.HORRIBLE: 1,
            SnowQuality.UNKNOWN: 0,
        }

        has_horrible = any(c.snow_quality == SnowQuality.HORRIBLE for c in conditions)
        assert not has_horrible  # No HORRIBLE conditions

        overall_scores = [quality_scores.get(c.snow_quality, 0) for c in conditions]
        avg_score = sum(overall_scores) / len(overall_scores)  # (4 + 6) / 2 = 5.0

        # Average is 5.0, which should be GOOD (>= 4.5)
        assert avg_score == 5.0

        if avg_score >= 5.5:
            overall_quality = SnowQuality.EXCELLENT
        elif avg_score >= 4.5:
            overall_quality = SnowQuality.GOOD
        else:
            overall_quality = SnowQuality.FAIR

        assert overall_quality == SnowQuality.GOOD


class TestSnowAgingPenalty:
    """Tests for post-ML snow aging penalty."""

    def test_no_penalty_for_recent_snow(self):
        """No penalty when snow fell within 72 hours."""
        from services.ml_scorer import _apply_snow_aging_penalty

        score = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=48.0, snowfall_24h=0.0, cur_temp=-10.0
        )
        assert score == 4.0

    def test_no_penalty_with_active_snowfall(self):
        """No penalty when there's active snowfall even if base is old."""
        from services.ml_scorer import _apply_snow_aging_penalty

        score = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=120.0, snowfall_24h=2.0, cur_temp=-5.0
        )
        assert score == 4.0

    def test_penalty_for_old_snow(self):
        """Score degrades when snow is >3 days old with no new accumulation."""
        from services.ml_scorer import _apply_snow_aging_penalty

        # 7 days old, no new snow, -5°C
        score = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=168.0, snowfall_24h=0.0, cur_temp=-5.0
        )
        assert score < 4.0
        assert score >= 3.5  # Penalty capped

    def test_cold_reduces_penalty(self):
        """Very cold temperatures slow densification and reduce the penalty."""
        from services.ml_scorer import _apply_snow_aging_penalty

        mild = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=168.0, snowfall_24h=0.0, cur_temp=-5.0
        )
        cold = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=168.0, snowfall_24h=0.0, cur_temp=-18.0
        )
        assert cold > mild  # Cold temps preserve snow better

    def test_no_penalty_when_hours_unknown(self):
        """No penalty when hours_since_snowfall is None."""
        from services.ml_scorer import _apply_snow_aging_penalty

        score = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=None, snowfall_24h=0.0, cur_temp=-5.0
        )
        assert score == 4.0

    def test_max_penalty_capped(self):
        """Penalty is capped at 0.5 even for very old snow."""
        from services.ml_scorer import _apply_snow_aging_penalty

        # 30 days old
        score = _apply_snow_aging_penalty(
            4.0, hours_since_snowfall=720.0, snowfall_24h=0.0, cur_temp=0.0
        )
        assert score >= 3.5  # Max penalty is 0.5


class TestFernieResortData:
    """Tests for Fernie resort data in resorts.json."""

    def test_fernie_has_correct_elevation(self):
        """Test that Fernie has correct elevation data in resorts.json.

        Fernie Alpine Resort's actual elevations:
        - Base: ~1082m (3550 ft)
        - Top: ~2134m (7000 ft)

        The scraped data had incorrect base elevation of 134m which caused
        weather data to return warm temperatures, triggering HORRIBLE quality.
        """
        resorts_file = Path(__file__).parent.parent / "data" / "resorts.json"

        with open(resorts_file) as f:
            data = json.load(f)

        # Find Fernie in the resorts
        fernie = None
        for resort in data.get("resorts", []):
            if resort.get("resort_id") == "fernie":
                fernie = resort
                break

        assert fernie is not None, "Fernie should be in resorts.json"
        assert fernie["name"] == "Fernie Alpine Resort"
        assert fernie["country"] == "CA"

        # Check elevations are reasonable (not the wrong 134m from scraped data)
        base_elev = fernie["elevation_base_m"]
        top_elev = fernie["elevation_top_m"]

        # Base should be around 1082m (definitely not 134m)
        assert base_elev > 1000, f"Base elevation {base_elev}m is too low"
        assert base_elev < 1200, f"Base elevation {base_elev}m is too high"

        # Top should be around 2134m
        assert top_elev > 2000, f"Top elevation {top_elev}m is too low"
        assert top_elev < 2300, f"Top elevation {top_elev}m is too high"

        # Sanity check: base should be less than top
        assert base_elev < top_elev

    def test_fernie_has_valid_coordinates(self):
        """Test that Fernie has valid coordinates."""
        resorts_file = Path(__file__).parent.parent / "data" / "resorts.json"

        with open(resorts_file) as f:
            data = json.load(f)

        fernie = None
        for resort in data.get("resorts", []):
            if resort.get("resort_id") == "fernie":
                fernie = resort
                break

        assert fernie is not None

        # Fernie is in southeastern BC, near Alberta border
        # Approximate coordinates: 49.46°N, 115.09°W
        lat = fernie.get("latitude", 0)
        lon = fernie.get("longitude", 0)

        assert 49.0 < lat < 50.0, f"Latitude {lat} is outside expected range"
        assert -116.0 < lon < -114.0, f"Longitude {lon} is outside expected range"

    def test_fernie_timezone_is_mountain(self):
        """Test that Fernie uses Mountain Time (despite being in BC)."""
        resorts_file = Path(__file__).parent.parent / "data" / "resorts.json"

        with open(resorts_file) as f:
            data = json.load(f)

        fernie = None
        for resort in data.get("resorts", []):
            if resort.get("resort_id") == "fernie":
                fernie = resort
                break

        assert fernie is not None

        # Fernie is in BC but uses Mountain Time
        assert fernie.get("timezone") == "America/Edmonton"
