"""Service for storing and querying notification history."""

import logging
from datetime import UTC, datetime

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from models.notification import NotificationPayload, NotificationRecord
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb

logger = logging.getLogger(__name__)


class NotificationHistoryService:
    """Service for managing in-app notification history."""

    def __init__(self, table):
        """Initialize with DynamoDB notifications table."""
        self.table = table

    def store_notification(
        self, user_id: str, payload: NotificationPayload
    ) -> NotificationRecord:
        """Store a notification record after successful push delivery.

        Args:
            user_id: User who received the notification
            payload: The notification payload that was sent

        Returns:
            The created NotificationRecord
        """
        record = NotificationRecord.create(user_id=user_id, payload=payload)

        try:
            item = record.model_dump()
            item["notification_type"] = record.notification_type.value
            item = prepare_for_dynamodb(item)
            self.table.put_item(Item=item)
            return record
        except ClientError as e:
            logger.error("Failed to store notification for user %s: %s", user_id, e)
            raise

    def get_notifications(
        self, user_id: str, limit: int = 30, cursor: str | None = None
    ) -> dict:
        """Get paginated notification history for a user, newest first.

        Args:
            user_id: User ID
            limit: Max items to return
            cursor: Last notification_id from previous page for pagination

        Returns:
            Dict with 'notifications' list and optional 'cursor' for next page
        """
        try:
            kwargs = {
                "KeyConditionExpression": Key("user_id").eq(user_id),
                "ScanIndexForward": False,  # Newest first (ULID is time-ordered)
                "Limit": limit,
            }

            if cursor:
                kwargs["ExclusiveStartKey"] = {
                    "user_id": user_id,
                    "notification_id": cursor,
                }

            response = self.table.query(**kwargs)

            notifications = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                notifications.append(NotificationRecord(**parsed))

            result = {"notifications": notifications}

            last_key = response.get("LastEvaluatedKey")
            if last_key:
                result["cursor"] = last_key["notification_id"]

            return result

        except ClientError as e:
            logger.error("Failed to get notifications for user %s: %s", user_id, e)
            raise

    def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """Mark a single notification as read.

        Args:
            user_id: User ID (partition key)
            notification_id: Notification ID (sort key)

        Returns:
            True if updated, False if not found
        """
        try:
            self.table.update_item(
                Key={
                    "user_id": user_id,
                    "notification_id": notification_id,
                },
                UpdateExpression="SET read_at = :ts",
                ConditionExpression="attribute_exists(notification_id)",
                ExpressionAttributeValues={
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            logger.error("Failed to mark notification as read: %s", e)
            raise

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all unread notifications as read for a user.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        try:
            # Query all unread notifications
            response = self.table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                FilterExpression=Attr("read_at").not_exists()
                | Attr("read_at").eq(None),
            )

            now = datetime.now(UTC).isoformat()
            count = 0

            for item in response.get("Items", []):
                try:
                    self.table.update_item(
                        Key={
                            "user_id": item["user_id"],
                            "notification_id": item["notification_id"],
                        },
                        UpdateExpression="SET read_at = :ts",
                        ExpressionAttributeValues={":ts": now},
                    )
                    count += 1
                except ClientError:
                    logger.warning(
                        "Failed to mark notification %s as read",
                        item["notification_id"],
                    )

            return count

        except ClientError as e:
            logger.error(
                "Failed to mark all notifications as read for user %s: %s",
                user_id,
                e,
            )
            raise

    def get_unread_count(self, user_id: str) -> int:
        """Get the count of unread notifications for a user.

        Args:
            user_id: User ID

        Returns:
            Number of unread notifications
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                FilterExpression=Attr("read_at").not_exists()
                | Attr("read_at").eq(None),
                Select="COUNT",
            )
            return response.get("Count", 0)

        except ClientError as e:
            logger.error("Failed to get unread count for user %s: %s", user_id, e)
            raise
