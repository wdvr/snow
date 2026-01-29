"""Trip planning data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TripStatus(str, Enum):
    """Trip status enum."""

    PLANNED = "planned"  # Future trip
    ACTIVE = "active"  # Currently on the trip
    COMPLETED = "completed"  # Trip finished
    CANCELLED = "cancelled"  # Trip was cancelled


class TripAlertType(str, Enum):
    """Types of trip alerts."""

    POWDER_ALERT = "powder_alert"  # Fresh snow expected
    WARM_SPELL = "warm_spell"  # Warming temperatures warning
    CONDITIONS_IMPROVED = "conditions_improved"  # Conditions got better
    CONDITIONS_DEGRADED = "conditions_degraded"  # Conditions got worse
    TRIP_REMINDER = "trip_reminder"  # Upcoming trip reminder


class TripConditionSnapshot(BaseModel):
    """Snapshot of conditions at trip creation or update."""

    timestamp: str = Field(..., description="When this snapshot was taken")
    snow_quality: str = Field(..., description="Overall snow quality at snapshot time")
    fresh_snow_cm: float = Field(default=0.0, description="Fresh snow at snapshot")
    predicted_snow_cm: float = Field(default=0.0, description="Predicted snow for trip dates")
    temperature_celsius: float | None = Field(None, description="Temperature at snapshot")


class TripAlert(BaseModel):
    """An alert/notification for a trip."""

    alert_id: str = Field(..., description="Unique alert identifier")
    alert_type: TripAlertType = Field(..., description="Type of alert")
    message: str = Field(..., description="Human-readable alert message")
    created_at: str = Field(..., description="When the alert was created")
    is_read: bool = Field(default=False, description="Whether user has seen this alert")
    data: dict[str, Any] = Field(default_factory=dict, description="Additional alert data")

    model_config = ConfigDict(use_enum_values=True)


class Trip(BaseModel):
    """A planned ski trip."""

    trip_id: str = Field(..., description="Unique trip identifier")
    user_id: str = Field(..., description="User who created the trip")
    resort_id: str = Field(..., description="Resort for this trip")
    resort_name: str = Field(..., description="Resort name (denormalized for display)")

    # Trip dates
    start_date: str = Field(..., description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Trip end date (YYYY-MM-DD)")

    # Status
    status: TripStatus = Field(default=TripStatus.PLANNED, description="Current trip status")

    # Notes
    notes: str | None = Field(None, description="User notes for the trip")
    party_size: int = Field(default=1, ge=1, le=50, description="Number of people on trip")

    # Condition tracking
    conditions_at_creation: TripConditionSnapshot | None = Field(
        None, description="Conditions when trip was planned"
    )
    latest_conditions: TripConditionSnapshot | None = Field(
        None, description="Most recent condition check"
    )

    # Alerts
    alerts: list[TripAlert] = Field(default_factory=list, description="Trip alerts")
    alert_preferences: dict[str, bool] = Field(
        default_factory=lambda: {
            "powder_alerts": True,
            "warm_spell_warnings": True,
            "condition_updates": True,
            "trip_reminders": True,
        },
        description="Which alerts to send for this trip",
    )

    # Timestamps
    created_at: str = Field(..., description="When trip was created")
    updated_at: str = Field(..., description="When trip was last updated")

    # TTL for completed/cancelled trips (auto-delete after 1 year)
    ttl: int | None = Field(None, description="Unix timestamp for record expiration")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date format is YYYY-MM-DD."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

    @property
    def days_until_trip(self) -> int | None:
        """Calculate days until trip starts."""
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            delta = (start - today).days
            return delta if delta >= 0 else None
        except (ValueError, TypeError):
            return None

    @property
    def trip_duration_days(self) -> int:
        """Calculate trip duration in days."""
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            return (end - start).days + 1  # Inclusive
        except (ValueError, TypeError):
            return 1

    @property
    def is_upcoming(self) -> bool:
        """Check if trip is in the future."""
        days = self.days_until_trip
        return days is not None and days >= 0

    @property
    def is_past(self) -> bool:
        """Check if trip is in the past."""
        try:
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return end < today
        except (ValueError, TypeError):
            return False

    @property
    def unread_alert_count(self) -> int:
        """Count unread alerts."""
        return sum(1 for alert in self.alerts if not alert.is_read)


class TripCreate(BaseModel):
    """Request model for creating a trip."""

    resort_id: str = Field(..., description="Resort ID for the trip")
    start_date: str = Field(..., description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Trip end date (YYYY-MM-DD)")
    notes: str | None = Field(None, max_length=500, description="Optional notes")
    party_size: int = Field(default=1, ge=1, le=50, description="Number of people")
    alert_preferences: dict[str, bool] | None = Field(
        None, description="Optional alert preferences"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date format is YYYY-MM-DD."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

    @field_validator("end_date")
    @classmethod
    def validate_end_after_start(cls, v: str, info) -> str:
        """Validate end date is after or equal to start date."""
        start_date = info.data.get("start_date")
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(v, "%Y-%m-%d")
                if end < start:
                    raise ValueError("End date must be on or after start date")
            except ValueError as e:
                if "End date" in str(e):
                    raise
        return v


class TripUpdate(BaseModel):
    """Request model for updating a trip."""

    start_date: str | None = Field(None, description="New start date")
    end_date: str | None = Field(None, description="New end date")
    notes: str | None = Field(None, max_length=500, description="Updated notes")
    party_size: int | None = Field(None, ge=1, le=50, description="Updated party size")
    status: TripStatus | None = Field(None, description="New status")
    alert_preferences: dict[str, bool] | None = Field(None, description="Updated alert preferences")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        """Validate date format is YYYY-MM-DD."""
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

    model_config = ConfigDict(use_enum_values=True)
