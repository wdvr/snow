"""Notification service for push notifications and device token management."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from models.notification import (
    DeviceToken,
    NotificationPayload,
    NotificationType,
    ResortEvent,
    UserNotificationPreferences,
)
from models.user import UserPreferences

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing push notifications."""

    def __init__(
        self,
        device_tokens_table,
        user_preferences_table,
        resort_events_table,
        weather_conditions_table,
        resorts_table,
        sns_client=None,
        apns_platform_arn: str | None = None,
    ):
        """Initialize notification service.

        Args:
            device_tokens_table: DynamoDB table for device tokens
            user_preferences_table: DynamoDB table for user preferences
            resort_events_table: DynamoDB table for resort events
            weather_conditions_table: DynamoDB table for weather conditions
            resorts_table: DynamoDB table for resorts
            sns_client: Optional SNS client (for testing)
            apns_platform_arn: ARN of the APNs platform application
        """
        self.device_tokens_table = device_tokens_table
        self.user_preferences_table = user_preferences_table
        self.resort_events_table = resort_events_table
        self.weather_conditions_table = weather_conditions_table
        self.resorts_table = resorts_table
        self.sns = sns_client or boto3.client("sns")
        self.apns_platform_arn = apns_platform_arn or os.environ.get(
            "APNS_PLATFORM_APP_ARN"
        )

    # =========================================================================
    # Device Token Management
    # =========================================================================

    def register_device_token(
        self,
        user_id: str,
        device_id: str,
        token: str,
        platform: str = "ios",
        app_version: str | None = None,
    ) -> DeviceToken:
        """Register a device token for push notifications.

        Args:
            user_id: User ID
            device_id: Unique device identifier
            token: APNs device token
            platform: Platform (ios, android)
            app_version: App version

        Returns:
            Created or updated DeviceToken
        """
        device_token = DeviceToken.create(
            user_id=user_id,
            device_id=device_id,
            token=token,
            platform=platform,
            app_version=app_version,
        )

        # Store in DynamoDB
        self.device_tokens_table.put_item(Item=device_token.model_dump())

        logger.info(f"Registered device token for user {user_id}, device {device_id}")
        return device_token

    def unregister_device_token(self, user_id: str, device_id: str) -> bool:
        """Unregister a device token.

        Args:
            user_id: User ID
            device_id: Device identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            self.device_tokens_table.delete_item(
                Key={"user_id": user_id, "device_id": device_id}
            )
            logger.info(f"Unregistered device token for user {user_id}, device {device_id}")
            return True
        except ClientError as e:
            logger.error(f"Error unregistering device token: {e}")
            return False

    def get_user_device_tokens(self, user_id: str) -> list[DeviceToken]:
        """Get all device tokens for a user.

        Args:
            user_id: User ID

        Returns:
            List of device tokens
        """
        response = self.device_tokens_table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
        )

        return [DeviceToken(**item) for item in response.get("Items", [])]

    # =========================================================================
    # Push Notification Sending
    # =========================================================================

    def send_push_notification(
        self, device_token: str, payload: NotificationPayload
    ) -> bool:
        """Send a push notification to a device.

        Args:
            device_token: APNs device token
            payload: Notification payload

        Returns:
            True if sent successfully
        """
        if not self.apns_platform_arn:
            logger.warning("APNs platform ARN not configured, skipping notification")
            return False

        try:
            # Create a platform endpoint for this device token
            endpoint_response = self.sns.create_platform_endpoint(
                PlatformApplicationArn=self.apns_platform_arn,
                Token=device_token,
            )
            endpoint_arn = endpoint_response["EndpointArn"]

            # Send the notification
            apns_payload = payload.to_apns_payload()
            message = json.dumps({"APNS": json.dumps(apns_payload)})

            self.sns.publish(
                TargetArn=endpoint_arn,
                Message=message,
                MessageStructure="json",
            )

            logger.info(f"Sent push notification: {payload.title}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "EndpointDisabled":
                logger.warning(f"Endpoint disabled for token, removing: {device_token[:20]}...")
                # Token is no longer valid, could clean up here
            else:
                logger.error(f"Error sending push notification: {e}")
            return False

    def send_notification_to_user(
        self, user_id: str, payload: NotificationPayload
    ) -> int:
        """Send a notification to all devices of a user.

        Args:
            user_id: User ID
            payload: Notification payload

        Returns:
            Number of devices notified
        """
        device_tokens = self.get_user_device_tokens(user_id)
        sent_count = 0

        for device in device_tokens:
            if self.send_push_notification(device.token, payload):
                sent_count += 1

        return sent_count

    # =========================================================================
    # Resort Events
    # =========================================================================

    def create_resort_event(self, event: ResortEvent) -> ResortEvent:
        """Create a new resort event.

        Args:
            event: Resort event to create

        Returns:
            Created event
        """
        self.resort_events_table.put_item(Item=event.model_dump())
        logger.info(f"Created resort event: {event.title} at {event.resort_id}")
        return event

    def get_upcoming_events(
        self, resort_id: str, days_ahead: int = 7
    ) -> list[ResortEvent]:
        """Get upcoming events for a resort.

        Args:
            resort_id: Resort ID
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming events
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        future_date = (datetime.utcnow() + timedelta(days=days_ahead)).strftime(
            "%Y-%m-%d"
        )

        response = self.resort_events_table.query(
            IndexName="EventDateIndex",
            KeyConditionExpression="resort_id = :rid AND event_date BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":rid": resort_id,
                ":start": today,
                ":end": future_date,
            },
        )

        return [ResortEvent(**item) for item in response.get("Items", [])]

    def get_new_events_since(
        self, resort_id: str, since_timestamp: str
    ) -> list[ResortEvent]:
        """Get events created since a given timestamp.

        Args:
            resort_id: Resort ID
            since_timestamp: ISO timestamp to check from

        Returns:
            List of new events
        """
        response = self.resort_events_table.query(
            KeyConditionExpression="resort_id = :rid",
            FilterExpression="created_at > :since",
            ExpressionAttributeValues={
                ":rid": resort_id,
                ":since": since_timestamp,
            },
        )

        return [ResortEvent(**item) for item in response.get("Items", [])]

    # =========================================================================
    # Notification Processing (for Lambda)
    # =========================================================================

    def get_fresh_snow_cm(self, resort_id: str) -> float:
        """Get the fresh snow in cm for a resort from recent conditions.

        Args:
            resort_id: Resort ID

        Returns:
            Fresh snow in cm (0 if not available)
        """
        try:
            # Get the most recent condition
            response = self.weather_conditions_table.query(
                KeyConditionExpression="resort_id = :rid",
                ExpressionAttributeValues={":rid": resort_id},
                ScanIndexForward=False,  # Most recent first
                Limit=1,
            )

            items = response.get("Items", [])
            if not items:
                return 0.0

            # Get fresh_snow_cm from the condition
            return float(items[0].get("fresh_snow_cm", 0.0))

        except Exception as e:
            logger.error(f"Error getting fresh snow for {resort_id}: {e}")
            return 0.0

    def get_resort_name(self, resort_id: str) -> str:
        """Get resort name from resort ID.

        Args:
            resort_id: Resort ID

        Returns:
            Resort name or resort_id if not found
        """
        try:
            response = self.resorts_table.get_item(Key={"resort_id": resort_id})
            item = response.get("Item")
            if item:
                return item.get("name", resort_id)
            return resort_id
        except Exception as e:
            logger.error(f"Error getting resort name for {resort_id}: {e}")
            return resort_id

    def process_user_notifications(
        self, user_id: str, prefs: UserPreferences
    ) -> list[NotificationPayload]:
        """Process notifications for a single user.

        Checks their favorite resorts for:
        1. Fresh snow above threshold
        2. New resort events

        Args:
            user_id: User ID
            prefs: User preferences

        Returns:
            List of notifications to send
        """
        notifications = []
        notification_settings = prefs.get_notification_settings()

        # Skip if notifications are disabled
        if not notification_settings.notifications_enabled:
            return notifications

        # Process each favorite resort
        for resort_id in prefs.favorite_resorts:
            # Check grace period - max 1 notification per 24h per resort
            if not notification_settings.can_notify_for_resort(resort_id):
                logger.debug(f"Skipping {resort_id} for user {user_id} - grace period")
                continue

            # Get resort-specific settings or use defaults
            resort_settings = notification_settings.resort_settings.get(resort_id)
            snow_threshold = (
                resort_settings.fresh_snow_threshold_cm
                if resort_settings
                else notification_settings.default_snow_threshold_cm
            )
            fresh_snow_enabled = (
                resort_settings.fresh_snow_enabled
                if resort_settings
                else notification_settings.fresh_snow_alerts
            )
            events_enabled = (
                resort_settings.event_notifications_enabled
                if resort_settings
                else notification_settings.event_alerts
            )

            resort_name = self.get_resort_name(resort_id)

            # Check for fresh snow
            if fresh_snow_enabled:
                fresh_snow = self.get_fresh_snow_cm(resort_id)
                if fresh_snow >= snow_threshold:
                    notifications.append(
                        NotificationPayload(
                            notification_type=NotificationType.FRESH_SNOW,
                            title=f"Fresh Snow at {resort_name}!",
                            body=f"{fresh_snow:.0f}cm of fresh snow has fallen. Perfect conditions for skiing!",
                            resort_id=resort_id,
                            resort_name=resort_name,
                            data={"fresh_snow_cm": fresh_snow},
                        )
                    )
                    # Mark as notified for this resort
                    notification_settings.mark_notified(resort_id)

            # Check for new events
            if events_enabled:
                # Get events created in the last hour
                one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                new_events = self.get_new_events_since(resort_id, one_hour_ago)

                for event in new_events:
                    notifications.append(
                        NotificationPayload(
                            notification_type=NotificationType.RESORT_EVENT,
                            title=f"Event at {resort_name}",
                            body=f"{event.title} on {event.event_date}",
                            resort_id=resort_id,
                            resort_name=resort_name,
                            data={
                                "event_id": event.event_id,
                                "event_type": event.event_type,
                                "event_date": event.event_date,
                            },
                        )
                    )
                    # Mark as notified for this resort
                    notification_settings.mark_notified(resort_id)

        # Save updated notification settings (with last_notified times)
        if notifications:
            prefs.notification_settings = notification_settings
            self._save_user_preferences(prefs)

        return notifications

    def _save_user_preferences(self, prefs: UserPreferences) -> None:
        """Save user preferences to DynamoDB."""
        try:
            self.user_preferences_table.put_item(Item=prefs.model_dump())
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")

    def process_all_notifications(self) -> dict:
        """Process notifications for all users.

        This is the main entry point for the hourly Lambda.

        Returns:
            Summary of notifications processed
        """
        summary = {
            "users_processed": 0,
            "notifications_sent": 0,
            "errors": 0,
        }

        try:
            # Scan all user preferences
            response = self.user_preferences_table.scan()
            users = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.user_preferences_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                users.extend(response.get("Items", []))

            logger.info(f"Processing notifications for {len(users)} users")

            for user_data in users:
                try:
                    prefs = UserPreferences(**user_data)
                    user_id = prefs.user_id

                    # Skip users with no favorites
                    if not prefs.favorite_resorts:
                        continue

                    # Get notifications for this user
                    notifications = self.process_user_notifications(user_id, prefs)

                    # Send notifications
                    for notification in notifications:
                        sent = self.send_notification_to_user(user_id, notification)
                        summary["notifications_sent"] += sent

                    summary["users_processed"] += 1

                except Exception as e:
                    logger.error(f"Error processing user {user_data.get('user_id')}: {e}")
                    summary["errors"] += 1

        except Exception as e:
            logger.error(f"Error in process_all_notifications: {e}")
            summary["errors"] += 1

        logger.info(f"Notification processing complete: {summary}")
        return summary
