"""Performance tests for API endpoints.

These tests verify that API endpoints meet performance requirements.
Tests will FAIL if response times exceed thresholds:
- Batch snow quality endpoint: must complete in <2000ms
"""

import os
import time
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from utils.cache import clear_all_caches
from utils.dynamodb_utils import prepare_for_dynamodb

# Set environment variables before any app imports
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
os.environ["RESORTS_TABLE"] = "snow-tracker-resorts-perf-test"
os.environ["WEATHER_CONDITIONS_TABLE"] = "snow-tracker-weather-conditions-perf-test"
os.environ["USER_PREFERENCES_TABLE"] = "snow-tracker-user-preferences-perf-test"
os.environ["WEATHER_API_KEY"] = "test-key"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing"

# Performance thresholds in milliseconds
BATCH_SNOW_QUALITY_THRESHOLD_MS = 2000  # Must complete in <2 seconds


@pytest.fixture(scope="module")
def aws_mock():
    """Set up AWS mock for the entire module."""
    with mock_aws():
        yield


@pytest.fixture(scope="module")
def dynamodb_tables(aws_mock):
    """Create DynamoDB tables for performance testing."""
    dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

    # Create resorts table
    resorts_table = dynamodb.create_table(
        TableName="snow-tracker-resorts-perf-test",
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
        TableName="snow-tracker-weather-conditions-perf-test",
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
        TableName="snow-tracker-user-preferences-perf-test",
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
    from fastapi.testclient import TestClient

    from handlers.api_handler import app, reset_services

    # Reset services to ensure they use the mocked DynamoDB
    reset_services()

    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear API caches before each test to measure cold performance."""
    clear_all_caches()
    yield
    clear_all_caches()


def create_test_resort(resort_id: str, name: str) -> dict:
    """Create a test resort with valid coordinates."""
    return {
        "resort_id": resort_id,
        "name": name,
        "country": "CA",
        "region": "BC",
        "elevation_points": [
            {
                "level": "base",
                "elevation_meters": 1500,
                "elevation_feet": 4921,
                "latitude": 49.0 + (hash(resort_id) % 100) / 1000,
                "longitude": -120.0 + (hash(resort_id) % 100) / 1000,
                "weather_station_id": None,
            },
            {
                "level": "mid",
                "elevation_meters": 1800,
                "elevation_feet": 5905,
                "latitude": 49.05 + (hash(resort_id) % 100) / 1000,
                "longitude": -119.95 + (hash(resort_id) % 100) / 1000,
                "weather_station_id": None,
            },
            {
                "level": "top",
                "elevation_meters": 2200,
                "elevation_feet": 7218,
                "latitude": 49.1 + (hash(resort_id) % 100) / 1000,
                "longitude": -119.9 + (hash(resort_id) % 100) / 1000,
                "weather_station_id": None,
            },
        ],
        "timezone": "America/Vancouver",
        "official_website": f"https://{resort_id}.com",
        "weather_sources": ["weatherapi"],
        "created_at": "2026-01-20T10:00:00Z",
        "updated_at": "2026-01-20T10:00:00Z",
    }


def create_test_weather_condition(resort_id: str, elevation_level: str) -> dict:
    """Create a test weather condition record."""
    return {
        "resort_id": resort_id,
        "elevation_level": elevation_level,
        "timestamp": datetime.now(UTC).isoformat(),
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


class TestAPIPerformance:
    """Performance tests for API endpoints."""

    def test_batch_snow_quality_50_resorts_cold_cache(
        self, app_client, dynamodb_tables
    ):
        """
        Test batch snow quality endpoint with 50 resorts (cold cache).

        PERFORMANCE REQUIREMENT: Must complete in <2000ms
        """
        resorts_table = dynamodb_tables["resorts_table"]
        weather_table = dynamodb_tables["weather_table"]

        # Create 50 test resorts with weather data
        resort_ids = []
        for i in range(50):
            resort_id = f"perf-test-resort-{i:03d}"
            resort_ids.append(resort_id)

            # Add resort
            resort_data = create_test_resort(resort_id, f"Performance Test Resort {i}")
            resorts_table.put_item(Item=prepare_for_dynamodb(resort_data))

            # Add weather conditions for each elevation
            for level in ["base", "mid", "top"]:
                condition = create_test_weather_condition(resort_id, level)
                weather_table.put_item(Item=prepare_for_dynamodb(condition))

        try:
            # Clear cache to test cold performance
            clear_all_caches()

            # Make the batch request and time it
            start_time = time.perf_counter()
            response = app_client.get(
                f"/api/v1/snow-quality/batch?resort_ids={','.join(resort_ids)}"
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert len(data["results"]) == 50

            # CRITICAL: Performance assertion
            assert elapsed_ms < BATCH_SNOW_QUALITY_THRESHOLD_MS, (
                f"Batch snow quality for 50 resorts took {elapsed_ms:.0f}ms, "
                f"exceeds threshold of {BATCH_SNOW_QUALITY_THRESHOLD_MS}ms"
            )

            print(f"\n✓ 50 resorts cold cache: {elapsed_ms:.0f}ms")

        finally:
            # Cleanup
            for resort_id in resort_ids:
                resorts_table.delete_item(Key={"resort_id": resort_id})
                for _ in ["base", "mid", "top"]:
                    try:
                        weather_table.delete_item(
                            Key={
                                "resort_id": resort_id,
                                "timestamp": datetime.now(UTC).isoformat()[:19] + "Z",
                            }
                        )
                    except Exception:
                        pass

    def test_batch_snow_quality_200_resorts_cold_cache(
        self, app_client, dynamodb_tables
    ):
        """
        Test batch snow quality endpoint with 200 resorts (maximum batch size).

        PERFORMANCE REQUIREMENT: Must complete in <2000ms
        """
        resorts_table = dynamodb_tables["resorts_table"]
        weather_table = dynamodb_tables["weather_table"]

        # Create 200 test resorts with weather data
        resort_ids = []
        for i in range(200):
            resort_id = f"perf-test-large-{i:03d}"
            resort_ids.append(resort_id)

            # Add resort
            resort_data = create_test_resort(resort_id, f"Large Performance Test {i}")
            resorts_table.put_item(Item=prepare_for_dynamodb(resort_data))

            # Add weather conditions (only mid elevation for speed)
            condition = create_test_weather_condition(resort_id, "mid")
            weather_table.put_item(Item=prepare_for_dynamodb(condition))

        try:
            # Clear cache to test cold performance
            clear_all_caches()

            # Make the batch request and time it
            start_time = time.perf_counter()
            response = app_client.get(
                f"/api/v1/snow-quality/batch?resort_ids={','.join(resort_ids)}"
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert len(data["results"]) == 200

            # CRITICAL: Performance assertion
            assert elapsed_ms < BATCH_SNOW_QUALITY_THRESHOLD_MS, (
                f"Batch snow quality for 200 resorts took {elapsed_ms:.0f}ms, "
                f"exceeds threshold of {BATCH_SNOW_QUALITY_THRESHOLD_MS}ms"
            )

            print(f"\n✓ 200 resorts cold cache: {elapsed_ms:.0f}ms")

        finally:
            # Cleanup
            for resort_id in resort_ids:
                resorts_table.delete_item(Key={"resort_id": resort_id})

    def test_batch_snow_quality_warm_cache_performance(
        self, app_client, dynamodb_tables
    ):
        """
        Test batch snow quality endpoint with warm cache.

        Warm cache should be significantly faster than cold cache.
        """
        resorts_table = dynamodb_tables["resorts_table"]
        weather_table = dynamodb_tables["weather_table"]

        # Create 100 test resorts
        resort_ids = []
        for i in range(100):
            resort_id = f"perf-warm-{i:03d}"
            resort_ids.append(resort_id)

            resort_data = create_test_resort(resort_id, f"Warm Cache Test {i}")
            resorts_table.put_item(Item=prepare_for_dynamodb(resort_data))

            condition = create_test_weather_condition(resort_id, "mid")
            weather_table.put_item(Item=prepare_for_dynamodb(condition))

        try:
            # First request (cold cache)
            clear_all_caches()
            start_time = time.perf_counter()
            response = app_client.get(
                f"/api/v1/snow-quality/batch?resort_ids={','.join(resort_ids)}"
            )
            cold_elapsed_ms = (time.perf_counter() - start_time) * 1000
            assert response.status_code == 200

            # Second request (warm cache) - should be faster
            start_time = time.perf_counter()
            response = app_client.get(
                f"/api/v1/snow-quality/batch?resort_ids={','.join(resort_ids)}"
            )
            warm_elapsed_ms = (time.perf_counter() - start_time) * 1000
            assert response.status_code == 200

            # Warm cache should be noticeably faster
            assert warm_elapsed_ms < cold_elapsed_ms, (
                f"Warm cache ({warm_elapsed_ms:.0f}ms) should be faster than "
                f"cold cache ({cold_elapsed_ms:.0f}ms)"
            )

            print(
                f"\n✓ 100 resorts cold: {cold_elapsed_ms:.0f}ms, warm: {warm_elapsed_ms:.0f}ms"
            )

        finally:
            # Cleanup
            for resort_id in resort_ids:
                resorts_table.delete_item(Key={"resort_id": resort_id})

    def test_get_resorts_endpoint_performance(self, app_client, dynamodb_tables):
        """
        Test /api/v1/resorts endpoint with many resorts.

        PERFORMANCE REQUIREMENT: Must complete in <2000ms for 500 resorts
        """
        resorts_table = dynamodb_tables["resorts_table"]

        # Create 500 test resorts
        resort_ids = []
        for i in range(500):
            resort_id = f"perf-resorts-{i:03d}"
            resort_ids.append(resort_id)

            resort_data = create_test_resort(resort_id, f"Resorts List Test {i}")
            resorts_table.put_item(Item=prepare_for_dynamodb(resort_data))

        try:
            # Clear cache
            clear_all_caches()

            # Time the request
            start_time = time.perf_counter()
            response = app_client.get("/api/v1/resorts")
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            assert response.status_code == 200
            data = response.json()
            assert len(data["resorts"]) >= 500

            # Performance check
            assert elapsed_ms < BATCH_SNOW_QUALITY_THRESHOLD_MS, (
                f"Get resorts took {elapsed_ms:.0f}ms, "
                f"exceeds threshold of {BATCH_SNOW_QUALITY_THRESHOLD_MS}ms"
            )

            print(f"\n✓ 500 resorts list endpoint: {elapsed_ms:.0f}ms")

        finally:
            # Cleanup
            for resort_id in resort_ids:
                resorts_table.delete_item(Key={"resort_id": resort_id})

    def test_batch_endpoint_rejects_over_limit(self, app_client):
        """Test that batch endpoint rejects requests exceeding the limit."""
        # Create 201 resort IDs (over the 200 limit)
        resort_ids = [f"test-{i}" for i in range(201)]

        response = app_client.get(
            f"/api/v1/snow-quality/batch?resort_ids={','.join(resort_ids)}"
        )

        assert response.status_code == 400
        assert "Maximum 200 resorts" in response.json()["detail"]
