"""Tests for the quality explanation service."""

import pytest

from models.weather import SnowQuality, WeatherCondition
from services.quality_explanation_service import (
    generate_quality_explanation,
    generate_timeline_explanation,
    score_to_100,
)


def _make_condition(**kwargs) -> WeatherCondition:
    """Create a WeatherCondition with defaults for testing."""
    defaults = {
        "resort_id": "test-resort",
        "elevation_level": "top",
        "timestamp": "2026-02-20T12:00:00Z",
        "current_temp_celsius": -5.0,
        "min_temp_celsius": -10.0,
        "max_temp_celsius": 0.0,
        "snowfall_24h_cm": 0.0,
        "snowfall_48h_cm": 0.0,
        "snowfall_72h_cm": 0.0,
        "snow_quality": SnowQuality.FAIR,
        "data_source": "test",
        "source_confidence": "medium",
    }
    defaults.update(kwargs)
    return WeatherCondition(**defaults)


# MARK: - Surface description tests


class TestExcellentExplanation:
    def test_fresh_powder_24h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.EXCELLENT,
            snowfall_24h_cm=15.0,
            current_temp_celsius=-10.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "15cm" in explanation
        assert "24 hours" in explanation

    def test_fresh_powder_48h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.EXCELLENT,
            snowfall_24h_cm=3.0,
            snowfall_48h_cm=12.0,
            current_temp_celsius=-8.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "12cm" in explanation
        assert "48 hours" in explanation

    def test_fresh_powder_default(self):
        cond = _make_condition(
            snow_quality=SnowQuality.EXCELLENT,
            snowfall_24h_cm=3.0,
            snowfall_48h_cm=5.0,
            snowfall_after_freeze_cm=10.0,
            current_temp_celsius=-10.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "powder" in explanation.lower()


class TestGoodExplanation:
    def test_recent_snow(self):
        cond = _make_condition(
            snow_quality=SnowQuality.GOOD,
            snowfall_24h_cm=7.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "7cm" in explanation
        assert "recent snow" in explanation

    def test_good_surface_default(self):
        cond = _make_condition(
            snow_quality=SnowQuality.GOOD,
            snowfall_24h_cm=2.0,
            snowfall_after_freeze_cm=8.0,
            hours_since_last_snowfall=72.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "soft" in explanation.lower() or "rideable" in explanation.lower()


class TestFairExplanation:
    def test_limited_fresh_snow(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            snowfall_24h_cm=0.0,
            snowfall_after_freeze_cm=8.0,
            hours_since_last_snowfall=96.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "firm" in explanation.lower() or "groomed" in explanation.lower()

    def test_warming_conditions(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            snowfall_after_freeze_cm=5.0,
            currently_warming=True,
            current_temp_celsius=2.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "warming" in explanation.lower() or "softening" in explanation.lower()


class TestPoorExplanation:
    def test_freeze_thaw(self):
        cond = _make_condition(
            snow_quality=SnowQuality.POOR,
            last_freeze_thaw_hours_ago=48.0,
            snowfall_after_freeze_cm=1.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "thaw" in explanation.lower() or "packed" in explanation.lower()

    def test_aged_cover(self):
        cond = _make_condition(
            snow_quality=SnowQuality.POOR,
            snowfall_after_freeze_cm=5.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert len(explanation) > 10


class TestBadExplanation:
    def test_icy_recent_thaw(self):
        cond = _make_condition(
            snow_quality=SnowQuality.BAD,
            last_freeze_thaw_hours_ago=24.0,
            snowfall_after_freeze_cm=0.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "icy" in explanation.lower() or "refrozen" in explanation.lower()


class TestHorribleExplanation:
    def test_warm_temps(self):
        cond = _make_condition(
            snow_quality=SnowQuality.HORRIBLE,
            current_temp_celsius=8.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "not skiable" in explanation.lower()
        assert "8°C" in explanation

    def test_no_snow(self):
        cond = _make_condition(
            snow_quality=SnowQuality.HORRIBLE,
            current_temp_celsius=-2.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "not skiable" in explanation.lower()


# MARK: - Temperature description tests


class TestTemperatureExplanation:
    def test_very_cold(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            current_temp_celsius=-18.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "firm and squeaky" in explanation or "-18°C" in explanation

    def test_cold_preservation(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            current_temp_celsius=-10.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "preservation" in explanation.lower() or "-10°C" in explanation

    def test_warming_above_zero(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            current_temp_celsius=2.0,
            currently_warming=True,
        )
        explanation = generate_quality_explanation(cond)
        assert "softening" in explanation or "warming" in explanation.lower()


# MARK: - Base depth tests


class TestBaseDepthExplanation:
    def test_deep_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            snow_depth_cm=250.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "250cm" in explanation
        assert "deep" in explanation.lower()

    def test_solid_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            snow_depth_cm=120.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "120cm" in explanation

    def test_thin_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            snow_depth_cm=30.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "30cm" in explanation
        assert "thin" in explanation.lower()


# MARK: - Forecast outlook tests


class TestForecastExplanation:
    def test_heavy_snow_24h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            predicted_snow_24h_cm=15.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "15cm" in explanation
        assert "24 hours" in explanation

    def test_moderate_snow_48h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            predicted_snow_48h_cm=12.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "12cm" in explanation or "48 hours" in explanation

    def test_no_snow_forecast(self):
        cond = _make_condition(
            snow_quality=SnowQuality.FAIR,
            predicted_snow_72h_cm=0.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "no snow" in explanation.lower()


# MARK: - Timeline explanation tests


class TestTimelineExplanation:
    def test_excellent_with_snowfall(self):
        result = generate_timeline_explanation(
            quality="excellent",
            temperature_c=-10.0,
            snowfall_cm=8.0,
            snow_depth_cm=150.0,
            wind_speed_kmh=5.0,
            is_forecast=False,
        )
        assert "powder" in result.lower()
        assert "8cm" in result

    def test_forecast_prefix(self):
        result = generate_timeline_explanation(
            quality="good",
            temperature_c=-5.0,
            snowfall_cm=3.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=10.0,
            is_forecast=True,
        )
        assert result.startswith("Expected:")

    def test_warm_temperature(self):
        result = generate_timeline_explanation(
            quality="fair",
            temperature_c=5.0,
            snowfall_cm=0.0,
            snow_depth_cm=80.0,
            wind_speed_kmh=10.0,
            is_forecast=False,
        )
        assert "warm" in result.lower() or "wet" in result.lower()

    def test_strong_wind(self):
        result = generate_timeline_explanation(
            quality="fair",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=50.0,
            is_forecast=False,
        )
        assert "wind" in result.lower()

    def test_horrible(self):
        result = generate_timeline_explanation(
            quality="horrible",
            temperature_c=10.0,
            snowfall_cm=0.0,
            snow_depth_cm=0.0,
            wind_speed_kmh=5.0,
            is_forecast=False,
        )
        assert "not skiable" in result.lower()

    def test_invalid_quality(self):
        result = generate_timeline_explanation(
            quality="invalid_quality",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=10.0,
            is_forecast=False,
        )
        assert "unavailable" in result.lower()


# MARK: - Score conversion tests


class TestScoreTo100:
    def test_minimum_score(self):
        assert score_to_100(1.0) == 0

    def test_maximum_score(self):
        assert score_to_100(6.0) == 100

    def test_middle_score(self):
        assert score_to_100(3.5) == 50

    def test_clamp_below(self):
        assert score_to_100(0.5) == 0

    def test_clamp_above(self):
        assert score_to_100(7.0) == 100

    def test_known_values(self):
        # fair threshold (3.5) = 50
        assert score_to_100(3.5) == 50
        # good threshold (4.25) = 65
        assert score_to_100(4.25) == 65
        # excellent threshold (5.0) = 80
        assert score_to_100(5.0) == 80
