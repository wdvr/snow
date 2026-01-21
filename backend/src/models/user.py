"""User data models."""

from typing import List, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User data model."""

    user_id: str = Field(..., description="Unique user identifier from Apple Sign In")
    email: str | None = Field(None, description="User email address")
    first_name: str | None = Field(None, description="User first name")
    last_name: str | None = Field(None, description="User last name")
    created_at: str = Field(..., description="ISO timestamp when user was created")
    last_login: str | None = Field(None, description="ISO timestamp of last login")
    is_active: bool = Field(default=True, description="Whether user account is active")

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            # Add custom encoders if needed
        }


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
        description="User notification preferences",
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

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            # Add custom encoders if needed
        }
