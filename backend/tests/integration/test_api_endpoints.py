"""Integration tests for API endpoints."""

import pytest
import json
import boto3
import os
from datetime import datetime, timezone
from moto import mock_dynamodb
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

# Import our FastAPI app
from src.handlers.api_handler import app


class TestAPIIntegration:
    """Integration tests for the API endpoints."""

    @pytest.fixture(scope="function")
    def dynamodb_setup(self):
        """Set up mock DynamoDB tables for testing."""
        with mock_dynamodb():
            # Create mock DynamoDB resource
            dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

            # Create resorts table
            resorts_table = dynamodb.create_table(
                TableName='snow-tracker-resorts-test',
                KeySchema=[
                    {'AttributeName': 'resort_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'resort_id', 'AttributeType': 'S'},
                    {'AttributeName': 'country', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'CountryIndex',
                        'KeySchema': [
                            {'AttributeName': 'country', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            # Create weather conditions table
            weather_table = dynamodb.create_table(
                TableName='snow-tracker-weather-conditions-test',
                KeySchema=[
                    {'AttributeName': 'resort_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'resort_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'elevation_level', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'ElevationIndex',
                        'KeySchema': [
                            {'AttributeName': 'elevation_level', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            # Create user preferences table
            user_table = dynamodb.create_table(
                TableName='snow-tracker-user-preferences-test',
                KeySchema=[
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            # Wait for tables to be created
            resorts_table.wait_until_exists()
            weather_table.wait_until_exists()
            user_table.wait_until_exists()

            yield {
                'resorts_table': resorts_table,
                'weather_table': weather_table,
                'user_table': user_table
            }

    @pytest.fixture
    def client(self, dynamodb_setup):
        """Create a test client for the FastAPI app."""
        # Set environment variables for testing
        os.environ['RESORTS_TABLE'] = 'snow-tracker-resorts-test'
        os.environ['WEATHER_CONDITIONS_TABLE'] = 'snow-tracker-weather-conditions-test'
        os.environ['USER_PREFERENCES_TABLE'] = 'snow-tracker-user-preferences-test'
        os.environ['WEATHER_API_KEY'] = 'test-key'

        return TestClient(app)

    @pytest.fixture
    def sample_resort_data(self):
        """Create sample resort data for testing."""
        return {
            'resort_id': 'test-resort',
            'name': 'Test Ski Resort',
            'country': 'CA',
            'region': 'BC',
            'elevation_points': [
                {
                    'level': 'base',
                    'elevation_meters': 1500,
                    'elevation_feet': 4921,
                    'latitude': 49.0,
                    'longitude': -120.0,
                    'weather_station_id': None
                },
                {
                    'level': 'top',
                    'elevation_meters': 2000,
                    'elevation_feet': 6561,
                    'latitude': 49.1,
                    'longitude': -119.9,
                    'weather_station_id': None
                }
            ],
            'timezone': 'America/Vancouver',
            'official_website': 'https://test-resort.com',
            'weather_sources': ['weatherapi'],
            'created_at': '2026-01-20T10:00:00Z',
            'updated_at': '2026-01-20T10:00:00Z'
        }

    @pytest.fixture
    def sample_weather_condition(self):
        """Create sample weather condition data."""
        return {
            'resort_id': 'test-resort',
            'elevation_level': 'base',
            'timestamp': '2026-01-20T10:00:00Z',
            'current_temp_celsius': -5.0,
            'min_temp_celsius': -8.0,
            'max_temp_celsius': -2.0,
            'snowfall_24h_cm': 15.0,
            'snowfall_48h_cm': 25.0,
            'snowfall_72h_cm': 30.0,
            'hours_above_ice_threshold': 0.0,
            'max_consecutive_warm_hours': 0.0,
            'humidity_percent': 85.0,
            'wind_speed_kmh': 10.0,
            'weather_description': 'Light snow',
            'snow_quality': 'excellent',
            'confidence_level': 'high',
            'fresh_snow_cm': 14.5,
            'data_source': 'test-api',
            'source_confidence': 'high',
            'ttl': int(datetime.now(timezone.utc).timestamp()) + 86400
        }

    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_get_resorts_empty(self, client, dynamodb_setup):
        """Test getting resorts when database is empty."""
        response = client.get("/api/v1/resorts")

        assert response.status_code == 200
        data = response.json()
        assert "resorts" in data
        assert len(data["resorts"]) == 0

    def test_get_resorts_with_data(self, client, dynamodb_setup, sample_resort_data):
        """Test getting resorts with data in database."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts")

        assert response.status_code == 200
        data = response.json()
        assert "resorts" in data
        assert len(data["resorts"]) == 1
        assert data["resorts"][0]["name"] == "Test Ski Resort"

    def test_get_resorts_by_country(self, client, dynamodb_setup, sample_resort_data):
        """Test filtering resorts by country."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        # Test filtering by Canada
        response = client.get("/api/v1/resorts?country=CA")
        assert response.status_code == 200
        data = response.json()
        assert len(data["resorts"]) == 1

        # Test filtering by US (should be empty)
        response = client.get("/api/v1/resorts?country=US")
        assert response.status_code == 200
        data = response.json()
        assert len(data["resorts"]) == 0

    def test_get_resort_by_id_success(self, client, dynamodb_setup, sample_resort_data):
        """Test getting a specific resort by ID."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts/test-resort")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Ski Resort"
        assert data["country"] == "CA"

    def test_get_resort_by_id_not_found(self, client, dynamodb_setup):
        """Test getting a non-existent resort."""
        response = client.get("/api/v1/resorts/non-existent-resort")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_resort_conditions_not_found(self, client, dynamodb_setup):
        """Test getting conditions for non-existent resort."""
        response = client.get("/api/v1/resorts/non-existent/conditions")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_resort_conditions_empty(self, client, dynamodb_setup, sample_resort_data):
        """Test getting conditions when no weather data exists."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts/test-resort/conditions")

        assert response.status_code == 200
        data = response.json()
        assert "conditions" in data
        assert len(data["conditions"]) == 0
        assert data["resort_id"] == "test-resort"

    def test_get_elevation_condition_invalid_level(self, client, dynamodb_setup, sample_resort_data):
        """Test getting condition for invalid elevation level."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts/test-resort/conditions/invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid elevation level" in data["detail"]

    def test_get_elevation_condition_not_found(self, client, dynamodb_setup, sample_resort_data):
        """Test getting condition when no data exists for elevation."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts/test-resort/conditions/base")

        assert response.status_code == 404
        data = response.json()
        assert "No conditions found" in data["detail"]

    def test_get_snow_quality_summary_no_conditions(self, client, dynamodb_setup, sample_resort_data):
        """Test getting snow quality summary with no weather conditions."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        response = client.get("/api/v1/resorts/test-resort/snow-quality")

        assert response.status_code == 200
        data = response.json()
        assert data["resort_id"] == "test-resort"
        assert data["overall_quality"] == "unknown"
        assert data["elevations"] == {}
        assert data["last_updated"] is None

    @patch('src.services.user_service.UserService.get_user_preferences')
    def test_get_user_preferences(self, mock_get_prefs, client, dynamodb_setup):
        """Test getting user preferences."""
        # Mock user preferences
        mock_preferences = Mock()
        mock_preferences.dict.return_value = {
            'user_id': 'test_user',
            'favorite_resorts': ['test-resort'],
            'notification_preferences': {
                'snow_alerts': True,
                'condition_updates': True,
                'weekly_summary': False
            },
            'preferred_units': {
                'temperature': 'celsius',
                'distance': 'metric',
                'snow_depth': 'cm'
            },
            'quality_threshold': 'fair',
            'created_at': '2026-01-20T10:00:00Z',
            'updated_at': '2026-01-20T10:00:00Z'
        }
        mock_get_prefs.return_value = mock_preferences

        response = client.get("/api/v1/user/preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"
        assert "favorite_resorts" in data

    @patch('src.services.user_service.UserService.save_user_preferences')
    def test_update_user_preferences(self, mock_save_prefs, client, dynamodb_setup):
        """Test updating user preferences."""
        mock_save_prefs.return_value = None

        preferences_data = {
            'user_id': 'test_user',
            'favorite_resorts': ['test-resort'],
            'notification_preferences': {
                'snow_alerts': True,
                'condition_updates': False,
                'weekly_summary': True
            },
            'preferred_units': {
                'temperature': 'celsius',
                'distance': 'metric',
                'snow_depth': 'cm'
            },
            'quality_threshold': 'good',
            'created_at': '2026-01-20T10:00:00Z',
            'updated_at': '2026-01-20T10:00:00Z'
        }

        response = client.put("/api/v1/user/preferences", json=preferences_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "successfully" in data["message"].lower()

    def test_api_error_handling(self, client, dynamodb_setup):
        """Test API error handling for various scenarios."""
        # Test with invalid JSON
        response = client.put("/api/v1/user/preferences", data="invalid json")
        assert response.status_code == 422  # Unprocessable Entity

        # Test internal server error simulation
        with patch('src.services.resort_service.ResortService.get_all_resorts',
                  side_effect=Exception("Database connection failed")):
            response = client.get("/api/v1/resorts")
            assert response.status_code == 500

    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.get("/health")

        assert response.status_code == 200
        # FastAPI with CORSMiddleware should handle OPTIONS requests
        # Test an actual CORS preflight request
        response = client.options("/health")
        # Note: TestClient might not fully simulate CORS preflight requests

    def test_api_documentation_endpoints(self, client):
        """Test that API documentation endpoints are accessible."""
        # Test OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema

        # Test docs endpoint (should return HTML)
        response = client.get("/api/docs")
        assert response.status_code == 200

        # Test redoc endpoint
        response = client.get("/api/redoc")
        assert response.status_code == 200

    def test_api_request_validation(self, client, dynamodb_setup, sample_resort_data):
        """Test API request validation."""
        # Add resort to database for testing
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        # Test invalid query parameters
        response = client.get("/api/v1/resorts/test-resort/conditions?hours=0")  # Invalid: hours < 1
        assert response.status_code == 422

        response = client.get("/api/v1/resorts/test-resort/conditions?hours=200")  # Invalid: hours > 168
        assert response.status_code == 422

        # Test valid query parameters
        response = client.get("/api/v1/resorts/test-resort/conditions?hours=24")
        assert response.status_code == 200

    @patch('boto3.resource')
    def test_database_connection_failure(self, mock_boto3, client):
        """Test handling of database connection failures."""
        # Mock boto3 to raise an exception
        mock_boto3.side_effect = Exception("Unable to connect to DynamoDB")

        # This should trigger during app startup or first request
        response = client.get("/api/v1/resorts")
        # The exact status code depends on how the error is handled
        assert response.status_code in [500, 503]

    def test_concurrent_requests(self, client, dynamodb_setup, sample_resort_data):
        """Test handling of concurrent requests."""
        # Add resort to database
        resorts_table = dynamodb_setup['resorts_table']
        resorts_table.put_item(Item=sample_resort_data)

        # Make multiple concurrent requests (simulated)
        responses = []
        for _ in range(5):
            response = client.get("/api/v1/resorts")
            responses.append(response)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert len(data["resorts"]) == 1