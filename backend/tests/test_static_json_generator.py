"""Tests for the static JSON generator service."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.static_json_generator import StaticJsonGenerator


class TestStaticJsonGenerator:
    """Tests for the StaticJsonGenerator class."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create a mock DynamoDB resource."""
        with patch("services.static_json_generator.dynamodb") as mock_db:
            yield mock_db

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        with patch("services.static_json_generator.s3_client") as mock_s3:
            yield mock_s3

    @pytest.fixture
    def sample_resort(self):
        """Create a sample resort for testing."""
        return Resort(
            resort_id="whistler-blackcomb",
            name="Whistler Blackcomb",
            country="CA",
            region="British Columbia",
            timezone="America/Vancouver",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.BASE,
                    elevation_meters=675,
                    elevation_feet=2214,
                    latitude=50.0843,
                    longitude=-122.9574,
                ),
                ElevationPoint(
                    level=ElevationLevel.MID,
                    elevation_meters=1550,
                    elevation_feet=5085,
                    latitude=50.0643,
                    longitude=-122.9374,
                ),
                ElevationPoint(
                    level=ElevationLevel.TOP,
                    elevation_meters=2284,
                    elevation_feet=7494,
                    latitude=50.0543,
                    longitude=-122.9274,
                ),
            ],
        )

    @pytest.fixture
    def sample_condition(self):
        """Create a sample weather condition for testing."""
        return WeatherCondition(
            resort_id="whistler-blackcomb",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-5.0,
            min_temp_celsius=-10.0,
            max_temp_celsius=0.0,
            snowfall_24h_cm=15.0,
            snowfall_48h_cm=25.0,
            snowfall_72h_cm=35.0,
            hours_above_ice_threshold=0.0,
            snow_quality=SnowQuality.GOOD,
            source_confidence=ConfidenceLevel.HIGH,
            snowfall_after_freeze_cm=20.0,
        )

    def test_generate_resorts_json(self, mock_dynamodb, mock_s3, sample_resort):
        """Test generating resorts.json file."""
        # Setup mock table
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {
                    "resort_id": "whistler-blackcomb",
                    "name": "Whistler Blackcomb",
                    "country": "CA",
                    "region": "British Columbia",
                    "timezone": "America/Vancouver",
                    "elevation_points": [
                        {
                            "level": "base",
                            "elevation_meters": 675,
                            "elevation_feet": 2214,
                            "latitude": 50.0843,
                            "longitude": -122.9574,
                        }
                    ],
                }
            ]
        }
        mock_dynamodb.Table.return_value = mock_table

        # Create generator and run
        generator = StaticJsonGenerator(
            resorts_table_name="test-resorts",
            weather_conditions_table_name="test-conditions",
            website_bucket="test-bucket",
        )

        result = generator._generate_resorts_json()

        # Verify S3 upload was called
        assert mock_s3.put_object.called
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["Bucket"] == "test-bucket"
        assert call_args.kwargs["Key"] == "data/resorts.json"
        assert call_args.kwargs["ContentType"] == "application/json"

        # Verify result
        assert result["file"] == "data/resorts.json"
        assert result["resort_count"] == 1

    def test_snow_quality_calculation_excellent(
        self, mock_dynamodb, mock_s3, sample_resort
    ):
        """Test snow quality calculation returns EXCELLENT for great conditions."""

        # Resort table returns one resort
        def mock_scan():
            return {
                "Items": [
                    {
                        "resort_id": "whistler-blackcomb",
                        "name": "Whistler Blackcomb",
                        "country": "CA",
                        "region": "British Columbia",
                        "timezone": "America/Vancouver",
                        "elevation_points": [
                            {
                                "level": "mid",
                                "elevation_meters": 1550,
                                "elevation_feet": 5085,
                                "latitude": 50.0643,
                                "longitude": -122.9374,
                            }
                        ],
                    }
                ]
            }

        # Weather table returns excellent condition
        def mock_query(**kwargs):
            if "ElevationIndex" in str(kwargs.get("IndexName", "")):
                return {"Items": []}
            return {
                "Items": [
                    {
                        "resort_id": "whistler-blackcomb",
                        "elevation_level": "mid",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "current_temp_celsius": Decimal("-5.0"),
                        "min_temp_celsius": Decimal("-10.0"),
                        "max_temp_celsius": Decimal("0.0"),
                        "snowfall_24h_cm": Decimal("20.0"),
                        "snowfall_48h_cm": Decimal("30.0"),
                        "snowfall_72h_cm": Decimal("40.0"),
                        "hours_above_ice_threshold": Decimal("0.0"),
                        "snow_quality": "excellent",
                        "source_confidence": "high",
                        "snowfall_after_freeze_cm": Decimal("25.0"),
                        "data_source": "open-meteo",
                    }
                ]
            }

        resorts_table = MagicMock()
        resorts_table.scan = mock_scan

        conditions_table = MagicMock()
        conditions_table.query = mock_query

        def table_factory(name):
            if "resort" in name.lower():
                return resorts_table
            return conditions_table

        mock_dynamodb.Table = table_factory

        generator = StaticJsonGenerator(
            resorts_table_name="test-resorts",
            weather_conditions_table_name="test-conditions",
            website_bucket="test-bucket",
        )

        generator._generate_snow_quality_json()

        # Verify S3 upload was called
        assert mock_s3.put_object.called

        # Check the uploaded JSON content
        call_args = mock_s3.put_object.call_args
        uploaded_content = call_args.kwargs["Body"].decode("utf-8")
        data = json.loads(uploaded_content)

        assert "results" in data
        assert "whistler-blackcomb" in data["results"]
        assert data["results"]["whistler-blackcomb"]["overall_quality"] == "excellent"

    def test_snow_quality_horrible_makes_resort_not_skiable(
        self, mock_dynamodb, mock_s3
    ):
        """Test that HORRIBLE quality at any elevation makes resort not skiable."""
        resorts_table = MagicMock()
        resorts_table.scan.return_value = {
            "Items": [
                {
                    "resort_id": "test-resort",
                    "name": "Test Resort",
                    "country": "US",
                    "region": "Colorado",
                    "timezone": "America/Denver",
                    "elevation_points": [
                        {
                            "level": "base",
                            "elevation_meters": 2500,
                            "elevation_feet": 8202,
                            "latitude": 39.0,
                            "longitude": -106.0,
                        },
                        {
                            "level": "top",
                            "elevation_meters": 3500,
                            "elevation_feet": 11483,
                            "latitude": 39.1,
                            "longitude": -106.1,
                        },
                    ],
                }
            ]
        }

        conditions_table = MagicMock()

        # Return conditions based on elevation level
        def mock_query(**kwargs):
            if ":level" in str(kwargs.get("ExpressionAttributeValues", {})):
                level = kwargs["ExpressionAttributeValues"].get(":level", "")
                if level == "base":
                    # Base has HORRIBLE conditions
                    return {
                        "Items": [
                            {
                                "resort_id": "test-resort",
                                "elevation_level": "base",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "current_temp_celsius": Decimal("10.0"),
                                "min_temp_celsius": Decimal("5.0"),
                                "max_temp_celsius": Decimal("15.0"),
                                "snowfall_24h_cm": Decimal("0.0"),
                                "hours_above_ice_threshold": Decimal("24.0"),
                                "snow_quality": "horrible",
                                "source_confidence": "high",
                                "data_source": "open-meteo",
                            }
                        ]
                    }
                elif level == "top":
                    # Top has EXCELLENT conditions
                    return {
                        "Items": [
                            {
                                "resort_id": "test-resort",
                                "elevation_level": "top",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "current_temp_celsius": Decimal("-10.0"),
                                "min_temp_celsius": Decimal("-15.0"),
                                "max_temp_celsius": Decimal("-5.0"),
                                "snowfall_24h_cm": Decimal("30.0"),
                                "hours_above_ice_threshold": Decimal("0.0"),
                                "snow_quality": "excellent",
                                "source_confidence": "high",
                                "snowfall_after_freeze_cm": Decimal("30.0"),
                                "data_source": "open-meteo",
                            }
                        ]
                    }
            return {"Items": []}

        conditions_table.query = mock_query

        def table_factory(name):
            if "resort" in name.lower():
                return resorts_table
            return conditions_table

        mock_dynamodb.Table = table_factory

        generator = StaticJsonGenerator(
            resorts_table_name="test-resorts",
            weather_conditions_table_name="test-conditions",
            website_bucket="test-bucket",
        )

        generator._generate_snow_quality_json()

        # Check the uploaded JSON content
        call_args = mock_s3.put_object.call_args
        uploaded_content = call_args.kwargs["Body"].decode("utf-8")
        data = json.loads(uploaded_content)

        # If ANY elevation is HORRIBLE, resort should be HORRIBLE
        assert data["results"]["test-resort"]["overall_quality"] == "horrible"

    def test_generate_all_creates_both_files(self, mock_dynamodb, mock_s3):
        """Test that generate_all creates both resorts.json and snow-quality.json."""
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb.Table.return_value = mock_table

        generator = StaticJsonGenerator(
            resorts_table_name="test-resorts",
            weather_conditions_table_name="test-conditions",
            website_bucket="test-bucket",
        )

        result = generator.generate_all()

        # Should create 2 files
        assert len(result["files"]) == 2
        file_names = [f["file"] for f in result["files"]]
        assert "data/resorts.json" in file_names
        assert "data/snow-quality.json" in file_names
        assert result["success"] is True

    def test_s3_upload_content_type_and_cache(self, mock_dynamodb, mock_s3):
        """Test that S3 uploads have correct content type and cache headers."""
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        mock_dynamodb.Table.return_value = mock_table

        generator = StaticJsonGenerator(
            resorts_table_name="test-resorts",
            weather_conditions_table_name="test-conditions",
            website_bucket="test-bucket",
        )

        generator._generate_resorts_json()

        # Verify S3 upload headers
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["ContentType"] == "application/json"
        assert call_args.kwargs["CacheControl"] == "public, max-age=3600"
