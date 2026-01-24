"""Tests for DynamoDB utility functions."""

from decimal import Decimal

import pytest

from utils.dynamodb_utils import (
    decimal_to_python,
    parse_from_dynamodb,
    parse_items_from_dynamodb,
    prepare_for_dynamodb,
    python_to_decimal,
)


class TestDecimalToPython:
    """Tests for decimal_to_python function."""

    def test_converts_decimal_to_float(self):
        """Test converting Decimal to float."""
        result = decimal_to_python(Decimal("3.14"))
        assert result == 3.14
        assert isinstance(result, float)

    def test_converts_decimal_to_int_when_whole_number(self):
        """Test converting whole number Decimal to int."""
        result = decimal_to_python(Decimal("42"))
        assert result == 42
        assert isinstance(result, int)

    def test_converts_negative_decimal(self):
        """Test converting negative Decimal."""
        result = decimal_to_python(Decimal("-5.5"))
        assert result == -5.5
        assert isinstance(result, float)

    def test_converts_zero(self):
        """Test converting zero Decimal."""
        result = decimal_to_python(Decimal("0"))
        assert result == 0
        assert isinstance(result, int)

    def test_converts_nested_dict(self):
        """Test converting nested dictionary with Decimals."""
        data = {
            "temperature": Decimal("-5.0"),
            "snowfall": Decimal("15"),
            "nested": {
                "latitude": Decimal("49.123456"),
                "longitude": Decimal("-118.987654"),
            },
        }
        result = decimal_to_python(data)

        # Note: Decimal("-5.0") becomes int -5 since it's a whole number
        assert result["temperature"] == -5
        assert isinstance(result["temperature"], int)
        assert result["snowfall"] == 15
        assert isinstance(result["snowfall"], int)
        assert result["nested"]["latitude"] == 49.123456
        assert result["nested"]["longitude"] == -118.987654

    def test_converts_list_with_decimals(self):
        """Test converting list containing Decimals."""
        data = [Decimal("1.5"), Decimal("2"), Decimal("3.7")]
        result = decimal_to_python(data)

        assert result == [1.5, 2, 3.7]
        assert isinstance(result[0], float)
        assert isinstance(result[1], int)
        assert isinstance(result[2], float)

    def test_preserves_strings(self):
        """Test that strings are preserved."""
        result = decimal_to_python("test_string")
        assert result == "test_string"

    def test_preserves_none(self):
        """Test that None is preserved."""
        result = decimal_to_python(None)
        assert result is None

    def test_preserves_booleans(self):
        """Test that booleans are preserved."""
        assert decimal_to_python(True) is True
        assert decimal_to_python(False) is False

    def test_complex_nested_structure(self):
        """Test converting complex nested structure."""
        data = {
            "resort_id": "test-resort",
            "elevation_points": [
                {
                    "level": "base",
                    "elevation_meters": Decimal("1500"),
                    "latitude": Decimal("49.0"),
                    "longitude": Decimal("-120.0"),
                },
                {
                    "level": "top",
                    "elevation_meters": Decimal("2000"),
                    "latitude": Decimal("49.1"),
                    "longitude": Decimal("-119.9"),
                },
            ],
            "weather_data": {"temperature": Decimal("-8.5"), "humidity": Decimal("85")},
        }
        result = decimal_to_python(data)

        assert result["resort_id"] == "test-resort"
        assert result["elevation_points"][0]["elevation_meters"] == 1500
        assert isinstance(result["elevation_points"][0]["elevation_meters"], int)
        assert result["elevation_points"][0]["latitude"] == 49.0
        assert result["weather_data"]["temperature"] == -8.5


class TestPythonToDecimal:
    """Tests for python_to_decimal function."""

    def test_converts_float_to_decimal(self):
        """Test converting float to Decimal."""
        result = python_to_decimal(3.14)
        assert result == Decimal("3.14")
        assert isinstance(result, Decimal)

    def test_converts_int_to_decimal(self):
        """Test converting int to Decimal."""
        result = python_to_decimal(42)
        assert result == Decimal("42")
        assert isinstance(result, Decimal)

    def test_converts_negative_float(self):
        """Test converting negative float."""
        result = python_to_decimal(-5.5)
        assert result == Decimal("-5.5")

    def test_converts_zero(self):
        """Test converting zero."""
        result = python_to_decimal(0)
        assert result == Decimal("0")

    def test_converts_nested_dict(self):
        """Test converting nested dictionary."""
        data = {
            "temperature": -5.0,
            "snowfall": 15,
            "nested": {"latitude": 49.123456, "longitude": -118.987654},
        }
        result = python_to_decimal(data)

        assert result["temperature"] == Decimal("-5.0")
        assert result["snowfall"] == Decimal("15")
        assert result["nested"]["latitude"] == Decimal("49.123456")

    def test_converts_list_with_floats(self):
        """Test converting list containing floats."""
        data = [1.5, 2, 3.7]
        result = python_to_decimal(data)

        assert result[0] == Decimal("1.5")
        assert result[1] == Decimal("2")
        assert result[2] == Decimal("3.7")

    def test_preserves_strings(self):
        """Test that strings are preserved."""
        result = python_to_decimal("test_string")
        assert result == "test_string"

    def test_preserves_none(self):
        """Test that None is preserved."""
        result = python_to_decimal(None)
        assert result is None

    def test_preserves_booleans(self):
        """Test that booleans are preserved (not converted to Decimal)."""
        assert python_to_decimal(True) is True
        assert python_to_decimal(False) is False

    def test_handles_float_precision(self):
        """Test that floats with precision issues are handled."""
        # This tests that we round to avoid floating point weirdness
        result = python_to_decimal(0.1 + 0.2)  # Famous floating point issue
        # The result should be close to 0.3, not 0.30000000000000004
        assert float(result) == pytest.approx(0.3, abs=1e-6)


class TestPrepareForDynamodb:
    """Tests for prepare_for_dynamodb function."""

    def test_prepares_simple_dict(self):
        """Test preparing a simple dictionary."""
        data = {"name": "Test Resort", "temperature": -5.0, "elevation": 1500}
        result = prepare_for_dynamodb(data)

        assert result["name"] == "Test Resort"
        assert result["temperature"] == Decimal("-5.0")
        assert result["elevation"] == Decimal("1500")

    def test_prepares_weather_condition(self):
        """Test preparing a typical weather condition item."""
        data = {
            "resort_id": "test-resort",
            "elevation_level": "base",
            "timestamp": "2026-01-20T10:00:00Z",
            "current_temp_celsius": -5.0,
            "min_temp_celsius": -8.0,
            "max_temp_celsius": -2.0,
            "snowfall_24h_cm": 15.0,
            "humidity_percent": 85.0,
            "snow_quality": "excellent",
            "ttl": 1737370000,
        }
        result = prepare_for_dynamodb(data)

        assert result["current_temp_celsius"] == Decimal("-5.0")
        assert result["snowfall_24h_cm"] == Decimal("15.0")
        assert result["humidity_percent"] == Decimal("85.0")
        assert result["ttl"] == Decimal("1737370000")
        assert result["resort_id"] == "test-resort"
        assert result["snow_quality"] == "excellent"


class TestParseFromDynamodb:
    """Tests for parse_from_dynamodb function."""

    def test_parses_simple_dict(self):
        """Test parsing a simple dictionary."""
        data = {
            "name": "Test Resort",
            "temperature": Decimal("-5.0"),
            "elevation": Decimal("1500"),
        }
        result = parse_from_dynamodb(data)

        assert result["name"] == "Test Resort"
        # Note: Decimal("-5.0") becomes int -5 since it's a whole number
        assert result["temperature"] == -5
        assert isinstance(result["temperature"], int)
        assert result["elevation"] == 1500
        assert isinstance(result["elevation"], int)

    def test_parses_weather_condition(self):
        """Test parsing a typical weather condition item from DynamoDB."""
        data = {
            "resort_id": "test-resort",
            "elevation_level": "base",
            "timestamp": "2026-01-20T10:00:00Z",
            "current_temp_celsius": Decimal("-5.0"),
            "min_temp_celsius": Decimal("-8.0"),
            "max_temp_celsius": Decimal("-2.0"),
            "snowfall_24h_cm": Decimal("15.0"),
            "humidity_percent": Decimal("85"),
            "snow_quality": "excellent",
            "ttl": Decimal("1737370000"),
        }
        result = parse_from_dynamodb(data)

        # Note: Whole number Decimals become ints
        assert result["current_temp_celsius"] == -5
        assert isinstance(result["current_temp_celsius"], int)
        assert result["snowfall_24h_cm"] == 15
        assert result["humidity_percent"] == 85
        assert isinstance(result["humidity_percent"], int)
        assert result["ttl"] == 1737370000
        assert result["resort_id"] == "test-resort"


class TestParseItemsFromDynamodb:
    """Tests for parse_items_from_dynamodb function."""

    def test_parses_list_of_items(self):
        """Test parsing a list of DynamoDB items."""
        items = [
            {
                "resort_id": "resort-1",
                "temperature": Decimal("-5.0"),
                "elevation": Decimal("1500"),
            },
            {
                "resort_id": "resort-2",
                "temperature": Decimal("-3.5"),
                "elevation": Decimal("2000"),
            },
        ]
        result = parse_items_from_dynamodb(items)

        assert len(result) == 2
        assert result[0]["temperature"] == -5.0
        assert result[1]["temperature"] == -3.5
        assert result[0]["elevation"] == 1500
        assert result[1]["elevation"] == 2000

    def test_parses_empty_list(self):
        """Test parsing an empty list."""
        result = parse_items_from_dynamodb([])
        assert result == []


class TestRoundTrip:
    """Tests for round-trip conversion (Python -> DynamoDB -> Python)."""

    def test_round_trip_preserves_data(self):
        """Test that data survives a round trip through conversion."""
        original = {
            "resort_id": "test-resort",
            "name": "Test Ski Resort",
            "elevation_points": [
                {
                    "level": "base",
                    "elevation_meters": 1500,
                    "latitude": 49.123456,
                    "longitude": -118.987654,
                }
            ],
            "weather": {"temperature": -5.5, "humidity": 85, "wind_speed": 15.3},
            "active": True,
            "notes": None,
        }

        # Convert to DynamoDB format and back
        dynamodb_format = prepare_for_dynamodb(original)
        recovered = parse_from_dynamodb(dynamodb_format)

        # Check that string values are preserved exactly
        assert recovered["resort_id"] == original["resort_id"]
        assert recovered["name"] == original["name"]

        # Check that numeric values are preserved (with appropriate types)
        assert recovered["elevation_points"][0]["elevation_meters"] == 1500
        assert recovered["elevation_points"][0]["latitude"] == pytest.approx(49.123456)
        assert recovered["elevation_points"][0]["longitude"] == pytest.approx(
            -118.987654
        )

        assert recovered["weather"]["temperature"] == pytest.approx(-5.5)
        assert recovered["weather"]["humidity"] == 85
        assert recovered["weather"]["wind_speed"] == pytest.approx(15.3)

        # Check that booleans and None are preserved
        assert recovered["active"] is True
        assert recovered["notes"] is None
