"""Lambda handler for processing weather data."""

import json
import logging
import os
from datetime import UTC, datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from models.weather import WeatherCondition
from services.resort_service import ResortService
from services.snow_quality_service import SnowQualityService
from services.weather_service import WeatherService
from utils.dynamodb_utils import prepare_for_dynamodb

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Environment variables
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
WEATHER_CONDITIONS_TABLE = os.environ.get(
    "WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev"
)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")


def weather_processor_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for scheduled weather data processing.

    This function:
    1. Fetches all active resorts from DynamoDB
    2. Retrieves current weather data for each elevation point
    3. Processes data through snow quality algorithm
    4. Stores results in weather conditions table

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
        weather_service = WeatherService(api_key=WEATHER_API_KEY)
        snow_quality_service = SnowQualityService()

        # Statistics tracking
        stats = {
            "resorts_processed": 0,
            "elevation_points_processed": 0,
            "conditions_saved": 0,
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

                # Process each elevation point
                for elevation_point in resort.elevation_points:
                    try:
                        # Fetch current weather data
                        weather_data = weather_service.get_current_weather(
                            latitude=elevation_point.latitude,
                            longitude=elevation_point.longitude,
                            elevation_meters=elevation_point.elevation_meters,
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

                        stats["elevation_points_processed"] += 1
                        stats["conditions_saved"] += 1

                        logger.info(
                            f"Processed {resort.resort_id} {elevation_point.level.value}: "
                            f"Quality={snow_quality.value}, Fresh Snow={fresh_snow_cm}cm, "
                            f"Confidence={confidence.value}"
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
        item = weather_condition.dict()

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
