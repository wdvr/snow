"""Tests for the quality explanation service."""

import pytest

from models.weather import SnowQuality, WeatherCondition
from services.quality_explanation_service import (
    generate_overall_explanation,
    generate_quality_explanation,
    generate_score_change_reason,
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
        "snow_quality": SnowQuality.DECENT,
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
        assert "solid" in explanation.lower() or "good" in explanation.lower()


class TestFairExplanation:
    def test_limited_fresh_snow(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            snowfall_24h_cm=0.0,
            snowfall_after_freeze_cm=8.0,
            hours_since_last_snowfall=96.0,
            current_temp_celsius=-5.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "firm" in explanation.lower() or "groomed" in explanation.lower()

    def test_warming_conditions(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
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
            snow_quality=SnowQuality.DECENT,
            current_temp_celsius=-18.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "firm and squeaky" in explanation or "-18°C" in explanation

    def test_cold_preservation(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            current_temp_celsius=-10.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "preservation" in explanation.lower() or "-10°C" in explanation

    def test_warming_above_zero(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            current_temp_celsius=2.0,
            currently_warming=True,
        )
        explanation = generate_quality_explanation(cond)
        assert "softening" in explanation or "warming" in explanation.lower()


# MARK: - Base depth tests


class TestBaseDepthExplanation:
    def test_deep_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            snow_depth_cm=250.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "250cm" in explanation
        assert "deep" in explanation.lower()

    def test_solid_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            snow_depth_cm=120.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "120cm" in explanation

    def test_thin_base(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            snow_depth_cm=30.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "30cm" in explanation
        assert "thin" in explanation.lower()


# MARK: - Forecast outlook tests


class TestForecastExplanation:
    def test_heavy_snow_24h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            predicted_snow_24h_cm=15.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "15cm" in explanation
        assert "24 hours" in explanation

    def test_moderate_snow_48h(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            predicted_snow_48h_cm=12.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "12cm" in explanation or "48 hours" in explanation

    def test_no_snow_forecast(self):
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
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
            quality="decent",
            temperature_c=5.0,
            snowfall_cm=0.0,
            snow_depth_cm=80.0,
            wind_speed_kmh=10.0,
            is_forecast=False,
        )
        assert "warm" in result.lower() or "wet" in result.lower()

    def test_strong_wind(self):
        result = generate_timeline_explanation(
            quality="decent",
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
        # Piecewise-linear: 3.5 maps to 65 (breakpoint)
        assert score_to_100(3.5) == 65

    def test_clamp_below(self):
        assert score_to_100(0.5) == 0

    def test_clamp_above(self):
        assert score_to_100(7.0) == 100

    def test_known_values(self):
        # Piecewise-linear calibration breakpoints:
        # (1.0, 0), (2.5, 22), (3.5, 65), (4.5, 83), (5.5, 95), (6.0, 100)
        assert score_to_100(2.5) == 22
        assert score_to_100(3.5) == 65
        assert score_to_100(4.5) == 83
        assert score_to_100(5.5) == 95


# MARK: - Overall explanation tests


class TestOverallExplanation:
    """Tests for generate_overall_explanation with mixed elevations."""

    def test_matching_elevation_uses_standard_explanation(self):
        """When an elevation matches overall quality, use its standard explanation."""
        conditions = [
            _make_condition(
                elevation_level="top",
                snow_quality=SnowQuality.GOOD,
                fresh_snow_cm=80.0,
                current_temp_celsius=-5.0,
            ),
            _make_condition(
                elevation_level="base",
                snow_quality=SnowQuality.POOR,
                current_temp_celsius=2.0,
            ),
        ]
        result = generate_overall_explanation(conditions, SnowQuality.GOOD)
        # Should use top elevation's standard explanation (deep base text)
        assert "non-refrozen" in result or "80cm" in result

    def test_no_match_synthesizes_mixed(self):
        """When no elevation matches overall quality, synthesize mixed description."""
        # Niseko-like: top=fair, mid=bad, base=bad → overall=poor
        conditions = [
            _make_condition(
                elevation_level="top",
                snow_quality=SnowQuality.DECENT,
                fresh_snow_cm=48.0,
                current_temp_celsius=-3.0,
                snow_depth_cm=88.0,
            ),
            _make_condition(
                elevation_level="mid",
                snow_quality=SnowQuality.BAD,
                current_temp_celsius=0.4,
                last_freeze_thaw_hours_ago=1.0,
            ),
            _make_condition(
                elevation_level="base",
                snow_quality=SnowQuality.BAD,
                current_temp_celsius=3.8,
                last_freeze_thaw_hours_ago=1.0,
            ),
        ]
        result = generate_overall_explanation(conditions, SnowQuality.POOR)
        assert result is not None
        # Uses representative (mid) with POOR quality override
        # Should describe poor conditions using mid's freeze-thaw data
        assert (
            "thaw" in result.lower()
            or "hard" in result.lower()
            or "refrozen" in result.lower()
        )

    def test_mixed_excellent_top_poor_lower(self):
        """Excellent at top but poor lower → synthesized explanation."""
        conditions = [
            _make_condition(
                elevation_level="top",
                snow_quality=SnowQuality.EXCELLENT,
                snowfall_24h_cm=20.0,
                current_temp_celsius=-10.0,
                snow_depth_cm=200.0,
            ),
            _make_condition(
                elevation_level="base",
                snow_quality=SnowQuality.POOR,
                current_temp_celsius=-2.0,
            ),
        ]
        # Overall good (between excellent and poor), representative is top (no mid)
        result = generate_overall_explanation(conditions, SnowQuality.GOOD)
        assert result is not None
        # Uses representative (top) with GOOD quality override
        # Should describe good conditions using top's snow data
        assert "powder" in result.lower() or "snow" in result.lower()

    def test_empty_conditions_returns_none(self):
        """Empty conditions list returns None."""
        result = generate_overall_explanation([], SnowQuality.DECENT)
        assert result is None

    def test_single_matching_condition(self):
        """Single condition matching quality uses standard explanation."""
        conditions = [
            _make_condition(
                elevation_level="top",
                snow_quality=SnowQuality.DECENT,
                fresh_snow_cm=10.0,
            ),
        ]
        result = generate_overall_explanation(conditions, SnowQuality.DECENT)
        assert result is not None
        # Should use standard fair explanation
        assert "10cm" in result or "fresh" in result.lower()


# MARK: - Wind/Visibility Score Impact Tests (Regression)


class TestWindVisibilityScoreImpact:
    """Regression tests: wind/visibility explanations must mention score impact."""

    def test_windy_mentions_score(self):
        """Wind above 25 km/h should say it decreases the score."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            wind_speed_kmh=30.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "score" in explanation.lower(), (
            f"Wind explanation should mention score impact, got: {explanation}"
        )

    def test_strong_wind_mentions_score(self):
        """Strong wind (>40 km/h) should say it lowers the score."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            wind_speed_kmh=50.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "lowers the score" in explanation.lower(), (
            f"Strong wind should say 'lowers the score', got: {explanation}"
        )
        assert "50" in explanation

    def test_strong_gusts_mention_score(self):
        """Strong gusts (>60 km/h) should say it lowers/lower the score."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            wind_gust_kmh=70.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "lower the score" in explanation.lower(), (
            f"Strong gusts should mention score impact, got: {explanation}"
        )
        assert "70" in explanation

    def test_low_visibility_mentions_score(self):
        """Low visibility (<1000m) should mention score impact."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            visibility_m=800.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "score" in explanation.lower(), (
            f"Low visibility should mention score impact, got: {explanation}"
        )

    def test_very_low_visibility_mentions_score(self):
        """Very low visibility (<500m) should mention score impact."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            visibility_m=300.0,
        )
        explanation = generate_quality_explanation(cond)
        assert "score" in explanation.lower(), (
            f"Very low visibility should mention score impact, got: {explanation}"
        )

    def test_no_wind_no_visibility_mention(self):
        """Normal wind and visibility should not mention score impact."""
        cond = _make_condition(
            snow_quality=SnowQuality.DECENT,
            wind_speed_kmh=15.0,
            visibility_m=5000.0,
        )
        explanation = generate_quality_explanation(cond)
        # Should not contain wind/visibility score text
        assert "wind" not in explanation.lower() or "score" not in explanation.lower()


class TestTimelineWindVisibilityScoreImpact:
    """Regression tests: timeline wind/visibility explanations must mention score impact."""

    def test_timeline_wind_mentions_score(self):
        """Timeline wind >25 should mention score decrease."""
        result = generate_timeline_explanation(
            quality="decent",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=30.0,
            is_forecast=False,
        )
        assert "score" in result.lower(), (
            f"Timeline wind explanation should mention score, got: {result}"
        )

    def test_timeline_strong_wind_mentions_score(self):
        """Timeline strong wind >40 should say it lowers the score."""
        result = generate_timeline_explanation(
            quality="decent",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=50.0,
            is_forecast=False,
        )
        assert "lowers the score" in result.lower(), (
            f"Timeline strong wind should say 'lowers the score', got: {result}"
        )

    def test_timeline_gusts_mention_score(self):
        """Timeline strong gusts should mention score impact."""
        result = generate_timeline_explanation(
            quality="decent",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=20.0,
            is_forecast=False,
            wind_gust_kmh=70.0,
        )
        assert "lower the score" in result.lower(), (
            f"Timeline gusts should mention score impact, got: {result}"
        )

    def test_timeline_low_visibility_mentions_score(self):
        """Timeline low visibility should mention score impact."""
        result = generate_timeline_explanation(
            quality="decent",
            temperature_c=-5.0,
            snowfall_cm=0.0,
            snow_depth_cm=100.0,
            wind_speed_kmh=10.0,
            is_forecast=False,
            visibility_m=800.0,
        )
        assert "score" in result.lower(), (
            f"Timeline visibility should mention score, got: {result}"
        )


# MARK: - Score Change Reason Tests


def _timeline_point(**kwargs) -> dict:
    """Create a timeline point dict with defaults for score change reason testing."""
    defaults = {
        "date": "2026-02-20",
        "time_label": "midday",
        "hour": 12,
        "timestamp": "2026-02-20T12:00",
        "temperature_c": -5.0,
        "wind_speed_kmh": 10.0,
        "wind_gust_kmh": 15.0,
        "visibility_m": 10000.0,
        "snowfall_cm": 0.0,
        "snow_depth_cm": 100.0,
        "snow_quality": "good",
        "quality_score": 3.8,
        "snow_score": 70,
        "explanation": "Good conditions.",
        "weather_code": 3,
        "weather_description": "Overcast",
        "is_forecast": False,
    }
    defaults.update(kwargs)
    return defaults


class TestScoreChangeReason:
    """Tests for generate_score_change_reason()."""

    def test_no_previous_returns_none(self):
        """First point in timeline has no previous, should return None."""
        point = _timeline_point()
        assert generate_score_change_reason(point, None) is None

    def test_same_score_returns_none(self):
        """When score doesn't change, no reason is needed."""
        prev = _timeline_point(snow_score=70)
        curr = _timeline_point(snow_score=70)
        assert generate_score_change_reason(curr, prev) is None

    def test_missing_score_returns_none(self):
        """When score is missing, return None."""
        prev = _timeline_point(snow_score=None)
        curr = _timeline_point(snow_score=70)
        assert generate_score_change_reason(curr, prev) is None

    def test_fresh_snow_improves(self):
        """Fresh snowfall should be identified as the improving factor."""
        prev = _timeline_point(snow_score=60, snowfall_cm=0.0)
        curr = _timeline_point(snow_score=80, snowfall_cm=8.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "8cm" in reason or "fresh" in reason.lower()

    def test_warming_above_freezing(self):
        """Warming above freezing should mention softening."""
        prev = _timeline_point(snow_score=75, temperature_c=-2.0)
        curr = _timeline_point(snow_score=65, temperature_c=4.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "warm" in reason.lower() or "soften" in reason.lower()

    def test_cooling_below_freezing(self):
        """Cooling below freezing should mention firming up."""
        prev = _timeline_point(snow_score=60, temperature_c=2.0)
        curr = _timeline_point(snow_score=70, temperature_c=-5.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "cool" in reason.lower() or "firm" in reason.lower()

    def test_refreezing_creates_ice(self):
        """When temps drop from above zero to below, mention icy surface."""
        prev = _timeline_point(snow_score=65, temperature_c=2.0)
        curr = _timeline_point(snow_score=50, temperature_c=-1.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "refreez" in reason.lower() or "icy" in reason.lower()

    def test_wind_increase_worsens(self):
        """Increasing wind should be flagged as worsening factor."""
        prev = _timeline_point(snow_score=75, wind_speed_kmh=10.0)
        curr = _timeline_point(snow_score=60, wind_speed_kmh=35.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "wind" in reason.lower()

    def test_wind_easing_improves(self):
        """Decreasing wind should be flagged as improving factor."""
        prev = _timeline_point(snow_score=60, wind_speed_kmh=40.0)
        curr = _timeline_point(snow_score=72, wind_speed_kmh=10.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "wind" in reason.lower() and (
            "eas" in reason.lower() or "improv" in reason.lower()
        )

    def test_gust_increase_worsens(self):
        """Increasing gusts should be flagged."""
        prev = _timeline_point(snow_score=75, wind_gust_kmh=20.0)
        curr = _timeline_point(snow_score=60, wind_gust_kmh=55.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "gust" in reason.lower() or "wind" in reason.lower()

    def test_visibility_drop_worsens(self):
        """Significant visibility drop should be flagged."""
        prev = _timeline_point(snow_score=75, visibility_m=5000.0)
        curr = _timeline_point(snow_score=65, visibility_m=500.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "visibility" in reason.lower() or "vis" in reason.lower()

    def test_visibility_improving(self):
        """Visibility improving from low should be flagged."""
        prev = _timeline_point(snow_score=60, visibility_m=500.0)
        curr = _timeline_point(snow_score=72, visibility_m=5000.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "visibility" in reason.lower() or "improv" in reason.lower()

    def test_snowfall_stopped_worsens(self):
        """When snowfall stops, settling conditions should be noted."""
        prev = _timeline_point(snow_score=80, snowfall_cm=5.0)
        curr = _timeline_point(snow_score=70, snowfall_cm=0.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert (
            "stop" in reason.lower()
            or "settl" in reason.lower()
            or "declin" in reason.lower()
        )

    def test_generic_improvement_fallback(self):
        """When no specific factor is dominant, generic improvement message shown."""
        prev = _timeline_point(snow_score=68)
        curr = _timeline_point(snow_score=72)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "improv" in reason.lower()

    def test_generic_decline_fallback(self):
        """When no specific factor is dominant, generic decline message shown."""
        prev = _timeline_point(snow_score=72)
        curr = _timeline_point(snow_score=68)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "declin" in reason.lower()

    def test_significant_change_label(self):
        """Large score changes (>=15 pts) should mention significance."""
        prev = _timeline_point(snow_score=50, snowfall_cm=0.0)
        curr = _timeline_point(snow_score=85, snowfall_cm=15.0)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "significantly" in reason.lower() or "15cm" in reason

    def test_slight_change_label(self):
        """Small score changes (<5 pts) should say 'slightly'."""
        prev = _timeline_point(snow_score=70)
        curr = _timeline_point(snow_score=73)
        reason = generate_score_change_reason(curr, prev)
        assert reason is not None
        assert "slightly" in reason.lower()
