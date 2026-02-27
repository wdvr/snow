#!/usr/bin/env python3
"""
Spot-check 100 resorts for timeline score stability.

Fetches Open-Meteo data (14 past + 7 forecast days) for 100 evenly-spaced
resorts, computes ML scores at morning/midday/afternoon windows, applies
the production smoothing algorithm, then flags any resort where a forecast
score drops >20 points (0-100 scale) from today's midday score.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timezone

import requests

sys.path.insert(0, "src")

from services.ml_scorer import predict_quality_at_hour, raw_score_to_quality
from services.openmeteo_service import _smooth_timeline_scores
from services.quality_explanation_service import score_to_100

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_PARAMS = (
    "temperature_2m,snowfall,snow_depth,wind_speed_10m,"
    "wind_gusts_10m,weather_code,cloud_cover,visibility"
)
PAST_DAYS = 14
FORECAST_DAYS = 7
WORKERS = 15
SUSPICIOUS_DROP_THRESHOLD = 20  # points on 0-100 scale
HOURS_OF_DAY = [7, 12, 16]  # morning, midday, afternoon


def load_resorts(path: str, n: int = 100) -> list[dict]:
    """Load resorts.json and pick n evenly-spaced resorts."""
    with open(path) as f:
        data = json.load(f)
    all_resorts = data["resorts"]
    total = len(all_resorts)
    if total <= n:
        return all_resorts
    step = total / n
    return [all_resorts[int(i * step)] for i in range(n)]


def fetch_openmeteo(resort: dict) -> dict | None:
    """Fetch Open-Meteo hourly data for a resort at mid elevation."""
    params = {
        "latitude": resort["latitude"],
        "longitude": resort["longitude"],
        "elevation": resort.get("elevation_mid_m", 2000),
        "hourly": HOURLY_PARAMS,
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "GMT",
    }
    for attempt in range(3):
        try:
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == 2:
                print(f"  WARN: Failed to fetch {resort['name']}: {e}")
                return None
            time.sleep(1)
    return None


def build_timeline(resort: dict, meteo: dict) -> list[dict]:
    """
    Build timeline points (morning/midday/afternoon per day) and compute
    ML scores for each, then apply smoothing.
    """
    hourly = meteo.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    snowfall = hourly.get("snowfall", [])
    snow_depth = hourly.get("snow_depth", [])
    wind_speed = hourly.get("wind_speed_10m", [])
    wind_gusts = hourly.get("wind_gusts_10m", [])
    weather_code = hourly.get("weather_code", [])
    cloud_cover = hourly.get("cloud_cover", [])
    visibility = hourly.get("visibility", [])

    if not times:
        return []

    elevation = resort.get("elevation_mid_m", 2000)

    # Determine today in UTC
    now_utc = datetime.now(UTC)
    today_str = now_utc.strftime("%Y-%m-%d")

    # Forecast starts at beginning of today (GMT timezone)
    forecast_start = today_str + "T00:00"

    # Build a time->index lookup
    time_to_idx = {t: i for i, t in enumerate(times)}

    # Collect all unique dates
    dates_seen = sorted({t[:10] for t in times})

    points = []
    for date_str in dates_seen:
        for hour in HOURS_OF_DAY:
            time_key = f"{date_str}T{hour:02d}:00"
            idx = time_to_idx.get(time_key)
            if idx is None:
                continue

            is_forecast = time_key >= forecast_start

            try:
                quality_enum, raw_score = predict_quality_at_hour(
                    hourly_times=times,
                    temps=temps,
                    snowfall=snowfall,
                    wind_speeds=wind_speed,
                    target_hour_index=idx,
                    elevation_m=elevation,
                    snow_depth_arr=snow_depth,
                    weather_code_arr=weather_code,
                    cloud_cover_arr=cloud_cover,
                    hourly_visibility=visibility,
                    hourly_wind_gusts=wind_gusts,
                )
            except Exception:
                continue

            snow_score = score_to_100(raw_score)

            points.append(
                {
                    "date": date_str,
                    "hour": hour,
                    "time": time_key,
                    "is_forecast": is_forecast,
                    "snow_score": snow_score,
                    "quality_score": round(raw_score, 2),
                    "snow_quality": (
                        quality_enum.value
                        if hasattr(quality_enum, "value")
                        else str(quality_enum)
                    ),
                }
            )

    # Apply production smoothing
    _smooth_timeline_scores(points, raw_score_to_quality, score_to_100)

    return points


def analyse_resort(resort: dict) -> dict | None:
    """Fetch data, build timeline, check for suspicious drops."""
    meteo = fetch_openmeteo(resort)
    if meteo is None:
        return None

    points = build_timeline(resort, meteo)
    if not points:
        return None

    now_utc = datetime.now(UTC)
    today_str = now_utc.strftime("%Y-%m-%d")

    # Find today's midday score
    today_midday = [p for p in points if p["date"] == today_str and p["hour"] == 12]
    if not today_midday:
        return None
    today_score = today_midday[0]["snow_score"]

    # Find all forecast midday scores after today
    forecast_midday = [
        p
        for p in points
        if p["is_forecast"] and p["hour"] == 12 and p["date"] > today_str
    ]
    if not forecast_midday:
        return None

    worst = min(forecast_midday, key=lambda p: p["snow_score"])
    worst_score = worst["snow_score"]
    delta = today_score - worst_score

    return {
        "resort_name": resort["name"],
        "resort_id": resort["resort_id"],
        "today_score": today_score,
        "worst_forecast_score": worst_score,
        "worst_forecast_date": worst["date"],
        "delta": delta,
        "suspicious": delta > SUSPICIOUS_DROP_THRESHOLD,
        "num_forecast_days": len(forecast_midday),
    }


def main():
    resorts_path = "data/resorts.json"
    resorts = load_resorts(resorts_path, n=100)
    print(f"Spot-checking {len(resorts)} resorts for timeline score stability")
    print(
        f"Threshold: flag if any forecast midday score drops > {SUSPICIOUS_DROP_THRESHOLD} pts from today"
    )
    print(f"Using {WORKERS} workers for parallel fetching")
    print("-" * 80)

    results = []
    errors = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_resort = {executor.submit(analyse_resort, r): r for r in resorts}
        for i, future in enumerate(as_completed(future_to_resort), 1):
            resort = future_to_resort[future]
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
                else:
                    errors += 1
            except Exception as e:
                print(f"  ERROR processing {resort['name']}: {e}")
                errors += 1

            if i % 25 == 0 or i == len(resorts):
                print(f"  Progress: {i}/{len(resorts)} resorts processed")

    # Summary
    suspicious = [r for r in results if r["suspicious"]]
    clean = [r for r in results if not r["suspicious"]]

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Resorts analysed:       {len(results)}")
    print(f"Fetch/processing errors: {errors}")
    print(f"Clean (drop <= {SUSPICIOUS_DROP_THRESHOLD} pts):   {len(clean)}")
    print(f"Suspicious (drop > {SUSPICIOUS_DROP_THRESHOLD}):   {len(suspicious)}")
    print()

    if suspicious:
        suspicious.sort(key=lambda r: r["delta"], reverse=True)
        print(
            f"{'Resort':<35} {'Today':>6} {'Worst':>6} {'Delta':>6} {'Worst Date':>12}"
        )
        print("-" * 70)
        for r in suspicious:
            print(
                f"{r['resort_name']:<35} "
                f"{r['today_score']:>6} "
                f"{r['worst_forecast_score']:>6} "
                f"{r['delta']:>+6} "
                f"{r['worst_forecast_date']:>12}"
            )
    else:
        print("No suspicious drops detected. Smoothing is working as expected.")

    # Also show score distribution
    if results:
        scores = [r["today_score"] for r in results]
        deltas = [r["delta"] for r in results]
        print()
        print(
            f"Today's score range:  {min(scores)} - {max(scores)} (mean {sum(scores) / len(scores):.0f})"
        )
        print(f"Max forecast drop:    {max(deltas)} pts")
        print(f"Mean forecast drop:   {sum(deltas) / len(deltas):.1f} pts")


if __name__ == "__main__":
    main()
