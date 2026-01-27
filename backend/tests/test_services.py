"""Tests for service layer functionality."""

from datetime import UTC, datetime, timezone
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from models.weather import ConfidenceLevel
from services.resort_service import ResortService
from services.user_service import UserService
from services.weather_service import WeatherService


class TestResortService:
    """Test cases for ResortService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.scan.return_value = {"Items": []}
        table.get_item.return_value = {"Item": None}
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.query.return_value = {"Items": []}
        return table

    @pytest.fixture
    def resort_service(self, mock_table):
        """Create a ResortService instance with mocked table."""
        return ResortService(mock_table)

    @pytest.fixture
    def sample_resort_data(self):
        """Create sample resort data for testing."""
        return {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "CA",
            "region": "BC",
            "elevation_points": [
                {
                    "level": "base",
                    "elevation_meters": 1500,
                    "elevation_feet": 4921,
                    "latitude": 49.0,
                    "longitude": -120.0,
                    "weather_station_id": None,
                }
            ],
            "timezone": "America/Vancouver",
            "official_website": "https://test-resort.com",
            "weather_sources": ["weatherapi"],
            "created_at": "2026-01-20T10:00:00Z",
            "updated_at": "2026-01-20T10:00:00Z",
        }

    def test_get_all_resorts_success(
        self, resort_service, mock_table, sample_resort_data
    ):
        """Test successful retrieval of all resorts."""
        mock_table.scan.return_value = {"Items": [sample_resort_data]}

        resorts = resort_service.get_all_resorts()

        assert len(resorts) == 1
        assert resorts[0].resort_id == "test-resort"
        assert resorts[0].name == "Test Resort"
        mock_table.scan.assert_called_once()

    def test_get_all_resorts_empty(self, resort_service, mock_table):
        """Test retrieval when no resorts exist."""
        mock_table.scan.return_value = {"Items": []}

        resorts = resort_service.get_all_resorts()

        assert len(resorts) == 0
        mock_table.scan.assert_called_once()

    def test_get_all_resorts_db_error(self, resort_service, mock_table):
        """Test handling of database errors during resort retrieval."""
        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "scan",
        )

        with pytest.raises(Exception, match="Failed to retrieve resorts from database"):
            resort_service.get_all_resorts()

    def test_get_resort_success(self, resort_service, mock_table, sample_resort_data):
        """Test successful retrieval of a specific resort."""
        mock_table.get_item.return_value = {"Item": sample_resort_data}

        resort = resort_service.get_resort("test-resort")

        assert resort is not None
        assert resort.resort_id == "test-resort"
        assert resort.name == "Test Resort"
        mock_table.get_item.assert_called_once_with(Key={"resort_id": "test-resort"})

    def test_get_resort_not_found(self, resort_service, mock_table):
        """Test retrieval of non-existent resort."""
        mock_table.get_item.return_value = {}

        resort = resort_service.get_resort("non-existent")

        assert resort is None
        mock_table.get_item.assert_called_once()

    def test_create_resort_success(self, resort_service, mock_table, sample_resort):
        """Test successful resort creation."""
        created_resort = resort_service.create_resort(sample_resort)

        assert created_resort == sample_resort
        mock_table.put_item.assert_called_once()

        # Verify the correct condition was used
        call_args = mock_table.put_item.call_args
        assert "ConditionExpression" in call_args[1]
        assert call_args[1]["ConditionExpression"] == "attribute_not_exists(resort_id)"

    def test_create_resort_already_exists(
        self, resort_service, mock_table, sample_resort
    ):
        """Test creation of resort that already exists."""
        mock_table.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Item exists",
                }
            },
            "put_item",
        )

        with pytest.raises(Exception, match="already exists"):
            resort_service.create_resort(sample_resort)

    def test_update_resort_success(self, resort_service, mock_table, sample_resort):
        """Test successful resort update."""
        updated_resort = resort_service.update_resort(sample_resort)

        assert updated_resort == sample_resort
        mock_table.put_item.assert_called_once()

    def test_delete_resort_success(self, resort_service, mock_table):
        """Test successful resort deletion."""
        result = resort_service.delete_resort("test-resort")

        assert result is True
        mock_table.delete_item.assert_called_once_with(
            Key={"resort_id": "test-resort"},
            ConditionExpression="attribute_exists(resort_id)",
        )

    def test_delete_resort_not_found(self, resort_service, mock_table):
        """Test deletion of non-existent resort."""
        mock_table.delete_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Item not found",
                }
            },
            "delete_item",
        )

        with pytest.raises(Exception, match="does not exist"):
            resort_service.delete_resort("non-existent")

    def test_get_resorts_by_country(
        self, resort_service, mock_table, sample_resort_data
    ):
        """Test retrieval of resorts by country."""
        mock_table.query.return_value = {"Items": [sample_resort_data]}

        resorts = resort_service.get_resorts_by_country("CA")

        assert len(resorts) == 1
        assert resorts[0].country == "CA"
        mock_table.query.assert_called_once()

        # Check query parameters
        call_args = mock_table.query.call_args
        assert call_args[1]["IndexName"] == "CountryIndex"
        assert ":country" in str(call_args[1]["ExpressionAttributeValues"])

    def test_search_resorts(self, resort_service, mock_table, sample_resort_data):
        """Test resort search functionality."""
        mock_table.scan.return_value = {"Items": [sample_resort_data]}

        # Test search by name
        resorts = resort_service.search_resorts("Test")
        assert len(resorts) == 1

        # Test search by region
        resorts = resort_service.search_resorts("BC")
        assert len(resorts) == 1

        # Test search by country
        resorts = resort_service.search_resorts("CA")
        assert len(resorts) == 1

        # Test case insensitive search
        resorts = resort_service.search_resorts("test")
        assert len(resorts) == 1

    def test_get_resort_statistics(self, resort_service, mock_table):
        """Test resort statistics generation."""
        # Mock multiple resorts from different countries
        mock_resorts_data = [
            {
                "resort_id": "ca-resort-1",
                "name": "CA Resort 1",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "base",
                        "elevation_meters": 1000,
                        "elevation_feet": 3280,
                        "latitude": 49.0,
                        "longitude": -120.0,
                    },
                    {
                        "level": "top",
                        "elevation_meters": 2000,
                        "elevation_feet": 6562,
                        "latitude": 49.1,
                        "longitude": -119.9,
                    },
                ],
                "timezone": "America/Vancouver",
            },
            {
                "resort_id": "ca-resort-2",
                "name": "CA Resort 2",
                "country": "CA",
                "region": "AB",
                "elevation_points": [
                    {
                        "level": "base",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 51.0,
                        "longitude": -115.0,
                    },
                    {
                        "level": "mid",
                        "elevation_meters": 2000,
                        "elevation_feet": 6562,
                        "latitude": 51.05,
                        "longitude": -114.95,
                    },
                    {
                        "level": "top",
                        "elevation_meters": 2500,
                        "elevation_feet": 8202,
                        "latitude": 51.1,
                        "longitude": -114.9,
                    },
                ],
                "timezone": "America/Edmonton",
            },
            {
                "resort_id": "us-resort-1",
                "name": "US Resort 1",
                "country": "US",
                "region": "CO",
                "elevation_points": [
                    {
                        "level": "base",
                        "elevation_meters": 2500,
                        "elevation_feet": 8202,
                        "latitude": 39.0,
                        "longitude": -105.0,
                    },
                    {
                        "level": "top",
                        "elevation_meters": 3500,
                        "elevation_feet": 11483,
                        "latitude": 39.1,
                        "longitude": -104.9,
                    },
                ],
                "timezone": "America/Denver",
            },
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        stats = resort_service.get_resort_statistics()

        assert stats["total_resorts"] == 3
        assert stats["resorts_by_country"]["CA"] == 2
        assert stats["resorts_by_country"]["US"] == 1
        assert stats["total_elevation_points"] == 7  # 2 + 3 + 2
        assert abs(stats["average_elevation_points_per_resort"] - 7 / 3) < 0.1

    def test_get_nearby_resorts_success(self, resort_service, mock_table):
        """Test finding nearby resorts."""
        # Mock resorts at different distances from Vancouver (49.28, -123.12)
        mock_resorts_data = [
            {
                "resort_id": "whistler",
                "name": "Whistler",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 50.1163,  # ~95km from Vancouver
                        "longitude": -122.9574,
                    },
                ],
                "timezone": "America/Vancouver",
            },
            {
                "resort_id": "big-white",
                "name": "Big White",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1800,
                        "elevation_feet": 5905,
                        "latitude": 49.7167,  # ~350km from Vancouver
                        "longitude": -118.9333,
                    },
                ],
                "timezone": "America/Vancouver",
            },
            {
                "resort_id": "lake-louise",
                "name": "Lake Louise",
                "country": "CA",
                "region": "AB",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 2100,
                        "elevation_feet": 6889,
                        "latitude": 51.4200,  # ~650km from Vancouver
                        "longitude": -116.1650,
                    },
                ],
                "timezone": "America/Edmonton",
            },
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        # Search from Vancouver with 200km radius
        nearby = resort_service.get_nearby_resorts(
            latitude=49.2827, longitude=-123.1207, radius_km=200.0
        )

        # Should only find Whistler (within 200km)
        assert len(nearby) == 1
        assert nearby[0][0].resort_id == "whistler"
        assert 90 < nearby[0][1] < 100  # Distance should be ~95km

    def test_get_nearby_resorts_larger_radius(self, resort_service, mock_table):
        """Test finding nearby resorts with larger radius."""
        mock_resorts_data = [
            {
                "resort_id": "whistler",
                "name": "Whistler",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 50.1163,
                        "longitude": -122.9574,
                    },
                ],
                "timezone": "America/Vancouver",
            },
            {
                "resort_id": "big-white",
                "name": "Big White",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1800,
                        "elevation_feet": 5905,
                        "latitude": 49.7167,
                        "longitude": -118.9333,
                    },
                ],
                "timezone": "America/Vancouver",
            },
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        # Search with 500km radius - should find both
        nearby = resort_service.get_nearby_resorts(
            latitude=49.2827, longitude=-123.1207, radius_km=500.0
        )

        assert len(nearby) == 2
        # Results should be sorted by distance (Whistler first)
        assert nearby[0][0].resort_id == "whistler"
        assert nearby[1][0].resort_id == "big-white"

    def test_get_nearby_resorts_limit(self, resort_service, mock_table):
        """Test that limit parameter works correctly."""
        # Create multiple nearby resorts
        mock_resorts_data = [
            {
                "resort_id": f"resort-{i}",
                "name": f"Resort {i}",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "base",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 49.0 + (i * 0.01),
                        "longitude": -120.0,
                    },
                ],
                "timezone": "America/Vancouver",
            }
            for i in range(10)
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        nearby = resort_service.get_nearby_resorts(
            latitude=49.0, longitude=-120.0, radius_km=100.0, limit=3
        )

        assert len(nearby) == 3

    def test_get_nearby_resorts_empty(self, resort_service, mock_table):
        """Test finding nearby resorts when none are within radius."""
        mock_resorts_data = [
            {
                "resort_id": "far-resort",
                "name": "Far Resort",
                "country": "JP",
                "region": "Hokkaido",
                "elevation_points": [
                    {
                        "level": "base",
                        "elevation_meters": 1000,
                        "elevation_feet": 3280,
                        "latitude": 43.0,  # Very far from Vancouver
                        "longitude": 141.0,
                    },
                ],
                "timezone": "Asia/Tokyo",
            },
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        nearby = resort_service.get_nearby_resorts(
            latitude=49.2827, longitude=-123.1207, radius_km=100.0
        )

        assert len(nearby) == 0

    def test_get_nearby_resorts_sorted_by_distance(self, resort_service, mock_table):
        """Test that results are sorted by distance ascending."""
        mock_resorts_data = [
            {
                "resort_id": "far",
                "name": "Far Resort",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 50.0,  # Further
                        "longitude": -120.0,
                    },
                ],
                "timezone": "America/Vancouver",
            },
            {
                "resort_id": "near",
                "name": "Near Resort",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 49.1,  # Closer
                        "longitude": -120.0,
                    },
                ],
                "timezone": "America/Vancouver",
            },
        ]
        mock_table.scan.return_value = {"Items": mock_resorts_data}

        nearby = resort_service.get_nearby_resorts(
            latitude=49.0, longitude=-120.0, radius_km=200.0
        )

        assert len(nearby) == 2
        # Should be sorted by distance - near resort first
        assert nearby[0][0].resort_id == "near"
        assert nearby[1][0].resort_id == "far"
        # Distances should be in ascending order
        assert nearby[0][1] < nearby[1][1]


class TestWeatherService:
    """Test cases for WeatherService."""

    @pytest.fixture
    def weather_service(self):
        """Create a WeatherService instance."""
        return WeatherService(api_key="test-api-key")

    @pytest.fixture
    def mock_weather_response(self):
        """Create mock weather API response."""
        return {
            "current": {
                "temp_c": -5.0,
                "humidity": 85,
                "wind_kph": 10.0,
                "condition": {"text": "Light snow"},
            },
            "location": {"name": "Test Location"},
        }

    @pytest.fixture
    def mock_forecast_response(self):
        """Create mock forecast API response."""
        return {
            "forecast": {
                "forecastday": [
                    {
                        "day": {
                            "totalsnow_cm": 10.0,
                            "mintemp_c": -8.0,
                            "maxtemp_c": -2.0,
                        },
                        "hour": [{"temp_c": -5.0}, {"temp_c": -3.0}, {"temp_c": -7.0}],
                    }
                ]
            },
            "location": {"name": "Test Location"},
        }

    @patch("requests.get")
    def test_get_current_weather_success(
        self, mock_get, weather_service, mock_weather_response, mock_forecast_response
    ):
        """Test successful weather data retrieval."""
        # Mock current weather response
        mock_current_response = Mock()
        mock_current_response.raise_for_status.return_value = None
        mock_current_response.json.return_value = mock_weather_response

        # Mock forecast response
        mock_forecast_response_obj = Mock()
        mock_forecast_response_obj.raise_for_status.return_value = None
        mock_forecast_response_obj.json.return_value = mock_forecast_response

        # Configure requests.get to return different responses
        mock_get.side_effect = [mock_current_response, mock_forecast_response_obj]

        weather_data = weather_service.get_current_weather(
            latitude=49.0, longitude=-120.0, elevation_meters=1500
        )

        assert weather_data["current_temp_celsius"] == -5.0
        assert weather_data["humidity_percent"] == 85
        assert weather_data["wind_speed_kmh"] == 10.0
        assert weather_data["weather_description"] == "Light snow"
        assert weather_data["data_source"] == "weatherapi.com"
        assert weather_data["source_confidence"] == ConfidenceLevel.MEDIUM
        assert "raw_data" in weather_data

        # Verify API calls were made
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_get_current_weather_api_error(self, mock_get, weather_service):
        """Test handling of weather API errors."""
        mock_get.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="Error processing weather data"):
            weather_service.get_current_weather(49.0, -120.0, 1500)

    def test_calculate_ice_hours(self, weather_service):
        """Test ice formation hours calculation."""
        forecast_data = {
            "hourly_temperatures": [
                -2.0,
                5.0,
                6.0,
                -1.0,
                -3.0,
            ]  # 2 hours above 3°C threshold
        }

        ice_hours = weather_service._calculate_ice_hours(
            forecast_data, threshold_temp=3.0
        )

        assert ice_hours == 2.0

    def test_calculate_max_warm_hours(self, weather_service):
        """Test maximum consecutive warm hours calculation."""
        forecast_data = {
            "hourly_temperatures": [
                -2.0,
                2.0,
                3.0,
                1.0,
                -1.0,
                0.5,
                1.0,
            ]  # 3 consecutive hours >= 0°C
        }

        max_warm_hours = weather_service._calculate_max_warm_hours(
            forecast_data, threshold_temp=0.0
        )

        assert max_warm_hours == 3.0

    def test_validate_api_key(self, weather_service):
        """Test API key validation."""
        with patch("requests.get") as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            is_valid = weather_service.validate_api_key()
            assert is_valid is True

            # Mock failed response
            mock_response.status_code = 401
            is_valid = weather_service.validate_api_key()
            assert is_valid is False

    @patch("requests.get")
    def test_get_weather_forecast(
        self, mock_get, weather_service, mock_forecast_response
    ):
        """Test weather forecast retrieval."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_forecast_response
        mock_get.return_value = mock_response

        forecast = weather_service.get_weather_forecast(49.0, -120.0, days=5)

        assert "forecast" in forecast
        assert "location" in forecast
        mock_get.assert_called_once()


class TestUserService:
    """Test cases for UserService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.get_item.return_value = {"Item": None}
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        return table

    @pytest.fixture
    def user_service(self, mock_table):
        """Create a UserService instance with mocked table."""
        return UserService(mock_table)

    @pytest.fixture
    def sample_user_preferences_data(self):
        """Create sample user preferences data."""
        return {
            "user_id": "test_user_123",
            "favorite_resorts": ["big-white", "lake-louise"],
            "notification_preferences": {
                "snow_alerts": True,
                "condition_updates": False,
                "weekly_summary": True,
            },
            "preferred_units": {
                "temperature": "celsius",
                "distance": "metric",
                "snow_depth": "cm",
            },
            "quality_threshold": "fair",
            "created_at": "2026-01-20T10:00:00Z",
            "updated_at": "2026-01-20T11:00:00Z",
        }

    def test_get_user_preferences_success(
        self, user_service, mock_table, sample_user_preferences_data
    ):
        """Test successful retrieval of user preferences."""
        mock_table.get_item.return_value = {"Item": sample_user_preferences_data}

        preferences = user_service.get_user_preferences("test_user_123")

        assert preferences is not None
        assert preferences.user_id == "test_user_123"
        assert len(preferences.favorite_resorts) == 2
        mock_table.get_item.assert_called_once_with(Key={"user_id": "test_user_123"})

    def test_get_user_preferences_not_found(self, user_service, mock_table):
        """Test retrieval of non-existent user preferences."""
        mock_table.get_item.return_value = {}

        preferences = user_service.get_user_preferences("non_existent_user")

        assert preferences is None

    def test_save_user_preferences_success(
        self, user_service, mock_table, sample_user_preferences
    ):
        """Test successful saving of user preferences."""
        with patch("src.services.user_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2026-01-20T12:00:00Z"
            )
            mock_datetime.now.return_value = datetime.now(UTC)

            saved_preferences = user_service.save_user_preferences(
                sample_user_preferences
            )

            assert saved_preferences.user_id == sample_user_preferences.user_id
            mock_table.put_item.assert_called_once()

    def test_save_user_preferences_db_error(
        self, user_service, mock_table, sample_user_preferences
    ):
        """Test handling of database errors during preferences save."""
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "put_item",
        )

        with pytest.raises(Exception, match="Failed to save user preferences"):
            user_service.save_user_preferences(sample_user_preferences)

    def test_delete_user_data_success(self, user_service, mock_table):
        """Test successful deletion of user data."""
        result = user_service.delete_user_data("test_user_123")

        assert result is True
        mock_table.delete_item.assert_called_once_with(Key={"user_id": "test_user_123"})

    def test_delete_user_data_db_error(self, user_service, mock_table):
        """Test handling of database errors during user data deletion."""
        mock_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "delete_item",
        )

        with pytest.raises(Exception, match="Failed to delete user data"):
            user_service.delete_user_data("test_user_123")
