"""User management service."""

from datetime import UTC, datetime, timezone
from typing import Optional

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
            item = preferences.dict()

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
            item = user.dict()

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
            item = user.dict()

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

    def delete_user_data(self, user_id: str) -> bool:
        """Delete all user data (GDPR compliance)."""
        try:
            # Delete user preferences
            self.table.delete_item(Key={"user_id": user_id})

            # TODO: Delete from other tables (user table, etc.)
            # This should be implemented when user table is created

            return True

        except ClientError as e:
            raise Exception(f"Failed to delete user data for {user_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error deleting user data: {str(e)}")

    def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        try:
            # TODO: Implement when user table exists
            pass

        except Exception as e:
            raise Exception(f"Error updating last login for {user_id}: {str(e)}")
