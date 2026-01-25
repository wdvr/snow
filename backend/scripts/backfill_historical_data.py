#!/usr/bin/env python3
"""
One-time script to backfill historical weather data.

This script fetches historical data (up to 14 days) from Open-Meteo
to detect freeze-thaw cycles and calculate snowfall since the last thaw.

Usage:
    PYTHONPATH=src python scripts/backfill_historical_data.py [--dry-run] [--resort RESORT_ID]
"""

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import boto3
import requests

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.weather import ConfidenceLevel, WeatherCondition
from services.resort_service import ResortService
from services.snow_quality_service import SnowQualityService
from utils.dynamodb_utils import prepare_for_dynamodb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Open-Meteo supports up to 16 days of historical data via forecast API
MAX_HISTORICAL_DAYS = 14

# Ice formation thresholds: (temp_celsius, required_consecutive_hours)
ICE_THRESHOLDS = [
    (3.0, 3),  # 3 hours at +3°C
    (2.0, 6),  # 6 hours at +2°C
    (1.0, 8),  # 8 hours at +1°C
]


def fetch_extended_historical_data(
    latitude: float, longitude: float, elevation_meters: int, past_days: int = 14
) -> dict:
    """
    Fetch extended historical weather data from Open-Meteo.

    Returns hourly temperature and snowfall data for the specified period.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation_meters,
        "current": "temperature_2m",
        "hourly": "temperature_2m,snowfall,snow_depth",
        "past_days": min(past_days, MAX_HISTORICAL_DAYS),
        "forecast_days": 1,  # Just need current, focus on historical
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def find_last_freeze_thaw_event(hourly_temps: list, hourly_times: list) -> tuple:
    """
    Find the last freeze-thaw event in the historical data.

    Returns:
        tuple: (hours_ago, event_end_index) or (None, None) if no event found
    """
    if not hourly_temps or not hourly_times:
        return None, None

    # Find current hour index
    now = datetime.now(UTC)
    now_str = now.strftime("%Y-%m-%dT%H:00")
    current_index = len(hourly_times) - 1

    for i, time_str in enumerate(hourly_times):
        if time_str[:13] >= now_str[:13]:
            current_index = i
            break

    # Search backwards for ice formation events
    for i in range(current_index, -1, -1):
        if i >= len(hourly_temps) or hourly_temps[i] is None:
            continue

        temp = hourly_temps[i]

        # Check each threshold
        for threshold_temp, required_hours in ICE_THRESHOLDS:
            if temp >= threshold_temp:
                # Count consecutive hours at or above this threshold
                consecutive = 0
                for j in range(i, max(-1, i - required_hours - 1), -1):
                    if (
                        j >= 0
                        and j < len(hourly_temps)
                        and hourly_temps[j] is not None
                        and hourly_temps[j] >= threshold_temp
                    ):
                        consecutive += 1
                    else:
                        break

                if consecutive >= required_hours:
                    # Found an ice formation event!
                    hours_ago = current_index - i
                    return hours_ago, i

    # No event found in historical data
    return None, None


def calculate_snowfall_since_event(
    hourly_snowfall: list, event_end_index: int, current_index: int
) -> float:
    """Calculate total snowfall since the freeze-thaw event."""
    if event_end_index is None:
        # No event found - sum all available snowfall
        return sum(s for s in hourly_snowfall if s is not None)

    total = 0.0
    for i in range(event_end_index + 1, min(current_index + 1, len(hourly_snowfall))):
        if hourly_snowfall[i] is not None:
            total += hourly_snowfall[i]

    return total


def process_resort(
    resort, weather_conditions_table, snow_quality_service, dry_run: bool = False
):
    """Process a single resort and store historical conditions."""
    logger.info(f"Processing {resort.name} ({resort.resort_id})...")

    for elevation_point in resort.elevation_points:
        try:
            # Fetch extended historical data
            data = fetch_extended_historical_data(
                latitude=elevation_point.latitude,
                longitude=elevation_point.longitude,
                elevation_meters=elevation_point.elevation_meters,
                past_days=MAX_HISTORICAL_DAYS,
            )

            hourly = data.get("hourly", {})
            current = data.get("current", {})

            hourly_temps = hourly.get("temperature_2m", [])
            hourly_snowfall = hourly.get("snowfall", [])
            hourly_times = hourly.get("time", [])
            hourly_snow_depth = hourly.get("snow_depth", [])

            # Find current index
            now = datetime.now(UTC)
            now_str = now.strftime("%Y-%m-%dT%H:00")
            current_index = len(hourly_times) - 1
            for i, time_str in enumerate(hourly_times):
                if time_str[:13] >= now_str[:13]:
                    current_index = i
                    break

            # Find last freeze-thaw event
            hours_ago, event_index = find_last_freeze_thaw_event(
                hourly_temps, hourly_times
            )

            # Calculate snowfall since event
            snowfall_after_freeze = calculate_snowfall_since_event(
                hourly_snowfall, event_index, current_index
            )

            # Calculate recent snowfall
            start_24h = max(0, current_index - 24)
            start_48h = max(0, current_index - 48)
            start_72h = max(0, current_index - 72)

            snowfall_24h = sum(
                s
                for s in hourly_snowfall[start_24h : current_index + 1]
                if s is not None
            )
            snowfall_48h = sum(
                s
                for s in hourly_snowfall[start_48h : current_index + 1]
                if s is not None
            )
            snowfall_72h = sum(
                s
                for s in hourly_snowfall[start_72h : current_index + 1]
                if s is not None
            )

            # Get min/max temp last 24h
            temps_24h = [
                t for t in hourly_temps[start_24h : current_index + 1] if t is not None
            ]
            min_temp_24h = min(temps_24h) if temps_24h else 0.0
            max_temp_24h = max(temps_24h) if temps_24h else 0.0

            # Current temperature
            current_temp = current.get("temperature_2m", hourly_temps[current_index])

            # Currently warming?
            currently_warming = (
                current_temp >= 1.0 if current_temp is not None else False
            )

            # Hours since last snowfall
            hours_since_snowfall = None
            for i in range(current_index, -1, -1):
                if hourly_snowfall[i] is not None and hourly_snowfall[i] > 0:
                    hours_since_snowfall = float(current_index - i)
                    break

            # Current snow depth
            snow_depth = 0.0
            for depth in reversed(hourly_snow_depth):
                if depth is not None:
                    snow_depth = depth * 100  # m to cm
                    break

            # Log findings
            if hours_ago is not None:
                if hours_ago > MAX_HISTORICAL_DAYS * 24:
                    hours_display = f"{MAX_HISTORICAL_DAYS}+ days"
                else:
                    days = hours_ago // 24
                    remaining_hours = hours_ago % 24
                    if days > 0:
                        hours_display = f"{days}d {remaining_hours}h"
                    else:
                        hours_display = f"{hours_ago}h"
                logger.info(
                    f"  {elevation_point.level.value}: Last freeze-thaw: {hours_display} ago, "
                    f"Snow since: {snowfall_after_freeze:.1f}cm, "
                    f"24h: {snowfall_24h:.1f}cm, Temp: {current_temp:.1f}°C"
                )
            else:
                logger.info(
                    f"  {elevation_point.level.value}: No freeze-thaw in {MAX_HISTORICAL_DAYS} days! "
                    f"Total snow: {snowfall_72h:.1f}cm (72h), Temp: {current_temp:.1f}°C"
                )
                # If no freeze-thaw found, set to max days
                hours_ago = MAX_HISTORICAL_DAYS * 24
                snowfall_after_freeze = sum(s for s in hourly_snowfall if s is not None)

            # Create weather condition
            weather_condition = WeatherCondition(
                resort_id=resort.resort_id,
                elevation_level=elevation_point.level.value,
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=current_temp or 0.0,
                min_temp_celsius=min_temp_24h,
                max_temp_celsius=max_temp_24h,
                snowfall_24h_cm=snowfall_24h,
                snowfall_48h_cm=snowfall_48h,
                snowfall_72h_cm=snowfall_72h,
                hours_above_ice_threshold=0.0,  # Recalculated by service
                max_consecutive_warm_hours=0.0,
                snowfall_after_freeze_cm=snowfall_after_freeze,
                hours_since_last_snowfall=hours_since_snowfall,
                last_freeze_thaw_hours_ago=float(hours_ago) if hours_ago else None,
                currently_warming=currently_warming,
                humidity_percent=None,
                wind_speed_kmh=None,
                weather_description=None,
                data_source="open-meteo.com (backfill)",
                source_confidence=ConfidenceLevel.MEDIUM,
                raw_data={
                    "backfill_days": MAX_HISTORICAL_DAYS,
                    "snow_depth_cm": snow_depth,
                },
            )

            # Assess snow quality
            snow_quality, fresh_snow_cm, confidence = (
                snow_quality_service.assess_snow_quality(weather_condition)
            )
            weather_condition.snow_quality = snow_quality
            weather_condition.fresh_snow_cm = fresh_snow_cm
            weather_condition.confidence_level = confidence

            # Set TTL
            weather_condition.ttl = int(
                datetime.now(UTC).timestamp() + 7 * 24 * 60 * 60
            )

            # Save to DynamoDB
            if not dry_run:
                item = weather_condition.model_dump()
                item = prepare_for_dynamodb(item)
                weather_conditions_table.put_item(Item=item)
                logger.info(
                    f"    Saved: Quality={snow_quality.value if hasattr(snow_quality, 'value') else snow_quality}"
                )
            else:
                logger.info(
                    f"    [DRY RUN] Would save: Quality={snow_quality.value if hasattr(snow_quality, 'value') else snow_quality}"
                )

        except Exception as e:
            logger.error(f"  Error processing {elevation_point.level.value}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill historical weather data")
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't write to DynamoDB"
    )
    parser.add_argument("--resort", type=str, help="Process only this resort ID")
    args = parser.parse_args()

    # Get environment
    env = os.environ.get("ENVIRONMENT", "staging")
    resorts_table = os.environ.get("RESORTS_TABLE", f"snow-tracker-resorts-{env}")
    conditions_table = os.environ.get(
        "WEATHER_CONDITIONS_TABLE", f"snow-tracker-weather-conditions-{env}"
    )

    logger.info(f"Environment: {env}")
    logger.info(f"Resorts table: {resorts_table}")
    logger.info(f"Conditions table: {conditions_table}")
    logger.info(f"Fetching {MAX_HISTORICAL_DAYS} days of historical data")

    if args.dry_run:
        logger.info("DRY RUN - no data will be written")

    # Initialize services
    dynamodb = boto3.resource("dynamodb")
    resort_service = ResortService(dynamodb.Table(resorts_table))
    weather_conditions_table = dynamodb.Table(conditions_table)
    snow_quality_service = SnowQualityService()

    # Get resorts
    resorts = resort_service.get_all_resorts()
    logger.info(f"Found {len(resorts)} resorts")

    if args.resort:
        resorts = [r for r in resorts if r.resort_id == args.resort]
        if not resorts:
            logger.error(f"Resort not found: {args.resort}")
            sys.exit(1)

    # Process each resort
    for resort in resorts:
        try:
            process_resort(
                resort, weather_conditions_table, snow_quality_service, args.dry_run
            )
        except Exception as e:
            logger.error(f"Failed to process {resort.resort_id}: {e}")

    logger.info("Backfill complete!")


if __name__ == "__main__":
    main()
