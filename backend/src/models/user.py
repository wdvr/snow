"""User data models."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.notification import UserNotificationPreferences


class User(BaseModel):
    """User data model."""

    user_id: str = Field(..., description="Unique user identifier from Apple Sign In")
    email: str | None = Field(None, description="User email address")
    first_name: str | None = Field(None, description="User first name")
    last_name: str | None = Field(None, description="User last name")
    created_at: str = Field(..., description="ISO timestamp when user was created")
    last_login: str | None = Field(None, description="ISO timestamp of last login")
    is_active: bool = Field(default=True, description="Whether user account is active")


class UserPreferences(BaseModel):
    """User preferences data model."""

    user_id: str = Field(..., description="Unique user identifier")
    favorite_resorts: list[str] = Field(
        default_factory=list, description="List of favorite resort IDs"
    )
    notification_preferences: dict = Field(
        default_factory=lambda: {
            "snow_alerts": True,
            "condition_updates": True,
            "weekly_summary": False,
        },
        description="Legacy notification preferences (deprecated, use notification_settings)",
    )
    # New detailed notification settings
    notification_settings: UserNotificationPreferences | None = Field(
        default=None,
        description="Detailed notification settings with per-resort configuration",
    )
    preferred_units: dict = Field(
        default_factory=lambda: {
            "temperature": "celsius",  # celsius or fahrenheit
            "distance": "metric",  # metric or imperial
            "snow_depth": "cm",  # cm or inches
        },
        description="User preferred units",
    )
    quality_threshold: str = Field(
        default="fair",
        description="Minimum snow quality to trigger alerts (excellent, good, fair, poor)",
    )
    created_at: str = Field(
        ..., description="ISO timestamp when preferences were created"
    )
    updated_at: str = Field(
        ..., description="ISO timestamp when preferences were last updated"
    )

    def get_notification_settings(self) -> UserNotificationPreferences:
        """Get notification settings, initializing from legacy if needed."""
        if self.notification_settings is not None:
            return self.notification_settings

        # Convert legacy notification_preferences to new format
        legacy = self.notification_preferences or {}
        return UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=legacy.get("snow_alerts", True),
            event_alerts=legacy.get("condition_updates", True),
            weekly_summary=legacy.get("weekly_summary", False),
        )
