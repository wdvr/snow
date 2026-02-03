"""Data models for Snow Quality Tracker."""

from .notification import (
    DeviceToken,
    NotificationPayload,
    NotificationRecord,
    NotificationType,
    ResortEvent,
    ResortNotificationSettings,
    UserNotificationPreferences,
)
from .resort import ElevationPoint, Resort
from .user import User, UserPreferences
from .weather import ConfidenceLevel, SnowQuality, WeatherCondition

__all__ = [
    "Resort",
    "ElevationPoint",
    "WeatherCondition",
    "SnowQuality",
    "ConfidenceLevel",
    "User",
    "UserPreferences",
    "DeviceToken",
    "NotificationPayload",
    "NotificationRecord",
    "NotificationType",
    "ResortEvent",
    "ResortNotificationSettings",
    "UserNotificationPreferences",
]
