"""Notification-related data models."""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""

    FRESH_SNOW = "fresh_snow"
    RESORT_EVENT = "resort_event"
    POWDER_ALERT = "powder_alert"
    CONDITIONS_IMPROVED = "conditions_improved"
    THAW_ALERT = "thaw_alert"  # Temperature went from minus to plus for 4+ hours
    FREEZE_ALERT = "freeze_alert"  # Temperature went from plus to minus


# Funny messages for thaw alerts (rotate through these)
THAW_MESSAGES = [
    "Skating rink incoming! 🎿 Thaw cycle detected - expect icy patches later.",
    "The mountain's having a hot flash! Thawing has begun, brace for ice.",
    "Sun's out, slush is forming! Thaw alert - afternoon skiing may get crunchy.",
    "Meltdown mode activated! Time to practice your ice dance moves.",
    "Spring vibes detected! Thawing underway - grab those wider skis.",
    "The snow is sweating! Expect slush by noon and ice by sunset.",
    "Warm spell warning! The mountain is melting - corn snow ahead.",
    "Temperature rising! Get ready for the refreeze rollercoaster.",
    "Thaw cycle engaged! Today's powder becomes tomorrow's skating rink.",
    "Heat wave on the slopes! Enjoy the slush before it turns to ice.",
]

# Funny messages for freeze alerts (rotate through these)
FREEZE_MESSAGES = [
    "Skating on ice ahead! 🥶 Freeze cycle started - sharpen those edges!",
    "Brrr! The mountain's gone into deep freeze mode. Ice rink conditions incoming.",
    "Jack Frost is back! Everything's refreezing - careful on those hard-packed runs.",
    "The big chill has arrived! Yesterday's slush is today's bobsled track.",
    "Freezing temps locked in! Time to channel your inner figure skater.",
    "Winter's revenge! The thaw is over, bulletproof ice now forming.",
    "Ice age begins! Better bring those freshly sharpened edges.",
    "Frost alert! The mountain is hardening up - ski with caution.",
    "Sub-zero lockdown! The slush has turned to survival mode skiing.",
    "Deep freeze engaged! Those groomed runs are now Olympic luge tracks.",
]

# Powder day alert messages (rotate through these)
POWDER_MESSAGES = [
    "POWDER DAY! 🎿 {resort_name} got {snow_cm}cm of fresh snow overnight!",
    "It's dumping at {resort_name}! {snow_cm}cm and counting - time to call in sick!",
    "Fresh tracks alert! {resort_name} has {snow_cm}cm of new powder waiting for you!",
    "The snow gods have spoken! {resort_name} is buried under {snow_cm}cm of fresh!",
    "Drop everything! {snow_cm}cm of fresh powder at {resort_name} - this is not a drill!",
    "Waist deep at {resort_name}! {snow_cm}cm of pure bliss just fell from the sky!",
    "POW POW POW! {resort_name} scored {snow_cm}cm of fresh - your office called, they understand.",
    "Winter wonderland at {resort_name}! {snow_cm}cm of champagne powder has arrived!",
    "Alert: {resort_name} is having a powder party! {snow_cm}cm and the trees are fully loaded!",
    "Best day of the season? {resort_name} just got {snow_cm}cm of epic fresh snow!",
]


class DeviceToken(BaseModel):
    """APNs device token for push notifications."""

    user_id: str = Field(..., description="User ID who owns this device")
    device_id: str = Field(..., description="Unique device identifier")
    token: str = Field(..., description="APNs device token")
    platform: str = Field(default="ios", description="Platform (ios, android)")
    app_version: str | None = Field(
        None, description="App version when token was registered"
    )
    created_at: str = Field(..., description="ISO timestamp when token was created")
    updated_at: str = Field(
        ..., description="ISO timestamp when token was last updated"
    )
    ttl: int | None = Field(None, description="TTL for auto-expiry (epoch timestamp)")

    @classmethod
    def create(
        cls,
        user_id: str,
        device_id: str,
        token: str,
        platform: str = "ios",
        app_version: str | None = None,
        ttl_days: int = 90,
    ) -> "DeviceToken":
        """Create a new device token with auto-generated timestamps."""
        now = datetime.now(UTC)
        ttl_timestamp = int((now.timestamp()) + (ttl_days * 24 * 60 * 60))

        return cls(
            user_id=user_id,
            device_id=device_id,
            token=token,
            platform=platform,
            app_version=app_version,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            ttl=ttl_timestamp,
        )


class ResortNotificationSettings(BaseModel):
    """Notification settings for a specific resort."""

    resort_id: str = Field(..., description="Resort ID")
    fresh_snow_enabled: bool = Field(default=True, description="Notify on fresh snow")
    fresh_snow_threshold_cm: float = Field(
        default=1.0, description="Minimum fresh snow in cm to trigger notification"
    )
    event_notifications_enabled: bool = Field(
        default=True, description="Notify on resort events"
    )
    powder_alerts_enabled: bool = Field(
        default=True, description="Enable powder alerts for this resort"
    )
    powder_threshold_cm: float | None = Field(
        None, description="Per-resort powder threshold override"
    )


class UserNotificationPreferences(BaseModel):
    """User's notification preferences."""

    # Global settings
    notifications_enabled: bool = Field(
        default=True, description="Master switch for all notifications"
    )
    fresh_snow_alerts: bool = Field(
        default=True, description="Enable fresh snow notifications globally"
    )
    event_alerts: bool = Field(
        default=True, description="Enable resort event notifications globally"
    )
    thaw_freeze_alerts: bool = Field(
        default=True, description="Enable thaw/freeze cycle notifications"
    )
    powder_alerts: bool = Field(
        default=True, description="Enable powder day notifications"
    )
    weekly_summary: bool = Field(
        default=False, description="Enable weekly snow summary"
    )

    # Default thresholds (can be overridden per resort)
    default_snow_threshold_cm: float = Field(
        default=1.0, description="Default minimum snow in cm to trigger notification"
    )
    powder_snow_threshold_cm: float = Field(
        default=15.0,
        description="Fresh snow threshold for powder day alert (cm)",
    )

    # Per-resort overrides (resort_id -> settings)
    resort_settings: dict[str, ResortNotificationSettings] = Field(
        default_factory=dict,
        description="Per-resort notification settings overrides",
    )

    # Quiet hours
    quiet_hours_enabled: bool = Field(default=False, description="Enable quiet hours")
    quiet_hours_start: str = Field(
        default="22:00", description="Quiet hours start (HH:MM)"
    )
    quiet_hours_end: str = Field(default="07:00", description="Quiet hours end (HH:MM)")
    timezone: str = Field(default="UTC", description="User's timezone for quiet hours")

    # Grace period - track last notification time per resort to limit frequency
    # Key: resort_id, Value: ISO timestamp of last notification
    last_notified: dict[str, str] = Field(
        default_factory=dict,
        description="Last notification time per resort (for grace period)",
    )

    # Grace period in hours (minimum time between notifications for same resort)
    grace_period_hours: int = Field(
        default=24, description="Minimum hours between notifications for same resort"
    )

    # Temperature state tracking per resort for thaw/freeze alerts
    # Key: resort_id, Value: "frozen" (below 0), "thawed" (above 0), or "unknown"
    temperature_state: dict[str, str] = Field(
        default_factory=dict,
        description="Last known temperature state per resort (frozen/thawed)",
    )

    # Timestamp when positive temps started per resort (for 4-hour thaw detection)
    # Key: resort_id, Value: ISO timestamp when temp went positive
    thaw_started_at: dict[str, str] = Field(
        default_factory=dict,
        description="When temperature went positive per resort",
    )

    def can_notify_for_resort(self, resort_id: str) -> bool:
        """Check if we can send a notification for this resort based on grace period."""
        if resort_id not in self.last_notified:
            return True

        last_time_str = self.last_notified[resort_id]
        try:
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            hours_since = (now - last_time).total_seconds() / 3600
            return hours_since >= self.grace_period_hours
        except (ValueError, TypeError):
            return True

    def mark_notified(self, resort_id: str) -> None:
        """Mark that a notification was sent for this resort."""
        self.last_notified[resort_id] = datetime.now(UTC).isoformat()


class ResortEvent(BaseModel):
    """Event at a resort (e.g., free store event, special offer)."""

    resort_id: str = Field(..., description="Resort ID where event takes place")
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(
        ...,
        description="Type of event (e.g., 'free_store', 'special_offer', 'competition')",
    )
    title: str = Field(..., description="Event title")
    description: str | None = Field(None, description="Event description")
    event_date: str = Field(..., description="Date of the event (YYYY-MM-DD)")
    start_time: str | None = Field(None, description="Start time (HH:MM)")
    end_time: str | None = Field(None, description="End time (HH:MM)")
    location: str | None = Field(None, description="Location within resort")
    url: str | None = Field(None, description="URL for more information")
    created_at: str = Field(..., description="ISO timestamp when event was created")
    ttl: int | None = Field(None, description="TTL for auto-expiry (epoch timestamp)")

    @classmethod
    def create(
        cls,
        resort_id: str,
        event_id: str,
        event_type: str,
        title: str,
        event_date: str,
        description: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        location: str | None = None,
        url: str | None = None,
        ttl_days: int = 30,
    ) -> "ResortEvent":
        """Create a new resort event with auto-generated timestamps."""
        now = datetime.now(UTC)
        ttl_timestamp = int((now.timestamp()) + (ttl_days * 24 * 60 * 60))

        return cls(
            resort_id=resort_id,
            event_id=event_id,
            event_type=event_type,
            title=title,
            description=description,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            location=location,
            url=url,
            created_at=now.isoformat(),
            ttl=ttl_timestamp,
        )


class NotificationPayload(BaseModel):
    """Payload for a push notification."""

    notification_type: NotificationType = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body text")
    resort_id: str | None = Field(None, description="Related resort ID")
    resort_name: str | None = Field(None, description="Related resort name")
    data: dict = Field(default_factory=dict, description="Additional data payload")

    def to_apns_payload(self) -> dict:
        """Convert to APNs payload format."""
        return {
            "aps": {
                "alert": {
                    "title": self.title,
                    "body": self.body,
                },
                "sound": "default",
                "badge": 1,
            },
            "notification_type": self.notification_type.value,
            "resort_id": self.resort_id,
            "resort_name": self.resort_name,
            **self.data,
        }


class NotificationRecord(BaseModel):
    """Record of a sent notification (for deduplication and history)."""

    notification_id: str = Field(..., description="Unique notification ID")
    user_id: str = Field(..., description="User who received notification")
    notification_type: NotificationType = Field(..., description="Type of notification")
    resort_id: str | None = Field(None, description="Related resort ID")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    sent_at: str = Field(..., description="ISO timestamp when notification was sent")
    read_at: str | None = Field(
        None, description="ISO timestamp when notification was read"
    )
    data: dict = Field(default_factory=dict, description="Additional data")
