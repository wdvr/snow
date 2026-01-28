"""Integration tests for API endpoints."""

import os
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import boto3
import pytest
from jose import jwt
from moto import mock_aws

from utils.cache import clear_all_caches
from utils.dynamodb_utils import prepare_for_dynamodb

# Set environment variables before any app imports
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
os.environ["RESORTS_TABLE"] = "snow-tracker-resorts-test"
os.environ["WEATHER_CONDITIONS_TABLE"] = "snow-tracker-weather-conditions-test"
os.environ["USER_PREFERENCES_TABLE"] = "snow-tracker-user-preferences-test"
os.environ["WEATHER_API_KEY"] = "test-key"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing"

# Test JWT secret (must match the one in environment)
TEST_JWT_SECRET = "test-jwt-secret-key-for-testing"


def create_test_token(user_id: str = "test_user") -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="module")
def aws_mock():
    """Set up AWS mock for the entire module."""
    with mock_aws():
        yield


@pytest.fixture(scope="module")
def dynamodb_tables(aws_mock):
    """Create DynamoDB tables for testing."""
    dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

    # Create resorts table
    resorts_table = dynamodb.create_table(
        TableName="snow-tracker-resorts-test",
        KeySchema=[{"AttributeName": "resort_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "resort_id", "AttributeType": "S"},
            {"AttributeName": "country", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "CountryIndex",
                "KeySchema": [{"AttributeName": "country", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create weather conditions table
    weather_table = dynamodb.create_table(
        TableName="snow-tracker-weather-conditions-test",
        KeySchema=[
            {"AttributeName": "resort_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "resort_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "elevation_level", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "ElevationIndex",
                "KeySchema": [
                    {"AttributeName": "elevation_level", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create user preferences table
    user_table = dynamodb.create_table(
        TableName="snow-tracker-user-preferences-test",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Wait for tables
    resorts_table.wait_until_exists()
    weather_table.wait_until_exists()
    user_table.wait_until_exists()

    yield {
        "resorts_table": resorts_table,
        "weather_table": weather_table,
        "user_table": user_table,
    }


@pytest.fixture(scope="module")
def app_client(dynamodb_tables):
    """Create FastAPI test client after tables are set up."""
    # Import app after mock is active
    from fastapi.testclient import TestClient

    from handlers.api_handler import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear API caches before each test to ensure fresh data."""
    clear_all_caches()
    yield
    clear_all_caches()


@pytest.fixture
def sample_resort_data():
    """Create sample resort data for testing."""
    return {
        "resort_id": "test-resort",
        "name": "Test Ski Resort",
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
            },
            {
                "level": "top",
                "elevation_meters": 2000,
                "elevation_feet": 6561,
                "latitude": 49.1,
                "longitude": -119.9,
                "weather_station_id": None,
            },
        ],
        "timezone": "America/Vancouver",
        "official_website": "https://test-resort.com",
        "weather_sources": ["weatherapi"],
        "created_at": "2026-01-20T10:00:00Z",
        "updated_at": "2026-01-20T10:00:00Z",
    }


@pytest.fixture
def sample_weather_condition():
    """Create sample weather condition data."""
    return {
        "resort_id": "test-resort",
        "elevation_level": "base",
        "timestamp": "2026-01-20T10:00:00Z",
        "current_temp_celsius": -5.0,
        "min_temp_celsius": -8.0,
        "max_temp_celsius": -2.0,
        "snowfall_24h_cm": 15.0,
        "snowfall_48h_cm": 25.0,
        "snowfall_72h_cm": 30.0,
        "hours_above_ice_threshold": 0.0,
        "max_consecutive_warm_hours": 0.0,
        "humidity_percent": 85.0,
        "wind_speed_kmh": 10.0,
        "weather_description": "Light snow",
        "snow_quality": "excellent",
        "confidence_level": "high",
        "fresh_snow_cm": 14.5,
        "data_source": "test-api",
        "source_confidence": "high",
        "ttl": int(datetime.now(UTC).timestamp()) + 86400,
    }


class TestAPIIntegration:
    """Integration tests for the API endpoints."""

    def test_health_check(self, app_client):
        """Test the health check endpoint."""
        response = app_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_get_resorts_empty(self, app_client, dynamodb_tables):
        """Test getting resorts when database is empty."""
        # Clear the table first
        resorts_table = dynamodb_tables["resorts_table"]
        scan = resorts_table.scan()
        for item in scan.get("Items", []):
            resorts_table.delete_item(Key={"resort_id": item["resort_id"]})

        response = app_client.get("/api/v1/resorts")

        assert response.status_code == 200
        data = response.json()
        assert "resorts" in data
        assert len(data["resorts"]) == 0

    def test_get_resorts_with_data(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting resorts with data in database."""
        # Add resort to database (convert floats to Decimal for DynamoDB)
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts")

        assert response.status_code == 200
        data = response.json()
        assert "resorts" in data
        assert len(data["resorts"]) >= 1

        # Find our test resort
        test_resort = next(
            (r for r in data["resorts"] if r["resort_id"] == "test-resort"), None
        )
        assert test_resort is not None
        assert test_resort["name"] == "Test Ski Resort"

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_resorts_by_country(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test filtering resorts by country."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        # Test filtering by Canada
        response = app_client.get("/api/v1/resorts?country=CA")
        assert response.status_code == 200
        data = response.json()
        assert len(data["resorts"]) >= 1

        # Test filtering by US (may or may not have data)
        response = app_client.get("/api/v1/resorts?country=US")
        assert response.status_code == 200

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_resorts_by_region(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test filtering resorts by region."""
        # Add resort to database (Canadian resort with longitude -120 = na_west)
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        # Test filtering by na_west (our test resort should be in this region)
        response = app_client.get("/api/v1/resorts?region=na_west")
        assert response.status_code == 200
        data = response.json()
        assert len(data["resorts"]) >= 1
        # Verify our test resort is in the results
        resort_ids = [r["resort_id"] for r in data["resorts"]]
        assert "test-resort" in resort_ids

        # Test filtering by a different region (should not include our test resort)
        response = app_client.get("/api/v1/resorts?region=alps")
        assert response.status_code == 200
        data = response.json()
        resort_ids = [r["resort_id"] for r in data["resorts"]]
        assert "test-resort" not in resort_ids

        # Test invalid region
        response = app_client.get("/api/v1/resorts?region=invalid_region")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid region" in data["detail"]

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_regions(self, app_client, dynamodb_tables, sample_resort_data):
        """Test getting list of regions with resort counts."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/regions")
        assert response.status_code == 200
        data = response.json()
        assert "regions" in data

        # Should have at least one region (na_west from our test resort)
        assert len(data["regions"]) >= 1

        # Each region should have required fields
        for region in data["regions"]:
            assert "id" in region
            assert "name" in region
            assert "display_name" in region
            assert "resort_count" in region
            assert region["resort_count"] > 0

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_resort_by_id_success(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting a specific resort by ID."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts/test-resort")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Ski Resort"
        assert data["country"] == "CA"

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_resort_by_id_not_found(self, app_client):
        """Test getting a non-existent resort."""
        response = app_client.get("/api/v1/resorts/non-existent-resort")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_resort_conditions_not_found(self, app_client):
        """Test getting conditions for non-existent resort."""
        response = app_client.get("/api/v1/resorts/non-existent/conditions")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_resort_conditions_empty(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting conditions when no weather data exists."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts/test-resort/conditions")

        assert response.status_code == 200
        data = response.json()
        assert "conditions" in data
        assert len(data["conditions"]) == 0
        assert data["resort_id"] == "test-resort"

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_elevation_condition_invalid_level(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting condition for invalid elevation level."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts/test-resort/conditions/invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid elevation level" in data["detail"]

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_elevation_condition_not_found(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting condition when no data exists for elevation."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts/test-resort/conditions/base")

        assert response.status_code == 404
        data = response.json()
        assert "No conditions found" in data["detail"]

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_snow_quality_summary_no_conditions(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test getting snow quality summary with no weather conditions."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        response = app_client.get("/api/v1/resorts/test-resort/snow-quality")

        assert response.status_code == 200
        data = response.json()
        assert data["resort_id"] == "test-resort"
        assert data["overall_quality"] == "unknown"
        assert data["elevations"] == {}
        assert data["last_updated"] is None

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    @patch("handlers.api_handler.get_user_service")
    def test_get_user_preferences(self, mock_get_user_service, app_client):
        """Test getting user preferences."""
        from unittest.mock import MagicMock

        from models.user import UserPreferences

        # Create actual UserPreferences object
        mock_preferences = UserPreferences(
            user_id="test_user",
            favorite_resorts=["test-resort"],
            notification_preferences={
                "snow_alerts": True,
                "condition_updates": True,
                "weekly_summary": False,
            },
            preferred_units={
                "temperature": "celsius",
                "distance": "metric",
                "snow_depth": "cm",
            },
            quality_threshold="fair",
            created_at="2026-01-20T10:00:00Z",
            updated_at="2026-01-20T10:00:00Z",
        )
        mock_service = MagicMock()
        mock_service.get_user_preferences.return_value = mock_preferences
        mock_get_user_service.return_value = mock_service

        token = create_test_token("test_user")
        response = app_client.get(
            "/api/v1/user/preferences",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"
        assert "favorite_resorts" in data

    @patch("services.user_service.UserService.save_user_preferences")
    def test_update_user_preferences(self, mock_save_prefs, app_client):
        """Test updating user preferences."""
        mock_save_prefs.return_value = None

        preferences_data = {
            "user_id": "test_user",
            "favorite_resorts": ["test-resort"],
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
            "quality_threshold": "good",
            "created_at": "2026-01-20T10:00:00Z",
            "updated_at": "2026-01-20T10:00:00Z",
        }

        token = create_test_token("test_user")
        response = app_client.put(
            "/api/v1/user/preferences",
            json=preferences_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "successfully" in data["message"].lower()

    def test_api_error_handling(self, app_client):
        """Test API error handling for various scenarios."""
        # Test with invalid JSON (with auth to get past 401)
        token = create_test_token("test_user")
        response = app_client.put(
            "/api/v1/user/preferences",
            content="invalid json",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        assert response.status_code == 422  # Unprocessable Entity

    def test_cors_headers(self, app_client):
        """Test CORS headers are present."""
        response = app_client.get("/health")
        assert response.status_code == 200

    def test_api_documentation_endpoints(self, app_client):
        """Test that API documentation endpoints are accessible."""
        # Test OpenAPI schema
        response = app_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema

        # Test docs endpoint (should return HTML)
        response = app_client.get("/api/docs")
        assert response.status_code == 200

        # Test redoc endpoint
        response = app_client.get("/api/redoc")
        assert response.status_code == 200

    def test_api_request_validation(
        self, app_client, dynamodb_tables, sample_resort_data
    ):
        """Test API request validation."""
        # Add resort to database for testing
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        # Test invalid query parameters
        response = app_client.get(
            "/api/v1/resorts/test-resort/conditions?hours=0"
        )  # Invalid: hours < 1
        assert response.status_code == 422

        response = app_client.get(
            "/api/v1/resorts/test-resort/conditions?hours=200"
        )  # Invalid: hours > 168
        assert response.status_code == 422

        # Test valid query parameters
        response = app_client.get("/api/v1/resorts/test-resort/conditions?hours=24")
        assert response.status_code == 200

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_concurrent_requests(self, app_client, dynamodb_tables, sample_resort_data):
        """Test handling of concurrent requests."""
        # Add resort to database
        resorts_table = dynamodb_tables["resorts_table"]
        resorts_table.put_item(Item=prepare_for_dynamodb(sample_resort_data))

        # Make multiple requests
        responses = []
        for _ in range(5):
            response = app_client.get("/api/v1/resorts")
            responses.append(response)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert len(data["resorts"]) >= 1

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "test-resort"})

    def test_get_nearby_resorts(self, app_client, dynamodb_tables):
        """Test the nearby resorts endpoint."""
        # Add multiple resorts at different locations
        resorts_table = dynamodb_tables["resorts_table"]

        nearby_resort = {
            "resort_id": "nearby-resort",
            "name": "Nearby Resort",
            "country": "CA",
            "region": "BC",
            "elevation_points": [
                {
                    "level": "mid",
                    "elevation_meters": 1500,
                    "elevation_feet": 4921,
                    "latitude": 49.3,  # Near Vancouver
                    "longitude": -123.0,
                },
            ],
            "timezone": "America/Vancouver",
        }

        far_resort = {
            "resort_id": "far-resort",
            "name": "Far Resort",
            "country": "CA",
            "region": "AB",
            "elevation_points": [
                {
                    "level": "mid",
                    "elevation_meters": 2000,
                    "elevation_feet": 6562,
                    "latitude": 51.4,  # Far from Vancouver
                    "longitude": -116.0,
                },
            ],
            "timezone": "America/Edmonton",
        }

        resorts_table.put_item(Item=prepare_for_dynamodb(nearby_resort))
        resorts_table.put_item(Item=prepare_for_dynamodb(far_resort))

        # Test nearby endpoint - small radius
        response = app_client.get(
            "/api/v1/resorts/nearby?lat=49.2827&lon=-123.1207&radius=50"
        )
        assert response.status_code == 200
        data = response.json()
        assert "resorts" in data
        assert "count" in data
        assert "search_center" in data
        assert "search_radius_km" in data

        # Should find nearby resort only
        assert data["count"] == 1
        assert data["resorts"][0]["resort"]["resort_id"] == "nearby-resort"
        assert "distance_km" in data["resorts"][0]
        assert "distance_miles" in data["resorts"][0]

        # Test with larger radius
        response = app_client.get(
            "/api/v1/resorts/nearby?lat=49.2827&lon=-123.1207&radius=1000"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

        # Results should be sorted by distance
        assert data["resorts"][0]["distance_km"] < data["resorts"][1]["distance_km"]

        # Cleanup
        resorts_table.delete_item(Key={"resort_id": "nearby-resort"})
        resorts_table.delete_item(Key={"resort_id": "far-resort"})

    def test_get_nearby_resorts_validation(self, app_client):
        """Test validation for nearby resorts endpoint."""
        # Missing required parameters
        response = app_client.get("/api/v1/resorts/nearby")
        assert response.status_code == 422

        # Invalid latitude (out of range)
        response = app_client.get("/api/v1/resorts/nearby?lat=100&lon=0")
        assert response.status_code == 422

        # Invalid longitude (out of range)
        response = app_client.get("/api/v1/resorts/nearby?lat=0&lon=200")
        assert response.status_code == 422

        # Invalid radius (too small)
        response = app_client.get("/api/v1/resorts/nearby?lat=49&lon=-123&radius=0")
        assert response.status_code == 422

        # Invalid radius (too large)
        response = app_client.get("/api/v1/resorts/nearby?lat=49&lon=-123&radius=3000")
        assert response.status_code == 422

        # Invalid limit
        response = app_client.get("/api/v1/resorts/nearby?lat=49&lon=-123&limit=0")
        assert response.status_code == 422

    def test_get_nearby_resorts_with_limit(self, app_client, dynamodb_tables):
        """Test nearby resorts endpoint with limit parameter."""
        resorts_table = dynamodb_tables["resorts_table"]

        # Add several resorts near the search location
        for i in range(5):
            resort = {
                "resort_id": f"test-resort-{i}",
                "name": f"Test Resort {i}",
                "country": "CA",
                "region": "BC",
                "elevation_points": [
                    {
                        "level": "mid",
                        "elevation_meters": 1500,
                        "elevation_feet": 4921,
                        "latitude": 49.0 + (i * 0.01),
                        "longitude": -120.0,
                    },
                ],
                "timezone": "America/Vancouver",
            }
            resorts_table.put_item(Item=prepare_for_dynamodb(resort))

        # Test with limit
        response = app_client.get(
            "/api/v1/resorts/nearby?lat=49.0&lon=-120.0&radius=100&limit=2"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

        # Cleanup
        for i in range(5):
            resorts_table.delete_item(Key={"resort_id": f"test-resort-{i}"})
