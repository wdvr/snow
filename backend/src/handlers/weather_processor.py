"""Lambda handler for processing weather data.

Supports two modes:
1. Sequential mode (default): Processes all resorts in a single Lambda
2. Parallel mode: Orchestrates multiple worker Lambdas by region

Set PARALLEL_PROCESSING=true to enable parallel mode.
"""

import json
import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
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
lambda_client = boto3.client("lambda")

# Environment variables
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
WEATHER_CONDITIONS_TABLE = os.environ.get(
    "WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev"
)
ENABLE_SCRAPING = os.environ.get("ENABLE_SCRAPING", "true").lower() == "true"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PARALLEL_PROCESSING = os.environ.get("PARALLEL_PROCESSING", "false").lower() == "true"
WEATHER_WORKER_LAMBDA = os.environ.get(
    "WEATHER_WORKER_LAMBDA", f"snow-tracker-weather-worker-{ENVIRONMENT}"
)
# Number of elevation points to process concurrently (for sequential mode)
ELEVATION_CONCURRENCY = int(os.environ.get("ELEVATION_CONCURRENCY", "5"))


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
                "MetricName": "ResortsSkipped",
                "Value": stats.get("resorts_skipped", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "GracefulTimeout",
                "Value": 1.0 if stats.get("timeout_graceful", False) else 0.0,
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


def get_remaining_time_ms(context) -> int:
    """Get remaining Lambda execution time in milliseconds."""
    if context and hasattr(context, "get_remaining_time_in_millis"):
        return context.get_remaining_time_in_millis()
    return 600000  # Default 10 minutes if no context


def process_elevation_point(
    elevation_point: Any,
    resort_id: str,
    weather_service: OpenMeteoService,
    snow_quality_service: SnowQualityService,
    weather_conditions_table,
    scraper: OnTheSnowScraper | None,
    scraped_data: Any | None,
) -> dict[str, Any]:
    """Process a single elevation point and save the weather condition.

    Returns a dict with success status, the weather condition, and any error info.
    """
    result = {"success": False, "error": None, "level": None, "weather_condition": None}

    try:
        level = (
            elevation_point.level.value
            if hasattr(elevation_point.level, "value")
            else elevation_point.level
        )
        result["level"] = level

        # Fetch current weather data from Open-Meteo
        weather_data = weather_service.get_current_weather(
            latitude=elevation_point.latitude,
            longitude=elevation_point.longitude,
            elevation_meters=elevation_point.elevation_meters,
        )

        # Merge with scraped data if available
        if scraped_data and scraper:
            weather_data = scraper.merge_with_weather_data(weather_data, scraped_data)

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

        # Set TTL (expire after 7 days)
        weather_condition.ttl = int(datetime.now(UTC).timestamp() + 7 * 24 * 60 * 60)

        # Save to DynamoDB
        save_weather_condition(weather_conditions_table, weather_condition)

        result["success"] = True
        result["weather_condition"] = weather_condition

    except Exception as e:
        result["error"] = str(e)
        logger.error(
            f"Error processing elevation {result['level']} for {resort_id}: {e}"
        )

    return result


# Minimum time buffer before timeout (60 seconds)
MIN_TIME_BUFFER_MS = 60000


def orchestrate_parallel_processing(context) -> dict[str, Any]:
    """
    Orchestrate parallel weather processing by invoking worker Lambdas.

    Groups resorts by region and invokes a separate Lambda for each region.
    This allows processing all resorts in parallel, avoiding timeout issues.

    Returns:
        Dict with orchestration results
    """
    start_time = datetime.now(UTC)
    logger.info("Starting parallel weather processing orchestration")

    # Get all resorts
    resort_service = ResortService(dynamodb.Table(RESORTS_TABLE))
    resorts = resort_service.get_all_resorts()

    if not resorts:
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No resorts to process"}),
        }

    # Group resorts by region
    resorts_by_region: dict[str, list[str]] = defaultdict(list)
    for resort in resorts:
        region = getattr(resort, "region", "unknown")
        resorts_by_region[region].append(resort.resort_id)

    logger.info(f"Grouped {len(resorts)} resorts into {len(resorts_by_region)} regions")

    # Invoke worker Lambda for each region (asynchronously)
    invocations = []
    for region, resort_ids in resorts_by_region.items():
        try:
            payload = {
                "resort_ids": resort_ids,
                "region": region,
            }

            logger.info(
                f"Invoking worker for region {region} with {len(resort_ids)} resorts"
            )

            response = lambda_client.invoke(
                FunctionName=WEATHER_WORKER_LAMBDA,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(payload),
            )

            invocations.append(
                {
                    "region": region,
                    "resort_count": len(resort_ids),
                    "status_code": response.get("StatusCode"),
                    "success": response.get("StatusCode") == 202,
                }
            )

        except Exception as e:
            logger.error(f"Failed to invoke worker for region {region}: {e}")
            invocations.append(
                {
                    "region": region,
                    "resort_count": len(resort_ids),
                    "error": str(e),
                    "success": False,
                }
            )

    # Calculate results
    successful = sum(1 for i in invocations if i.get("success"))
    failed = len(invocations) - successful
    duration = (datetime.now(UTC) - start_time).total_seconds()

    # Publish orchestrator metrics
    try:
        cloudwatch.put_metric_data(
            Namespace="SnowTracker/Orchestrator",
            MetricData=[
                {
                    "MetricName": "WorkersInvoked",
                    "Value": successful,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                {
                    "MetricName": "WorkerInvocationsFailed",
                    "Value": failed,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                {
                    "MetricName": "TotalResortsDispatched",
                    "Value": len(resorts),
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                {
                    "MetricName": "OrchestrationDuration",
                    "Value": duration,
                    "Unit": "Seconds",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
            ],
        )
    except Exception as e:
        logger.error(f"Failed to publish orchestrator metrics: {e}")

    logger.info(
        f"Orchestration complete: {successful}/{len(invocations)} workers invoked, "
        f"{len(resorts)} resorts dispatched in {duration:.2f}s"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Dispatched {len(resorts)} resorts to {successful} workers",
                "mode": "parallel",
                "workers_invoked": successful,
                "workers_failed": failed,
                "total_resorts": len(resorts),
                "regions": list(resorts_by_region.keys()),
                "duration_seconds": duration,
                "invocations": invocations,
            }
        ),
    }


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

    Handles graceful timeout:
    - Checks remaining time before each resort
    - Stops processing if < 60s remaining
    - Next cron invocation will process remaining resorts

    Args:
        event: Lambda event (scheduled CloudWatch event)
        context: Lambda context object

    Returns:
        Dict with processing results and statistics
    """
    try:
        logger.info(f"Starting weather processing at {datetime.now(UTC).isoformat()}")

        # Check if parallel processing is enabled
        if PARALLEL_PROCESSING:
            logger.info("Parallel processing mode enabled - orchestrating workers")
            return orchestrate_parallel_processing(context)

        logger.info(
            "Sequential processing mode (set PARALLEL_PROCESSING=true for parallel)"
        )

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
            "resorts_skipped": 0,
            "elevation_points_processed": 0,
            "conditions_saved": 0,
            "scraper_hits": 0,
            "scraper_misses": 0,
            "errors": 0,
            "start_time": datetime.now(UTC).isoformat(),
            "timeout_graceful": False,
        }

        # Get all active resorts
        resorts = resort_service.get_all_resorts()
        logger.info(f"Found {len(resorts)} resorts to process")

        weather_conditions_table = dynamodb.Table(WEATHER_CONDITIONS_TABLE)

        for resort in resorts:
            # Check remaining time before processing each resort
            remaining_ms = get_remaining_time_ms(context)
            if remaining_ms < MIN_TIME_BUFFER_MS:
                logger.warning(
                    f"Approaching timeout ({remaining_ms}ms remaining), "
                    f"stopping gracefully after {stats['resorts_processed']} resorts. "
                    f"Skipping {len(resorts) - stats['resorts_processed']} resorts."
                )
                stats["timeout_graceful"] = True
                stats["resorts_skipped"] = len(resorts) - stats["resorts_processed"]
                break
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

                # Process elevation points concurrently using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=ELEVATION_CONCURRENCY) as executor:
                    futures = {
                        executor.submit(
                            process_elevation_point,
                            elevation_point,
                            resort.resort_id,
                            weather_service,
                            snow_quality_service,
                            weather_conditions_table,
                            scraper,
                            scraped_data,
                        ): elevation_point
                        for elevation_point in resort.elevation_points
                    }

                    for future in as_completed(futures):
                        result = future.result()
                        if result["success"]:
                            stats["elevation_points_processed"] += 1
                            stats["conditions_saved"] += 1

                            # Publish snow condition metrics for Grafana
                            if result["weather_condition"]:
                                publish_condition_metrics(result["weather_condition"])

                            # Log success
                            weather_condition = result["weather_condition"]
                            if weather_condition:
                                quality_str = (
                                    weather_condition.snow_quality.value
                                    if hasattr(weather_condition.snow_quality, "value")
                                    else weather_condition.snow_quality
                                )
                                confidence_str = (
                                    weather_condition.confidence_level.value
                                    if hasattr(
                                        weather_condition.confidence_level, "value"
                                    )
                                    else weather_condition.confidence_level
                                )
                                logger.info(
                                    f"Processed {resort.resort_id} {result['level']}: "
                                    f"Quality={quality_str}, "
                                    f"Fresh Snow={weather_condition.fresh_snow_cm}cm, "
                                    f"Confidence={confidence_str}"
                                )
                        else:
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

        if stats["timeout_graceful"]:
            logger.info(
                f"Weather processing stopped gracefully due to timeout. "
                f"Processed {stats['resorts_processed']}/{len(resorts)} resorts. "
                f"Remaining {stats['resorts_skipped']} will be processed in next cron run."
            )
        else:
            logger.info(f"Weather processing completed. Stats: {stats}")

        # Publish metrics to CloudWatch for Grafana dashboards
        publish_metrics(stats)

        message = (
            "Weather processing stopped gracefully (timeout)"
            if stats["timeout_graceful"]
            else "Weather processing completed successfully"
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": message, "stats": stats}),
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
