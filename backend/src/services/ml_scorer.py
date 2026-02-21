"""ML-based snow quality scorer.

Loads trained neural network weights and performs inference on weather conditions.
The model takes 24 engineered features computed from raw hourly weather data
and outputs a quality score from 1.0 (HORRIBLE) to 6.0 (EXCELLENT).

See ml/ALGORITHM.md for full documentation.
"""

import json
import logging
import math
from datetime import UTC
from pathlib import Path
from typing import Any

from models.weather import SnowQuality

logger = logging.getLogger(__name__)

# Load model weights at module level (loaded once per Lambda cold start)
# Model weights are included in the Lambda package at ml_model/
MODEL_PATH = Path(__file__).parent.parent / "ml_model" / "model_weights_v2.json"
_model = None


def _transpose_weights(weights: dict) -> dict:
    """Pre-transpose W1 for fast row-major dot products.

    Converts W1 from [n_input][n_hidden] to W1_T[n_hidden][n_input]
    so forward pass can use zip() instead of column indexing.
    """
    W1 = weights["W1"]
    n_input = len(W1)
    n_hidden = len(W1[0]) if W1 else 0
    W1_T = [[W1[i][j] for i in range(n_input)] for j in range(n_hidden)]
    return {**weights, "W1_T": W1_T}


def _load_model() -> dict:
    """Load model weights from JSON file."""
    global _model
    if _model is not None:
        return _model
    try:
        with open(MODEL_PATH) as f:
            _model = json.load(f)
        # Pre-transpose weights for faster inference
        ensemble = _model.get("ensemble", [])
        if ensemble:
            _model["ensemble"] = [_transpose_weights(m) for m in ensemble]
            logger.info(
                f"Loaded ML model v2 ensemble ({len(ensemble)} models, "
                f"primary: {_model['architecture']['hidden_size']} hidden)"
            )
        else:
            _model["weights"] = _transpose_weights(_model["weights"])
            logger.info(
                f"Loaded ML model v2 ({_model['architecture']['hidden_size']} hidden neurons)"
            )
        return _model
    except FileNotFoundError:
        logger.warning(f"ML model not found at {MODEL_PATH}, falling back to heuristic")
        return None


def _relu(x: float) -> float:
    return max(0.0, x)


def _sigmoid(x: float) -> float:
    x = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def _forward_single(normalized: list[float], weights: dict) -> float:
    """Run forward pass through a single neural network.

    Uses pre-transposed W1_T for fast row-major dot products.
    """
    W1_T = weights["W1_T"]
    b1 = weights["b1"]
    W2 = weights["W2"]
    b2 = weights["b2"]

    # Hidden layer: z = W1^T @ x + b1, then ReLU
    # W1_T[j] is the weight row for hidden neuron j
    hidden = [
        max(0.0, sum(w * x for w, x in zip(row, normalized, strict=False)) + b)
        for row, b in zip(W1_T, b1, strict=False)
    ]

    # Output: sigmoid(W2^T @ hidden + b2) * 5 + 1
    z_out = sum(h * w[0] for h, w in zip(hidden, W2, strict=False)) + b2[0]
    z_out = max(-500.0, min(500.0, z_out))
    return (1.0 / (1.0 + math.exp(-z_out))) * 5.0 + 1.0


def _forward_ensemble(normalized: list[float], ensemble: list[dict]) -> float:
    """Run forward pass through ensemble of models and average predictions."""
    total = 0.0
    for model_weights in ensemble:
        total += _forward_single(normalized, model_weights)
    return total / len(ensemble)


def engineer_features(raw: dict[str, float]) -> list[float]:
    """Transform raw weather features into engineered features for the model.

    Args:
        raw: Dict with keys matching RAW_FEATURE_COLUMNS from training.

    Returns:
        List of 27 engineered feature values.
    """

    # Convert all values to float to handle DynamoDB Decimal types
    def _f(key, default=0.0):
        v = raw.get(key, default)
        return float(v) if v is not None else float(default)

    ct = _f("cur_temp")
    max24 = _f("max_temp_24h", ct)
    max48 = _f("max_temp_48h", max24)
    min24 = _f("min_temp_24h", ct)
    ft_days = _f("freeze_thaw_days_ago", 14.0)
    warmest = _f("warmest_thaw")
    snow_ft = _f("snow_since_freeze_cm")
    snow24 = _f("snowfall_24h_cm")
    snow72 = _f("snowfall_72h_cm")
    elev = _f("elevation_m", 1500.0)
    ha0 = _f("total_hours_above_0C_since_ft")
    ha3 = _f("total_hours_above_3C_since_ft")
    ha6 = _f("total_hours_above_6C_since_ft")
    ca0 = _f("cur_hours_above_0C")
    ca3 = _f("cur_hours_above_3C")
    ca6 = _f("cur_hours_above_6C")
    avg_wind = _f("avg_wind_24h")
    max_wind = _f("max_wind_24h")

    return [
        ct,
        max24,
        min24,
        max48 - max24,
        min(ft_days, 14.0),
        warmest,
        warmest * (1.0 / max(ft_days, 0.1)),
        snow_ft,
        snow24,
        snow72,
        snow72 - snow24,
        elev / 1000.0,
        ha0,
        ha3,
        ha6,
        ca0,
        ca3,
        ca6,
        avg_wind,
        max_wind,
        snow24 * max(0, 1.0 - avg_wind / 40.0),
        snow24 * max(0, -ct) / 10.0,
        snow_ft * max(0, -ct) / 10.0,
        max(0, ct) * ca0,
        max(0, max24 - 3) * ha3,
        snow24 * (1.0 if ct < 0 else 0.5),
        1.0 if (ct > 10 and ca0 > 48) else 0.0,
    ]


def extract_features_from_condition(
    condition: Any,
    elevation_m: float | None = None,
) -> dict[str, float] | None:
    """Extract raw ML features from a WeatherCondition object.

    Uses pre-computed ml_features if available, otherwise approximates
    from available fields.

    Args:
        condition: WeatherCondition object
        elevation_m: Elevation in meters (from resort data)

    Returns:
        Dict of raw features, or None if insufficient data.
    """
    # Check for pre-computed ML features first
    ml_features = getattr(condition, "ml_features", None)
    if ml_features and isinstance(ml_features, dict):
        return ml_features

    # Fall back to approximation from available fields
    cur_temp = condition.current_temp_celsius
    if cur_temp is None:
        return None

    max_temp = condition.max_temp_celsius or cur_temp
    min_temp = condition.min_temp_celsius or cur_temp

    # Approximate freeze-thaw days from hours
    ft_hours = getattr(condition, "last_freeze_thaw_hours_ago", None)
    ft_days = ft_hours / 24.0 if ft_hours is not None else 14.0

    # Approximate warmest_thaw: if there was a recent thaw and it's cold now,
    # max_temp is a reasonable proxy for the thaw warmth
    warmest_thaw = 0.0
    if ft_days < 14.0 and max_temp > 0:
        warmest_thaw = max_temp

    # Hours above thresholds - approximate from available fields
    hours_above_3c = getattr(condition, "hours_above_ice_threshold", 0.0) or 0.0
    max_warm_hours = getattr(condition, "max_consecutive_warm_hours", 0.0) or 0.0

    # Estimate hours above other thresholds from hours_above_3c
    # If we know hours above 3C, hours above 0C is always >= that
    ha0 = max_warm_hours if max_warm_hours > hours_above_3c else hours_above_3c * 1.5
    ha3 = hours_above_3c
    ha6 = hours_above_3c * 0.3  # rough approximation

    # Current warm spell
    ca0 = max_warm_hours if cur_temp >= 0 else 0
    ca3 = hours_above_3c if cur_temp >= 3 else 0
    ca6 = hours_above_3c * 0.3 if cur_temp >= 6 else 0

    # Wind approximation from condition fields
    wind_speed = getattr(condition, "wind_speed_kmh", 0.0) or 0.0

    return {
        "cur_temp": cur_temp,
        "max_temp_24h": max_temp,
        "max_temp_48h": max_temp,  # approximate: same as 24h
        "min_temp_24h": min_temp,
        "freeze_thaw_days_ago": ft_days,
        "warmest_thaw": warmest_thaw,
        "snow_since_freeze_cm": getattr(condition, "snowfall_after_freeze_cm", 0.0)
        or 0.0,
        "snowfall_24h_cm": condition.snowfall_24h_cm or 0.0,
        "snowfall_72h_cm": condition.snowfall_72h_cm or 0.0,
        "elevation_m": elevation_m or 1500.0,
        "total_hours_above_0C_since_ft": ha0,
        "total_hours_above_1C_since_ft": ha0 * 0.85,
        "total_hours_above_2C_since_ft": ha3 * 1.2,
        "total_hours_above_3C_since_ft": ha3,
        "total_hours_above_4C_since_ft": ha3 * 0.7,
        "total_hours_above_5C_since_ft": ha6 * 1.3,
        "total_hours_above_6C_since_ft": ha6,
        "cur_hours_above_0C": ca0,
        "cur_hours_above_1C": ca0 * 0.85,
        "cur_hours_above_2C": ca3 * 1.2,
        "cur_hours_above_3C": ca3,
        "cur_hours_above_4C": ca3 * 0.7,
        "cur_hours_above_5C": ca6 * 1.3,
        "cur_hours_above_6C": ca6,
        "cur_wind_kmh": float(wind_speed),
        "max_wind_24h": float(wind_speed) * 1.5,  # approximate
        "avg_wind_24h": float(wind_speed),
    }


def _extract_features_at_hour(
    temps: list[float | None],
    snowfall: list[float | None],
    wind_speeds: list[float | None],
    target_hour: int,
    elevation_m: float,
) -> dict[str, float] | None:
    """Core feature extraction at a specific hour index.

    Computes the 27 ML input features (pre-engineering) from hourly weather
    arrays centered on target_hour. Used by both real-time conditions and
    timeline predictions.
    """
    if target_hour < 48 or not temps or target_hour >= len(temps):
        return None

    cur_temp = temps[target_hour] if temps[target_hour] is not None else 0.0

    # Max/min temp windows
    h24_start = max(0, target_hour - 24)
    h48_start = max(0, target_hour - 48)
    temps_24h = [t for t in temps[h24_start:target_hour] if t is not None]
    temps_48h = [t for t in temps[h48_start:target_hour] if t is not None]

    max_temp_24h = max(temps_24h) if temps_24h else cur_temp
    min_temp_24h = min(temps_24h) if temps_24h else cur_temp
    max_temp_48h = max(temps_48h) if temps_48h else max_temp_24h

    # Snowfall windows
    snow_24h = sum(s for s in snowfall[h24_start:target_hour] if s is not None)
    h72_start = max(0, target_hour - 72)
    snow_72h = sum(s for s in snowfall[h72_start:target_hour] if s is not None)

    # Freeze-thaw detection (same algorithm as collect_data.py)
    freeze_thaw_hour = None
    warmest_thaw = 0.0
    state = "looking_for_freeze"
    cold_hours = 0
    warm_hours = 0
    warm_peak = 0.0

    for h in range(target_hour, max(target_hour - 336, -1), -1):
        if h < 0 or h >= len(temps) or temps[h] is None:
            continue
        t = temps[h]
        if state == "looking_for_freeze":
            if t <= -1.0:
                cold_hours += 1
                if cold_hours >= 2:
                    state = "looking_for_thaw"
                    cold_hours = 0
            else:
                cold_hours = 0
        elif state == "looking_for_thaw":
            if t >= 0.0:
                warm_hours += 1
                warm_peak = max(warm_peak, t)
                if warm_hours >= 3:
                    freeze_thaw_hour = h + warm_hours + 2
                    warmest_thaw = warm_peak
                    break
            else:
                warm_hours = 0
                warm_peak = 0.0

    ft_days = (target_hour - freeze_thaw_hour) / 24.0 if freeze_thaw_hour else 14.0
    ft_start = freeze_thaw_hour or 0
    snow_since_freeze = sum(s for s in snowfall[ft_start:target_hour] if s is not None)

    since_ft_temps = [t for t in temps[ft_start:target_hour] if t is not None]
    ha = {th: sum(1 for t in since_ft_temps if t >= th) for th in range(7)}

    # Current warm spell
    ca = {}
    for threshold in range(7):
        count = 0
        for h in range(target_hour, max(target_hour - 168, -1), -1):
            if h < 0 or h >= len(temps) or temps[h] is None:
                break
            if temps[h] >= threshold:
                count += 1
            else:
                break
        ca[threshold] = count

    # Wind features
    if wind_speeds and len(wind_speeds) > target_hour:
        wind_24h = [w for w in wind_speeds[h24_start:target_hour] if w is not None]
        cur_wind = (
            wind_speeds[target_hour] if wind_speeds[target_hour] is not None else 0.0
        )
        avg_wind_24h = sum(wind_24h) / len(wind_24h) if wind_24h else 0.0
        max_wind_24h = max(wind_24h) if wind_24h else 0.0
    else:
        cur_wind = 0.0
        avg_wind_24h = 0.0
        max_wind_24h = 0.0

    return {
        "cur_temp": cur_temp,
        "max_temp_24h": max_temp_24h,
        "max_temp_48h": max_temp_48h,
        "min_temp_24h": min_temp_24h,
        "freeze_thaw_days_ago": ft_days,
        "warmest_thaw": warmest_thaw,
        "snow_since_freeze_cm": snow_since_freeze,
        "snowfall_24h_cm": snow_24h,
        "snowfall_72h_cm": snow_72h,
        "elevation_m": elevation_m,
        "total_hours_above_0C_since_ft": ha[0],
        "total_hours_above_1C_since_ft": ha[1],
        "total_hours_above_2C_since_ft": ha[2],
        "total_hours_above_3C_since_ft": ha[3],
        "total_hours_above_4C_since_ft": ha[4],
        "total_hours_above_5C_since_ft": ha[5],
        "total_hours_above_6C_since_ft": ha[6],
        "cur_hours_above_0C": ca[0],
        "cur_hours_above_1C": ca[1],
        "cur_hours_above_2C": ca[2],
        "cur_hours_above_3C": ca[3],
        "cur_hours_above_4C": ca[4],
        "cur_hours_above_5C": ca[5],
        "cur_hours_above_6C": ca[6],
        "cur_wind_kmh": cur_wind,
        "max_wind_24h": max_wind_24h,
        "avg_wind_24h": avg_wind_24h,
    }


def extract_features_from_raw_data(
    condition: Any,
    elevation_m: float | None = None,
) -> dict[str, float] | None:
    """Extract ML features from raw hourly data stored in condition.raw_data.

    This gives exact features (not approximations) when raw_data is available.
    """
    raw_data = getattr(condition, "raw_data", None)
    if not raw_data or not isinstance(raw_data, dict):
        return None

    api_response = raw_data.get("api_response", raw_data)
    hourly = api_response.get("hourly", {})
    temps = hourly.get("temperature_2m", [])
    snowfall = hourly.get("snowfall", [])
    wind_speeds = hourly.get("wind_speed_10m", [])

    if not temps or len(temps) < 48:
        return None

    from datetime import datetime

    hourly_times = hourly.get("time", [])

    # Find current hour index
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:00")
    current_index = len(hourly_times) - 1
    for i, time_str in enumerate(hourly_times):
        if time_str[:13] >= now_str[:13]:
            current_index = i
            break

    elev = float(elevation_m or raw_data.get("elevation_meters", 1500.0))
    return _extract_features_at_hour(temps, snowfall, wind_speeds, current_index, elev)


def _apply_snow_aging_penalty(
    score: float,
    hours_since_snowfall: float | None,
    snowfall_24h: float,
    cur_temp: float,
) -> float:
    """Apply a post-ML penalty for aged snow conditions.

    The ML model doesn't directly see hours_since_last_snowfall as a feature.
    Old snow (>3 days) without fresh accumulation densifies and hardens, even
    without freeze-thaw cycles. This adjustment nudges the score down.

    Args:
        score: Raw ML score (1.0-6.0)
        hours_since_snowfall: Hours since last significant snowfall
        snowfall_24h: Recent snowfall in cm (last 24h)
        cur_temp: Current temperature in Celsius

    Returns:
        Adjusted score (1.0-6.0)
    """
    if hours_since_snowfall is None or hours_since_snowfall <= 48:
        return score
    if snowfall_24h >= 0.5:
        # Recent snow — no aging penalty
        return score

    # Penalty: -0.15 per day beyond 2 days, max -0.8
    # Snow compacts ~30% per day; after 5 days it's hard packed
    days_since = hours_since_snowfall / 24.0
    age_penalty = min(0.8, (days_since - 2.0) * 0.15)

    # Cold temps slow densification: reduce penalty at very cold temps
    if cur_temp < -15:
        age_penalty *= 0.6
    elif cur_temp < -8:
        age_penalty *= 0.8

    return max(1.0, score - age_penalty)


def predict_quality(
    condition: Any,
    elevation_m: float | None = None,
) -> tuple[SnowQuality, float]:
    """Predict snow quality using the ML model.

    Tries to extract features from raw_data first (most accurate),
    falls back to approximation from condition fields.

    Args:
        condition: WeatherCondition object
        elevation_m: Elevation in meters

    Returns:
        Tuple of (SnowQuality, raw_score)
    """
    model = _load_model()
    if model is None:
        return SnowQuality.UNKNOWN, 3.5

    # Try exact features from raw data first
    raw_features = extract_features_from_raw_data(condition, elevation_m)
    if raw_features is None:
        # Fall back to approximation
        raw_features = extract_features_from_condition(condition, elevation_m)
    if raw_features is None:
        return SnowQuality.UNKNOWN, 3.5

    # Engineer features
    features = engineer_features(raw_features)

    # Normalize
    norm = model["normalization"]
    mean = norm["mean"]
    std = norm["std"]
    normalized = [(f - m) / s for f, m, s in zip(features, mean, std, strict=False)]

    # Run inference — ensemble if available, single model otherwise
    ensemble = model.get("ensemble", [])
    if ensemble:
        score = _forward_ensemble(normalized, ensemble)
    else:
        score = _forward_single(normalized, model["weights"])
    score = max(1.0, min(6.0, score))

    # Post-ML adjustment: penalize aged snow
    hours_since = getattr(condition, "hours_since_last_snowfall", None)
    cur_temp = getattr(condition, "current_temp_celsius", 0.0) or 0.0
    snow_24h = getattr(condition, "snowfall_24h_cm", 0.0) or 0.0
    score = _apply_snow_aging_penalty(score, hours_since, snow_24h, cur_temp)

    # Map to quality
    thresholds = model["quality_thresholds"]
    if score >= thresholds["excellent"]:
        quality = SnowQuality.EXCELLENT
    elif score >= thresholds["good"]:
        quality = SnowQuality.GOOD
    elif score >= thresholds["fair"]:
        quality = SnowQuality.FAIR
    elif score >= thresholds["poor"]:
        quality = SnowQuality.POOR
    elif score >= thresholds["bad"]:
        quality = SnowQuality.BAD
    else:
        quality = SnowQuality.HORRIBLE

    return quality, score


def predict_quality_at_hour(
    hourly_times: list[str],
    temps: list[float | None],
    snowfall: list[float | None],
    wind_speeds: list[float | None],
    target_hour_index: int,
    elevation_m: float,
) -> tuple[SnowQuality, float]:
    """Predict snow quality at a specific hour index using the ML model.

    This is used by the timeline to compute ML-based quality predictions
    at each timeline point, rather than falling back to the heuristic.

    Args:
        hourly_times: List of ISO time strings (for reference, not used in computation)
        temps: Hourly temperature array
        snowfall: Hourly snowfall array (cm)
        wind_speeds: Hourly wind speed array (km/h)
        target_hour_index: Index into the arrays for the target hour
        elevation_m: Elevation in meters

    Returns:
        Tuple of (SnowQuality, raw_score)
    """
    model = _load_model()
    if model is None:
        return SnowQuality.UNKNOWN, 3.5

    raw_features = _extract_features_at_hour(
        temps, snowfall, wind_speeds, target_hour_index, elevation_m
    )
    if raw_features is None:
        return SnowQuality.UNKNOWN, 3.5

    features = engineer_features(raw_features)

    norm = model["normalization"]
    normalized = [
        (f - m) / s
        for f, m, s in zip(features, norm["mean"], norm["std"], strict=False)
    ]

    ensemble = model.get("ensemble", [])
    if ensemble:
        score = _forward_ensemble(normalized, ensemble)
    else:
        score = _forward_single(normalized, model["weights"])
    score = max(1.0, min(6.0, score))

    # Post-ML adjustment: penalize aged snow
    # Compute hours since last significant snowfall from the array
    hours_since_snow = None
    snow_24h = raw_features.get("snowfall_24h_cm", 0.0)
    for h in range(target_hour_index, max(target_hour_index - 336, -1), -1):
        if h < 0 or h >= len(snowfall):
            break
        s = snowfall[h]
        if s is not None and s > 0.1:
            hours_since_snow = float(target_hour_index - h)
            break
    cur_temp = temps[target_hour_index] if temps[target_hour_index] is not None else 0.0
    score = _apply_snow_aging_penalty(score, hours_since_snow, snow_24h, cur_temp)

    thresholds = model["quality_thresholds"]
    if score >= thresholds["excellent"]:
        quality = SnowQuality.EXCELLENT
    elif score >= thresholds["good"]:
        quality = SnowQuality.GOOD
    elif score >= thresholds["fair"]:
        quality = SnowQuality.FAIR
    elif score >= thresholds["poor"]:
        quality = SnowQuality.POOR
    elif score >= thresholds["bad"]:
        quality = SnowQuality.BAD
    else:
        quality = SnowQuality.HORRIBLE

    return quality, score
