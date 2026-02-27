"""Debug script to investigate forecast score drops for European lower-elevation resorts.

Fetches timeline data from Open-Meteo (14 days past + 7 days forecast) and
analyzes the ML model features and scores at various future hours to identify
why scores drop in the forecast period.

Usage:
    cd backend && PYTHONPATH=src python3 scripts/debug_forecast_drops.py
"""

import json
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "src")

import requests

from services.ml_scorer import (
    _apply_cold_accumulation_boost,
    _apply_snow_aging_penalty,
    _extract_features_at_hour,
    _load_model,
    engineer_features,
    predict_quality_at_hour,
)

# ── Target resorts ──────────────────────────────────────────────────────────
TARGET_IDS = [
    "chamonix",
    "kitzbuehel",
    "cortina",
    "lech-zuers",
    "courchevel",
]

# ── Load resort data ────────────────────────────────────────────────────────
with open("data/resorts.json") as f:
    data = json.load(f)
resorts_list = data["resorts"]
resorts_by_id = {r["resort_id"]: r for r in resorts_list}

# ── Open-Meteo parameters (same as timeline endpoint) ──────────────────────
OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_PARAMS = "temperature_2m,snowfall,snow_depth,wind_speed_10m,wind_gusts_10m,weather_code,cloud_cover,visibility"


def fetch_hourly_data(lat, lon, elev):
    """Fetch hourly data from Open-Meteo with 14 past + 7 forecast days."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "elevation": elev,
        "hourly": HOURLY_PARAMS,
        "past_days": 14,
        "forecast_days": 7,
        "timezone": "GMT",
    }
    resp = requests.get(OPENMETEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def find_current_hour_index(times):
    """Find the index of the current hour in the hourly times array."""
    now = datetime.now(UTC)
    now_str = now.strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(times):
        if t[:13] == now_str[:13]:
            return i
    # Fallback: find closest
    for i, t in enumerate(times):
        pt = datetime.fromisoformat(t).replace(tzinfo=UTC)
        if pt >= now:
            return max(0, i - 1)
    return len(times) - 1


def analyze_resort(resort_id):
    """Analyze a single resort for forecast score drops."""
    resort = resorts_by_id.get(resort_id)
    if not resort:
        print(f"  !! Resort '{resort_id}' not found in resorts.json")
        return

    name = resort["name"]
    lat = resort["latitude"]
    lon = resort["longitude"]
    mid_elev = resort.get("elevation_mid_m", 2000)
    top_elev = resort.get("elevation_top_m", mid_elev + 500)
    base_elev = resort.get("elevation_base_m", mid_elev - 500)

    print(f"\n{'=' * 80}")
    print(f"  {name} ({resort_id})")
    print(f"  Lat={lat}, Lon={lon}")
    print(f"  Elevations: base={base_elev}m, mid={mid_elev}m, top={top_elev}m")
    print(f"{'=' * 80}")

    data = fetch_hourly_data(lat, lon, mid_elev)
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    snowfall = hourly.get("snowfall", [])
    snow_depth = hourly.get("snow_depth", [])
    wind = hourly.get("wind_speed_10m", [])
    wind_gusts = hourly.get("wind_gusts_10m", [])
    weather_code = hourly.get("weather_code", [])
    cloud_cover = hourly.get("cloud_cover", [])
    visibility = hourly.get("visibility", [])

    now_idx = find_current_hour_index(times)
    print(f"\n  Total hours: {len(times)}, Current hour index: {now_idx}")
    print(f"  Current time: {times[now_idx] if now_idx < len(times) else 'N/A'}")

    # ── Offsets to inspect: now, +24h, +48h, ... +168h ──────────────────────
    offsets = [0, 24, 48, 72, 96, 120, 144, 168]
    offset_labels = ["now", "+24h", "+48h", "+72h", "+96h", "+120h", "+144h", "+168h"]

    # ── Section 1: Raw snow_depth from Open-Meteo ──────────────────────────
    print("\n  --- Raw Open-Meteo snow_depth (meters) ---")
    print(
        f"  {'Offset':<10} {'Time':<20} {'snow_depth(m)':<16} {'snow_depth(cm)':<16} {'temp(°C)':<10}"
    )
    for offset, label in zip(offsets, offset_labels, strict=False):
        idx = now_idx + offset
        if idx >= len(times):
            print(f"  {label:<10} (out of range)")
            continue
        sd = (
            snow_depth[idx]
            if idx < len(snow_depth) and snow_depth[idx] is not None
            else None
        )
        sd_cm = sd * 100 if sd is not None else None
        temp = temps[idx] if idx < len(temps) and temps[idx] is not None else None
        print(
            f"  {label:<10} {times[idx]:<20} {sd if sd is not None else 'None':<16} {f'{sd_cm:.1f}' if sd_cm is not None else 'None':<16} {f'{temp:.1f}' if temp is not None else 'None':<10}"
        )

    # ── Section 2: ML features at each offset ──────────────────────────────
    print("\n  --- ML Features at each offset ---")
    header = f"  {'Offset':<10} {'snow_depth_cm':<16} {'snow_since_ft':<16} {'ft_days_ago':<14} {'cur_temp':<10} {'warmest_thaw':<14} {'snow_24h':<10} {'snow_72h':<10}"
    print(header)

    feature_rows = []
    for offset, label in zip(offsets, offset_labels, strict=False):
        idx = now_idx + offset
        if idx >= len(times) or idx < 48:
            print(f"  {label:<10} (insufficient data: idx={idx})")
            feature_rows.append(None)
            continue

        feats = _extract_features_at_hour(
            temps,
            snowfall,
            wind,
            idx,
            mid_elev,
            snow_depth,
            weather_code,
            cloud_cover,
            visibility,
            wind_gusts,
        )
        if feats is None:
            print(f"  {label:<10} (features=None)")
            feature_rows.append(None)
            continue

        feature_rows.append(feats)
        print(
            f"  {label:<10} "
            f"{feats['snow_depth_cm']:<16.1f} "
            f"{feats['snow_since_freeze_cm']:<16.1f} "
            f"{feats['freeze_thaw_days_ago']:<14.1f} "
            f"{feats['cur_temp']:<10.1f} "
            f"{feats['warmest_thaw']:<14.1f} "
            f"{feats['snowfall_24h_cm']:<10.1f} "
            f"{feats['snowfall_72h_cm']:<10.1f}"
        )

    # ── Section 3: ML scores ───────────────────────────────────────────────
    print("\n  --- ML Scores (raw + post-adjustments) ---")
    print(
        f"  {'Offset':<10} {'Quality':<12} {'Raw Score':<12} {'Neural Net':<12} {'Aging Pen.':<12} {'Cold Boost':<12}"
    )

    for offset, label, feats in zip(offsets, offset_labels, feature_rows, strict=False):
        idx = now_idx + offset
        if idx >= len(times) or feats is None:
            print(f"  {label:<10} (skipped)")
            continue

        quality, raw_score = predict_quality_at_hour(
            times,
            temps,
            snowfall,
            wind,
            idx,
            mid_elev,
            snow_depth,
            weather_code,
            cloud_cover,
            visibility,
            wind_gusts,
        )

        # Compute the "pure" neural net score (before adjustments)
        model = _load_model()
        features_vec = engineer_features(feats)
        norm = model["normalization"]
        normalized = [
            (f - m) / s
            for f, m, s in zip(features_vec, norm["mean"], norm["std"], strict=False)
        ]
        ensemble = model.get("ensemble", [])
        if ensemble:
            from services.ml_scorer import _forward_ensemble

            nn_score = _forward_ensemble(normalized, ensemble)
        else:
            from services.ml_scorer import _forward_single

            nn_score = _forward_single(normalized, model["weights"])
        nn_score = max(1.0, min(6.0, nn_score))

        # Compute aging penalty effect
        hours_since_snow = None
        for h in range(idx, max(idx - 336, -1), -1):
            if h < 0 or h >= len(snowfall):
                break
            s = snowfall[h]
            if s is not None and s > 0.1:
                hours_since_snow = float(idx - h)
                break
        cur_temp = temps[idx] if temps[idx] is not None else 0.0
        after_aging = _apply_snow_aging_penalty(
            nn_score, hours_since_snow, feats["snowfall_24h_cm"], cur_temp
        )
        aging_delta = after_aging - nn_score

        # Compute cold accumulation boost effect
        after_boost = _apply_cold_accumulation_boost(
            after_aging,
            feats["snow_since_freeze_cm"],
            feats["freeze_thaw_days_ago"],
            cur_temp,
        )
        boost_delta = after_boost - after_aging

        q_str = quality.value if hasattr(quality, "value") else str(quality)
        print(
            f"  {label:<10} "
            f"{q_str:<12} "
            f"{raw_score:<12.2f} "
            f"{nn_score:<12.2f} "
            f"{aging_delta:<+12.2f} "
            f"{boost_delta:<+12.2f}"
        )

    # ── Section 4: Detailed freeze-thaw analysis ───────────────────────────
    print("\n  --- Freeze-Thaw Debug (at each offset) ---")
    for offset, label, feats in zip(offsets, offset_labels, feature_rows, strict=False):
        idx = now_idx + offset
        if idx >= len(times) or feats is None:
            continue

        ft_days = feats["freeze_thaw_days_ago"]
        warmest = feats["warmest_thaw"]
        snow_since_ft = feats["snow_since_freeze_cm"]
        hrs_above_0 = feats["total_hours_above_0C_since_ft"]

        # How many hours until we go above 0?
        first_thaw_offset = None
        for h in range(idx, min(idx + 168, len(temps))):
            if temps[h] is not None and temps[h] >= 0:
                first_thaw_offset = h - idx
                break

        print(
            f"  {label}: ft_days_ago={ft_days:.1f}, warmest_thaw={warmest:.1f}°C, "
            f"snow_since_ft={snow_since_ft:.1f}cm, hrs_above_0={hrs_above_0}, "
            f"first_thaw_in={first_thaw_offset}h"
        )

    # ── Section 5: Snow depth trajectory (hourly for first 48h) ────────────
    print("\n  --- Hourly Snow Depth Trajectory (now to +48h) ---")
    print(
        f"  {'Hour':<6} {'Time':<20} {'Raw SD(cm)':<12} {'Temp(°C)':<10} {'Snowfall':<10}"
    )
    for h_offset in range(0, min(49, len(times) - now_idx), 3):
        idx = now_idx + h_offset
        sd = (
            snow_depth[idx]
            if idx < len(snow_depth) and snow_depth[idx] is not None
            else None
        )
        sd_cm = sd * 100 if sd is not None else None
        temp = temps[idx] if idx < len(temps) and temps[idx] is not None else None
        sf = snowfall[idx] if idx < len(snowfall) and snowfall[idx] is not None else 0
        print(
            f"  +{h_offset:<5} {times[idx]:<20} {f'{sd_cm:.1f}' if sd_cm is not None else 'None':<12} "
            f"{f'{temp:.1f}' if temp is not None else 'None':<10} {sf:.1f}"
        )


def main():
    print("=" * 80)
    print("  FORECAST SCORE DROP ANALYSIS")
    print(f"  Run at: {datetime.now(UTC).isoformat()}")
    print(f"  Resorts: {', '.join(TARGET_IDS)}")
    print("=" * 80)

    for resort_id in TARGET_IDS:
        try:
            analyze_resort(resort_id)
        except Exception as e:
            print(f"\n  !! Error analyzing {resort_id}: {e}")
            import traceback

            traceback.print_exc()

    # ── Summary / Pattern Identification ────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  PATTERN ANALYSIS")
    print(f"{'=' * 80}")
    print("""
  Look for these patterns in the data above:

  1. SNOW DEPTH CRASH: Does Open-Meteo's raw snow_depth drop from
     significant values to near-zero in the forecast period? This is the
     most common cause — Open-Meteo's melt model is overly aggressive.

  2. FREEZE-THAW FALSE POSITIVE: Does freeze_thaw_days_ago go from 14.0
     (no event) to a small number in the forecast? Even brief forecast
     temps above 0°C can trigger the freeze-thaw detector, which resets
     snow_since_freeze_cm.

  3. SNOW AGING PENALTY: Does hours_since_snowfall grow large in the
     forecast period (no future snow predicted), causing the aging penalty
     to accumulate?

  4. COLD ACCUMULATION BOOST LOST: If freeze-thaw triggers in the forecast,
     snow_since_freeze_cm resets and the cold accumulation boost disappears.

  The ML model's snow_depth_cm feature has a floor clamp (see
  _extract_features_at_hour) but if the raw Open-Meteo depth drops to near
  zero, the floor might still be too low.
""")


if __name__ == "__main__":
    main()
