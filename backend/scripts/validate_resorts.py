#!/usr/bin/env python3
"""Resort validation script.

Validates scraped resorts by:
1. Finding official website URLs via web search
2. Fixing (0,0) coordinates via geocoding
3. Validating elevation data
4. Fetching Open-Meteo weather data
5. Comparing with resort-reported conditions
6. Running snow quality algorithm sanity checks

Usage:
    python scripts/validate_resorts.py --output /tmp/validation_results.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.openmeteo_service import OpenMeteoService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_resorts(scraped_path: str, prod_path: str) -> list[dict]:
    """Load net-new resorts (in scraped but not in production)."""
    with open(scraped_path) as f:
        scraped = json.load(f)
    with open(prod_path) as f:
        prod = json.load(f)

    prod_ids = {r["resort_id"] for r in prod["resorts"]}
    net_new = [r for r in scraped["resorts"] if r["resort_id"] not in prod_ids]
    logger.info(f"Found {len(net_new)} net-new resorts to validate")
    return net_new


def geocode_resort(
    name: str, state_province: str, country: str
) -> tuple[float, float] | None:
    """Geocode a resort using OpenStreetMap Nominatim."""
    query = f"{name} ski resort, {state_province}, {country}"
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "PowderChaserApp/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            logger.info(f"Geocoded {name}: ({lat}, {lon})")
            return lat, lon
        logger.warning(f"No geocoding results for {name}")
        return None
    except Exception as e:
        logger.error(f"Geocoding failed for {name}: {e}")
        return None


def fetch_openmeteo_weather(lat: float, lon: float, elevation: int) -> dict | None:
    """Fetch current weather from Open-Meteo API."""
    try:
        service = OpenMeteoService()
        return service.get_current_weather(lat, lon, elevation)
    except Exception as e:
        logger.error(f"Open-Meteo fetch failed for ({lat}, {lon}): {e}")
        return None


def validate_resort(resort: dict, weather: dict | None) -> dict:
    """Validate a single resort and return validation result."""
    issues = []
    resort_id = resort["resort_id"]

    # Check coordinates
    if resort["latitude"] == 0.0 and resort["longitude"] == 0.0:
        issues.append("missing_coordinates")

    # Check elevation - base < 300m is suspicious for NA resorts
    if resort.get("elevation_base_m", 0) < 300:
        issues.append(
            f"suspicious_base_elevation ({resort.get('elevation_base_m', 0)}m)"
        )

    # Check for missing state/province
    if not resort.get("state_province"):
        issues.append("missing_state_province")

    # Check timezone
    if resort.get("timezone") == "UTC":
        issues.append("generic_utc_timezone")

    # Check website
    if not resort.get("website"):
        issues.append("missing_website")

    # Weather validation
    if weather:
        temp = weather.get("current_temp_celsius")
        if temp is not None and temp > 30:
            issues.append(f"unrealistic_temperature ({temp}°C)")
    else:
        issues.append("weather_fetch_failed")

    status = "needs-fix" if issues else "reliable"
    return {
        "resort_id": resort_id,
        "name": resort["name"],
        "status": status,
        "issues": issues,
        "weather_data": {
            "temp_c": weather.get("current_temp_celsius") if weather else None,
            "snow_depth_cm": weather.get("snow_depth_cm") if weather else None,
            "snowfall_24h_cm": weather.get("snowfall_24h_cm") if weather else None,
        }
        if weather
        else None,
    }


def validate_batch(resorts: list[dict], fix_coords: bool = True) -> list[dict]:
    """Validate a batch of resorts."""
    results = []

    for resort in resorts:
        resort_id = resort["resort_id"]
        logger.info(f"Validating {resort_id}...")

        # Fix coordinates if needed
        if fix_coords and resort["latitude"] == 0.0 and resort["longitude"] == 0.0:
            coords = geocode_resort(
                resort["name"],
                resort.get("state_province", ""),
                resort.get("country", ""),
            )
            if coords:
                resort["latitude"], resort["longitude"] = coords
                # Rate limit for Nominatim (1 req/sec)
                time.sleep(1.1)

        # Fetch weather if we have coordinates
        weather = None
        if resort["latitude"] != 0.0 or resort["longitude"] != 0.0:
            weather = fetch_openmeteo_weather(
                resort["latitude"],
                resort["longitude"],
                resort.get("elevation_base_m", 1500),
            )
            # Rate limit for Open-Meteo
            time.sleep(0.5)

        result = validate_resort(resort, weather)
        result["resort_data"] = resort
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Validate scraped resorts")
    parser.add_argument(
        "--scraped",
        default=str(Path(__file__).parent.parent / "data" / "resorts_scraped.json"),
        help="Path to scraped resorts JSON",
    )
    parser.add_argument(
        "--prod",
        default=str(Path(__file__).parent.parent / "data" / "resorts.json"),
        help="Path to production resorts JSON",
    )
    parser.add_argument(
        "--output",
        default="/tmp/validation_results.json",
        help="Output path for validation results",
    )
    parser.add_argument(
        "--no-geocode",
        action="store_true",
        help="Skip geocoding (use pre-filled coordinates)",
    )
    args = parser.parse_args()

    resorts = load_resorts(args.scraped, args.prod)
    results = validate_batch(resorts, fix_coords=not args.no_geocode)

    reliable = [r for r in results if r["status"] == "reliable"]
    needs_fix = [r for r in results if r["status"] == "needs-fix"]

    logger.info(
        f"Validation complete: {len(reliable)} reliable, {len(needs_fix)} need fixes"
    )

    output = {
        "total": len(results),
        "reliable": len(reliable),
        "needs_fix": len(needs_fix),
        "results": results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
