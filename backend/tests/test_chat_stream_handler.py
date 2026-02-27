"""Tests for chat_stream_handler._execute_tool (streaming chat tool dispatch)."""

from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_dynamodb_with_resort(resort_item=None):
    """Return a mock DynamoDB resource with resorts and conditions tables."""
    dynamodb = MagicMock()

    resorts_table = MagicMock()
    conditions_table = MagicMock()
    history_table = MagicMock()
    reports_table = MagicMock()

    if resort_item is not None:
        resorts_table.get_item.return_value = {"Item": resort_item}
    else:
        resorts_table.get_item.return_value = {}

    conditions_table.query.return_value = {"Items": []}
    history_table.query.return_value = {"Items": []}
    reports_table.query.return_value = {"Items": []}
    resorts_table.scan.return_value = {"Items": []}

    def table_factory(name):
        if "resorts" in name:
            return resorts_table
        if "weather-conditions" in name:
            return conditions_table
        if "daily-history" in name:
            return history_table
        if "condition-reports" in name:
            return reports_table
        return MagicMock()

    dynamodb.Table.side_effect = table_factory
    return dynamodb


SAMPLE_RESORT = {
    "resort_id": "whistler-blackcomb",
    "name": "Whistler Blackcomb",
    "country": "CA",
    "region": "na_west",
    "elevation_points": [
        {
            "level": "base",
            "latitude": Decimal("50.09"),
            "longitude": Decimal("-122.95"),
            "elevation_meters": Decimal("675"),
        },
        {
            "level": "mid",
            "latitude": Decimal("50.07"),
            "longitude": Decimal("-122.93"),
            "elevation_meters": Decimal("1500"),
        },
        {
            "level": "top",
            "latitude": Decimal("50.06"),
            "longitude": Decimal("-122.91"),
            "elevation_meters": Decimal("2284"),
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests for get_resort_forecast tool
# ---------------------------------------------------------------------------


class TestGetResortForecast:
    """Tests for the get_resort_forecast tool in chat_stream_handler."""

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_missing_resort_id(self):
        from handlers.chat_stream_handler import _execute_tool

        dynamodb = _mock_dynamodb_with_resort()
        result = _execute_tool("get_resort_forecast", {}, dynamodb)
        assert "error" in result
        assert "Missing resort_id" in result["error"]

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_resort_not_found(self):
        from handlers.chat_stream_handler import _execute_tool

        dynamodb = _mock_dynamodb_with_resort(resort_item=None)
        result = _execute_tool(
            "get_resort_forecast", {"resort_id": "nonexistent"}, dynamodb
        )
        assert "error" in result
        assert "not found" in result["error"]

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_no_elevation_data(self):
        from handlers.chat_stream_handler import _execute_tool

        resort = {
            "resort_id": "no-elevation",
            "name": "No Elevation Resort",
            "elevation_points": [],
        }
        dynamodb = _mock_dynamodb_with_resort(resort_item=resort)
        result = _execute_tool(
            "get_resort_forecast", {"resort_id": "no-elevation"}, dynamodb
        )
        assert "error" in result
        assert "No elevation data" in result["error"]

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    @patch("services.openmeteo_service.OpenMeteoService.get_timeline_data")
    def test_successful_forecast(self, mock_timeline):
        from handlers.chat_stream_handler import _execute_tool

        mock_timeline.return_value = {
            "data": [
                {
                    "date": "2026-02-26",
                    "time": "09:00",
                    "temperature_c": -5.0,
                    "snowfall_cm": 2.5,
                },
                {
                    "date": "2026-02-26",
                    "time": "12:00",
                    "temperature_c": -2.0,
                    "snowfall_cm": 1.0,
                },
                {
                    "date": "2026-02-26",
                    "time": "15:00",
                    "temperature_c": -3.0,
                    "snowfall_cm": 0.5,
                },
                {
                    "date": "2026-02-27",
                    "time": "09:00",
                    "temperature_c": -8.0,
                    "snowfall_cm": 10.0,
                },
                {
                    "date": "2026-02-27",
                    "time": "12:00",
                    "temperature_c": -6.0,
                    "snowfall_cm": 5.0,
                },
            ],
        }

        dynamodb = _mock_dynamodb_with_resort(resort_item=SAMPLE_RESORT)
        result = _execute_tool(
            "get_resort_forecast",
            {"resort_id": "whistler-blackcomb"},
            dynamodb,
        )

        assert result["resort_id"] == "whistler-blackcomb"
        assert result["resort_name"] == "Whistler Blackcomb"
        assert result["elevation_level"] == "mid"
        assert len(result["days"]) == 2

        day1 = result["days"][0]
        assert day1["date"] == "2026-02-26"
        assert day1["min_temp_c"] == -5.0
        assert day1["max_temp_c"] == -2.0
        assert day1["total_snowfall_cm"] == 4.0

        day2 = result["days"][1]
        assert day2["date"] == "2026-02-27"
        assert day2["min_temp_c"] == -8.0
        assert day2["max_temp_c"] == -6.0
        assert day2["total_snowfall_cm"] == 15.0

        # Verify Open-Meteo was called with mid elevation point
        mock_timeline.assert_called_once_with(
            latitude=50.07,
            longitude=-122.93,
            elevation_meters=1500,
            elevation_level="mid",
        )

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    @patch("services.openmeteo_service.OpenMeteoService.get_timeline_data")
    def test_prefers_mid_elevation(self, mock_timeline):
        """Should prefer mid > top > base elevation."""
        from handlers.chat_stream_handler import _execute_tool

        mock_timeline.return_value = {"data": []}
        dynamodb = _mock_dynamodb_with_resort(resort_item=SAMPLE_RESORT)
        _execute_tool(
            "get_resort_forecast",
            {"resort_id": "whistler-blackcomb"},
            dynamodb,
        )
        # mid elevation should be picked
        call_kwargs = mock_timeline.call_args[1]
        assert call_kwargs["elevation_meters"] == 1500
        assert call_kwargs["elevation_level"] == "mid"

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    @patch("services.openmeteo_service.OpenMeteoService.get_timeline_data")
    def test_falls_back_to_top_if_no_mid(self, mock_timeline):
        from handlers.chat_stream_handler import _execute_tool

        resort = {
            "resort_id": "top-only",
            "name": "Top Only Resort",
            "elevation_points": [
                {
                    "level": "base",
                    "latitude": Decimal("50.0"),
                    "longitude": Decimal("-122.0"),
                    "elevation_meters": Decimal("675"),
                },
                {
                    "level": "top",
                    "latitude": Decimal("50.1"),
                    "longitude": Decimal("-122.1"),
                    "elevation_meters": Decimal("2200"),
                },
            ],
        }
        mock_timeline.return_value = {"data": []}
        dynamodb = _mock_dynamodb_with_resort(resort_item=resort)
        _execute_tool("get_resort_forecast", {"resort_id": "top-only"}, dynamodb)
        call_kwargs = mock_timeline.call_args[1]
        assert call_kwargs["elevation_meters"] == 2200
        assert call_kwargs["elevation_level"] == "top"

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    @patch("services.openmeteo_service.OpenMeteoService.get_timeline_data")
    def test_openmeteo_failure_returns_error(self, mock_timeline):
        from handlers.chat_stream_handler import _execute_tool

        mock_timeline.side_effect = Exception("API timeout")
        dynamodb = _mock_dynamodb_with_resort(resort_item=SAMPLE_RESORT)
        result = _execute_tool(
            "get_resort_forecast",
            {"resort_id": "whistler-blackcomb"},
            dynamodb,
        )
        assert "error" in result
        assert "Failed to fetch forecast" in result["error"]

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    @patch("services.openmeteo_service.OpenMeteoService.get_timeline_data")
    def test_limits_to_7_days(self, mock_timeline):
        from handlers.chat_stream_handler import _execute_tool

        # Generate 10 days of data
        data_points = []
        for day in range(10):
            data_points.append(
                {
                    "date": f"2026-02-{20 + day:02d}",
                    "time": "12:00",
                    "temperature_c": -5.0,
                    "snowfall_cm": 1.0,
                }
            )
        mock_timeline.return_value = {"data": data_points}
        dynamodb = _mock_dynamodb_with_resort(resort_item=SAMPLE_RESORT)
        result = _execute_tool(
            "get_resort_forecast",
            {"resort_id": "whistler-blackcomb"},
            dynamodb,
        )
        assert len(result["days"]) == 7
