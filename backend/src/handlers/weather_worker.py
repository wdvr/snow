"""Lambda handler for processing weather data for a subset of resorts.

This worker Lambda is invoked by the orchestrator (weather_processor) to process
a batch of resorts in parallel. Each worker handles one region's resorts.
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from models.weather import WeatherCondition
from services.onthesnow_scraper import OnTheSnowScraper
from services.openmeteo_service import OpenMeteoService
from services.snow_quality_service import SnowQualityService
from services.snow_summary_service import SnowSummaryService
from utils.dynamodb_utils import prepare_for_dynamodb

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
WEATHER_CONDITIONS_TABLE = os.environ.get(
    "WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev"
)
SNOW_SUMMARY_TABLE = os.environ.get(
    "SNOW_SUMMARY_TABLE", "snow-tracker-snow-summary-dev"
)
ENABLE_SCRAPING = os.environ.get("ENABLE_SCRAPING", "true").lower() == "true"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
# Number of elevation points to process concurrently
ELEVATION_CONCURRENCY = int(os.environ.get("ELEVATION_CONCURRENCY", "3"))
# Delay between resorts to avoid overwhelming external APIs (seconds)
INTER_RESORT_DELAY = float(os.environ.get("INTER_RESORT_DELAY", "0.5"))

# TTL for weather conditions: 60 days (extended from 7 days)
WEATHER_CONDITIONS_TTL_DAYS = 60


def publish_worker_metrics(stats: dict[str, Any], region: str) -> None:
    """Publish worker metrics to CloudWatch."""
    try:
        metrics = [
            {
                "MetricName": "WorkerResortsProcessed",
                "Value": stats.get("resorts_processed", 0),
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "Region", "Value": region},
                ],
            },
            {
                "MetricName": "WorkerConditionsSaved",
                "Value": stats.get("conditions_saved", 0),
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "Region", "Value": region},
                ],
            },
            {
                "MetricName": "WorkerErrors",
                "Value": stats.get("errors", 0),
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "Region", "Value": region},
                ],
            },
            {
                "MetricName": "WorkerDuration",
                "Value": stats.get("duration_seconds", 0),
                "Unit": "Seconds",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "Region", "Value": region},
                ],
            },
        ]

        cloudwatch.put_metric_data(
            Namespace="SnowTracker/WeatherWorker", MetricData=metrics
        )
        logger.info(f"Published {len(metrics)} worker metrics for region {region}")

    except Exception as e:
        logger.error(f"Failed to publish worker metrics: {e}")


def save_weather_condition(table, weather_condition: WeatherCondition) -> None:
    """Save weather condition to DynamoDB table."""
    try:
        item = weather_condition.model_dump()
        item = prepare_for_dynamodb(item)
        table.put_item(Item=item)
    except ClientError as e:
        logger.error(f"Error saving weather condition to DynamoDB: {str(e)}")
        raise


def process_elevation_point(
    elevation_point: dict | Any,
    resort_id: str,
    weather_service: OpenMeteoService,
    snow_quality_service: SnowQualityService,
    weather_conditions_table,
    scraper: OnTheSnowScraper | None,
    scraped_data: Any | None,
    snow_summary_service: SnowSummaryService | None = None,
) -> dict[str, Any]:
    """Process a single elevation point and save the weather condition.

    Also updates the snow summary table with accumulated snowfall data.

    Returns a dict with success status and any error info.
    """
    result = {"success": False, "error": None, "level": None}

    try:
        # Handle both dict and object formats
        if isinstance(elevation_point, dict):
            lat = elevation_point.get("latitude")
            lon = elevation_point.get("longitude")
            elev = elevation_point.get("elevation_meters")
            level = elevation_point.get("level", "mid")
        else:
            lat = elevation_point.latitude
            lon = elevation_point.longitude
            elev = elevation_point.elevation_meters
            level = getattr(elevation_point.level, "value", elevation_point.level)

        result["level"] = level

        # Get existing snow summary for this resort/elevation
        last_known_freeze_date = None
        existing_summary = None
        if snow_summary_service:
            existing_summary = snow_summary_service.get_or_create_summary(
                resort_id, level
            )
            last_known_freeze_date = existing_summary.get("last_freeze_date")

        # Fetch current weather data from Open-Meteo
        # Pass the last known freeze date for better accumulation tracking
        weather_data = weather_service.get_current_weather(
            latitude=lat,
            longitude=lon,
            elevation_meters=elev,
            last_known_freeze_date=last_known_freeze_date,
        )

        # Merge with scraped data if available
        if scraped_data and scraper:
            weather_data = scraper.merge_with_weather_data(weather_data, scraped_data)

        # Update snow summary based on weather data
        if snow_summary_service and existing_summary:
            freeze_detected = weather_data.get("freeze_event_detected", False)
            detected_freeze_date = weather_data.get("detected_freeze_date")

            if freeze_detected and detected_freeze_date:
                # New freeze event detected - record it and reset accumulation
                snow_summary_service.record_freeze_event(
                    resort_id=resort_id,
                    elevation_level=level,
                    freeze_date=detected_freeze_date,
                )
                # After recording freeze, snowfall_after_freeze from Open-Meteo is accurate
                snow_summary_service.update_summary(
                    resort_id=resort_id,
                    elevation_level=level,
                    last_freeze_date=detected_freeze_date,
                    snowfall_since_freeze_cm=weather_data.get(
                        "snowfall_after_freeze_cm", 0.0
                    ),
                    total_season_snowfall_cm=(
                        existing_summary.get("total_season_snowfall_cm", 0.0)
                        + weather_data.get("snowfall_24h_cm", 0.0)
                    ),
                    last_updated=datetime.now(UTC).isoformat(),
                    season_start_date=existing_summary.get("season_start_date"),
                )
            else:
                # No new freeze - accumulate snowfall
                existing_accumulation = existing_summary.get(
                    "snowfall_since_freeze_cm", 0.0
                )
                openmeteo_accumulation = weather_data.get(
                    "snowfall_after_freeze_cm", 0.0
                )

                last_freeze_hours = weather_data.get("last_freeze_thaw_hours_ago")
                if last_freeze_hours and last_freeze_hours >= 336:  # 14 days
                    # Freeze is older than Open-Meteo can see
                    new_accumulation = existing_accumulation + weather_data.get(
                        "snowfall_24h_cm", 0.0
                    )
                    if weather_data.get("snowfall_24h_cm", 0.0) > 0:
                        snow_summary_service.update_summary(
                            resort_id=resort_id,
                            elevation_level=level,
                            last_freeze_date=existing_summary.get("last_freeze_date"),
                            snowfall_since_freeze_cm=new_accumulation,
                            total_season_snowfall_cm=(
                                existing_summary.get("total_season_snowfall_cm", 0.0)
                                + weather_data.get("snowfall_24h_cm", 0.0)
                            ),
                            last_updated=datetime.now(UTC).isoformat(),
                            season_start_date=existing_summary.get("season_start_date"),
                        )
                else:
                    # Open-Meteo can see the freeze - use its accumulation value
                    snow_summary_service.update_summary(
                        resort_id=resort_id,
                        elevation_level=level,
                        last_freeze_date=existing_summary.get("last_freeze_date"),
                        snowfall_since_freeze_cm=openmeteo_accumulation,
                        total_season_snowfall_cm=(
                            existing_summary.get("total_season_snowfall_cm", 0.0)
                            + max(0, openmeteo_accumulation - existing_accumulation)
                        ),
                        last_updated=datetime.now(UTC).isoformat(),
                        season_start_date=existing_summary.get("season_start_date"),
                    )

                # Use the higher accumulation value for weather condition
                weather_data["snowfall_after_freeze_cm"] = max(
                    openmeteo_accumulation, existing_accumulation
                )

        # Create weather condition object
        weather_condition = WeatherCondition(
            resort_id=resort_id,
            elevation_level=level,
            timestamp=datetime.now(UTC).isoformat(),
            **weather_data,
        )

        # Assess snow quality
        snow_quality, fresh_snow_cm, confidence = (
            snow_quality_service.assess_snow_quality(weather_condition)
        )

        # Update condition with assessment results
        weather_condition.snow_quality = snow_quality
        weather_condition.fresh_snow_cm = fresh_snow_cm
        weather_condition.confidence_level = confidence

        # Set TTL (expire after 60 days - extended from 7 days)
        weather_condition.ttl = int(
            datetime.now(UTC).timestamp() + WEATHER_CONDITIONS_TTL_DAYS * 24 * 60 * 60
        )

        # Save to DynamoDB
        save_weather_condition(weather_conditions_table, weather_condition)

        result["success"] = True
        logger.debug(
            f"Processed {resort_id} {level}: Quality="
            f"{snow_quality.value if hasattr(snow_quality, 'value') else snow_quality}"
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error(
            f"Error processing elevation {result['level']} for {resort_id}: {e}"
        )

    return result


def weather_worker_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Worker Lambda handler for processing weather data for a batch of resorts.

    This function is invoked by the orchestrator with a list of resort IDs to process.

    Args:
        event: Contains:
            - resort_ids: List of resort IDs to process
            - region: The region name (for metrics)
        context: Lambda context object

    Returns:
        Dict with processing results and statistics
    """
    resort_ids = event.get("resort_ids", [])
    region = event.get("region", "unknown")

    if not resort_ids:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No resort_ids provided"}),
        }

    logger.info(f"Processing {len(resort_ids)} resorts for region {region}")

    # Statistics tracking
    stats = {
        "resorts_processed": 0,
        "elevation_points_processed": 0,
        "conditions_saved": 0,
        "scraper_hits": 0,
        "scraper_misses": 0,
        "errors": 0,
        "start_time": datetime.now(UTC).isoformat(),
        "region": region,
    }

    try:
        # Initialize services
        resorts_table = dynamodb.Table(RESORTS_TABLE)
        weather_conditions_table = dynamodb.Table(WEATHER_CONDITIONS_TABLE)
        snow_summary_table = dynamodb.Table(SNOW_SUMMARY_TABLE)
        weather_service = OpenMeteoService()
        snow_quality_service = SnowQualityService()
        snow_summary_service = SnowSummaryService(snow_summary_table)

        # Initialize scraper if enabled
        scraper = OnTheSnowScraper() if ENABLE_SCRAPING else None
        logger.info(
            f"Snow summary service initialized with table: {SNOW_SUMMARY_TABLE}"
        )

        # Fetch resorts by ID using batch get
        resort_keys = [{"resort_id": rid} for rid in resort_ids]

        # DynamoDB batch_get_item has a limit of 100 items
        resorts = []
        for i in range(0, len(resort_keys), 100):
            batch_keys = resort_keys[i : i + 100]
            response = dynamodb.meta.client.batch_get_item(
                RequestItems={RESORTS_TABLE: {"Keys": batch_keys}}
            )
            resorts.extend(response.get("Responses", {}).get(RESORTS_TABLE, []))

        logger.info(f"Fetched {len(resorts)} resorts from DynamoDB")

        # Process each resort
        for resort_data in resorts:
            resort_id = resort_data.get("resort_id")
            resort_name = resort_data.get("name", resort_id)

            try:
                logger.info(f"Processing resort: {resort_name} ({resort_id})")

                # Get elevation points from resort data
                elevation_points = resort_data.get("elevation_points", [])
                if not elevation_points:
                    logger.warning(f"No elevation points for {resort_id}")
                    stats["errors"] += 1
                    continue

                # Try to get scraped data for this resort
                scraped_data = None
                if scraper and scraper.is_resort_supported(resort_id):
                    try:
                        scraped_data = scraper.get_snow_report(resort_id)
                        if scraped_data:
                            stats["scraper_hits"] += 1
                            logger.info(
                                f"Got scraped data for {resort_id}: "
                                f"24h={scraped_data.snowfall_24h_cm}cm"
                            )
                        else:
                            stats["scraper_misses"] += 1
                    except Exception as e:
                        logger.warning(f"Scraper failed for {resort_id}: {e}")
                        stats["scraper_misses"] += 1

                # Process elevation points concurrently using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=ELEVATION_CONCURRENCY) as executor:
                    futures = {
                        executor.submit(
                            process_elevation_point,
                            elevation_point,
                            resort_id,
                            weather_service,
                            snow_quality_service,
                            weather_conditions_table,
                            scraper,
                            scraped_data,
                            snow_summary_service,
                        ): elevation_point
                        for elevation_point in elevation_points
                    }

                    for future in as_completed(futures):
                        result = future.result()
                        if result["success"]:
                            stats["elevation_points_processed"] += 1
                            stats["conditions_saved"] += 1
                        else:
                            stats["errors"] += 1

                stats["resorts_processed"] += 1

                # Rate limit: small delay between resorts to avoid overwhelming APIs
                if INTER_RESORT_DELAY > 0:
                    time.sleep(INTER_RESORT_DELAY)

            except Exception as e:
                logger.error(f"Error processing resort {resort_id}: {str(e)}")
                stats["errors"] += 1

        stats["end_time"] = datetime.now(UTC).isoformat()
        stats["duration_seconds"] = (
            datetime.fromisoformat(stats["end_time"].replace("Z", "+00:00"))
            - datetime.fromisoformat(stats["start_time"].replace("Z", "+00:00"))
        ).total_seconds()

        logger.info(
            f"Worker completed for region {region}. "
            f"Processed {stats['resorts_processed']} resorts, "
            f"{stats['conditions_saved']} conditions saved, "
            f"{stats['errors']} errors"
        )

        # Publish metrics
        publish_worker_metrics(stats, region)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Processed {stats['resorts_processed']} resorts",
                    "stats": stats,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Fatal error in weather worker: {str(e)}")
        stats["errors"] += 1

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Weather worker failed",
                    "error": str(e),
                    "stats": stats,
                }
            ),
        }
