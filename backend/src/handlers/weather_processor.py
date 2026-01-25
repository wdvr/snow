"""Lambda handler for processing weather data."""

import json
import logging
import os
from datetime import UTC, datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from models.weather import WeatherCondition
from services.onthesnow_scraper import OnTheSnowScraper
from services.openmeteo_service import OpenMeteoService
from services.resort_service import ResortService
from services.snow_quality_service import SnowQualityService
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
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
ENABLE_SCRAPING = os.environ.get("ENABLE_SCRAPING", "true").lower() == "true"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


def publish_metrics(stats: dict[str, Any]) -> None:
    """Publish scraping metrics to CloudWatch for Grafana dashboards."""
    try:
        metrics = [
            {
                "MetricName": "ResortsProcessed",
                "Value": stats.get("resorts_processed", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ElevationPointsProcessed",
                "Value": stats.get("elevation_points_processed", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ConditionsSaved",
                "Value": stats.get("conditions_saved", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ScraperHits",
                "Value": stats.get("scraper_hits", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ScraperMisses",
                "Value": stats.get("scraper_misses", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ProcessingErrors",
                "Value": stats.get("errors", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ProcessingDuration",
                "Value": stats.get("duration_seconds", 0),
                "Unit": "Seconds",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
        ]

        # Calculate success rate
        total_scrapes = stats.get("scraper_hits", 0) + stats.get("scraper_misses", 0)
        if total_scrapes > 0:
            success_rate = (stats.get("scraper_hits", 0) / total_scrapes) * 100
            metrics.append(
                {
                    "MetricName": "ScraperSuccessRate",
                    "Value": success_rate,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                }
            )

        cloudwatch.put_metric_data(Namespace="SnowTracker/Scraping", MetricData=metrics)
        logger.info(f"Published {len(metrics)} metrics to CloudWatch")

    except Exception as e:
        logger.error(f"Failed to publish metrics to CloudWatch: {e}")


def publish_condition_metrics(weather_condition: "WeatherCondition") -> None:
    """Publish snow condition metrics to CloudWatch for monitoring."""
    try:
        # Convert quality to numeric score (0-3)
        quality_scores = {
            "excellent": 3,
            "good": 2,
            "fair": 1,
            "poor": 0,
            "bad": 0,
            "unknown": -1,
        }
        quality_str = (
            weather_condition.snow_quality.value
            if hasattr(weather_condition.snow_quality, "value")
            else weather_condition.snow_quality
        )
        quality_score = quality_scores.get(quality_str.lower(), -1)

        # Get values with fallbacks
        fresh_snow_cm = getattr(weather_condition, "fresh_snow_cm", 0.0) or 0.0
        snowfall_after_freeze = (
            getattr(weather_condition, "snowfall_after_freeze_cm", 0.0) or 0.0
        )
        last_freeze_hours = getattr(
            weather_condition, "last_freeze_thaw_hours_ago", None
        )
        currently_warming = getattr(weather_condition, "currently_warming", False)

        metrics = [
            {
                "MetricName": "SnowQualityScore",
                "Value": quality_score,
                "Unit": "None",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "ResortId", "Value": weather_condition.resort_id},
                    {"Name": "Elevation", "Value": weather_condition.elevation_level},
                ],
            },
            {
                "MetricName": "FreshSnowCm",
                "Value": fresh_snow_cm,
                "Unit": "None",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "ResortId", "Value": weather_condition.resort_id},
                    {"Name": "Elevation", "Value": weather_condition.elevation_level},
                ],
            },
            {
                "MetricName": "SnowAfterFreezeCm",
                "Value": snowfall_after_freeze,
                "Unit": "None",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "ResortId", "Value": weather_condition.resort_id},
                    {"Name": "Elevation", "Value": weather_condition.elevation_level},
                ],
            },
            {
                "MetricName": "CurrentlyWarming",
                "Value": 1.0 if currently_warming else 0.0,
                "Unit": "None",
                "Dimensions": [
                    {"Name": "Environment", "Value": ENVIRONMENT},
                    {"Name": "ResortId", "Value": weather_condition.resort_id},
                ],
            },
        ]

        # Add hours since last freeze event if available
        if last_freeze_hours is not None:
            metrics.append(
                {
                    "MetricName": "HoursSinceLastFreeze",
                    "Value": last_freeze_hours,
                    "Unit": "None",
                    "Dimensions": [
                        {"Name": "Environment", "Value": ENVIRONMENT},
                        {"Name": "ResortId", "Value": weather_condition.resort_id},
                    ],
                }
            )

        cloudwatch.put_metric_data(
            Namespace="SnowTracker/Conditions", MetricData=metrics
        )

    except Exception as e:
        logger.warning(f"Failed to publish condition metrics: {e}")


def weather_processor_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for scheduled weather data processing.

    This function:
    1. Fetches all active resorts from DynamoDB
    2. Retrieves current weather data for each elevation point
    3. Optionally scrapes resort-reported data from OnTheSnow
    4. Merges data sources for higher accuracy
    5. Processes data through snow quality algorithm
    6. Stores results in weather conditions table

    Args:
        event: Lambda event (scheduled CloudWatch event)
        context: Lambda context object

    Returns:
        Dict with processing results and statistics
    """
    try:
        logger.info(f"Starting weather processing at {datetime.now(UTC).isoformat()}")

        # Initialize services
        resort_service = ResortService(dynamodb.Table(RESORTS_TABLE))
        weather_service = OpenMeteoService()
        snow_quality_service = SnowQualityService()

        # Initialize scraper if enabled
        scraper = OnTheSnowScraper() if ENABLE_SCRAPING else None
        if scraper:
            logger.info("OnTheSnow scraping enabled")

        # Statistics tracking
        stats = {
            "resorts_processed": 0,
            "elevation_points_processed": 0,
            "conditions_saved": 0,
            "scraper_hits": 0,
            "scraper_misses": 0,
            "errors": 0,
            "start_time": datetime.now(UTC).isoformat(),
        }

        # Get all active resorts
        resorts = resort_service.get_all_resorts()
        logger.info(f"Found {len(resorts)} resorts to process")

        weather_conditions_table = dynamodb.Table(WEATHER_CONDITIONS_TABLE)

        for resort in resorts:
            try:
                logger.info(f"Processing resort: {resort.name} ({resort.resort_id})")

                # Try to get scraped data for this resort (once per resort, not per elevation)
                scraped_data = None
                if scraper and scraper.is_resort_supported(resort.resort_id):
                    try:
                        scraped_data = scraper.get_snow_report(resort.resort_id)
                        if scraped_data:
                            stats["scraper_hits"] += 1
                            logger.info(
                                f"Got scraped data for {resort.resort_id}: "
                                f"24h={scraped_data.snowfall_24h_cm}cm, "
                                f"48h={scraped_data.snowfall_48h_cm}cm"
                            )
                        else:
                            stats["scraper_misses"] += 1
                    except Exception as e:
                        logger.warning(f"Scraper failed for {resort.resort_id}: {e}")
                        stats["scraper_misses"] += 1

                # Process each elevation point
                for elevation_point in resort.elevation_points:
                    try:
                        # Fetch current weather data from Open-Meteo
                        weather_data = weather_service.get_current_weather(
                            latitude=elevation_point.latitude,
                            longitude=elevation_point.longitude,
                            elevation_meters=elevation_point.elevation_meters,
                        )

                        # Merge with scraped data if available (scraped data is more accurate)
                        if scraped_data:
                            weather_data = scraper.merge_with_weather_data(
                                weather_data, scraped_data
                            )

                        # Create weather condition object
                        weather_condition = WeatherCondition(
                            resort_id=resort.resort_id,
                            elevation_level=elevation_point.level.value,
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

                        # Set TTL (expire after 7 days)
                        weather_condition.ttl = int(
                            datetime.now(UTC).timestamp() + 7 * 24 * 60 * 60
                        )

                        # Save to DynamoDB
                        save_weather_condition(
                            weather_conditions_table, weather_condition
                        )

                        # Publish snow condition metrics for Grafana
                        publish_condition_metrics(weather_condition)

                        stats["elevation_points_processed"] += 1
                        stats["conditions_saved"] += 1

                        # Get string values for logging (enums might already be strings due to use_enum_values)
                        quality_str = (
                            snow_quality.value
                            if hasattr(snow_quality, "value")
                            else snow_quality
                        )
                        confidence_str = (
                            confidence.value
                            if hasattr(confidence, "value")
                            else confidence
                        )
                        level_str = (
                            elevation_point.level.value
                            if hasattr(elevation_point.level, "value")
                            else elevation_point.level
                        )

                        logger.info(
                            f"Processed {resort.resort_id} {level_str}: "
                            f"Quality={quality_str}, Fresh Snow={fresh_snow_cm}cm, "
                            f"Confidence={confidence_str}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing elevation {elevation_point.level.value} "
                            f"for resort {resort.resort_id}: {str(e)}"
                        )
                        stats["errors"] += 1

                stats["resorts_processed"] += 1

            except Exception as e:
                logger.error(f"Error processing resort {resort.resort_id}: {str(e)}")
                stats["errors"] += 1

        stats["end_time"] = datetime.now(UTC).isoformat()
        stats["duration_seconds"] = (
            datetime.fromisoformat(stats["end_time"].replace("Z", "+00:00"))
            - datetime.fromisoformat(stats["start_time"].replace("Z", "+00:00"))
        ).total_seconds()

        logger.info(f"Weather processing completed. Stats: {stats}")

        # Publish metrics to CloudWatch for Grafana dashboards
        publish_metrics(stats)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Weather processing completed successfully", "stats": stats}
            ),
        }

    except Exception as e:
        logger.error(f"Fatal error in weather processing: {str(e)}")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Weather processing failed", "error": str(e)}
            ),
        }


def save_weather_condition(table, weather_condition: WeatherCondition) -> None:
    """Save weather condition to DynamoDB table."""
    try:
        # Convert Pydantic model to DynamoDB item
        # Note: use_enum_values=True in Config already converts enums to strings
        item = weather_condition.model_dump()

        # Convert floats to Decimal for DynamoDB compatibility
        item = prepare_for_dynamodb(item)

        table.put_item(Item=item)

    except ClientError as e:
        logger.error(f"Error saving weather condition to DynamoDB: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving weather condition: {str(e)}")
        raise


def scheduled_weather_update_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Handler specifically for CloudWatch scheduled events.

    This is a wrapper around the main weather processor that handles
    CloudWatch Events trigger format.
    """
    logger.info("Triggered by CloudWatch scheduled event")
    logger.info(f"Event: {json.dumps(event, indent=2)}")

    # CloudWatch events have a different structure
    if (
        event.get("source") == "aws.events"
        and event.get("detail-type") == "Scheduled Event"
    ):
        # This is a scheduled trigger
        return weather_processor_handler(event, context)
    else:
        logger.warning(f"Unexpected event type: {event}")
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"message": "Invalid event type for scheduled weather update"}
            ),
        }
