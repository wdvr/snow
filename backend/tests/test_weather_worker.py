"""Tests for the weather worker Lambda handler.

Tests cover:
- save_weather_condition: DynamoDB writes, error handling
- process_elevation_point: dict and object elevation points, scraper merging,
  snow summary updates (freeze events, delta tracking, openmeteo accumulation),
  snowfall window consistency, quality attributes, error handling
- weather_worker_handler: full Lambda handler flow, batch DynamoDB fetches,
  parallel processing, rate limiting, scraper integration, error handling,
  empty inputs, statistics tracking
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from botocore.exceptions import ClientError

from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition

# ---------------------------------------------------------------------------
# Module path for patching
# ---------------------------------------------------------------------------
MODULE = "handlers.weather_worker"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_weather_data(**overrides):
    """Return a plausible weather-data dict as returned by OpenMeteoService."""
    defaults = {
        "current_temp_celsius": -5.0,
        "min_temp_celsius": -8.0,
        "max_temp_celsius": -2.0,
        "snowfall_24h_cm": 10.0,
        "snowfall_48h_cm": 15.0,
        "snowfall_72h_cm": 20.0,
        "hours_above_ice_threshold": 0.0,
        "max_consecutive_warm_hours": 0.0,
        "snowfall_after_freeze_cm": 10.0,
        "hours_since_last_snowfall": 2.0,
        "last_freeze_thaw_hours_ago": 72.0,
        "currently_warming": False,
        "humidity_percent": 80.0,
        "wind_speed_kmh": 12.0,
        "weather_description": "Light snow",
        "data_source": "open-meteo",
        "source_confidence": "high",
        "snow_depth_cm": 120.0,
    }
    defaults.update(overrides)
    return defaults


def _make_elevation_point_obj(level="mid", lat=49.72, lon=-118.93, elev=1800):
    """Create a minimal elevation-point-like object (non-dict)."""
    return SimpleNamespace(
        level=SimpleNamespace(value=level),
        latitude=lat,
        longitude=lon,
        elevation_meters=elev,
    )


def _make_elevation_point_dict(level="mid", lat=49.72, lon=-118.93, elev=1800):
    """Create a dict-format elevation point (as stored in DynamoDB)."""
    return {
        "latitude": lat,
        "longitude": lon,
        "elevation_meters": elev,
        "level": level,
    }


def _make_resort_data(
    resort_id="big-white",
    name="Big White",
    elevation_points=None,
):
    """Create a resort data dict as returned from DynamoDB batch_get_item."""
    if elevation_points is None:
        elevation_points = [
            _make_elevation_point_dict("base", elev=1508),
            _make_elevation_point_dict("mid", elev=1800),
            _make_elevation_point_dict("top", elev=2319),
        ]
    return {
        "resort_id": resort_id,
        "name": name,
        "elevation_points": elevation_points,
    }


def _make_condition():
    """Create a minimal WeatherCondition for testing."""
    return WeatherCondition(
        resort_id="big-white",
        elevation_level="mid",
        timestamp=datetime.now(UTC).isoformat(),
        current_temp_celsius=-5.0,
        min_temp_celsius=-8.0,
        max_temp_celsius=-2.0,
        data_source="open-meteo",
        source_confidence=ConfidenceLevel.HIGH,
    )


def _make_lambda_context():
    """Create a mock Lambda context object."""
    ctx = SimpleNamespace()
    ctx.get_remaining_time_in_millis = lambda: 300000
    return ctx


def _default_summary(freeze_date="2026-02-15"):
    """Create a default snow summary dict."""
    return {
        "last_freeze_date": freeze_date,
        "snowfall_since_freeze_cm": 5.0,
        "total_season_snowfall_cm": 100.0,
        "season_start_date": "2025-11-15",
        "last_snowfall_24h_cm": 3.0,
    }


def _setup_services(weather_data=None, quality_result=None, existing_summary=None):
    """Set up mock services with defaults."""
    weather_service = MagicMock()
    weather_service.get_current_weather.return_value = (
        weather_data or _make_weather_data()
    )

    snow_quality_service = MagicMock()
    snow_quality_service.assess_snow_quality.return_value = quality_result or (
        SnowQuality.GOOD,
        12.0,
        ConfidenceLevel.HIGH,
        4.5,
    )

    table = MagicMock()
    table.put_item.return_value = {}

    snow_summary_service = MagicMock()
    snow_summary_service.get_or_create_summary.return_value = (
        existing_summary or _default_summary()
    )

    return weather_service, snow_quality_service, table, snow_summary_service


# ---------------------------------------------------------------------------
# Tests for save_weather_condition
# ---------------------------------------------------------------------------


class TestSaveWeatherCondition:
    """Tests for saving a weather condition to DynamoDB."""

    def test_save_success(self):
        from handlers.weather_worker import save_weather_condition

        table = MagicMock()
        table.put_item.return_value = {}
        condition = _make_condition()

        save_weather_condition(table, condition)

        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["resort_id"] is not None

    def test_save_calls_prepare_for_dynamodb(self):
        """Verify that prepare_for_dynamodb is called before put_item."""
        from handlers.weather_worker import save_weather_condition

        table = MagicMock()
        table.put_item.return_value = {}
        condition = _make_condition()

        with patch(f"{MODULE}.prepare_for_dynamodb", wraps=lambda x: x) as mock_prep:
            save_weather_condition(table, condition)
            mock_prep.assert_called_once()

    def test_save_client_error_raises(self):
        from handlers.weather_worker import save_weather_condition

        table = MagicMock()
        table.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Rate exceeded",
                }
            },
            "PutItem",
        )
        condition = _make_condition()

        with pytest.raises(ClientError):
            save_weather_condition(table, condition)

    def test_save_unexpected_error_raises(self):
        from handlers.weather_worker import save_weather_condition

        table = MagicMock()
        table.put_item.side_effect = ValueError("unexpected")
        condition = _make_condition()

        with pytest.raises(ValueError):
            save_weather_condition(table, condition)


# ---------------------------------------------------------------------------
# Tests for process_elevation_point
# ---------------------------------------------------------------------------


class TestProcessElevationPoint:
    """Tests for processing a single elevation point."""

    def test_success_with_dict_elevation_point(self):
        """Dict-format elevation points (from DynamoDB) should work."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        assert result["error"] is None
        assert result["level"] == "mid"
        table.put_item.assert_called_once()

    def test_success_with_object_elevation_point(self):
        """Object-format elevation points with .level.value should work."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_obj("top")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        assert result["level"] == "top"

    def test_object_level_plain_string(self):
        """When elevation_point.level is a plain string (no .value)."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = SimpleNamespace(
            level="base",
            latitude=49.72,
            longitude=-118.93,
            elevation_meters=1508,
        )

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        assert result["level"] == "base"

    def test_without_scraper(self):
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("base")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="test-resort",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        ws.get_current_weather.assert_called_once()

    def test_with_scraper_data(self):
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("top")

        scraper = MagicMock()
        scraped_data = SimpleNamespace(snowfall_24h_cm=20.0, snowfall_48h_cm=30.0)
        merged_data = _make_weather_data(snowfall_24h_cm=20.0)
        scraper.merge_with_weather_data.return_value = merged_data

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="test-resort",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=scraper,
            scraped_data=scraped_data,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        scraper.merge_with_weather_data.assert_called_once()

    def test_scraper_not_called_without_scraped_data(self):
        """If scraped_data is None, scraper.merge should not be called."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("mid")
        scraper = MagicMock()

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="test-resort",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=scraper,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        scraper.merge_with_weather_data.assert_not_called()

    def test_without_snow_summary_service(self):
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, _ = _setup_services()
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=None,
        )

        assert result["success"] is True

    def test_freeze_event_detected(self):
        """When a new freeze event is detected, record_freeze_event should be called."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=True,
            detected_freeze_date="2026-02-20T12:00",
            snowfall_after_freeze_cm=5.0,
        )
        ws, sqs, table, sss = _setup_services(weather_data=weather_data)
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        sss.record_freeze_event.assert_called_once_with(
            resort_id="big-white",
            elevation_level="mid",
            freeze_date="2026-02-20T12:00",
        )
        sss.update_summary.assert_called_once()

    def test_freeze_event_updates_season_totals(self):
        """Freeze event update should accumulate total_season_snowfall."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=True,
            detected_freeze_date="2026-02-20",
            snowfall_after_freeze_cm=5.0,
            snowfall_24h_cm=8.0,
        )
        existing_summary = _default_summary()
        existing_summary["total_season_snowfall_cm"] = 200.0
        ws, sqs, table, sss = _setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        call_kwargs = sss.update_summary.call_args[1]
        assert call_kwargs["snowfall_since_freeze_cm"] == 5.0
        assert call_kwargs["total_season_snowfall_cm"] == 208.0  # 200 + 8

    def test_no_freeze_openmeteo_can_see_freeze(self):
        """When last_freeze_thaw_hours_ago < 336, use Open-Meteo accumulation."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=15.0,
            last_freeze_thaw_hours_ago=100,
        )
        existing_summary = {
            "last_freeze_date": "2026-02-10",
            "snowfall_since_freeze_cm": 10.0,
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
            "last_snowfall_24h_cm": 3.0,
        }
        ws, sqs, table, sss = _setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        sss.record_freeze_event.assert_not_called()
        sss.update_summary.assert_called_once()
        call_kwargs = sss.update_summary.call_args[1]
        # Uses openmeteo accumulation directly
        assert call_kwargs["snowfall_since_freeze_cm"] == 15.0
        # total_season adds the delta: 200 + max(0, 15 - 10) = 205
        assert call_kwargs["total_season_snowfall_cm"] == 205.0

    def test_no_freeze_older_than_14_days_delta_tracking(self):
        """When freeze > 336h, use delta tracking based on 24h snowfall change."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=8.0,
            last_freeze_thaw_hours_ago=400,  # > 336 hours
            snowfall_24h_cm=5.0,
        )
        existing_summary = {
            "last_freeze_date": "2026-02-01",
            "snowfall_since_freeze_cm": 20.0,
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
            "last_snowfall_24h_cm": 3.0,
        }
        ws, sqs, table, sss = _setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point_dict("top")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        sss.update_summary.assert_called_once()
        call_kwargs = sss.update_summary.call_args[1]
        # delta = max(0, 5.0 - 3.0) = 2.0
        # new accumulation = 20.0 + 2.0 = 22.0
        assert call_kwargs["snowfall_since_freeze_cm"] == 22.0
        # total = 200 + 2.0 = 202.0
        assert call_kwargs["total_season_snowfall_cm"] == 202.0
        assert call_kwargs["last_snowfall_24h_cm"] == 5.0

    def test_no_freeze_older_than_14_days_negative_delta_clamped(self):
        """Negative delta (24h dropped) should be clamped to 0."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=8.0,
            last_freeze_thaw_hours_ago=400,
            snowfall_24h_cm=2.0,  # Less than previous 3.0
        )
        existing_summary = {
            "last_freeze_date": "2026-02-01",
            "snowfall_since_freeze_cm": 20.0,
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
            "last_snowfall_24h_cm": 3.0,
        }
        ws, sqs, table, sss = _setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        call_kwargs = sss.update_summary.call_args[1]
        # delta = max(0, 2.0 - 3.0) = 0.0
        assert call_kwargs["snowfall_since_freeze_cm"] == 20.0  # unchanged
        assert call_kwargs["total_season_snowfall_cm"] == 200.0  # unchanged

    def test_no_freeze_uses_max_accumulation_for_weather_data(self):
        """Weather data should use the higher of openmeteo vs existing accumulation."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=5.0,
            last_freeze_thaw_hours_ago=100,
        )
        existing_summary = {
            "last_freeze_date": "2026-02-10",
            "snowfall_since_freeze_cm": 12.0,  # Higher than openmeteo's 5.0
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
            "last_snowfall_24h_cm": 3.0,
        }
        ws, sqs, table, sss = _setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        # The weather_data passed to WeatherCondition should have the higher value
        # Check what was passed to assess_snow_quality
        call_args = sqs.assess_snow_quality.call_args
        condition = call_args[0][0]
        assert condition.snowfall_after_freeze_cm == 12.0  # max(5.0, 12.0)

    def test_snowfall_window_consistency_48h_fix(self):
        """48h snowfall should be bumped up to match 24h if lower."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            snowfall_24h_cm=15.0,
            snowfall_48h_cm=10.0,  # inconsistent: less than 24h
            snowfall_72h_cm=20.0,
        )
        ws, sqs, table, sss = _setup_services(weather_data=weather_data)
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        # The condition created should have consistent windows
        condition = sqs.assess_snow_quality.call_args[0][0]
        assert condition.snowfall_48h_cm >= condition.snowfall_24h_cm

    def test_snowfall_window_consistency_72h_fix(self):
        """72h snowfall should be bumped up to match 48h if lower."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            snowfall_24h_cm=10.0,
            snowfall_48h_cm=20.0,
            snowfall_72h_cm=15.0,  # inconsistent: less than 48h
        )
        ws, sqs, table, sss = _setup_services(weather_data=weather_data)
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        condition = sqs.assess_snow_quality.call_args[0][0]
        assert condition.snowfall_72h_cm >= condition.snowfall_48h_cm

    def test_snowfall_window_both_inconsistent(self):
        """Both 48h and 72h should be fixed when both are inconsistent."""
        from handlers.weather_worker import process_elevation_point

        weather_data = _make_weather_data(
            snowfall_24h_cm=25.0,
            snowfall_48h_cm=10.0,  # < 24h
            snowfall_72h_cm=5.0,  # < 48h after fix
        )
        ws, sqs, table, sss = _setup_services(weather_data=weather_data)
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        condition = sqs.assess_snow_quality.call_args[0][0]
        # After fixing: 48h = 25.0 (bumped to match 24h), 72h = 25.0 (bumped to match 48h)
        assert condition.snowfall_48h_cm == 25.0
        assert condition.snowfall_72h_cm == 25.0

    def test_quality_attributes_set(self):
        """The weather condition should carry quality assessment results."""
        from handlers.weather_worker import process_elevation_point

        quality_result = (SnowQuality.EXCELLENT, 15.0, ConfidenceLevel.VERY_HIGH, 5.5)
        ws, sqs, table, sss = _setup_services(quality_result=quality_result)
        ep = _make_elevation_point_dict("top")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is True
        # Verify the condition saved to DynamoDB has quality attributes
        saved_item = table.put_item.call_args[1]["Item"]
        assert saved_item["snow_quality"] == SnowQuality.EXCELLENT.value
        assert saved_item["fresh_snow_cm"] == 15.0
        assert saved_item["confidence_level"] == ConfidenceLevel.VERY_HIGH.value
        assert saved_item["quality_score"] == 5.5

    def test_ttl_is_set(self):
        """Weather condition should have a TTL set."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("mid")

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        saved_item = table.put_item.call_args[1]["Item"]
        assert "ttl" in saved_item
        # TTL should be approximately 60 days from now
        expected_min = int(datetime.now(UTC).timestamp()) + 59 * 24 * 60 * 60
        expected_max = int(datetime.now(UTC).timestamp()) + 61 * 24 * 60 * 60
        assert expected_min <= saved_item["ttl"] <= expected_max

    def test_error_in_weather_service(self):
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ws.get_current_weather.side_effect = RuntimeError("API timeout")
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is False
        assert "API timeout" in result["error"]

    def test_error_in_dynamodb_save(self):
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Bad item"}},
            "PutItem",
        )
        ep = _make_elevation_point_dict("mid")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is False
        assert result["error"] is not None

    def test_error_preserves_level(self):
        """Even on error, the level should be captured from the elevation point."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ws.get_current_weather.side_effect = RuntimeError("fail")
        ep = _make_elevation_point_dict("top")

        result = process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        assert result["success"] is False
        assert result["level"] == "top"

    def test_passes_last_known_freeze_date_to_weather_service(self):
        """Weather service should receive the last_known_freeze_date from summary."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_dict("mid", lat=49.7, lon=-118.9, elev=1800)

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        ws.get_current_weather.assert_called_once_with(
            latitude=49.7,
            longitude=-118.9,
            elevation_meters=1800,
            last_known_freeze_date="2026-02-15",
        )

    def test_elevation_passed_to_quality_service(self):
        """Snow quality service should receive elevation_m for ML model."""
        from handlers.weather_worker import process_elevation_point

        ws, sqs, table, sss = _setup_services()
        ep = _make_elevation_point_obj("mid", elev=2000)

        process_elevation_point(
            elevation_point=ep,
            resort_id="big-white",
            weather_service=ws,
            snow_quality_service=sqs,
            weather_conditions_table=table,
            scraper=None,
            scraped_data=None,
            snow_summary_service=sss,
        )

        call_kwargs = sqs.assess_snow_quality.call_args[1]
        assert call_kwargs["elevation_m"] == 2000


# ---------------------------------------------------------------------------
# Tests for weather_worker_handler
# ---------------------------------------------------------------------------


TABLE_NAME = "snow-tracker-resorts-dev"


class TestWeatherWorkerHandler:
    """Tests for the main Lambda handler."""

    def _patch_all(self):
        """Return a context manager that patches all handler dependencies."""
        return (
            patch(f"{MODULE}.dynamodb"),
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
        )

    def test_empty_resort_ids_returns_400(self):
        from handlers.weather_worker import weather_worker_handler

        result = weather_worker_handler({"resort_ids": []}, _make_lambda_context())

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "No resort_ids" in body["error"]

    def test_missing_resort_ids_returns_400(self):
        from handlers.weather_worker import weather_worker_handler

        result = weather_worker_handler({}, _make_lambda_context())

        assert result["statusCode"] == 400

    def test_successful_single_resort_processing(self):
        from handlers.weather_worker import weather_worker_handler

        resort_data = _make_resort_data(
            resort_id="big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService") as mock_ws_cls,
            patch(f"{MODULE}.SnowQualityService") as mock_sqs_cls,
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort_data]}
            }
            mock_pep.return_value = {
                "success": True,
                "error": None,
                "level": "mid",
            }

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["resorts_processed"] == 1
        assert body["stats"]["conditions_saved"] == 1
        assert body["stats"]["errors"] == 0

    def test_multiple_resorts_processing(self):
        from handlers.weather_worker import weather_worker_handler

        resort1 = _make_resort_data(
            "resort-1",
            elevation_points=[_make_elevation_point_dict("mid")],
        )
        resort2 = _make_resort_data(
            "resort-2",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort1, resort2]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["resort-1", "resort-2"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["resorts_processed"] == 2
        assert body["stats"]["conditions_saved"] == 2

    def test_multiple_elevation_points(self):
        """Each elevation point should be processed."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[
                _make_elevation_point_dict("base"),
                _make_elevation_point_dict("mid"),
                _make_elevation_point_dict("top"),
            ],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["elevation_points_processed"] == 3
        assert body["stats"]["conditions_saved"] == 3
        assert mock_pep.call_count == 3

    def test_resort_with_no_elevation_points(self):
        """Resort with empty elevation_points should increment errors and skip."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data("empty-resort", elevation_points=[])

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }

            event = {"resort_ids": ["empty-resort"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["errors"] == 1
        assert body["stats"]["resorts_processed"] == 0
        mock_pep.assert_not_called()

    def test_elevation_point_failure_counted_as_error(self):
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "test-resort",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {
                "success": False,
                "error": "API failure",
                "level": "mid",
            }

            event = {"resort_ids": ["test-resort"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["errors"] == 1
        assert body["stats"]["conditions_saved"] == 0
        # Resort is still counted as processed even with elevation errors
        assert body["stats"]["resorts_processed"] == 1

    def test_batch_get_item_pagination(self):
        """Should handle more than 100 resort IDs by batching."""
        from handlers.weather_worker import weather_worker_handler

        resort_ids = [f"resort-{i}" for i in range(150)]
        resort_batch1 = [
            _make_resort_data(
                f"resort-{i}", elevation_points=[_make_elevation_point_dict("mid")]
            )
            for i in range(100)
        ]
        resort_batch2 = [
            _make_resort_data(
                f"resort-{i}", elevation_points=[_make_elevation_point_dict("mid")]
            )
            for i in range(100, 150)
        ]

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.side_effect = [
                {"Responses": {TABLE_NAME: resort_batch1}},
                {"Responses": {TABLE_NAME: resort_batch2}},
            ]
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": resort_ids, "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        assert mock_ddb.meta.client.batch_get_item.call_count == 2
        body = json.loads(result["body"])
        assert body["stats"]["resorts_processed"] == 150

    def test_scraper_enabled_hit(self):
        """Scraper hit should be counted in stats."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{MODULE}.ENABLE_SCRAPING", True),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            scraper = mock_scraper_cls.return_value
            scraper.is_resort_supported.return_value = True
            scraper.get_snow_report.return_value = SimpleNamespace(snowfall_24h_cm=20.0)
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["scraper_hits"] == 1
        assert body["stats"]["scraper_misses"] == 0

    def test_scraper_miss(self):
        """When scraper returns None, it should count as a miss."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{MODULE}.ENABLE_SCRAPING", True),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            scraper = mock_scraper_cls.return_value
            scraper.is_resort_supported.return_value = True
            scraper.get_snow_report.return_value = None
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["scraper_misses"] == 1

    def test_scraper_exception_counted_as_miss(self):
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{MODULE}.ENABLE_SCRAPING", True),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            scraper = mock_scraper_cls.return_value
            scraper.is_resort_supported.return_value = True
            scraper.get_snow_report.side_effect = RuntimeError("Scrape error")
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["scraper_misses"] == 1

    def test_scraper_disabled(self):
        """When scraping is disabled, scraper should not be initialized."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        mock_scraper_cls.assert_not_called()

    def test_resort_not_supported_by_scraper(self):
        """If scraper doesn't support the resort, scraping should be skipped."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "chamonix",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{MODULE}.ENABLE_SCRAPING", True),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            scraper = mock_scraper_cls.return_value
            scraper.is_resort_supported.return_value = False
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["chamonix"], "region": "alps"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        scraper.get_snow_report.assert_not_called()
        assert body["stats"]["scraper_hits"] == 0
        assert body["stats"]["scraper_misses"] == 0

    def test_resort_level_exception_caught(self):
        """An exception during resort processing should be caught, not crash."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "bad-resort",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.ThreadPoolExecutor") as mock_tpe,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_tpe.return_value.__enter__ = MagicMock(
                side_effect=RuntimeError("Thread pool error")
            )
            mock_tpe.return_value.__exit__ = MagicMock(return_value=False)

            event = {"resort_ids": ["bad-resort"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["errors"] >= 1

    def test_fatal_error_returns_500(self):
        """A fatal initialization error should return 500."""
        from handlers.weather_worker import weather_worker_handler

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService") as mock_ws_cls,
        ):
            mock_ws_cls.side_effect = RuntimeError("Service init failed")

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "failed" in body["message"].lower()
        assert "Service init failed" in body["error"]

    def test_region_in_stats(self):
        """Stats should contain the region from the event."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "alps"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["region"] == "alps"

    def test_default_region_unknown(self):
        """When no region is provided, should default to 'unknown'."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"]}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["region"] == "unknown"

    def test_stats_contain_timing_info(self):
        """Response should contain start_time, end_time, and duration_seconds."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        stats = body["stats"]
        assert "start_time" in stats
        assert "end_time" in stats
        assert "duration_seconds" in stats
        assert stats["duration_seconds"] >= 0

    def test_inter_resort_delay(self):
        """time.sleep should be called between resorts when INTER_RESORT_DELAY > 0."""
        from handlers.weather_worker import weather_worker_handler

        resort1 = _make_resort_data(
            "resort-1",
            elevation_points=[_make_elevation_point_dict("mid")],
        )
        resort2 = _make_resort_data(
            "resort-2",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 1.5),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.time.sleep") as mock_sleep,
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort1, resort2]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["resort-1", "resort-2"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        # sleep should be called once per resort
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.5)

    def test_no_delay_when_zero(self):
        """time.sleep should not be called when INTER_RESORT_DELAY is 0."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.time.sleep") as mock_sleep,
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        mock_sleep.assert_not_called()

    def test_batch_get_empty_response(self):
        """When DynamoDB returns empty Responses, handler should still complete."""
        from handlers.weather_worker import weather_worker_handler

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {"Responses": {}}

            event = {"resort_ids": ["nonexistent"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["resorts_processed"] == 0

    def test_parallel_elevation_processing_uses_thread_pool(self):
        """Verify ThreadPoolExecutor is used for elevation point processing.

        Rather than mocking ThreadPoolExecutor (which breaks as_completed),
        we let the real executor run and verify process_elevation_point is
        called for each elevation point concurrently.
        """
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[
                _make_elevation_point_dict("base"),
                _make_elevation_point_dict("mid"),
                _make_elevation_point_dict("top"),
            ],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.ELEVATION_CONCURRENCY", 3),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        # All 3 elevation points should have been submitted
        assert mock_pep.call_count == 3
        body = json.loads(result["body"])
        assert body["stats"]["conditions_saved"] == 3

    def test_mixed_success_and_failure_elevation_points(self):
        """Some elevation points succeed and some fail."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[
                _make_elevation_point_dict("base"),
                _make_elevation_point_dict("mid"),
                _make_elevation_point_dict("top"),
            ],
        )

        call_count = 0

        def alternating_result(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return {"success": False, "error": "API error", "level": "mid"}
            return {"success": True, "error": None, "level": "base"}

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.side_effect = alternating_result

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert body["stats"]["conditions_saved"] == 2
        assert body["stats"]["errors"] == 1

    def test_handler_uses_correct_table_names(self):
        """Handler should use table names from environment variables."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        # Verify DynamoDB Table was called with correct table names
        table_calls = [str(c) for c in mock_ddb.Table.call_args_list]
        assert any("snow-tracker-resorts" in c for c in table_calls)
        assert any("snow-tracker-weather-conditions" in c for c in table_calls)
        assert any("snow-tracker-snow-summary" in c for c in table_calls)

    def test_success_message_in_response(self):
        """Response body should contain a descriptive success message."""
        from handlers.weather_worker import weather_worker_handler

        resort = _make_resort_data(
            "big-white",
            elevation_points=[_make_elevation_point_dict("mid")],
        )

        with (
            patch(f"{MODULE}.dynamodb") as mock_ddb,
            patch(f"{MODULE}.OpenMeteoService"),
            patch(f"{MODULE}.SnowQualityService"),
            patch(f"{MODULE}.SnowSummaryService"),
            patch(f"{MODULE}.OnTheSnowScraper"),
            patch(f"{MODULE}.ENABLE_SCRAPING", False),
            patch(f"{MODULE}.INTER_RESORT_DELAY", 0.0),
            patch(f"{MODULE}.RESORTS_TABLE", TABLE_NAME),
            patch(f"{MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_ddb.meta.client.batch_get_item.return_value = {
                "Responses": {TABLE_NAME: [resort]}
            }
            mock_pep.return_value = {"success": True, "error": None, "level": "mid"}

            event = {"resort_ids": ["big-white"], "region": "na_west"}
            result = weather_worker_handler(event, _make_lambda_context())

        body = json.loads(result["body"])
        assert "Processed 1 resorts" in body["message"]
