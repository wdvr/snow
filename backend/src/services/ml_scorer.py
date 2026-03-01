"""ML-based snow quality scorer.

Loads trained neural network weights and performs inference on weather conditions.
The model takes engineered features computed from raw hourly weather data
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


def get_quality_thresholds() -> dict[str, float]:
    """Get quality thresholds from the loaded model.

    Returns optimized thresholds for mapping raw scores to quality labels.
    Falls back to default thresholds if model is not loaded.
    """
    model = _load_model()
    if model and "quality_thresholds" in model:
        return model["quality_thresholds"]
    return {
        "champagne_powder": 5.5,
        "powder_day": 5.0,
        "excellent": 4.5,
        "great": 4.0,
        "good": 3.5,
        "decent": 3.3,
        "mediocre": 2.9,
        "poor": 2.3,
        "bad": 1.4,
        "horrible": 0.0,
    }


def raw_score_to_quality(score: float) -> SnowQuality:
    """Convert a raw ML score to a SnowQuality enum using model thresholds."""
    t = get_quality_thresholds()
    if score >= t.get("champagne_powder", 5.5):
        return SnowQuality.CHAMPAGNE_POWDER
    elif score >= t.get("powder_day", 5.0):
        return SnowQuality.POWDER_DAY
    elif score >= t.get("excellent", 4.5):
        return SnowQuality.EXCELLENT
    elif score >= t.get("great", 4.0):
        return SnowQuality.GREAT
    elif score >= t.get("good", 3.5):
        return SnowQuality.GOOD
    elif score >= t.get("decent", 3.3):
        return SnowQuality.DECENT
    elif score >= t.get("mediocre", 2.9):
        return SnowQuality.MEDIOCRE
    elif score >= t.get("poor", 2.3):
        return SnowQuality.POOR
    elif score >= t.get("bad", 1.4):
        return SnowQuality.BAD
    else:
        return SnowQuality.HORRIBLE


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


def _compute_wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Compute wind chill temperature using the North American formula.

    Valid for temps <= 10C and wind >= 4.8 km/h.
    Returns the effective "feels like" temperature in C.
    """
    if temp_c > 10.0 or wind_kmh < 4.8:
        return temp_c
    wc = (
        13.12
        + 0.6215 * temp_c
        - 11.37 * (wind_kmh**0.16)
        + 0.3965 * temp_c * (wind_kmh**0.16)
    )
    return round(wc, 1)


# WMO weather codes indicating clear/sunny conditions
_CLEAR_WEATHER_CODES = {0, 1}  # Clear sky, Mainly clear
_SNOW_WEATHER_CODES = {71, 73, 75, 77, 85, 86}


def engineer_features(raw: dict[str, float]) -> list[float]:
    """Transform raw weather features into engineered features for the model.

    Args:
        raw: Dict with keys matching RAW_FEATURE_COLUMNS from training.

    Returns:
        List of 34 engineered feature values.
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
    snow_depth = _f("snow_depth_cm")

    # Weather comfort features
    cloud_cover = _f("cloud_cover_pct", 50.0)
    is_clear = _f("is_clear", 0.0)
    is_snowing = _f("is_snowing", 0.0)
    wind_chill = _f("wind_chill_c", ct)
    wind_chill_delta = _f("wind_chill_delta", 0.0)
    cur_wind = _f("cur_wind_kmh", avg_wind)

    # Visibility and gust features
    visibility_m = _f("visibility_m", 10000.0)
    min_vis_24h = _f("min_visibility_24h_m", 10000.0)
    max_gust = _f("max_wind_gust_24h", 0.0)

    # Snow freshness feature
    hours_since_snow = _f("hours_since_last_snowfall", 336.0)
    days_since_snow = min(hours_since_snow / 24.0, 14.0)

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
        snow_depth / 100.0,  # normalize to meters
        snow_ft / max(snow_depth, 1.0),  # fresh-to-total ratio
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
        # Weather comfort features (5)
        cloud_cover / 100.0,  # normalized 0-1
        is_clear,  # binary: clear or mainly clear sky
        wind_chill_delta,  # wind chill penalty (always <= 0)
        is_clear * max(0.0, 1.0 - cur_wind / 30.0),  # sunny calm indicator
        is_snowing * max(0, -ct) / 10.0 * max(0.0, 1.0 - avg_wind / 40.0),  # powder day
        # Visibility and gust features (3)
        visibility_m / 1000.0,  # normalized to km
        min_vis_24h / 1000.0,  # min visibility 24h, normalized to km
        max_gust / 100.0,  # max gust normalized
        # Snow freshness features (3)
        days_since_snow,
        max(0, days_since_snow - 2.0) * max(0, ct) / 5.0,  # aging * warmth
        snow24 / max(days_since_snow, 0.1),  # fresh snow rate
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

    # Snow depth from condition (if available)
    snow_depth_cm = getattr(condition, "snow_depth_cm", None) or 0.0

    # Weather comfort features from condition
    weather_code = getattr(condition, "weather_code", None)
    cloud_cover = 50.0  # default to partly cloudy if unknown
    is_clear = 0.0
    is_snowing = 0.0
    if weather_code is not None:
        weather_code = int(weather_code)
        is_clear = 1.0 if weather_code in _CLEAR_WEATHER_CODES else 0.0
        is_snowing = 1.0 if weather_code in _SNOW_WEATHER_CODES else 0.0
        # Approximate cloud cover from weather code
        if weather_code in {0, 1}:
            cloud_cover = 10.0
        elif weather_code == 2:
            cloud_cover = 50.0
        elif weather_code == 3:
            cloud_cover = 90.0
        else:
            cloud_cover = 75.0  # precipitation usually means cloudy

    wind_chill = _compute_wind_chill(cur_temp, float(wind_speed))
    wind_chill_delta = wind_chill - cur_temp

    # Wind gust and visibility from condition (v13 model features)
    visibility_m = getattr(condition, "visibility_m", None) or 10000.0
    min_visibility_24h_m = getattr(condition, "min_visibility_24h_m", None) or 10000.0
    max_wind_gust_24h = getattr(condition, "max_wind_gust_24h", None) or 0.0

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
        "snow_depth_cm": float(snow_depth_cm),
        "cloud_cover_pct": cloud_cover,
        "weather_code": float(weather_code) if weather_code is not None else 3.0,
        "is_clear": is_clear,
        "is_snowing": is_snowing,
        "wind_chill_c": wind_chill,
        "wind_chill_delta": wind_chill_delta,
        "visibility_m": float(visibility_m),
        "min_visibility_24h_m": float(min_visibility_24h_m),
        "max_wind_gust_24h": float(max_wind_gust_24h),
        "hours_since_last_snowfall": (
            float(getattr(condition, "hours_since_last_snowfall", None))
            if getattr(condition, "hours_since_last_snowfall", None) is not None
            else 336.0
        ),
    }


def _extract_features_at_hour(
    temps: list[float | None],
    snowfall: list[float | None],
    wind_speeds: list[float | None],
    target_hour: int,
    elevation_m: float,
    snow_depth_arr: list[float | None] | None = None,
    weather_code_arr: list[int | None] | None = None,
    cloud_cover_arr: list[float | None] | None = None,
    visibility_arr: list[float | None] | None = None,
    wind_gust_arr: list[float | None] | None = None,
) -> dict[str, float] | None:
    """Core feature extraction at a specific hour index.

    Computes the ML input features (pre-engineering) from hourly weather
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
    # Requires: 2+ cold hours (< -1°C) followed by 3+ warm hours (>= 0°C)
    # with warmest temp >= 1°C (prevents marginal forecast temps from triggering)
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

    # Ignore marginal freeze-thaw events. Real freeze-thaw cycles that damage
    # snow quality require sustained warm temps well above 0°C — a brief +1°C
    # forecast blip doesn't cause meaningful surface melt. Require warmest_thaw
    # >= 2°C to count as a real event (surface melt only starts above ~1.5°C
    # with solar radiation, and needs to be sustained for snowpack damage).
    if freeze_thaw_hour is not None and warmest_thaw < 2.0:
        freeze_thaw_hour = None
        warmest_thaw = 0.0

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

    # Snow depth at target hour (Open-Meteo returns snow_depth in meters)
    # Open-Meteo's forecast snow_depth can drop unrealistically fast due to its
    # simple melt model (e.g., 92cm → 1cm in 2 days at sub-zero temps). When the
    # target hour is in the forecast period, clamp snow_depth to at least the most
    # recent observed value minus a reasonable daily melt rate (5cm/day max when
    # temps stay below freezing, 15cm/day above freezing).
    if snow_depth_arr and len(snow_depth_arr) > target_hour:
        sd = snow_depth_arr[target_hour]
        snow_depth_cm = float(sd) * 100.0 if sd is not None else 0.0

        # Find the most recent plausible snow depth (last value >= 10cm)
        # to use as a floor for forecast periods
        recent_depth_cm = 0.0
        for h in range(
            min(target_hour, len(snow_depth_arr) - 1), max(target_hour - 168, -1), -1
        ):
            if h < 0:
                break
            v = snow_depth_arr[h]
            if v is not None and v * 100.0 >= 10.0:
                recent_depth_cm = v * 100.0
                # Calculate reasonable minimum based on days elapsed and temps
                days_elapsed = (target_hour - h) / 24.0
                if days_elapsed > 0:
                    # Check average temp in between
                    interval_temps = [t for t in temps[h:target_hour] if t is not None]
                    avg_temp = (
                        sum(interval_temps) / len(interval_temps)
                        if interval_temps
                        else 0.0
                    )
                    if avg_temp < 0:
                        melt_rate = 3.0  # cm/day sublimation at sub-zero
                    else:
                        melt_rate = 15.0  # cm/day active melt
                    floor_cm = max(0.0, recent_depth_cm - days_elapsed * melt_rate)
                    snow_depth_cm = max(snow_depth_cm, floor_cm)
                break
    else:
        snow_depth_cm = 0.0

    # Weather comfort features
    if weather_code_arr and len(weather_code_arr) > target_hour:
        wcode = weather_code_arr[target_hour]
        wcode = int(wcode) if wcode is not None else 3
    else:
        wcode = 3  # default to overcast

    if cloud_cover_arr and len(cloud_cover_arr) > target_hour:
        cloud_cover = cloud_cover_arr[target_hour]
        cloud_cover = float(cloud_cover) if cloud_cover is not None else 50.0
    else:
        cloud_cover = 50.0

    is_clear = 1.0 if wcode in _CLEAR_WEATHER_CODES else 0.0
    is_snowing = 1.0 if wcode in _SNOW_WEATHER_CODES else 0.0
    wind_chill = _compute_wind_chill(cur_temp, cur_wind)
    wind_chill_delta = wind_chill - cur_temp

    # Visibility features
    if visibility_arr and len(visibility_arr) > target_hour:
        vis = visibility_arr[target_hour]
        visibility_m = float(vis) if vis is not None else 10000.0
    else:
        visibility_m = 10000.0

    vis_24h = (
        [v for v in visibility_arr[h24_start:target_hour] if v is not None]
        if visibility_arr
        else []
    )
    min_visibility_24h_m = min(vis_24h) if vis_24h else visibility_m

    # Wind gust features
    if wind_gust_arr and len(wind_gust_arr) > target_hour:
        gust = wind_gust_arr[target_hour]
        max_wind_gust_24h = float(gust) if gust is not None else 0.0
    else:
        max_wind_gust_24h = 0.0

    gust_24h = (
        [g for g in wind_gust_arr[h24_start:target_hour] if g is not None]
        if wind_gust_arr
        else []
    )
    if gust_24h:
        max_wind_gust_24h = max(max_wind_gust_24h, max(gust_24h))

    # Hours since last significant snowfall (>0.1 cm in any hour)
    hours_since_last_snowfall = 336.0  # default: no recent snow (14 days)
    for h in range(target_hour, max(target_hour - 336, -1), -1):
        if h < 0 or h >= len(snowfall):
            break
        s = snowfall[h]
        if s is not None and s > 0.1:
            hours_since_last_snowfall = float(target_hour - h)
            break

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
        "snow_depth_cm": snow_depth_cm,
        "cloud_cover_pct": cloud_cover,
        "weather_code": float(wcode),
        "is_clear": is_clear,
        "is_snowing": is_snowing,
        "wind_chill_c": wind_chill,
        "wind_chill_delta": wind_chill_delta,
        "visibility_m": visibility_m,
        "min_visibility_24h_m": min_visibility_24h_m,
        "max_wind_gust_24h": max_wind_gust_24h,
        "hours_since_last_snowfall": hours_since_last_snowfall,
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
    snow_depth_arr = hourly.get("snow_depth", [])
    weather_code_arr = hourly.get("weather_code", [])
    cloud_cover_arr = hourly.get("cloud_cover", [])
    visibility_arr = hourly.get("visibility", [])
    wind_gust_arr = hourly.get("wind_gusts_10m", [])

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
    return _extract_features_at_hour(
        temps,
        snowfall,
        wind_speeds,
        current_index,
        elev,
        snow_depth_arr,
        weather_code_arr,
        cloud_cover_arr,
        visibility_arr or None,
        wind_gust_arr or None,
    )


def _override_snowfall_from_condition(
    raw_features: dict[str, float],
    condition: Any,
) -> None:
    """Override snowfall features with merged values from the condition.

    When supplementary sources (OnTheSnow, Snow-Forecast) report higher
    snowfall than Open-Meteo's hourly data, the merged condition fields
    are more accurate. This ensures the ML model uses the best available
    snowfall data rather than Open-Meteo's raw (often underreported) values.
    """
    merged_24h = getattr(condition, "snowfall_24h_cm", None)
    merged_72h = getattr(condition, "snowfall_72h_cm", None)
    merged_hours_since = getattr(condition, "hours_since_last_snowfall", None)

    if merged_24h is not None and merged_24h > raw_features.get("snowfall_24h_cm", 0):
        raw_features["snowfall_24h_cm"] = float(merged_24h)

    if merged_72h is not None and merged_72h > raw_features.get("snowfall_72h_cm", 0):
        raw_features["snowfall_72h_cm"] = float(merged_72h)

    # If merged hours_since_last_snowfall is set (e.g., estimated from resort data)
    # and it's smaller (more recent) than the raw_data value, use it
    if merged_hours_since is not None:
        raw_hours = raw_features.get("hours_since_last_snowfall", 336.0)
        if merged_hours_since < raw_hours:
            raw_features["hours_since_last_snowfall"] = float(merged_hours_since)

    # Reconcile snow_since_freeze_cm with merged snowfall data.
    # When Open-Meteo reports 0cm but resort stations report heavy snow,
    # snow_since_freeze_cm (computed from Open-Meteo hourly) can be 0
    # while snowfall_24h_cm (from merged sources) is 10+cm.
    merged_after_freeze = getattr(condition, "snowfall_after_freeze_cm", None)
    if merged_after_freeze is not None:
        raw_freeze = raw_features.get("snow_since_freeze_cm", 0.0)
        if merged_after_freeze > raw_freeze:
            raw_features["snow_since_freeze_cm"] = float(merged_after_freeze)


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

    # Override snowfall features with merged values from the condition.
    # raw_data features use Open-Meteo's hourly arrays, but the merger
    # may have corrected snowfall totals using resort-reported data
    # (OnTheSnow, Snow-Forecast). Without this, the ML model sees
    # Open-Meteo's underreported snowfall instead of the merged values.
    _override_snowfall_from_condition(raw_features, condition)

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

    # Apply physics constraints
    score = _apply_no_snowfall_cap(score, raw_features)
    score = _apply_fresh_snow_floor(score, raw_features)

    quality = raw_score_to_quality(score)

    return quality, score


def _apply_no_snowfall_cap(
    score: float,
    raw_features: dict[str, float],
) -> float:
    """Cap score when there is no recent snowfall — a physics constraint.

    "Champagne powder" and "powder day" ratings are physically impossible
    without fresh snow. The ML model can hallucinate high scores for
    forecast time slots when other features (cold temps, high snow depth)
    look favorable but snowfall is zero. This post-scoring guard enforces
    the physical constraint.

    Rules (conservative — only constrain impossible cases):
    - No snowfall in 72h (< 0.5cm): cap at 4.0 (GREAT). Fresh powder
      labels require actual fresh snow.
    - No snowfall in 24h but some in 72h (< 5cm total): cap at 4.5
      (EXCELLENT). Aging snow from 2-3 days ago can still be very good
      in cold conditions but is not "powder".

    Args:
        score: Raw ML score (1.0-6.0)
        raw_features: Dict of raw features from _extract_features_at_hour

    Returns:
        Capped score (1.0-6.0)
    """
    snow_24h = raw_features.get("snowfall_24h_cm", 0.0)
    snow_72h = raw_features.get("snowfall_72h_cm", 0.0)

    if snow_72h < 0.5:
        # No meaningful snowfall in 72h — impossible to have powder
        # Cap at GREAT (4.0); conditions can still be good with cold temps
        # and existing snow depth, but not "powder day" or "champagne powder"
        cap = 4.0
        if score > cap:
            logger.debug(
                f"No-snowfall cap: score {score:.2f} -> {cap:.1f} "
                f"(snow_24h={snow_24h:.1f}, snow_72h={snow_72h:.1f})"
            )
            return cap
    elif snow_24h < 0.5 and snow_72h < 5.0:
        # No fresh snow in 24h, modest amount in 72h — aging snow
        # Cap at EXCELLENT (4.5); 2-3 day old snow in cold conditions
        # can be excellent but not quite "powder day" territory
        cap = 4.5
        if score > cap:
            logger.debug(
                f"No-snowfall cap: score {score:.2f} -> {cap:.1f} "
                f"(snow_24h={snow_24h:.1f}, snow_72h={snow_72h:.1f})"
            )
            return cap

    return score


def _apply_fresh_snow_floor(
    score: float,
    raw_features: dict[str, float],
) -> float:
    """Enforce minimum score when significant fresh snow is present.

    The ML model can underestimate quality when Open-Meteo's raw hourly
    data shows 0cm but merged sources (resort stations) report heavy snow.
    This creates internally inconsistent features that confuse the model.

    Temperature tiers: cold temps produce better powder, warm temps mean
    softer snow but still fresh and very skiable.

    Rules:
    - Heavy fresh snow (>=15cm/24h): floor 4.5 (cold) / 4.0 (cool) / 3.0 (warm)
    - Moderate fresh snow (>=8cm/24h): floor 3.5 (cold) / 3.0 (cool) / 2.5 (warm)
    - Light fresh snow (>=3cm/24h): floor 2.5 (cold) / 2.0 (cool)

    Args:
        score: Raw ML score (1.0-6.0)
        raw_features: Dict of raw features from _extract_features_at_hour

    Returns:
        Floored score (1.0-6.0)
    """
    snow_24h = raw_features.get("snowfall_24h_cm", 0.0)
    cur_temp = raw_features.get("cur_temp", 0.0)
    hours_since = raw_features.get("hours_since_last_snowfall", 336.0)

    # Only apply if snow is truly recent (within last 24 hours)
    if hours_since > 24:
        return score

    floor = None
    if snow_24h >= 15.0:
        if cur_temp <= -5.0:
            floor = 4.5  # Heavy powder at very cold temps
        elif cur_temp <= 0.0:
            floor = 4.0  # Heavy fresh snow at freezing
        elif cur_temp <= 5.0:
            floor = 3.5  # Heavy fresh, mild but 15cm+ covers well
    elif snow_24h >= 8.0:
        if cur_temp <= -3.0:
            floor = 3.5  # Moderate fresh snow at cold temps
        elif cur_temp <= 0.0:
            floor = 3.0  # Moderate fresh at freezing
        elif cur_temp <= 5.0:
            floor = 3.0  # 8cm+ fresh covers refrozen base at mild temps
    elif snow_24h >= 3.0:
        if cur_temp <= 0.0:
            floor = 2.5  # Light fresh snow at freezing temps
        elif cur_temp <= 5.0:
            floor = 2.0  # Light fresh, slightly warm

    if floor is None:
        return score

    if score < floor:
        logger.debug(
            f"Fresh-snow floor: score {score:.2f} -> {floor:.1f} "
            f"(snow_24h={snow_24h:.1f}, temp={cur_temp:.1f}, "
            f"hours_since={hours_since:.0f})"
        )
        return floor
    return score


def predict_quality_at_hour(
    hourly_times: list[str],
    temps: list[float | None],
    snowfall: list[float | None],
    wind_speeds: list[float | None],
    target_hour_index: int,
    elevation_m: float,
    snow_depth_arr: list[float | None] | None = None,
    weather_code_arr: list[int | None] | None = None,
    cloud_cover_arr: list[float | None] | None = None,
    hourly_visibility: list[float | None] | None = None,
    hourly_wind_gusts: list[float | None] | None = None,
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
        snow_depth_arr: Hourly snow depth array (cm), optional
        weather_code_arr: Hourly WMO weather code array, optional
        cloud_cover_arr: Hourly cloud cover percentage array (0-100), optional

    Returns:
        Tuple of (SnowQuality, raw_score)
    """
    model = _load_model()
    if model is None:
        return SnowQuality.UNKNOWN, 3.5

    raw_features = _extract_features_at_hour(
        temps,
        snowfall,
        wind_speeds,
        target_hour_index,
        elevation_m,
        snow_depth_arr,
        weather_code_arr,
        cloud_cover_arr,
        hourly_visibility,
        hourly_wind_gusts,
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

    # Apply physics constraints
    score = _apply_no_snowfall_cap(score, raw_features)
    score = _apply_fresh_snow_floor(score, raw_features)

    quality = raw_score_to_quality(score)

    return quality, score
