"""Pytest configuration and shared fixtures."""

from datetime import UTC, datetime, timezone
from unittest.mock import Mock

import pytest

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.user import User, UserPreferences
from models.weather import (
    ConfidenceLevel,
    SnowQuality,
    SnowQualityAlgorithm,
    WeatherCondition,
)


@pytest.fixture
def sample_weather_condition():
    """Create a sample weather condition for testing."""
    # Use a recent timestamp for testing
    recent_timestamp = datetime.now(UTC).isoformat()
    return WeatherCondition(
        resort_id="big-white",
        elevation_level="mid",
        timestamp=recent_timestamp,
        current_temp_celsius=-5.0,
        min_temp_celsius=-8.0,
        max_temp_celsius=-2.0,
        snowfall_24h_cm=15.0,
        snowfall_48h_cm=25.0,
        snowfall_72h_cm=30.0,
        hours_above_ice_threshold=0.0,
        max_consecutive_warm_hours=0.0,
        humidity_percent=85.0,
        wind_speed_kmh=10.0,
        weather_description="Light snow",
        snow_quality=SnowQuality.EXCELLENT,
        confidence_level=ConfidenceLevel.HIGH,
        fresh_snow_cm=15.0,
        data_source="test-weather-api",
        source_confidence=ConfidenceLevel.HIGH,
        ttl=int(datetime.now(UTC).timestamp()) + 86400,
    )


@pytest.fixture
def poor_weather_condition():
    """Create a poor weather condition for testing edge cases."""
    return WeatherCondition(
        resort_id="big-white",
        elevation_level="base",
        timestamp="2026-01-19T14:00:00Z",  # 20 hours ago
        current_temp_celsius=4.0,  # Above freezing
        min_temp_celsius=1.0,
        max_temp_celsius=6.0,
        snowfall_24h_cm=2.0,  # Very little snow
        snowfall_48h_cm=5.0,
        snowfall_72h_cm=8.0,
        hours_above_ice_threshold=8.0,  # Lots of warm hours
        max_consecutive_warm_hours=6.0,
        humidity_percent=60.0,
        wind_speed_kmh=25.0,
        weather_description="Rain",
        snow_quality=SnowQuality.BAD,
        confidence_level=ConfidenceLevel.LOW,
        fresh_snow_cm=0.5,
        data_source="basic-weather-api",
        source_confidence=ConfidenceLevel.LOW,
        ttl=int(datetime.now(UTC).timestamp()) + 86400,
    )


@pytest.fixture
def sample_resort():
    """Create a sample resort for testing."""
    return Resort(
        resort_id="big-white",
        name="Big White Ski Resort",
        country="CA",
        region="BC",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1508,
                elevation_feet=4947,
                latitude=49.7167,
                longitude=-118.9333,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1800,
                elevation_feet=5906,
                latitude=49.7200,
                longitude=-118.9300,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2319,
                elevation_feet=7608,
                latitude=49.7233,
                longitude=-118.9267,
            ),
        ],
        timezone="America/Vancouver",
        official_website="https://www.bigwhite.com",
        weather_sources=["weatherapi", "snow-report"],
        created_at="2026-01-20T08:00:00Z",
        updated_at="2026-01-20T08:00:00Z",
    )


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        user_id="apple_user_123",
        email="test@example.com",
        first_name="John",
        last_name="Skier",
        created_at="2026-01-20T08:00:00Z",
        last_login="2026-01-20T10:00:00Z",
        is_active=True,
    )


@pytest.fixture
def sample_user_preferences():
    """Create sample user preferences for testing."""
    return UserPreferences(
        user_id="apple_user_123",
        favorite_resorts=["big-white", "lake-louise"],
        notification_preferences={
            "snow_alerts": True,
            "condition_updates": False,
            "weekly_summary": True,
        },
        preferred_units={
            "temperature": "celsius",
            "distance": "metric",
            "snow_depth": "cm",
        },
        quality_threshold="fair",
        created_at="2026-01-20T08:00:00Z",
        updated_at="2026-01-20T10:00:00Z",
    )


@pytest.fixture
def snow_quality_algorithm():
    """Create a test snow quality algorithm configuration."""
    return SnowQualityAlgorithm(
        ice_formation_temp_celsius=3.0,
        optimal_temp_celsius=-5.0,
        ice_formation_hours=4.0,
        fresh_snow_validity_hours=48.0,
        temperature_weight=0.4,
        time_weight=0.3,
        snowfall_weight=0.3,
    )


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    mock_table = Mock()
    mock_table.put_item.return_value = {}
    mock_table.get_item.return_value = {"Item": {}}
    mock_table.query.return_value = {"Items": []}
    mock_table.scan.return_value = {"Items": []}
    return mock_table
