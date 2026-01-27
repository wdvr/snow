"""Tests for data models."""

import pytest
from pydantic import ValidationError

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.user import User, UserPreferences
from models.weather import (
    ConfidenceLevel,
    SnowQuality,
    SnowQualityAlgorithm,
    WeatherCondition,
)


class TestResortModels:
    """Test cases for Resort-related models."""

    def test_elevation_level_enum(self):
        """Test ElevationLevel enum values and methods."""
        assert ElevationLevel.BASE == "base"
        assert ElevationLevel.MID == "mid"
        assert ElevationLevel.TOP == "top"

        # Test all enum values
        all_levels = list(ElevationLevel)
        assert len(all_levels) == 3
        assert ElevationLevel.BASE in all_levels

    def test_elevation_point_creation(self):
        """Test ElevationPoint model creation and validation."""
        point = ElevationPoint(
            level=ElevationLevel.BASE,
            elevation_meters=1500,
            elevation_feet=4921,
            latitude=49.0,
            longitude=-120.0,
            weather_station_id="test-station",
        )

        assert point.level == ElevationLevel.BASE
        assert point.elevation_meters == 1500
        assert point.elevation_feet == 4921
        assert point.latitude == 49.0
        assert point.longitude == -120.0
        assert point.weather_station_id == "test-station"

    def test_elevation_point_invalid_coordinates(self):
        """Test ElevationPoint validation with invalid coordinates."""
        # Invalid latitude (out of range)
        with pytest.raises(ValidationError):
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=200.0,  # Invalid
                longitude=-120.0,
            )

        # Invalid longitude (out of range)
        with pytest.raises(ValidationError):
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=49.0,
                longitude=-200.0,  # Invalid
            )

    def test_resort_creation(self):
        """Test Resort model creation."""
        elevation_points = [
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=49.0,
                longitude=-120.0,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2000,
                elevation_feet=6561,
                latitude=49.1,
                longitude=-119.9,
            ),
        ]

        resort = Resort(
            resort_id="test-resort",
            name="Test Resort",
            country="CA",
            region="BC",
            elevation_points=elevation_points,
            timezone="America/Vancouver",
            official_website="https://test-resort.com",
            weather_sources=["weatherapi"],
            created_at="2026-01-20T10:00:00Z",
            updated_at="2026-01-20T10:00:00Z",
        )

        assert resort.resort_id == "test-resort"
        assert resort.name == "Test Resort"
        assert len(resort.elevation_points) == 2
        assert resort.country == "CA"

    def test_resort_computed_properties(self):
        """Test Resort computed properties."""
        elevation_points = [
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=49.0,
                longitude=-120.0,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1750,
                elevation_feet=5741,
                latitude=49.05,
                longitude=-119.95,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2000,
                elevation_feet=6561,
                latitude=49.1,
                longitude=-119.9,
            ),
        ]

        resort = Resort(
            resort_id="test-resort",
            name="Test Resort",
            country="CA",
            region="BC",
            elevation_points=elevation_points,
            timezone="America/Vancouver",
        )

        # Test display location
        assert resort.display_location == "BC, Canada"

        # Test elevation range
        assert resort.elevation_range == "4921 - 6561 ft"

        # Test individual elevation points
        assert resort.base_elevation.elevation_meters == 1500
        assert resort.mid_elevation.elevation_meters == 1750
        assert resort.top_elevation.elevation_meters == 2000

        # Test elevation point lookup
        base_point = resort.elevation_point(ElevationLevel.BASE)
        assert base_point is not None
        assert base_point.elevation_meters == 1500

    def test_resort_json_serialization(self):
        """Test Resort JSON serialization and deserialization."""
        elevation_points = [
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=49.0,
                longitude=-120.0,
            )
        ]

        original_resort = Resort(
            resort_id="test-resort",
            name="Test Resort",
            country="CA",
            region="BC",
            elevation_points=elevation_points,
            timezone="America/Vancouver",
        )

        # Serialize to dict
        resort_dict = original_resort.model_dump()
        assert "resort_id" in resort_dict
        assert "elevation_points" in resort_dict

        # Deserialize from dict
        restored_resort = Resort(**resort_dict)
        assert restored_resort.resort_id == original_resort.resort_id
        assert len(restored_resort.elevation_points) == len(
            original_resort.elevation_points
        )


class TestWeatherModels:
    """Test cases for Weather-related models."""

    def test_snow_quality_enum(self):
        """Test SnowQuality enum values and properties."""
        # Test enum values
        assert SnowQuality.EXCELLENT == "excellent"
        assert SnowQuality.GOOD == "good"
        assert SnowQuality.FAIR == "fair"
        assert SnowQuality.POOR == "poor"
        assert SnowQuality.BAD == "bad"
        assert SnowQuality.HORRIBLE == "horrible"
        assert SnowQuality.UNKNOWN == "unknown"

        # Test all values are present (excellent, good, fair, poor, bad, horrible, unknown)
        all_qualities = list(SnowQuality)
        assert len(all_qualities) == 7

    def test_confidence_level_enum(self):
        """Test ConfidenceLevel enum values."""
        assert ConfidenceLevel.VERY_HIGH == "very_high"
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.VERY_LOW == "very_low"

        all_confidence_levels = list(ConfidenceLevel)
        assert len(all_confidence_levels) == 5

    def test_weather_condition_creation(self):
        """Test WeatherCondition model creation."""
        condition = WeatherCondition(
            resort_id="test-resort",
            elevation_level="base",
            timestamp="2026-01-20T10:00:00Z",
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
            fresh_snow_cm=14.5,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
            ttl=1640995200,
        )

        assert condition.resort_id == "test-resort"
        assert condition.current_temp_celsius == -5.0
        assert condition.snow_quality == SnowQuality.EXCELLENT
        assert condition.confidence_level == ConfidenceLevel.HIGH

    def test_weather_condition_computed_properties(self):
        """Test WeatherCondition computed properties."""
        condition = WeatherCondition(
            resort_id="test-resort",
            elevation_level="base",
            timestamp="2026-01-20T10:00:00Z",
            current_temp_celsius=-5.0,
            min_temp_celsius=-8.0,
            max_temp_celsius=-2.0,
            snowfall_24h_cm=15.0,
            snowfall_48h_cm=25.0,
            snowfall_72h_cm=30.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snow_quality=SnowQuality.GOOD,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=14.5,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        # Test elevation level enum conversion
        assert condition.elevation_level_enum == ElevationLevel.BASE

        # Test temperature conversion
        expected_fahrenheit = -5.0 * 9.0 / 5.0 + 32.0
        assert abs(condition.current_temp_fahrenheit - expected_fahrenheit) < 0.1

        # Test formatted temperature
        assert "°C" in condition.formatted_current_temp
        assert "°F" in condition.formatted_current_temp

        # Test formatted snowfall
        assert condition.formatted_snowfall_24h == "15.0cm"
        assert condition.formatted_fresh_snow == "14.5cm fresh"

    def test_weather_condition_validation(self):
        """Test WeatherCondition validation."""
        # Test valid condition
        valid_condition = WeatherCondition(
            resort_id="test",
            elevation_level="base",
            timestamp="2026-01-20T10:00:00Z",
            current_temp_celsius=-5.0,
            min_temp_celsius=-8.0,
            max_temp_celsius=-2.0,
            snowfall_24h_cm=15.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snow_quality=SnowQuality.GOOD,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=14.5,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        assert valid_condition.resort_id == "test"

    def test_snow_quality_algorithm_creation(self):
        """Test SnowQualityAlgorithm model creation."""
        algorithm = SnowQualityAlgorithm(
            ice_formation_temp_celsius=3.0,
            optimal_temp_celsius=-5.0,
            ice_formation_hours=4.0,
            fresh_snow_validity_hours=48.0,
            temperature_weight=0.4,
            time_weight=0.3,
            snowfall_weight=0.3,
        )

        assert algorithm.ice_formation_temp_celsius == 3.0
        assert algorithm.temperature_weight == 0.4
        assert algorithm.source_confidence_multiplier[ConfidenceLevel.VERY_HIGH] == 1.0


class TestUserModels:
    """Test cases for User-related models."""

    def test_user_creation(self):
        """Test User model creation."""
        user = User(
            user_id="apple_user_123",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            created_at="2026-01-20T10:00:00Z",
            last_login="2026-01-20T11:00:00Z",
            is_active=True,
        )

        assert user.user_id == "apple_user_123"
        assert user.email == "test@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.is_active is True

    def test_user_optional_fields(self):
        """Test User model with optional fields."""
        user = User(user_id="apple_user_456", created_at="2026-01-20T10:00:00Z")

        assert user.user_id == "apple_user_456"
        assert user.email is None
        assert user.first_name is None
        assert user.last_name is None
        assert user.last_login is None
        assert user.is_active is True  # Default value

    def test_user_preferences_creation(self):
        """Test UserPreferences model creation."""
        preferences = UserPreferences(
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
            created_at="2026-01-20T10:00:00Z",
            updated_at="2026-01-20T11:00:00Z",
        )

        assert preferences.user_id == "apple_user_123"
        assert len(preferences.favorite_resorts) == 2
        assert "big-white" in preferences.favorite_resorts
        assert preferences.notification_preferences["snow_alerts"] is True
        assert preferences.preferred_units["temperature"] == "celsius"
        assert preferences.quality_threshold == "fair"

    def test_user_preferences_defaults(self):
        """Test UserPreferences with default values."""
        preferences = UserPreferences(
            user_id="test_user",
            created_at="2026-01-20T10:00:00Z",
            updated_at="2026-01-20T10:00:00Z",
        )

        # Test default values
        assert preferences.favorite_resorts == []
        assert preferences.notification_preferences["snow_alerts"] is True
        assert preferences.notification_preferences["condition_updates"] is True
        assert preferences.notification_preferences["weekly_summary"] is False
        assert preferences.preferred_units["temperature"] == "celsius"
        assert preferences.preferred_units["distance"] == "metric"
        assert preferences.preferred_units["snow_depth"] == "cm"
        assert preferences.quality_threshold == "fair"

    def test_user_preferences_json_serialization(self):
        """Test UserPreferences JSON serialization."""
        original_prefs = UserPreferences(
            user_id="test_user",
            favorite_resorts=["resort1", "resort2"],
            created_at="2026-01-20T10:00:00Z",
            updated_at="2026-01-20T10:00:00Z",
        )

        # Serialize to dict
        prefs_dict = original_prefs.model_dump()
        assert "user_id" in prefs_dict
        assert "favorite_resorts" in prefs_dict

        # Deserialize from dict
        restored_prefs = UserPreferences(**prefs_dict)
        assert restored_prefs.user_id == original_prefs.user_id
        assert restored_prefs.favorite_resorts == original_prefs.favorite_resorts

    def test_model_validation_errors(self):
        """Test model validation with invalid data."""
        # Test Resort with missing required fields
        with pytest.raises(ValidationError):
            Resort(
                # Missing resort_id
                name="Test Resort",
                country="CA",
                region="BC",
                elevation_points=[],
                timezone="America/Vancouver",
            )

        # Test WeatherCondition with invalid enum values
        with pytest.raises(ValidationError):
            WeatherCondition(
                resort_id="test",
                elevation_level="base",
                timestamp="2026-01-20T10:00:00Z",
                current_temp_celsius=-5.0,
                min_temp_celsius=-8.0,
                max_temp_celsius=-2.0,
                snowfall_24h_cm=15.0,
                hours_above_ice_threshold=0.0,
                max_consecutive_warm_hours=0.0,
                snow_quality="invalid_quality",  # Invalid enum value
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=14.5,
                data_source="test-api",
                source_confidence=ConfidenceLevel.HIGH,
            )
