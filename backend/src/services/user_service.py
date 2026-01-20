"""User management service."""

from typing import Optional
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from ..models.user import User, UserPreferences


class UserService:
    """Service for managing user data and preferences."""

    def __init__(self, table):
        """Initialize the service with a DynamoDB table."""
        self.table = table

    def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences by user ID."""
        try:
            response = self.table.get_item(
                Key={'user_id': user_id}
            )

            item = response.get('Item')
            if not item:
                return None

            return UserPreferences(**item)

        except ClientError as e:
            raise Exception(f"Failed to retrieve user preferences for {user_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing user preferences: {str(e)}")

    def save_user_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """Save or update user preferences."""
        try:
            # Convert preferences to DynamoDB item format
            item = preferences.dict()

            # Ensure timestamps are set
            if not item.get('created_at'):
                item['created_at'] = datetime.now(timezone.utc).isoformat()

            item['updated_at'] = datetime.now(timezone.utc).isoformat()

            self.table.put_item(Item=item)

            return UserPreferences(**item)

        except ClientError as e:
            raise Exception(f"Failed to save user preferences: {str(e)}")
        except Exception as e:
            raise Exception(f"Error saving user preferences: {str(e)}")

    def create_user(self, user: User) -> User:
        """Create a new user record."""
        try:
            # Convert user to DynamoDB item format
            item = user.dict()

            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(user_id)'
            )

            return user

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
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

            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_exists(user_id)'
            )

            return user

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Exception(f"User {user.user_id} does not exist")
            else:
                raise Exception(f"Failed to update user: {str(e)}")
        except Exception as e:
            raise Exception(f"Error updating user: {str(e)}")

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            response = self.table.get_item(
                Key={'user_id': user_id}
            )

            item = response.get('Item')
            if not item:
                return None

            return User(**item)

        except ClientError as e:
            raise Exception(f"Failed to retrieve user {user_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing user data: {str(e)}")

    def delete_user_data(self, user_id: str) -> bool:
        """Delete all user data (GDPR compliance)."""
        try:
            # Delete user preferences
            self.table.delete_item(
                Key={'user_id': user_id}
            )

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