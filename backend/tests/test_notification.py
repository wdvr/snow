"""Tests for notification models and service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from models.notification import (
    DeviceToken,
    NotificationPayload,
    NotificationType,
    ResortEvent,
    ResortNotificationSettings,
    UserNotificationPreferences,
)
from models.user import UserPreferences


class TestDeviceToken:
    """Tests for DeviceToken model."""

    def test_create_device_token(self):
        """Test creating a device token."""
        token = DeviceToken.create(
            user_id="user123",
            device_id="device456",
            token="apns-token-abc",
            platform="ios",
            app_version="1.0.0",
        )

        assert token.user_id == "user123"
        assert token.device_id == "device456"
        assert token.token == "apns-token-abc"
        assert token.platform == "ios"
        assert token.app_version == "1.0.0"
        assert token.created_at is not None
        assert token.ttl is not None

    def test_ttl_is_90_days_in_future(self):
        """Test that TTL is set 90 days in the future by default."""
        token = DeviceToken.create(
            user_id="user123",
            device_id="device456",
            token="token",
        )

        now = datetime.utcnow().timestamp()
        expected_ttl = now + (90 * 24 * 60 * 60)

        # Allow 10 seconds tolerance
        assert abs(token.ttl - expected_ttl) < 10


class TestUserNotificationPreferences:
    """Tests for UserNotificationPreferences model."""

    def test_default_values(self):
        """Test default notification preferences."""
        prefs = UserNotificationPreferences()

        assert prefs.notifications_enabled is True
        assert prefs.fresh_snow_alerts is True
        assert prefs.event_alerts is True
        assert prefs.weekly_summary is False
        assert prefs.default_snow_threshold_cm == 1.0
        assert prefs.grace_period_hours == 24

    def test_can_notify_for_resort_first_time(self):
        """Test that we can notify for a resort that hasn't been notified before."""
        prefs = UserNotificationPreferences()
        assert prefs.can_notify_for_resort("resort123") is True

    def test_can_notify_respects_grace_period(self):
        """Test that grace period is respected."""
        prefs = UserNotificationPreferences()

        # Mark as notified now
        prefs.mark_notified("resort123")

        # Should not be able to notify again immediately
        assert prefs.can_notify_for_resort("resort123") is False

    def test_can_notify_after_grace_period(self):
        """Test that we can notify after grace period has passed."""
        prefs = UserNotificationPreferences(grace_period_hours=1)

        # Set last_notified to 2 hours ago
        two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        prefs.last_notified["resort123"] = two_hours_ago

        # Should be able to notify now
        assert prefs.can_notify_for_resort("resort123") is True


class TestNotificationPayload:
    """Tests for NotificationPayload model."""

    def test_to_apns_payload(self):
        """Test converting to APNs payload format."""
        payload = NotificationPayload(
            notification_type=NotificationType.FRESH_SNOW,
            title="Fresh Snow at Whistler!",
            body="15cm of fresh snow has fallen.",
            resort_id="whistler-blackcomb",
            resort_name="Whistler Blackcomb",
            data={"fresh_snow_cm": 15.0},
        )

        apns = payload.to_apns_payload()

        assert apns["aps"]["alert"]["title"] == "Fresh Snow at Whistler!"
        assert apns["aps"]["alert"]["body"] == "15cm of fresh snow has fallen."
        assert apns["aps"]["sound"] == "default"
        assert apns["notification_type"] == "fresh_snow"
        assert apns["resort_id"] == "whistler-blackcomb"
        assert apns["fresh_snow_cm"] == 15.0


class TestResortEvent:
    """Tests for ResortEvent model."""

    def test_create_resort_event(self):
        """Test creating a resort event."""
        event = ResortEvent.create(
            resort_id="whistler-blackcomb",
            event_id="event123",
            event_type="free_store",
            title="Free Demo Day",
            event_date="2025-02-01",
            description="Try the latest skis for free!",
        )

        assert event.resort_id == "whistler-blackcomb"
        assert event.event_id == "event123"
        assert event.event_type == "free_store"
        assert event.title == "Free Demo Day"
        assert event.event_date == "2025-02-01"


class TestUserPreferencesIntegration:
    """Tests for UserPreferences integration with notification settings."""

    def test_get_notification_settings_creates_default(self):
        """Test that get_notification_settings creates defaults if not set."""
        prefs = UserPreferences(
            user_id="user123",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        settings = prefs.get_notification_settings()

        assert settings.notifications_enabled is True
        assert settings.fresh_snow_alerts is True

    def test_get_notification_settings_migrates_legacy(self):
        """Test that legacy notification_preferences are migrated."""
        prefs = UserPreferences(
            user_id="user123",
            notification_preferences={
                "snow_alerts": False,
                "condition_updates": True,
                "weekly_summary": True,
            },
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        settings = prefs.get_notification_settings()

        assert settings.fresh_snow_alerts is False  # Migrated from snow_alerts
        assert settings.event_alerts is True  # Migrated from condition_updates
        assert settings.weekly_summary is True
