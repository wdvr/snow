#!/usr/bin/env python3
"""
Validate snow quality API output for 20 diverse test resorts.

Usage:
    python3 ml/validate_api.py              # hits prod
    python3 ml/validate_api.py staging      # hits staging
    python3 ml/validate_api.py <URL>        # hits custom URL
"""

import json
import sys
import urllib.request

APIS = {
    "prod": "https://api.powderchaserapp.com",
    "staging": "https://staging.api.powderchaserapp.com",
    "dev": "https://dev.api.powderchaserapp.com",
}

arg = sys.argv[1] if len(sys.argv) > 1 else "prod"
API = APIS.get(arg, arg)

RESORTS = [
    # NA West Coast
    "whistler-blackcomb",
    "mammoth-mountain",
    "palisades-tahoe",
    "big-white",
    # NA Rockies
    "vail",
    "park-city",
    "jackson-hole",
    "breckenridge",
    "steamboat",
    "aspen-snowmass",
    "telluride",
    # Canada
    "lake-louise",
    "revelstoke",
    # Alps
    "chamonix",
    "zermatt",
    "st-anton",
    "verbier",
    "val-disere",
    # Japan
    "niseko",
    "hakuba-valley",
]

print(f"\nAPI: {API}\n")
print(
    f"{'RESORT':<25} {'QUALITY':<12} {'SCORE':>5}  {'FRESH':>6}  {'TEMP':>5}  {'EXPLANATION'}"
)
print(f"{'-' * 25} {'-' * 12} {'-' * 5}  {'-' * 6}  {'-' * 5}  {'-' * 70}")

results = []
for resort_id in RESORTS:
    url = f"{API}/api/v1/resorts/{resort_id}/snow-quality"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        quality = data.get("overall_quality", "N/A")
        score = data.get("overall_snow_score", "N/A")
        explanation = data.get("overall_explanation", "")[:70]
        elevs = data.get("elevations", {})
        mid = elevs.get("mid", elevs.get("top", {}))
        fresh = mid.get("fresh_snow_cm", "?")
        temp = mid.get("temperature_celsius", "?")
        fresh_str = f"{fresh:.0f}cm" if isinstance(fresh, (int, float)) else str(fresh)
        temp_str = f"{temp:.0f}°C" if isinstance(temp, (int, float)) else str(temp)
        print(
            f"{resort_id:<25} {quality:<12} {score:>5}  {fresh_str:>6}  {temp_str:>5}  {explanation}"
        )
        results.append(
            {
                "resort_id": resort_id,
                "quality": quality,
                "score": score,
                "fresh_cm": fresh,
                "temp_c": temp,
            }
        )
    except Exception as e:
        print(f"{resort_id:<25} {'ERROR':<12} {'':>5}  {'':>6}  {'':>5}  {str(e)[:70]}")

# Summary
qualities = [r["quality"] for r in results]
for q in [
    "excellent",
    "great",
    "good",
    "decent",
    "mediocre",
    "poor",
    "bad",
    "horrible",
]:
    count = qualities.count(q)
    if count > 0:
        print(f"  {q}: {count}")
print(f"\nTotal: {len(results)} resorts checked")
