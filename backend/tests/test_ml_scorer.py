"""Tests for the ML-based snow quality scorer."""

import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models.weather import SnowQuality
from services.ml_scorer import (
    _apply_fresh_snow_floor,
    _apply_no_snowfall_cap,
    _compute_wind_chill,
    _extract_features_at_hour,
    _forward_single,
    _override_snowfall_from_condition,
    _relu,
    _sigmoid,
    _transpose_weights,
    engineer_features,
    extract_features_from_condition,
    predict_quality,
    predict_quality_at_hour,
    raw_score_to_quality,
)

# ── Helper fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_raw_features():
    """Raw features representing cold, snowy conditions (should score high)."""
    return {
        "cur_temp": -8.0,
        "max_temp_24h": -4.0,
        "max_temp_48h": -2.0,
        "min_temp_24h": -12.0,
        "freeze_thaw_days_ago": 10.0,
        "warmest_thaw": 3.0,
        "snow_since_freeze_cm": 60.0,
        "snowfall_24h_cm": 15.0,
        "snowfall_72h_cm": 35.0,
        "elevation_m": 2500.0,
        "total_hours_above_0C_since_ft": 5,
        "total_hours_above_1C_since_ft": 3,
        "total_hours_above_2C_since_ft": 2,
        "total_hours_above_3C_since_ft": 1,
        "total_hours_above_4C_since_ft": 0,
        "total_hours_above_5C_since_ft": 0,
        "total_hours_above_6C_since_ft": 0,
        "cur_hours_above_0C": 0,
        "cur_hours_above_1C": 0,
        "cur_hours_above_2C": 0,
        "cur_hours_above_3C": 0,
        "cur_hours_above_4C": 0,
        "cur_hours_above_5C": 0,
        "cur_hours_above_6C": 0,
        "cur_wind_kmh": 10.0,
        "max_wind_24h": 25.0,
        "avg_wind_24h": 12.0,
        "snow_depth_cm": 150.0,
    }


@pytest.fixture
def warm_raw_features():
    """Raw features representing warm, no-snow conditions (should score low)."""
    return {
        "cur_temp": 8.0,
        "max_temp_24h": 12.0,
        "max_temp_48h": 14.0,
        "min_temp_24h": 3.0,
        "freeze_thaw_days_ago": 1.0,
        "warmest_thaw": 12.0,
        "snow_since_freeze_cm": 0.0,
        "snowfall_24h_cm": 0.0,
        "snowfall_72h_cm": 0.0,
        "elevation_m": 1200.0,
        "total_hours_above_0C_since_ft": 24,
        "total_hours_above_1C_since_ft": 22,
        "total_hours_above_2C_since_ft": 20,
        "total_hours_above_3C_since_ft": 18,
        "total_hours_above_4C_since_ft": 15,
        "total_hours_above_5C_since_ft": 12,
        "total_hours_above_6C_since_ft": 10,
        "cur_hours_above_0C": 48,
        "cur_hours_above_1C": 46,
        "cur_hours_above_2C": 40,
        "cur_hours_above_3C": 35,
        "cur_hours_above_4C": 30,
        "cur_hours_above_5C": 25,
        "cur_hours_above_6C": 20,
        "cur_wind_kmh": 5.0,
        "max_wind_24h": 15.0,
        "avg_wind_24h": 8.0,
        "snow_depth_cm": 10.0,
    }


def _make_condition(**kwargs):
    """Create a minimal condition-like object."""
    defaults = {
        "current_temp_celsius": -5.0,
        "max_temp_celsius": -2.0,
        "min_temp_celsius": -10.0,
        "last_freeze_thaw_hours_ago": 240.0,
        "hours_above_ice_threshold": 5.0,
        "max_consecutive_warm_hours": 8.0,
        "snowfall_after_freeze_cm": 30.0,
        "snowfall_24h_cm": 10.0,
        "snowfall_72h_cm": 25.0,
        "wind_speed_kmh": 15.0,
        "snow_depth_cm": 100.0,
        "hours_since_last_snowfall": None,
        "weather_code": None,
        "ml_features": None,
        "raw_data": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── Math primitives ──────────────────────────────────────────────────────────


class TestMathPrimitives:
    def test_relu_positive(self):
        assert _relu(3.5) == 3.5

    def test_relu_negative(self):
        assert _relu(-2.0) == 0.0

    def test_relu_zero(self):
        assert _relu(0.0) == 0.0

    def test_sigmoid_zero(self):
        assert abs(_sigmoid(0.0) - 0.5) < 1e-6

    def test_sigmoid_large_positive(self):
        assert _sigmoid(100.0) > 0.99

    def test_sigmoid_large_negative(self):
        assert _sigmoid(-100.0) < 0.01

    def test_sigmoid_extreme_clamp(self):
        """Sigmoid should not overflow with extreme values."""
        assert 0.0 <= _sigmoid(1000.0) <= 1.0
        assert 0.0 <= _sigmoid(-1000.0) <= 1.0


# ── Weight transposition ─────────────────────────────────────────────────────


class TestTransposeWeights:
    def test_transpose_2x3(self):
        weights = {
            "W1": [[1, 2, 3], [4, 5, 6]],
            "b1": [0, 0, 0],
        }
        result = _transpose_weights(weights)
        assert result["W1_T"] == [[1, 4], [2, 5], [3, 6]]
        assert result["W1"] == weights["W1"]  # original preserved

    def test_transpose_empty(self):
        weights = {"W1": [], "b1": []}
        result = _transpose_weights(weights)
        assert result["W1_T"] == []


# ── Forward pass ─────────────────────────────────────────────────────────────


class TestForwardSingle:
    def test_output_in_range(self):
        """Output should be in [1.0, 6.0] range (sigmoid * 5 + 1)."""
        weights = {
            "W1_T": [[0.1, -0.2], [0.3, 0.4]],
            "b1": [0.0, 0.0],
            "W2": [[0.5], [-0.5]],
            "b2": [0.0],
        }
        result = _forward_single([1.0, 2.0], weights)
        assert 1.0 <= result <= 6.0

    def test_zero_weights_gives_midpoint(self):
        """All-zero weights should give sigmoid(0) * 5 + 1 = 3.5."""
        weights = {
            "W1_T": [[0.0, 0.0], [0.0, 0.0]],
            "b1": [0.0, 0.0],
            "W2": [[0.0], [0.0]],
            "b2": [0.0],
        }
        result = _forward_single([1.0, 2.0], weights)
        assert abs(result - 3.5) < 0.01


# ── Feature engineering ──────────────────────────────────────────────────────


class TestEngineerFeatures:
    def test_output_length(self, sample_raw_features):
        """Should produce exactly 34 engineered features."""
        features = engineer_features(sample_raw_features)
        assert len(features) == 40

    def test_cur_temp_is_first(self, sample_raw_features):
        features = engineer_features(sample_raw_features)
        assert features[0] == sample_raw_features["cur_temp"]

    def test_elevation_normalized(self, sample_raw_features):
        """Elevation should be divided by 1000."""
        features = engineer_features(sample_raw_features)
        assert features[11] == pytest.approx(2.5)  # 2500 / 1000

    def test_snow_depth_normalized(self, sample_raw_features):
        """Snow depth should be in meters (/ 100)."""
        features = engineer_features(sample_raw_features)
        assert features[12] == pytest.approx(1.5)  # 150 / 100

    def test_fresh_to_total_ratio(self, sample_raw_features):
        """Fresh-to-total ratio = snow_since_freeze / max(snow_depth, 1)."""
        features = engineer_features(sample_raw_features)
        expected = 60.0 / 150.0
        assert features[13] == pytest.approx(expected)

    def test_temp_delta_48_24(self, sample_raw_features):
        """Feature index 3 = max_temp_48h - max_temp_24h."""
        features = engineer_features(sample_raw_features)
        assert features[3] == pytest.approx(-2.0 - (-4.0))

    def test_freeze_thaw_capped_at_14(self):
        """Freeze-thaw days_ago should be capped at 14."""
        raw = {"freeze_thaw_days_ago": 30.0}
        features = engineer_features(raw)
        assert features[4] == 14.0

    def test_missing_keys_default_to_zero(self):
        """All features should work with empty dict (using defaults)."""
        features = engineer_features({})
        assert len(features) == 40
        assert all(isinstance(f, float) for f in features)

    def test_wind_protected_snow(self, sample_raw_features):
        """Wind-protected snow = snowfall * max(0, 1 - avg_wind/40)."""
        features = engineer_features(sample_raw_features)
        expected = 15.0 * max(0, 1.0 - 12.0 / 40.0)
        assert features[22] == pytest.approx(expected)

    def test_summer_indicator(self, warm_raw_features):
        """Summer indicator = 1.0 if temp > 10 and ca0 > 48."""
        features = engineer_features(warm_raw_features)
        # cur_temp=8 < 10 so should be 0
        assert features[28] == 0.0

    def test_summer_indicator_triggered(self):
        """Summer indicator should be 1.0 for hot temps with long warm spell."""
        raw = {"cur_temp": 15.0, "cur_hours_above_0C": 72}
        features = engineer_features(raw)
        assert features[28] == 1.0

    def test_cloud_cover_normalized(self, sample_raw_features):
        """Cloud cover should be normalized to 0-1."""
        sample_raw_features["cloud_cover_pct"] = 80.0
        features = engineer_features(sample_raw_features)
        assert features[29] == pytest.approx(0.8)

    def test_is_clear_feature(self, sample_raw_features):
        """is_clear should be passed through."""
        sample_raw_features["is_clear"] = 1.0
        features = engineer_features(sample_raw_features)
        assert features[30] == 1.0

    def test_wind_chill_delta(self, sample_raw_features):
        """Wind chill delta should be <= 0 (wind makes it colder)."""
        sample_raw_features["wind_chill_delta"] = -5.3
        features = engineer_features(sample_raw_features)
        assert features[31] == pytest.approx(-5.3)

    def test_sunny_calm_indicator(self, sample_raw_features):
        """Sunny + calm wind should produce positive indicator."""
        sample_raw_features["is_clear"] = 1.0
        sample_raw_features["cur_wind_kmh"] = 5.0
        features = engineer_features(sample_raw_features)
        expected = 1.0 * max(0.0, 1.0 - 5.0 / 30.0)
        assert features[32] == pytest.approx(expected)

    def test_sunny_calm_zero_when_cloudy(self, sample_raw_features):
        """Sunny calm indicator should be 0 when sky is not clear."""
        sample_raw_features["is_clear"] = 0.0
        sample_raw_features["cur_wind_kmh"] = 5.0
        features = engineer_features(sample_raw_features)
        assert features[32] == 0.0

    def test_powder_day_indicator(self):
        """Active snowing + cold + calm = positive powder day indicator."""
        raw = {
            "is_snowing": 1.0,
            "cur_temp": -8.0,
            "avg_wind_24h": 10.0,
        }
        features = engineer_features(raw)
        expected = 1.0 * 8.0 / 10.0 * max(0.0, 1.0 - 10.0 / 40.0)
        assert features[33] == pytest.approx(expected)


# ── Wind chill computation ────────────────────────────────────────────────────


class TestWindChill:
    def test_no_chill_warm_temps(self):
        """No wind chill applied when temp > 10C."""
        assert _compute_wind_chill(15.0, 30.0) == 15.0

    def test_no_chill_calm_wind(self):
        """No wind chill applied when wind < 4.8 km/h."""
        assert _compute_wind_chill(-10.0, 3.0) == -10.0

    def test_chill_applied(self):
        """Wind chill should make it feel colder."""
        wc = _compute_wind_chill(-10.0, 30.0)
        assert wc < -10.0

    def test_stronger_wind_more_chill(self):
        """Stronger wind should produce more wind chill."""
        mild = _compute_wind_chill(-5.0, 10.0)
        strong = _compute_wind_chill(-5.0, 50.0)
        assert strong < mild

    def test_boundary_conditions(self):
        """Test at the exact boundary: >10C and <4.8 km/h."""
        # At 10.1C, formula not applied (> 10)
        assert _compute_wind_chill(10.1, 20.0) == 10.1
        # At exactly 10C, formula IS applied (<= 10)
        wc = _compute_wind_chill(10.0, 20.0)
        assert wc < 10.0
        # Wind < 4.8 km/h, no chill applied
        assert _compute_wind_chill(-5.0, 4.7) == -5.0


# ── Extract features from condition ──────────────────────────────────────────


class TestExtractFeaturesFromCondition:
    def test_returns_dict(self):
        condition = _make_condition()
        result = extract_features_from_condition(condition, 2000.0)
        assert isinstance(result, dict)
        assert "cur_temp" in result
        assert "snow_depth_cm" in result

    def test_none_when_no_temperature(self):
        condition = _make_condition(current_temp_celsius=None)
        result = extract_features_from_condition(condition, 2000.0)
        assert result is None

    def test_uses_ml_features_if_available(self):
        """Should return pre-computed ml_features directly."""
        ml_feats = {"cur_temp": -3.0, "some_feature": 42.0}
        condition = _make_condition(ml_features=ml_feats)
        result = extract_features_from_condition(condition, 2000.0)
        assert result == ml_feats

    def test_elevation_from_param(self):
        condition = _make_condition()
        result = extract_features_from_condition(condition, 3000.0)
        assert result["elevation_m"] == 3000.0

    def test_default_elevation(self):
        condition = _make_condition()
        result = extract_features_from_condition(condition, None)
        assert result["elevation_m"] == 1500.0

    def test_freeze_thaw_days_from_hours(self):
        condition = _make_condition(last_freeze_thaw_hours_ago=48.0)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["freeze_thaw_days_ago"] == pytest.approx(2.0)

    def test_no_freeze_thaw_defaults_14(self):
        condition = _make_condition(last_freeze_thaw_hours_ago=None)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["freeze_thaw_days_ago"] == 14.0

    def test_snow_depth_included(self):
        condition = _make_condition(snow_depth_cm=200.0)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["snow_depth_cm"] == 200.0

    def test_all_expected_keys_present(self):
        condition = _make_condition()
        result = extract_features_from_condition(condition, 2000.0)
        expected_keys = [
            "cur_temp",
            "max_temp_24h",
            "max_temp_48h",
            "min_temp_24h",
            "freeze_thaw_days_ago",
            "warmest_thaw",
            "snow_since_freeze_cm",
            "snowfall_24h_cm",
            "snowfall_72h_cm",
            "elevation_m",
            "cur_wind_kmh",
            "max_wind_24h",
            "avg_wind_24h",
            "snow_depth_cm",
            "cloud_cover_pct",
            "weather_code",
            "is_clear",
            "is_snowing",
            "wind_chill_c",
            "wind_chill_delta",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_weather_code_clear_sky(self):
        """Clear sky weather code should set is_clear=1."""
        condition = _make_condition(weather_code=0)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["is_clear"] == 1.0
        assert result["cloud_cover_pct"] == 10.0

    def test_weather_code_snowing(self):
        """Snow weather code should set is_snowing=1."""
        condition = _make_condition(weather_code=73)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["is_snowing"] == 1.0
        assert result["is_clear"] == 0.0

    def test_wind_chill_in_condition(self):
        """Wind chill should be computed from temp and wind."""
        condition = _make_condition(current_temp_celsius=-10.0, wind_speed_kmh=30.0)
        result = extract_features_from_condition(condition, 2000.0)
        assert result["wind_chill_c"] < -10.0
        assert result["wind_chill_delta"] < 0.0


# ── Extract features at hour ─────────────────────────────────────────────────


class TestExtractFeaturesAtHour:
    def _make_hourly_data(self, n_hours=120, base_temp=-5.0, snowfall_per_hour=0.2):
        """Create simple hourly data arrays."""
        temps = [base_temp + (i % 24 - 12) * 0.5 for i in range(n_hours)]
        snowfall = [snowfall_per_hour if i % 3 == 0 else 0.0 for i in range(n_hours)]
        wind = [10.0 + (i % 12) for i in range(n_hours)]
        snow_depth = [0.5 + i * 0.001 for i in range(n_hours)]  # meters
        return temps, snowfall, wind, snow_depth

    def test_returns_features_dict(self):
        temps, snow, wind, depth = self._make_hourly_data()
        result = _extract_features_at_hour(temps, snow, wind, 72, 2000.0, depth)
        assert isinstance(result, dict)
        assert "cur_temp" in result

    def test_none_when_target_too_early(self):
        """Need at least 48 hours of history."""
        temps, snow, wind, _ = self._make_hourly_data(n_hours=60)
        result = _extract_features_at_hour(temps, snow, wind, 24, 2000.0)
        assert result is None

    def test_none_when_target_out_of_range(self):
        temps, snow, wind, _ = self._make_hourly_data(n_hours=60)
        result = _extract_features_at_hour(temps, snow, wind, 100, 2000.0)
        assert result is None

    def test_none_when_empty_temps(self):
        result = _extract_features_at_hour([], [], [], 0, 2000.0)
        assert result is None

    def test_snow_depth_m_to_cm_conversion(self):
        """Open-Meteo returns snow depth in meters; should be converted to cm."""
        temps, snow, wind, depth = self._make_hourly_data()
        depth_at_72 = depth[72]  # ~0.572 meters
        result = _extract_features_at_hour(temps, snow, wind, 72, 2000.0, depth)
        assert result["snow_depth_cm"] == pytest.approx(depth_at_72 * 100.0)

    def test_no_snow_depth_array(self):
        """snow_depth_cm should be 0.0 if no depth array provided."""
        temps, snow, wind, _ = self._make_hourly_data()
        result = _extract_features_at_hour(temps, snow, wind, 72, 2000.0, None)
        assert result["snow_depth_cm"] == 0.0

    def test_snowfall_24h_sum(self):
        """24h snowfall should be sum of snowfall in the previous 24 hours."""
        temps = [-5.0] * 120
        snowfall = [0.0] * 120
        # Put 1.0cm each hour for hours 48-72 (24 hours)
        for i in range(48, 72):
            snowfall[i] = 1.0
        wind = [10.0] * 120
        result = _extract_features_at_hour(temps, snowfall, wind, 72, 2000.0)
        assert result["snowfall_24h_cm"] == pytest.approx(24.0)

    def test_freeze_thaw_detection(self):
        """Should detect freeze-thaw when there's a warm→cold pattern."""
        n = 120
        temps = [-5.0] * n
        # Create warm period then cold period before target
        for i in range(40, 50):
            temps[i] = 3.0  # warm
        for i in range(50, 60):
            temps[i] = -3.0  # cold
        snowfall = [0.0] * n
        wind = [10.0] * n
        result = _extract_features_at_hour(temps, snowfall, wind, 72, 2000.0)
        assert result is not None
        assert result["freeze_thaw_days_ago"] < 14.0  # Should detect the event


# ── No-snowfall cap ─────────────────────────────────────────────────────────


class TestNoSnowfallCap:
    """Tests for _apply_no_snowfall_cap which enforces physics constraints.

    Champagne powder and powder day ratings are physically impossible
    without fresh snowfall. This cap prevents the ML model from
    hallucinating high scores when snowfall is zero.
    """

    def test_no_cap_with_fresh_snow(self):
        """Score should not be capped when there's fresh snowfall."""
        features = {"snowfall_24h_cm": 10.0, "snowfall_72h_cm": 20.0}
        assert _apply_no_snowfall_cap(5.8, features) == 5.8

    def test_cap_at_4_0_no_snow_72h(self):
        """Score should be capped at 4.0 when no snowfall in 72h."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.0}
        assert _apply_no_snowfall_cap(6.0, features) == 4.0

    def test_cap_at_4_0_trace_snow_72h(self):
        """Trace snowfall (< 0.5cm) in 72h should still trigger the cap."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.3}
        assert _apply_no_snowfall_cap(5.5, features) == 4.0

    def test_cap_at_4_5_no_24h_modest_72h(self):
        """No snow in 24h but modest 72h total should cap at 4.5."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 3.0}
        assert _apply_no_snowfall_cap(5.5, features) == 4.5

    def test_no_cap_when_score_below_threshold(self):
        """Score below the cap should not be modified."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.0}
        assert _apply_no_snowfall_cap(3.5, features) == 3.5

    def test_no_cap_sufficient_72h_snow(self):
        """With >= 5cm in 72h and some in 24h, no cap should apply."""
        features = {"snowfall_24h_cm": 2.0, "snowfall_72h_cm": 8.0}
        assert _apply_no_snowfall_cap(5.5, features) == 5.5

    def test_no_cap_sufficient_72h_no_24h(self):
        """With >= 5cm in 72h but none in 24h, no cap at 4.5 applies (mid-tier only)."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 6.0}
        # 72h >= 5.0 and 24h < 0.5 -> second rule doesn't apply because 72h >= 5.0
        # First rule doesn't apply because 72h >= 0.5
        assert _apply_no_snowfall_cap(5.0, features) == 5.0

    def test_champagne_powder_impossible_no_snow(self):
        """Champagne powder (6.0) should never occur with zero snowfall."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.0}
        result = _apply_no_snowfall_cap(6.0, features)
        assert result <= 4.0

    def test_powder_day_impossible_no_snow(self):
        """Powder day (5.0+) should never occur with zero snowfall."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.0}
        result = _apply_no_snowfall_cap(5.2, features)
        assert result <= 4.0

    def test_missing_keys_default_to_zero(self):
        """Missing snowfall keys should default to 0.0 (triggering cap)."""
        result = _apply_no_snowfall_cap(5.5, {})
        assert result <= 4.0

    def test_borderline_72h_at_threshold(self):
        """Exactly 0.5cm in 72h should NOT trigger the strict cap."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 0.5}
        # 72h = 0.5, not < 0.5, so first rule doesn't apply
        # 24h < 0.5 and 72h < 5.0 -> second rule applies, cap at 4.5
        assert _apply_no_snowfall_cap(5.0, features) == 4.5

    def test_borderline_24h_at_threshold(self):
        """Exactly 0.5cm in 24h should NOT trigger the second cap."""
        features = {"snowfall_24h_cm": 0.5, "snowfall_72h_cm": 2.0}
        # 72h >= 0.5 -> first rule doesn't apply
        # 24h = 0.5, not < 0.5 -> second rule doesn't apply
        assert _apply_no_snowfall_cap(5.0, features) == 5.0


# ── raw_score_to_quality ─────────────────────────────────────────────────────


class TestRawScoreToQuality:
    def test_highest_is_champagne_powder(self):
        assert raw_score_to_quality(6.0) == SnowQuality.CHAMPAGNE_POWDER

    def test_lowest_is_horrible(self):
        assert raw_score_to_quality(1.0) == SnowQuality.HORRIBLE

    def test_monotonic_ordering(self):
        """Higher scores should map to better or equal qualities."""
        scores = [1.0, 1.4, 2.3, 2.9, 3.3, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        qualities = [raw_score_to_quality(s) for s in scores]
        quality_order = {
            SnowQuality.HORRIBLE: 0,
            SnowQuality.BAD: 1,
            SnowQuality.POOR: 2,
            SnowQuality.MEDIOCRE: 3,
            SnowQuality.DECENT: 4,
            SnowQuality.GOOD: 5,
            SnowQuality.GREAT: 6,
            SnowQuality.EXCELLENT: 7,
            SnowQuality.POWDER_DAY: 8,
            SnowQuality.CHAMPAGNE_POWDER: 9,
        }
        orders = [quality_order[q] for q in qualities]
        assert orders == sorted(orders)


# ── Integration: predict_quality ─────────────────────────────────────────────


class TestPredictQuality:
    def test_returns_tuple(self):
        condition = _make_condition()
        quality, score = predict_quality(condition, 2000.0)
        assert isinstance(quality, SnowQuality)
        assert isinstance(score, float)

    def test_score_in_range(self):
        condition = _make_condition()
        _, score = predict_quality(condition, 2000.0)
        assert 1.0 <= score <= 6.0

    def test_cold_snowy_scores_higher_than_warm_dry(self):
        """Cold conditions with snow should score higher than warm without."""
        cold_snowy = _make_condition(
            current_temp_celsius=-10.0,
            max_temp_celsius=-5.0,
            min_temp_celsius=-15.0,
            snowfall_24h_cm=20.0,
            snowfall_72h_cm=40.0,
            snowfall_after_freeze_cm=50.0,
            snow_depth_cm=200.0,
        )
        warm_dry = _make_condition(
            current_temp_celsius=10.0,
            max_temp_celsius=15.0,
            min_temp_celsius=5.0,
            snowfall_24h_cm=0.0,
            snowfall_72h_cm=0.0,
            snowfall_after_freeze_cm=0.0,
            last_freeze_thaw_hours_ago=12.0,
            snow_depth_cm=5.0,
        )
        _, cold_score = predict_quality(cold_snowy, 2500.0)
        _, warm_score = predict_quality(warm_dry, 1500.0)
        assert cold_score > warm_score

    def test_no_model_returns_unknown(self):
        """If model file is missing, should return UNKNOWN."""
        import services.ml_scorer as ml_mod

        original = ml_mod._model
        ml_mod._model = None
        try:
            with patch.object(ml_mod, "MODEL_PATH", "/nonexistent/path.json"):
                ml_mod._model = None  # Force reload
                quality, score = predict_quality(_make_condition(), 2000.0)
                assert quality == SnowQuality.UNKNOWN
                assert score == 3.5
        finally:
            ml_mod._model = original

    def test_none_temp_returns_unknown(self):
        condition = _make_condition(
            current_temp_celsius=None,
            ml_features=None,
            raw_data=None,
        )
        quality, score = predict_quality(condition, 2000.0)
        assert quality == SnowQuality.UNKNOWN

    def test_uses_raw_data_when_available(self):
        """Should prefer raw_data features over condition approximation."""
        # Create a minimal raw_data with enough hours
        n = 120
        raw_data = {
            "hourly": {
                "temperature_2m": [-8.0 + (i % 24 - 12) * 0.3 for i in range(n)],
                "snowfall": [0.5 if i % 4 == 0 else 0.0 for i in range(n)],
                "wind_speed_10m": [12.0] * n,
                "snow_depth": [0.8] * n,
                "time": [
                    f"2026-02-{18 + i // 24:02d}T{i % 24:02d}:00" for i in range(n)
                ],
            }
        }
        condition = _make_condition(raw_data=raw_data)
        quality, score = predict_quality(condition, 2500.0)
        assert isinstance(quality, SnowQuality)
        assert 1.0 <= score <= 6.0


# ── Integration: predict_quality_at_hour ─────────────────────────────────────


class TestPredictQualityAtHour:
    def test_returns_tuple(self):
        n = 120
        temps = [-5.0 + (i % 24 - 12) * 0.5 for i in range(n)]
        snowfall = [0.3 if i % 3 == 0 else 0.0 for i in range(n)]
        wind = [10.0] * n
        times = [f"2026-02-{18 + i // 24:02d}T{i % 24:02d}:00" for i in range(n)]
        quality, score = predict_quality_at_hour(
            times, temps, snowfall, wind, 72, 2500.0
        )
        assert isinstance(quality, SnowQuality)
        assert 1.0 <= score <= 6.0

    def test_with_snow_depth(self):
        n = 120
        temps = [-5.0] * n
        snowfall = [0.5] * n
        wind = [10.0] * n
        depth = [1.0] * n  # 1 meter
        times = [f"2026-02-{18 + i // 24:02d}T{i % 24:02d}:00" for i in range(n)]
        quality, score = predict_quality_at_hour(
            times, temps, snowfall, wind, 72, 2500.0, depth
        )
        assert 1.0 <= score <= 6.0

    def test_insufficient_data_returns_unknown(self):
        quality, score = predict_quality_at_hour([], [], [], [], 0, 2000.0)
        assert quality == SnowQuality.UNKNOWN
        assert score == 3.5


# ── Fresh-snow floor ────────────────────────────────────────────────────────


class TestFreshSnowFloor:
    """Tests for _apply_fresh_snow_floor which enforces minimum scores.

    When there is significant fresh snowfall at cold temps, the ML model
    should not produce unreasonably low scores. This floor is the symmetric
    counterpart to _apply_no_snowfall_cap.
    """

    def test_heavy_snow_cold_temps_floor_4_5(self):
        """21cm fresh snow at -7.5C should score at least 4.5."""
        features = {
            "snowfall_24h_cm": 21.0,
            "cur_temp": -7.5,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(2.6, features)
        assert result >= 4.5

    def test_moderate_snow_cold_temps_floor_3_5(self):
        """10cm fresh snow at -4C should score at least 3.5."""
        features = {
            "snowfall_24h_cm": 10.0,
            "cur_temp": -4.0,
            "hours_since_last_snowfall": 2.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result >= 3.5

    def test_light_snow_cold_temps_floor_2_5(self):
        """5cm fresh snow at -1C should score at least 2.5."""
        features = {
            "snowfall_24h_cm": 5.0,
            "cur_temp": -1.0,
            "hours_since_last_snowfall": 3.0,
        }
        result = _apply_fresh_snow_floor(1.5, features)
        assert result >= 2.5

    def test_floor_warm_temps_heavy_snow(self):
        """Heavy snow at +3C should be floored (still fresh coverage)."""
        features = {
            "snowfall_24h_cm": 20.0,
            "cur_temp": 3.0,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 3.5  # Heavy fresh, mild but 15cm+ covers well

    def test_no_floor_hot_temps(self):
        """Snow at +6C should NOT be floored (melting conditions)."""
        features = {
            "snowfall_24h_cm": 20.0,
            "cur_temp": 6.0,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 2.0

    def test_no_floor_stale_snow(self):
        """Snow that fell >24 hours ago should NOT be floored."""
        features = {
            "snowfall_24h_cm": 20.0,
            "cur_temp": -10.0,
            "hours_since_last_snowfall": 30.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 2.0

    def test_no_floor_when_score_already_above(self):
        """Score already above the floor should not be modified."""
        features = {
            "snowfall_24h_cm": 21.0,
            "cur_temp": -7.5,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(5.5, features)
        assert result == 5.5

    def test_no_floor_insufficient_snow(self):
        """< 3cm snow should not trigger any floor."""
        features = {
            "snowfall_24h_cm": 2.0,
            "cur_temp": -10.0,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(1.5, features)
        assert result == 1.5

    def test_boundary_heavy_snow_15cm(self):
        """Exactly 15cm at exactly -5C should trigger the 4.5 floor."""
        features = {
            "snowfall_24h_cm": 15.0,
            "cur_temp": -5.0,
            "hours_since_last_snowfall": 0.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 4.5

    def test_boundary_moderate_snow_8cm(self):
        """Exactly 8cm at exactly -3C should trigger the 3.5 floor."""
        features = {
            "snowfall_24h_cm": 8.0,
            "cur_temp": -3.0,
            "hours_since_last_snowfall": 0.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 3.5

    def test_boundary_light_snow_3cm(self):
        """Exactly 3cm at exactly 0C should trigger the 2.5 floor."""
        features = {
            "snowfall_24h_cm": 3.0,
            "cur_temp": 0.0,
            "hours_since_last_snowfall": 0.0,
        }
        result = _apply_fresh_snow_floor(1.5, features)
        assert result == 2.5

    def test_boundary_hours_since_exactly_12(self):
        """Exactly 12 hours since snowfall should still apply floor."""
        features = {
            "snowfall_24h_cm": 20.0,
            "cur_temp": -8.0,
            "hours_since_last_snowfall": 12.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 4.5

    def test_missing_hours_since_defaults_no_floor(self):
        """Missing hours_since_last_snowfall defaults to 336 (no floor)."""
        features = {
            "snowfall_24h_cm": 20.0,
            "cur_temp": -8.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 2.0

    def test_missing_snowfall_defaults_no_floor(self):
        """Missing snowfall keys default to 0 (no floor)."""
        features = {
            "cur_temp": -8.0,
            "hours_since_last_snowfall": 1.0,
        }
        result = _apply_fresh_snow_floor(2.0, features)
        assert result == 2.0


class TestOverrideSnowfallFromCondition:
    """Tests for _override_snowfall_from_condition.

    When the merger corrects snowfall totals using resort-reported data,
    these overrides must propagate to the ML features (which otherwise
    use Open-Meteo's raw hourly data directly).
    """

    def test_higher_merged_snowfall_overrides_raw(self):
        """Merged 24h snowfall > raw → override."""
        features = {"snowfall_24h_cm": 0.0, "snowfall_72h_cm": 2.0}
        condition = SimpleNamespace(
            snowfall_24h_cm=14.0,
            snowfall_72h_cm=25.0,
            hours_since_last_snowfall=12.0,
        )
        _override_snowfall_from_condition(features, condition)
        assert features["snowfall_24h_cm"] == 14.0
        assert features["snowfall_72h_cm"] == 25.0

    def test_lower_merged_snowfall_does_not_override(self):
        """Merged 24h snowfall < raw → keep raw (don't downgrade)."""
        features = {"snowfall_24h_cm": 10.0, "snowfall_72h_cm": 20.0}
        condition = SimpleNamespace(
            snowfall_24h_cm=5.0,
            snowfall_72h_cm=15.0,
            hours_since_last_snowfall=None,
        )
        _override_snowfall_from_condition(features, condition)
        assert features["snowfall_24h_cm"] == 10.0
        assert features["snowfall_72h_cm"] == 20.0

    def test_hours_since_override_when_more_recent(self):
        """Merged hours_since < raw → override (snow is more recent)."""
        features = {"hours_since_last_snowfall": 336.0}
        condition = SimpleNamespace(
            snowfall_24h_cm=None,
            snowfall_72h_cm=None,
            hours_since_last_snowfall=12.0,
        )
        _override_snowfall_from_condition(features, condition)
        assert features["hours_since_last_snowfall"] == 12.0

    def test_hours_since_no_override_when_raw_more_recent(self):
        """Raw hours_since < merged → keep raw."""
        features = {"hours_since_last_snowfall": 3.0}
        condition = SimpleNamespace(
            snowfall_24h_cm=None,
            snowfall_72h_cm=None,
            hours_since_last_snowfall=12.0,
        )
        _override_snowfall_from_condition(features, condition)
        assert features["hours_since_last_snowfall"] == 3.0

    def test_none_values_do_not_override(self):
        """None merged values don't affect raw features."""
        features = {"snowfall_24h_cm": 5.0, "hours_since_last_snowfall": 6.0}
        condition = SimpleNamespace(
            snowfall_24h_cm=None,
            snowfall_72h_cm=None,
            hours_since_last_snowfall=None,
        )
        _override_snowfall_from_condition(features, condition)
        assert features["snowfall_24h_cm"] == 5.0
        assert features["hours_since_last_snowfall"] == 6.0
