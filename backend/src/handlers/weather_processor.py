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
from services.snow_summary_service import SnowSummaryService
from utils.dynamodb_utils import prepare_for_dynamodb

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

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
PARALLEL_PROCESSING = os.environ.get("PARALLEL_PROCESSING", "false").lower() == "true"
WEATHER_WORKER_LAMBDA = os.environ.get(
    "WEATHER_WORKER_LAMBDA", f"snow-tracker-weather-worker-{ENVIRONMENT}"
)
# Number of elevation points to process concurrently (for sequential mode)
ELEVATION_CONCURRENCY = int(os.environ.get("ELEVATION_CONCURRENCY", "5"))
# Enable static JSON API generation after weather processing
ENABLE_STATIC_JSON = os.environ.get("ENABLE_STATIC_JSON", "true").lower() == "true"

# TTL for weather conditions: 60 days (extended from 7 days)
WEATHER_CONDITIONS_TTL_DAYS = 60


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
    snow_summary_service: SnowSummaryService | None = None,
) -> dict[str, Any]:
    """Process a single elevation point and save the weather condition.

    Also updates the snow summary table with accumulated snowfall data.

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
            latitude=elevation_point.latitude,
            longitude=elevation_point.longitude,
            elevation_meters=elevation_point.elevation_meters,
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
                # Update the summary with the new accumulation
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
                # Use the Open-Meteo snowfall_after_freeze if no freeze in 14 days
                # Otherwise add new snowfall to existing summary
                existing_accumulation = existing_summary.get(
                    "snowfall_since_freeze_cm", 0.0
                )
                openmeteo_accumulation = weather_data.get(
                    "snowfall_after_freeze_cm", 0.0
                )

                # If Open-Meteo can see the full history since freeze, use its value
                # Otherwise, add new snowfall to our tracked accumulation
                last_freeze_hours = weather_data.get("last_freeze_thaw_hours_ago")
                if last_freeze_hours and last_freeze_hours >= 336:  # 14 days
                    # Freeze is older than Open-Meteo can see
                    # Add Open-Meteo's 14-day accumulation to our existing total
                    new_accumulation = existing_accumulation + weather_data.get(
                        "snowfall_24h_cm", 0.0
                    )
                    # Only update if we have new snowfall
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
        snow_summary_service = SnowSummaryService(dynamodb.Table(SNOW_SUMMARY_TABLE))

        # Initialize scraper if enabled
        scraper = OnTheSnowScraper() if ENABLE_SCRAPING else None
        if scraper:
            logger.info("OnTheSnow scraping enabled")

        logger.info(
            f"Snow summary service initialized with table: {SNOW_SUMMARY_TABLE}"
        )

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
                            snow_summary_service,
                        ): elevation_point
                        for elevation_point in resort.elevation_points
                    }

                    for future in as_completed(futures):
                        result = future.result()
                        if result["success"]:
                            stats["elevation_points_processed"] += 1
                            stats["conditions_saved"] += 1

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

            # Generate static JSON API files after successful processing
            if ENABLE_STATIC_JSON:
                try:
                    logger.info("Generating static JSON API files...")
                    from services.static_json_generator import generate_static_json_api

                    json_result = generate_static_json_api()
                    stats["static_json"] = json_result
                    logger.info(
                        f"Static JSON generation complete: {json_result.get('files', [])}"
                    )
                except Exception as json_error:
                    logger.error(f"Failed to generate static JSON: {json_error}")
                    stats["static_json_error"] = str(json_error)

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
