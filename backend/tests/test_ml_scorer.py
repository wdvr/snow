"""Tests for the ML-based snow quality scorer."""

import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models.weather import SnowQuality
from services.ml_scorer import (
    _apply_cold_accumulation_boost,
    _apply_snow_aging_penalty,
    _extract_features_at_hour,
    _forward_single,
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
        """Should produce exactly 29 engineered features."""
        features = engineer_features(sample_raw_features)
        assert len(features) == 29

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
        assert len(features) == 29
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
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"


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


# ── Snow aging penalty ───────────────────────────────────────────────────────


class TestSnowAgingPenalty:
    def test_no_penalty_recent_snow(self):
        """No penalty when last snowfall was < 48 hours ago."""
        assert _apply_snow_aging_penalty(5.0, 24.0, 0.0, -5.0) == 5.0

    def test_no_penalty_with_fresh_snow(self):
        """No penalty when there's recent 24h snowfall."""
        assert _apply_snow_aging_penalty(5.0, 120.0, 1.0, -5.0) == 5.0

    def test_penalty_old_snow(self):
        """Penalty applied when snow is old and no recent accumulation."""
        result = _apply_snow_aging_penalty(5.0, 120.0, 0.0, -5.0)
        assert result < 5.0

    def test_penalty_capped_at_0_8(self):
        """Penalty should not exceed 0.8 (score doesn't drop more than 0.8)."""
        result = _apply_snow_aging_penalty(5.0, 480.0, 0.0, -5.0)
        assert result >= 5.0 - 0.8

    def test_cold_reduces_penalty(self):
        """Very cold temps should reduce the aging penalty."""
        warm_result = _apply_snow_aging_penalty(5.0, 120.0, 0.0, -5.0)
        cold_result = _apply_snow_aging_penalty(5.0, 120.0, 0.0, -20.0)
        assert cold_result > warm_result

    def test_score_never_below_1(self):
        """Score should never go below 1.0."""
        result = _apply_snow_aging_penalty(1.2, 480.0, 0.0, 0.0)
        assert result >= 1.0

    def test_none_hours_no_penalty(self):
        """No penalty when hours_since_snowfall is None."""
        assert _apply_snow_aging_penalty(5.0, None, 0.0, -5.0) == 5.0


# ── Cold accumulation boost ──────────────────────────────────────────────────


class TestColdAccumulationBoost:
    def test_no_boost_recent_freeze_thaw(self):
        """No boost if freeze-thaw was recent (< 5 days)."""
        result = _apply_cold_accumulation_boost(3.0, 100.0, 3.0, -10.0)
        assert result == 3.0

    def test_no_boost_little_snow(self):
        """No boost if accumulated snow < 15cm."""
        result = _apply_cold_accumulation_boost(3.0, 10.0, 10.0, -10.0)
        assert result == 3.0

    def test_no_boost_warm_temps(self):
        """No boost if temperature >= 0."""
        result = _apply_cold_accumulation_boost(3.0, 100.0, 10.0, 2.0)
        assert result == 3.0

    def test_boost_applied(self):
        """Boost applied with lots of snow, cold temps, no freeze-thaw."""
        result = _apply_cold_accumulation_boost(3.0, 100.0, 10.0, -15.0)
        assert result > 3.0

    def test_more_snow_more_boost(self):
        """More accumulated snow should give bigger boost."""
        low = _apply_cold_accumulation_boost(3.0, 20.0, 10.0, -10.0)
        high = _apply_cold_accumulation_boost(3.0, 120.0, 10.0, -10.0)
        assert high > low

    def test_colder_more_boost(self):
        """Colder temps should give bigger boost."""
        mild = _apply_cold_accumulation_boost(3.0, 80.0, 10.0, -2.0)
        cold = _apply_cold_accumulation_boost(3.0, 80.0, 10.0, -25.0)
        assert cold > mild

    def test_score_capped_at_6(self):
        """Score should not exceed 6.0."""
        result = _apply_cold_accumulation_boost(5.8, 150.0, 10.0, -25.0)
        assert result <= 6.0


# ── raw_score_to_quality ─────────────────────────────────────────────────────


class TestRawScoreToQuality:
    def test_highest_is_excellent(self):
        assert raw_score_to_quality(6.0) == SnowQuality.EXCELLENT

    def test_lowest_is_horrible(self):
        assert raw_score_to_quality(1.0) == SnowQuality.HORRIBLE

    def test_monotonic_ordering(self):
        """Higher scores should map to better or equal qualities."""
        scores = [1.0, 1.5, 2.5, 3.5, 4.5, 5.5, 6.0]
        qualities = [raw_score_to_quality(s) for s in scores]
        quality_order = {
            SnowQuality.HORRIBLE: 0,
            SnowQuality.BAD: 1,
            SnowQuality.POOR: 2,
            SnowQuality.FAIR: 3,
            SnowQuality.GOOD: 4,
            SnowQuality.EXCELLENT: 5,
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
