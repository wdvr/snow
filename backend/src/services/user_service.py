"""User management service."""

from datetime import UTC, datetime, timezone
from typing import Optional

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from models.user import User, UserPreferences
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb


class UserService:
    """Service for managing user data and preferences."""

    def __init__(self, table):
        """Initialize the service with a DynamoDB table."""
        self.table = table

    def get_user_preferences(self, user_id: str) -> UserPreferences | None:
        """Get user preferences by user ID."""
        try:
            response = self.table.get_item(Key={"user_id": user_id})

            item = response.get("Item")
            if not item:
                return None

            # Convert DynamoDB Decimal types to Python native types
            parsed_item = parse_from_dynamodb(item)
            return UserPreferences(**parsed_item)

        except ClientError as e:
            raise Exception(
                f"Failed to retrieve user preferences for {user_id}: {str(e)}"
            )
        except Exception as e:
            raise Exception(f"Error processing user preferences: {str(e)}")

    def save_user_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """Save or update user preferences."""
        try:
            # Convert preferences to DynamoDB item format
            item = preferences.model_dump()

            # Ensure timestamps are set
            if not item.get("created_at"):
                item["created_at"] = datetime.now(UTC).isoformat()

            item["updated_at"] = datetime.now(UTC).isoformat()

            # Convert Python types to DynamoDB Decimal types
            item = prepare_for_dynamodb(item)

            self.table.put_item(Item=item)

            # Parse back for return value
            return UserPreferences(**parse_from_dynamodb(item))

        except ClientError as e:
            raise Exception(f"Failed to save user preferences: {str(e)}")
        except Exception as e:
            raise Exception(f"Error saving user preferences: {str(e)}")

    def create_user(self, user: User) -> User:
        """Create a new user record."""
        try:
            # Convert user to DynamoDB item format
            item = user.model_dump()

            # Convert Python types to DynamoDB Decimal types
            item = prepare_for_dynamodb(item)

            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(user_id)"
            )

            return user

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception(f"User {user.user_id} already exists")
            else:
                raise Exception(f"Failed to create user: {str(e)}")
        except Exception as e:
            raise Exception(f"Error creating user: {str(e)}")

    def update_user(self, user: User) -> User:
        """Update an existing user record."""
        try:
            # Convert user to DynamoDB item format
            item = user.model_dump()

            # Convert Python types to DynamoDB Decimal types
            item = prepare_for_dynamodb(item)

            self.table.put_item(
                Item=item, ConditionExpression="attribute_exists(user_id)"
            )

            return user

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception(f"User {user.user_id} does not exist")
            else:
                raise Exception(f"Failed to update user: {str(e)}")
        except Exception as e:
            raise Exception(f"Error updating user: {str(e)}")

    def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        try:
            response = self.table.get_item(Key={"user_id": user_id})

            item = response.get("Item")
            if not item:
                return None

            # Convert DynamoDB Decimal types to Python native types
            parsed_item = parse_from_dynamodb(item)
            return User(**parsed_item)

        except ClientError as e:
            raise Exception(f"Failed to retrieve user {user_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing user data: {str(e)}")

    def delete_user_data(
        self,
        user_id: str,
        device_tokens_table=None,
        trips_table=None,
        chat_table=None,
        notifications_table=None,
        condition_reports_table=None,
        feedback_table=None,
    ) -> dict:
        """Delete all user data across all tables (account deletion).

        Returns dict with counts of deleted items per table.
        """
        import logging

        logger = logging.getLogger(__name__)
        results = {}

        # 1. Delete user preferences (primary table)
        try:
            self.table.delete_item(Key={"user_id": user_id})
            results["user_preferences"] = 1
        except ClientError as e:
            logger.error("Failed to delete user preferences for %s: %s", user_id, e)
            results["user_preferences"] = 0

        # 2. Delete device tokens (hash: user_id, sort: device_id)
        if device_tokens_table:
            try:
                response = device_tokens_table.query(
                    KeyConditionExpression=Key("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                for item in items:
                    device_tokens_table.delete_item(
                        Key={"user_id": user_id, "device_id": item["device_id"]}
                    )
                results["device_tokens"] = len(items)
            except ClientError as e:
                logger.error("Failed to delete device tokens for %s: %s", user_id, e)
                results["device_tokens"] = 0

        # 3. Delete trips (hash: user_id, sort: trip_id)
        if trips_table:
            try:
                response = trips_table.query(
                    KeyConditionExpression=Key("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                for item in items:
                    trips_table.delete_item(
                        Key={"user_id": user_id, "trip_id": item["trip_id"]}
                    )
                results["trips"] = len(items)
            except ClientError as e:
                logger.error("Failed to delete trips for %s: %s", user_id, e)
                results["trips"] = 0

        # 4. Delete chat conversations (hash: user_id, sort: conversation_id)
        if chat_table:
            try:
                response = chat_table.query(
                    KeyConditionExpression=Key("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                for item in items:
                    chat_table.delete_item(
                        Key={
                            "user_id": user_id,
                            "conversation_id": item["conversation_id"],
                        }
                    )
                results["chat"] = len(items)
            except ClientError as e:
                logger.error("Failed to delete chat data for %s: %s", user_id, e)
                results["chat"] = 0

        # 5. Delete notifications (hash: user_id, sort: notification_id)
        if notifications_table:
            try:
                response = notifications_table.query(
                    KeyConditionExpression=Key("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                for item in items:
                    notifications_table.delete_item(
                        Key={
                            "user_id": user_id,
                            "notification_id": item["notification_id"],
                        }
                    )
                results["notifications"] = len(items)
            except ClientError as e:
                logger.error("Failed to delete notifications for %s: %s", user_id, e)
                results["notifications"] = 0

        # 6. Delete condition reports (GSI: UserIdIndex, key: resort_id + report_id)
        if condition_reports_table:
            try:
                response = condition_reports_table.query(
                    IndexName="UserIdIndex",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                )
                items = response.get("Items", [])
                for item in items:
                    condition_reports_table.delete_item(
                        Key={
                            "resort_id": item["resort_id"],
                            "report_id": item["report_id"],
                        }
                    )
                results["condition_reports"] = len(items)
            except ClientError as e:
                logger.error(
                    "Failed to delete condition reports for %s: %s", user_id, e
                )
                results["condition_reports"] = 0

        # 7. Delete feedback (scan for user_id, best-effort)
        if feedback_table:
            try:
                response = feedback_table.scan(
                    FilterExpression=Attr("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                for item in items:
                    feedback_table.delete_item(Key={"feedback_id": item["feedback_id"]})
                results["feedback"] = len(items)
            except ClientError as e:
                logger.error("Failed to delete feedback for %s: %s", user_id, e)
                results["feedback"] = 0

        logger.info("Deleted user data for %s: %s", user_id, results)
        return results

    def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        try:
            # TODO: Implement when user table exists
            pass

        except Exception as e:
            raise Exception(f"Error updating last login for {user_id}: {str(e)}")
