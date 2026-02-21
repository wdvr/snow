#!/usr/bin/env python3
"""Collect training data from the production API for ML model improvement."""

import json
import urllib.request
import sys
from datetime import datetime

BASE_URL = "https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod"

RESORTS = [
    "whistler-blackcomb",
    "big-white",
    "silver-star",
    "sun-peaks",
    "lake-louise",
    "revelstoke",
    "vail",
    "park-city",
    "jackson-hole",
    "aspen-snowmass",
    "chamonix",
    "zermatt",
    "st-anton",
    "verbier",
    "niseko",
    "hakuba",
    "mammoth-mountain",
    "palisades-tahoe",
    "breckenridge",
    "steamboat",
    "telluride",
]

LEVELS = ["base", "mid", "top"]


def fetch_json(url):
    """Fetch JSON from a URL."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
        return None


def main():
    all_samples = []
    summary_rows = []

    for resort in RESORTS:
        print(f"Fetching {resort}...", file=sys.stderr)

        # Fetch snow quality (has overall + per-elevation scores)
        quality_url = f"{BASE_URL}/api/v1/resorts/{resort}/snow-quality"
        quality_data = fetch_json(quality_url)

        # Build a map of elevation -> quality info
        quality_by_level = {}
        if quality_data and "elevations" in quality_data:
            elevations = quality_data["elevations"]
            if isinstance(elevations, dict):
                quality_by_level = elevations
            elif isinstance(elevations, list):
                for elev in elevations:
                    level = elev.get("elevation_level", "")
                    quality_by_level[level] = elev

        for level in LEVELS:
            # Fetch conditions
            cond_url = f"{BASE_URL}/api/v1/resorts/{resort}/conditions/{level}"
            cond = fetch_json(cond_url)

            if not cond:
                print(f"  No conditions for {resort}/{level}", file=sys.stderr)
                continue

            # Extract raw data if available
            raw = cond.get("raw_data", {})
            api_resp = raw.get("api_response", {})

            # Get quality score for this elevation
            q_info = quality_by_level.get(level, {})
            # The conditions endpoint has quality_score (ML float 1-6)
            # The snow-quality endpoint has snow_score (0-100 display score) and quality (label)
            quality_score = cond.get("quality_score")
            quality_label = q_info.get("quality", cond.get("snow_quality", "unknown"))

            # Extract features from conditions
            sample = {
                "resort_id": resort,
                "elevation_level": level,
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "timestamp": cond.get("timestamp"),
                # Temperature features
                "current_temp_celsius": cond.get("current_temp_celsius"),
                "min_temp_celsius": cond.get("min_temp_celsius"),
                "max_temp_celsius": cond.get("max_temp_celsius"),
                # Snowfall features
                "snowfall_24h_cm": cond.get("snowfall_24h_cm"),
                "snowfall_48h_cm": cond.get("snowfall_48h_cm"),
                "snowfall_72h_cm": cond.get("snowfall_72h_cm"),
                "snow_depth_cm": cond.get("snow_depth_cm"),
                "fresh_snow_cm": cond.get("fresh_snow_cm"),
                "snowfall_after_freeze_cm": cond.get("snowfall_after_freeze_cm"),
                # Freeze-thaw features
                "last_freeze_thaw_hours_ago": cond.get("last_freeze_thaw_hours_ago"),
                "hours_above_ice_threshold": cond.get("hours_above_ice_threshold"),
                "max_consecutive_warm_hours": cond.get("max_consecutive_warm_hours"),
                # Wind
                "wind_speed_kmh": cond.get("wind_speed_kmh"),
                "humidity_percent": cond.get("humidity_percent"),
                # Elevation
                "elevation_meters": raw.get("elevation_meters"),
                "model_elevation": raw.get("model_elevation"),
                # Quality
                "quality_score": quality_score,
                "quality_label": quality_label,
                "confidence_level": cond.get("confidence_level"),
                "data_source": cond.get("data_source"),
                # Predictions
                "predicted_snow_24h_cm": cond.get("predicted_snow_24h_cm"),
                "predicted_snow_48h_cm": cond.get("predicted_snow_48h_cm"),
                "predicted_snow_72h_cm": cond.get("predicted_snow_72h_cm"),
                # Weather
                "weather_description": cond.get("weather_description"),
                "currently_warming": cond.get("currently_warming"),
                # Raw hourly data reference (for feature engineering)
                "has_hourly_data": "hourly" in api_resp if api_resp else False,
            }

            # Extract daily temperature arrays for feature engineering
            daily = api_resp.get("daily", {}) if api_resp else {}
            if daily:
                sample["daily_max_temps"] = daily.get("temperature_2m_max", [])
                sample["daily_min_temps"] = daily.get("temperature_2m_min", [])
                sample["daily_snowfall"] = daily.get("snowfall_sum", [])

            all_samples.append(sample)

            # Summary row
            summary_rows.append(
                {
                    "resort_id": resort,
                    "elevation": level,
                    "temperature": cond.get("current_temp_celsius"),
                    "snow_depth": cond.get("snow_depth_cm"),
                    "fresh_snow": cond.get("snowfall_24h_cm"),
                    "wind": cond.get("wind_speed_kmh"),
                    "quality_score": quality_score,
                    "quality_label": quality_label,
                }
            )

    # Output the full dataset
    output = {
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "source": "production_api",
        "api_base": BASE_URL,
        "total_samples": len(all_samples),
        "resorts_count": len(RESORTS),
        "elevation_levels": LEVELS,
        "samples": all_samples,
    }

    # Write to file
    with open("/Users/wouter/dev/snow/ml/production_training_data.json", "w") as f:
        json.dump(output, f, indent=2)

    print(
        f"\nCollected {len(all_samples)} samples from {len(RESORTS)} resorts",
        file=sys.stderr,
    )
    print("Written to ml/production_training_data.json\n", file=sys.stderr)

    # Print summary table
    print(
        f"{'Resort':<25} {'Elev':<6} {'Temp':>6} {'Depth':>7} {'Fresh':>6} {'Wind':>6} {'Score':>6} {'Quality':<12}"
    )
    print("-" * 90)
    for row in summary_rows:
        temp = f"{row['temperature']:.1f}" if row["temperature"] is not None else "N/A"
        depth = f"{row['snow_depth']:.0f}" if row["snow_depth"] is not None else "N/A"
        fresh = f"{row['fresh_snow']:.1f}" if row["fresh_snow"] is not None else "N/A"
        wind = f"{row['wind']:.0f}" if row["wind"] is not None else "N/A"
        score = (
            f"{row['quality_score']:.2f}" if row["quality_score"] is not None else "N/A"
        )
        print(
            f"{row['resort_id']:<25} {row['elevation']:<6} {temp:>6} {depth:>7} {fresh:>6} {wind:>6} {score:>6} {row['quality_label']:<12}"
        )

    # Now create scored training samples in the format matching scores_real.json
    training_scores = []
    for sample in all_samples:
        if sample["quality_score"] is not None:
            training_scores.append(
                {
                    "resort_id": sample["resort_id"],
                    "elevation_level": sample["elevation_level"],
                    "date": sample["date"],
                    "score": round(sample["quality_score"], 1),
                    "source": "production_api_collected",
                    "features": {
                        "cur_temp": sample["current_temp_celsius"],
                        "max_temp_24h": sample["max_temp_celsius"],
                        "min_temp_24h": sample["min_temp_celsius"],
                        "snowfall_24h_cm": sample["snowfall_24h_cm"],
                        "snowfall_72h_cm": sample["snowfall_72h_cm"],
                        "snow_depth_cm": sample["snow_depth_cm"],
                        "elevation_m": sample.get("elevation_meters")
                        or sample.get("model_elevation"),
                        "wind_speed_kmh": sample["wind_speed_kmh"],
                        "snowfall_after_freeze_cm": sample["snowfall_after_freeze_cm"],
                        "last_freeze_thaw_hours_ago": sample[
                            "last_freeze_thaw_hours_ago"
                        ],
                        "hours_above_ice_threshold": sample[
                            "hours_above_ice_threshold"
                        ],
                        "humidity_percent": sample["humidity_percent"],
                        "quality_label": sample["quality_label"],
                    },
                }
            )

    with open(
        "/Users/wouter/dev/snow/ml/scores/scores_production_collected.json", "w"
    ) as f:
        json.dump(training_scores, f, indent=2)

    print(
        f"\nWrote {len(training_scores)} scored training samples to ml/scores/scores_production_collected.json",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
