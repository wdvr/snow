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


def _load_model() -> dict:
    """Load model weights from JSON file."""
    global _model
    if _model is not None:
        return _model
    try:
        with open(MODEL_PATH) as f:
            _model = json.load(f)
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


def engineer_features(raw: dict[str, float]) -> list[float]:
    """Transform raw weather features into engineered features for the model.

    Args:
        raw: Dict with keys matching RAW_FEATURE_COLUMNS from training.

    Returns:
        List of 24 engineered feature values.
    """
    ct = raw.get("cur_temp", 0.0)
    max24 = raw.get("max_temp_24h", ct)
    max48 = raw.get("max_temp_48h", max24)
    min24 = raw.get("min_temp_24h", ct)
    ft_days = raw.get("freeze_thaw_days_ago", 14.0)
    warmest = raw.get("warmest_thaw", 0.0)
    snow_ft = raw.get("snow_since_freeze_cm", 0.0)
    snow24 = raw.get("snowfall_24h_cm", 0.0)
    snow72 = raw.get("snowfall_72h_cm", 0.0)
    elev = raw.get("elevation_m", 1500.0)
    ha0 = raw.get("total_hours_above_0C_since_ft", 0)
    ha3 = raw.get("total_hours_above_3C_since_ft", 0)
    ha6 = raw.get("total_hours_above_6C_since_ft", 0)
    ca0 = raw.get("cur_hours_above_0C", 0)
    ca3 = raw.get("cur_hours_above_3C", 0)
    ca6 = raw.get("cur_hours_above_6C", 0)

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

    if not temps or len(temps) < 48:
        return None

    from datetime import datetime, timezone

    hourly_times = hourly.get("time", [])

    # Find current hour index
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:00")
    current_index = len(hourly_times) - 1
    for i, time_str in enumerate(hourly_times):
        if time_str[:13] >= now_str[:13]:
            current_index = i
            break

    target_hour = current_index
    if target_hour < 48:
        return None

    cur_temp = temps[target_hour] if target_hour < len(temps) else temps[-1]

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
        "elevation_m": elevation_m or raw_data.get("elevation_meters", 1500.0),
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
    }


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

    # Forward pass through neural network
    W1 = model["weights"]["W1"]
    b1 = model["weights"]["b1"]
    W2 = model["weights"]["W2"]
    b2 = model["weights"]["b2"]

    n_hidden = len(b1)

    # Hidden layer: Z1 = X @ W1 + b1, A1 = relu(Z1)
    hidden = []
    for j in range(n_hidden):
        z = sum(normalized[i] * W1[i][j] for i in range(len(normalized))) + b1[j]
        hidden.append(_relu(z))

    # Output layer: Z2 = A1 @ W2 + b2, out = sigmoid(Z2) * 5 + 1
    z_out = sum(hidden[j] * W2[j][0] for j in range(n_hidden)) + b2[0]
    score = _sigmoid(z_out) * 5.0 + 1.0
    score = max(1.0, min(6.0, score))

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
