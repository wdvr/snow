"""Notification processor Lambda handler.

This Lambda runs hourly to check for conditions that warrant notifications:
1. Fresh snow at favorite resorts (>= threshold, default 1cm)
2. New resort events

It also handles weekly digest processing when triggered by the weekly schedule.

It respects a 24-hour grace period per resort to avoid notification spam.
"""

import logging
import os
from datetime import UTC, datetime

import boto3

from services.notification_service import NotificationService

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
USER_PREFERENCES_TABLE = os.environ.get(
    "USER_PREFERENCES_TABLE", f"snow-tracker-user-preferences-{ENVIRONMENT}"
)
DEVICE_TOKENS_TABLE = os.environ.get(
    "DEVICE_TOKENS_TABLE", f"snow-tracker-device-tokens-{ENVIRONMENT}"
)
WEATHER_CONDITIONS_TABLE = os.environ.get(
    "WEATHER_CONDITIONS_TABLE", f"snow-tracker-weather-conditions-{ENVIRONMENT}"
)
RESORT_EVENTS_TABLE = os.environ.get(
    "RESORT_EVENTS_TABLE", f"snow-tracker-resort-events-{ENVIRONMENT}"
)
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", f"snow-tracker-resorts-{ENVIRONMENT}")
APNS_PLATFORM_ARN = os.environ.get("APNS_PLATFORM_APP_ARN")

# Lazy-initialized service
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get or create NotificationService (lazy init for Lambda reuse)."""
    global _notification_service
    if _notification_service is None:
        dynamodb = boto3.resource("dynamodb")
        _notification_service = NotificationService(
            device_tokens_table=dynamodb.Table(DEVICE_TOKENS_TABLE),
            user_preferences_table=dynamodb.Table(USER_PREFERENCES_TABLE),
            resort_events_table=dynamodb.Table(RESORT_EVENTS_TABLE),
            weather_conditions_table=dynamodb.Table(WEATHER_CONDITIONS_TABLE),
            resorts_table=dynamodb.Table(RESORTS_TABLE),
            apns_platform_arn=APNS_PLATFORM_ARN,
        )
    return _notification_service


def _is_weekly_digest_event(event: dict) -> bool:
    """Check if the event is a weekly digest trigger.

    The weekly digest CloudWatch rule includes a specific input payload
    to distinguish it from the hourly notification trigger.

    Args:
        event: Lambda event

    Returns:
        True if this is a weekly digest trigger
    """
    return event.get("weekly_digest") is True


def notification_handler(event, context):
    """Lambda handler for notification processing.

    This handler is triggered hourly by CloudWatch Events for regular
    notifications, and weekly for the snow digest.

    If the event contains {"weekly_digest": true}, it runs the weekly
    digest processing instead of the regular hourly notifications.

    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context

    Returns:
        Summary of notifications processed
    """
    logger.info(f"Notification processor started at {datetime.now(UTC).isoformat()}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Event: {event}")

    try:
        service = get_notification_service()

        if _is_weekly_digest_event(event):
            logger.info("Processing weekly digest")
            summary = service.process_weekly_digest()
            message = "Weekly digest processing complete"
        else:
            summary = service.process_all_notifications()
            message = "Notification processing complete"

        logger.info(f"{message}: {summary}")

        return {
            "statusCode": 200,
            "body": {
                "message": message,
                "summary": summary,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Error in notification processor: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": {
                "message": f"Error processing notifications: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }


def weekly_digest_handler(event, context):
    """Lambda handler for weekly digest processing.

    This is an alternative entry point that can be used if a separate
    Lambda is preferred over reusing the notification handler.

    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context

    Returns:
        Summary of weekly digest processing
    """
    logger.info(f"Weekly digest processor started at {datetime.now(UTC).isoformat()}")
    logger.info(f"Environment: {ENVIRONMENT}")

    try:
        service = get_notification_service()
        summary = service.process_weekly_digest()

        logger.info(f"Weekly digest processing complete: {summary}")

        return {
            "statusCode": 200,
            "body": {
                "message": "Weekly digest processing complete",
                "summary": summary,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Error in weekly digest processor: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": {
                "message": f"Error processing weekly digest: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }


# For local testing
if __name__ == "__main__":
    # Test event (simulates CloudWatch scheduled event)
    test_event = {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
    }

    result = notification_handler(test_event, None)
    print(result)
