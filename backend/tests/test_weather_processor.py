"""Tests for the weather processor Lambda handler."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_elevation_point(level="mid", lat=49.72, lon=-118.93, elev=1800):
    """Create a minimal elevation-point-like object."""
    return SimpleNamespace(
        level=SimpleNamespace(value=level),
        latitude=lat,
        longitude=lon,
        elevation_meters=elev,
    )


def _make_resort(
    resort_id="big-white", name="Big White", region="na_west", elevation_points=None
):
    """Create a minimal resort-like object."""
    if elevation_points is None:
        elevation_points = [
            _make_elevation_point("base", elev=1508),
            _make_elevation_point("mid", elev=1800),
            _make_elevation_point("top", elev=2319),
        ]
    return SimpleNamespace(
        resort_id=resort_id,
        name=name,
        region=region,
        elevation_points=elevation_points,
    )


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


def _make_lambda_context(remaining_ms=300000):
    """Create a mock Lambda context object."""
    ctx = SimpleNamespace()
    ctx.get_remaining_time_in_millis = lambda: remaining_ms
    return ctx


# ---------------------------------------------------------------------------
# Tests for get_remaining_time_ms
# ---------------------------------------------------------------------------


class TestGetRemainingTimeMs:
    """Tests for the get_remaining_time_ms helper."""

    def test_with_valid_context(self):
        from handlers.weather_processor import get_remaining_time_ms

        ctx = _make_lambda_context(remaining_ms=120000)
        assert get_remaining_time_ms(ctx) == 120000

    def test_with_none_context(self):
        from handlers.weather_processor import get_remaining_time_ms

        assert get_remaining_time_ms(None) == 600000

    def test_with_context_missing_method(self):
        """A context without get_remaining_time_in_millis returns default."""
        from handlers.weather_processor import get_remaining_time_ms

        ctx = SimpleNamespace()  # no method
        assert get_remaining_time_ms(ctx) == 600000

    def test_with_false_like_context(self):
        """Passing a falsy non-None value (e.g. 0, empty dict) returns default."""
        from handlers.weather_processor import get_remaining_time_ms

        assert get_remaining_time_ms(0) == 600000
        assert get_remaining_time_ms({}) == 600000

    def test_with_large_remaining_time(self):
        from handlers.weather_processor import get_remaining_time_ms

        ctx = _make_lambda_context(remaining_ms=900000)
        assert get_remaining_time_ms(ctx) == 900000


# ---------------------------------------------------------------------------
# Tests for save_weather_condition
# ---------------------------------------------------------------------------


class TestSaveWeatherCondition:
    """Tests for saving a weather condition to DynamoDB."""

    def _make_condition(self):
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

    def test_save_success(self):
        from handlers.weather_processor import save_weather_condition

        table = MagicMock()
        table.put_item.return_value = {}
        condition = self._make_condition()

        save_weather_condition(table, condition)

        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["resort_id"] is not None

    def test_save_client_error_raises(self):
        from handlers.weather_processor import save_weather_condition

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
        condition = self._make_condition()

        with pytest.raises(ClientError):
            save_weather_condition(table, condition)

    def test_save_unexpected_error_raises(self):
        from handlers.weather_processor import save_weather_condition

        table = MagicMock()
        table.put_item.side_effect = ValueError("unexpected")
        condition = self._make_condition()

        with pytest.raises(ValueError):
            save_weather_condition(table, condition)


# ---------------------------------------------------------------------------
# Tests for process_elevation_point
# ---------------------------------------------------------------------------


class TestProcessElevationPoint:
    """Tests for processing a single elevation point."""

    def _setup_services(
        self, weather_data=None, quality_result=None, existing_summary=None
    ):
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
        snow_summary_service.get_or_create_summary.return_value = existing_summary or {
            "last_freeze_date": "2026-02-15",
            "snowfall_since_freeze_cm": 5.0,
            "total_season_snowfall_cm": 100.0,
            "season_start_date": "2025-11-15",
        }

        return weather_service, snow_quality_service, table, snow_summary_service

    def test_success_basic(self):
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, sss = self._setup_services()
        ep = _make_elevation_point("mid")

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
        assert result["weather_condition"] is not None
        table.put_item.assert_called_once()

    def test_success_without_scraper(self):
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, sss = self._setup_services()
        ep = _make_elevation_point("base")

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
        # Scraper merge should not have been called
        ws.get_current_weather.assert_called_once()

    def test_success_with_scraper_data(self):
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, sss = self._setup_services()
        ep = _make_elevation_point("top")

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

    def test_success_without_snow_summary_service(self):
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, _ = self._setup_services()
        ep = _make_elevation_point("mid")

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
        # No summary calls should happen
        assert result["weather_condition"] is not None

    def test_freeze_event_detected(self):
        from handlers.weather_processor import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=True,
            detected_freeze_date="2026-02-20",
            snowfall_after_freeze_cm=5.0,
        )
        ws, sqs, table, sss = self._setup_services(weather_data=weather_data)
        ep = _make_elevation_point("mid")

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
            freeze_date="2026-02-20",
        )
        sss.update_summary.assert_called_once()

    def test_no_freeze_event_openmeteo_can_see_freeze(self):
        """When last_freeze_thaw_hours_ago < 336, use Open-Meteo accumulation."""
        from handlers.weather_processor import process_elevation_point

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
        }
        ws, sqs, table, sss = self._setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point("mid")

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
        assert call_kwargs["snowfall_since_freeze_cm"] == 15.0

    def test_no_freeze_event_freeze_older_than_14_days_with_snowfall(self):
        """When freeze is older than 14 days AND there is new snowfall."""
        from handlers.weather_processor import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=8.0,
            last_freeze_thaw_hours_ago=400,  # > 336 hours
            snowfall_24h_cm=3.0,
        )
        existing_summary = {
            "last_freeze_date": "2026-02-01",
            "snowfall_since_freeze_cm": 20.0,
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
        }
        ws, sqs, table, sss = self._setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point("top")

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
        # existing 20.0 + 3.0 new snowfall
        assert call_kwargs["snowfall_since_freeze_cm"] == 23.0

    def test_no_freeze_event_freeze_older_than_14_days_no_snowfall(self):
        """When freeze is older than 14 days but zero new snowfall, no update."""
        from handlers.weather_processor import process_elevation_point

        weather_data = _make_weather_data(
            freeze_event_detected=False,
            snowfall_after_freeze_cm=8.0,
            last_freeze_thaw_hours_ago=400,
            snowfall_24h_cm=0.0,
        )
        existing_summary = {
            "last_freeze_date": "2026-02-01",
            "snowfall_since_freeze_cm": 20.0,
            "total_season_snowfall_cm": 200.0,
            "season_start_date": "2025-11-15",
        }
        ws, sqs, table, sss = self._setup_services(
            weather_data=weather_data, existing_summary=existing_summary
        )
        ep = _make_elevation_point("base")

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
        # No update_summary call when no new snowfall and freeze > 14 days
        sss.update_summary.assert_not_called()

    def test_error_in_weather_service(self):
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, sss = self._setup_services()
        ws.get_current_weather.side_effect = RuntimeError("API timeout")
        ep = _make_elevation_point("mid")

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
        assert result["weather_condition"] is None

    def test_level_without_value_attribute(self):
        """When elevation_point.level is a plain string rather than an enum."""
        from handlers.weather_processor import process_elevation_point

        ws, sqs, table, sss = self._setup_services()
        ep = SimpleNamespace(
            level="top",  # plain string, no .value
            latitude=49.72,
            longitude=-118.93,
            elevation_meters=2319,
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
        assert result["level"] == "top"

    def test_snowfall_window_consistency_48h_fix(self):
        """48h snowfall should be bumped up to match 24h if lower."""
        from handlers.weather_processor import process_elevation_point

        weather_data = _make_weather_data(
            snowfall_24h_cm=15.0,
            snowfall_48h_cm=10.0,  # inconsistent: less than 24h
            snowfall_72h_cm=20.0,
        )
        ws, sqs, table, sss = self._setup_services(weather_data=weather_data)
        ep = _make_elevation_point("mid")

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
        wc = result["weather_condition"]
        # 48h should have been bumped to at least 24h
        assert wc.snowfall_48h_cm >= wc.snowfall_24h_cm

    def test_snowfall_window_consistency_72h_fix(self):
        """72h snowfall should be bumped up to match 48h if lower."""
        from handlers.weather_processor import process_elevation_point

        weather_data = _make_weather_data(
            snowfall_24h_cm=10.0,
            snowfall_48h_cm=20.0,
            snowfall_72h_cm=15.0,  # inconsistent: less than 48h
        )
        ws, sqs, table, sss = self._setup_services(weather_data=weather_data)
        ep = _make_elevation_point("mid")

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
        wc = result["weather_condition"]
        assert wc.snowfall_72h_cm >= wc.snowfall_48h_cm

    def test_quality_attributes_set(self):
        """The weather condition object should carry quality assessment results."""
        from handlers.weather_processor import process_elevation_point

        quality_result = (SnowQuality.EXCELLENT, 15.0, ConfidenceLevel.VERY_HIGH, 5.5)
        ws, sqs, table, sss = self._setup_services(quality_result=quality_result)
        ep = _make_elevation_point("top")

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
        wc = result["weather_condition"]
        assert wc.snow_quality == SnowQuality.EXCELLENT.value
        assert wc.fresh_snow_cm == 15.0
        assert wc.confidence_level == ConfidenceLevel.VERY_HIGH.value
        assert wc.quality_score == 5.5


# ---------------------------------------------------------------------------
# Tests for weather_processor_handler
# ---------------------------------------------------------------------------


class TestWeatherProcessorHandler:
    """Tests for the main Lambda handler."""

    MODULE = "handlers.weather_processor"

    def _patch_handler_deps(
        self,
        resorts=None,
        parallel=False,
        remaining_ms=300000,
        enable_static_json=False,
    ):
        """Return a dict of patch objects for handler dependencies."""
        if resorts is None:
            resorts = [_make_resort()]

        patches = {
            "parallel": patch(f"{self.MODULE}.PARALLEL_PROCESSING", parallel),
            "enable_static_json": patch(
                f"{self.MODULE}.ENABLE_STATIC_JSON", enable_static_json
            ),
            "enable_scraping": patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            "dynamodb": patch(f"{self.MODULE}.dynamodb"),
            "resort_svc_cls": patch(f"{self.MODULE}.ResortService"),
            "weather_svc_cls": patch(f"{self.MODULE}.OpenMeteoService"),
            "quality_svc_cls": patch(f"{self.MODULE}.SnowQualityService"),
            "summary_svc_cls": patch(f"{self.MODULE}.SnowSummaryService"),
            "scraper_cls": patch(f"{self.MODULE}.OnTheSnowScraper"),
        }
        return patches

    def test_sequential_success(self):
        from handlers.weather_processor import weather_processor_handler

        resort = _make_resort(
            elevation_points=[_make_elevation_point("mid")],
        )

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb") as mock_ddb,
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService") as mock_ws_cls,
            patch(f"{self.MODULE}.SnowQualityService") as mock_sqs_cls,
            patch(f"{self.MODULE}.SnowSummaryService") as mock_sss_cls,
            patch(f"{self.MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_pep.return_value = {
                "success": True,
                "error": None,
                "level": "mid",
                "weather_condition": SimpleNamespace(
                    snow_quality=SimpleNamespace(value="good"),
                    fresh_snow_cm=10.0,
                    confidence_level=SimpleNamespace(value="high"),
                ),
            }

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "completed successfully" in body["message"]
        assert body["stats"]["resorts_processed"] == 1

    def test_parallel_mode_delegates(self):
        from handlers.weather_processor import weather_processor_handler

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", True),
            patch(f"{self.MODULE}.orchestrate_parallel_processing") as mock_opp,
        ):
            mock_opp.return_value = {
                "statusCode": 200,
                "body": json.dumps({"message": "Dispatched", "mode": "parallel"}),
            }
            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["mode"] == "parallel"
        mock_opp.assert_called_once_with(ctx)

    def test_timeout_handling(self):
        """Handler should stop processing when remaining time is low."""
        from handlers.weather_processor import weather_processor_handler

        resorts = [_make_resort(resort_id=f"resort-{i}") for i in range(5)]
        call_count = 0

        def decreasing_time():
            nonlocal call_count
            call_count += 1
            # First call: plenty of time; subsequent: near timeout
            if call_count == 1:
                return 120000
            return 30000  # < MIN_TIME_BUFFER_MS (60000)

        ctx = SimpleNamespace()
        ctx.get_remaining_time_in_millis = decreasing_time

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb") as mock_ddb,
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(f"{self.MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = resorts
            mock_pep.return_value = {
                "success": True,
                "error": None,
                "level": "mid",
                "weather_condition": SimpleNamespace(
                    snow_quality=SimpleNamespace(value="good"),
                    fresh_snow_cm=10.0,
                    confidence_level=SimpleNamespace(value="high"),
                ),
            }

            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["timeout_graceful"] is True
        # Should have processed only 1 resort (after the first check it was okay,
        # then second check triggers timeout)
        assert body["stats"]["resorts_processed"] < 5

    def test_no_resorts(self):
        from handlers.weather_processor import weather_processor_handler

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = []

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["resorts_processed"] == 0

    def test_fatal_error_returns_500(self):
        from handlers.weather_processor import weather_processor_handler

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.dynamodb") as mock_ddb,
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
        ):
            mock_rs_cls.side_effect = RuntimeError("Service init failed")

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "failed" in body["message"].lower()
        assert "Service init failed" in body["error"]

    def test_scraper_enabled_with_supported_resort(self):
        from handlers.weather_processor import weather_processor_handler

        resort = _make_resort(
            elevation_points=[_make_elevation_point("mid")],
        )

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", True),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(f"{self.MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{self.MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            scraper_inst = mock_scraper_cls.return_value
            scraper_inst.is_resort_supported.return_value = True
            scraper_inst.get_snow_report.return_value = SimpleNamespace(
                snowfall_24h_cm=20.0,
                snowfall_48h_cm=30.0,
            )
            mock_pep.return_value = {
                "success": True,
                "error": None,
                "level": "mid",
                "weather_condition": SimpleNamespace(
                    snow_quality=SimpleNamespace(value="good"),
                    fresh_snow_cm=10.0,
                    confidence_level=SimpleNamespace(value="high"),
                ),
            }

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        body = json.loads(result["body"])
        assert body["stats"]["scraper_hits"] == 1

    def test_scraper_failure_counted_as_miss(self):
        from handlers.weather_processor import weather_processor_handler

        resort = _make_resort(
            elevation_points=[_make_elevation_point("mid")],
        )

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", True),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(f"{self.MODULE}.OnTheSnowScraper") as mock_scraper_cls,
            patch(f"{self.MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            scraper_inst = mock_scraper_cls.return_value
            scraper_inst.is_resort_supported.return_value = True
            scraper_inst.get_snow_report.side_effect = RuntimeError("Scrape failed")
            mock_pep.return_value = {
                "success": True,
                "error": None,
                "level": "mid",
                "weather_condition": SimpleNamespace(
                    snow_quality=SimpleNamespace(value="fair"),
                    fresh_snow_cm=5.0,
                    confidence_level=SimpleNamespace(value="medium"),
                ),
            }

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        body = json.loads(result["body"])
        assert body["stats"]["scraper_misses"] == 1

    def test_elevation_point_error_increments_errors(self):
        from handlers.weather_processor import weather_processor_handler

        resort = _make_resort(
            elevation_points=[_make_elevation_point("mid")],
        )

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(f"{self.MODULE}.process_elevation_point") as mock_pep,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_pep.return_value = {
                "success": False,
                "error": "something failed",
                "level": "mid",
                "weather_condition": None,
            }

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        body = json.loads(result["body"])
        assert body["stats"]["errors"] == 1
        assert body["stats"]["conditions_saved"] == 0

    def test_resort_level_exception_caught(self):
        """An exception at the resort level should be caught and not crash."""
        from handlers.weather_processor import weather_processor_handler

        resort = _make_resort(
            elevation_points=[_make_elevation_point("mid")],
        )
        # Give the resort a name that will cause logging to work but
        # make the ThreadPoolExecutor submission fail.

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", False),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(f"{self.MODULE}.ThreadPoolExecutor") as mock_tpe,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_tpe.return_value.__enter__ = MagicMock(
                side_effect=RuntimeError("Thread pool error")
            )
            mock_tpe.return_value.__exit__ = MagicMock(return_value=False)

            ctx = _make_lambda_context(300000)
            result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["errors"] >= 1

    def test_static_json_generation_on_success(self):
        from handlers.weather_processor import weather_processor_handler

        with (
            patch(f"{self.MODULE}.PARALLEL_PROCESSING", False),
            patch(f"{self.MODULE}.ENABLE_STATIC_JSON", True),
            patch(f"{self.MODULE}.ENABLE_SCRAPING", False),
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.OpenMeteoService"),
            patch(f"{self.MODULE}.SnowQualityService"),
            patch(f"{self.MODULE}.SnowSummaryService"),
            patch(
                "handlers.weather_processor.generate_static_json_api",
                create=True,
            ) as mock_gen,
        ):
            # Patch the deferred import inside the handler
            mock_gen_module = MagicMock()
            mock_gen_module.generate_static_json_api.return_value = {
                "files": ["a.json"]
            }
            with patch.dict(
                "sys.modules",
                {"services.static_json_generator": mock_gen_module},
            ):
                mock_rs_cls.return_value.get_all_resorts.return_value = []

                ctx = _make_lambda_context(300000)
                result = weather_processor_handler({}, ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"].get("static_json") == {"files": ["a.json"]}


# ---------------------------------------------------------------------------
# Tests for orchestrate_parallel_processing
# ---------------------------------------------------------------------------


class TestOrchestrateParallelProcessing:
    """Tests for the parallel orchestration function."""

    MODULE = "handlers.weather_processor"

    def test_success_single_region(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        resort = _make_resort(resort_id="whistler", region="na_west")

        with (
            patch(f"{self.MODULE}.dynamodb") as mock_ddb,
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_lc.invoke.return_value = {"StatusCode": 202}

            ctx = _make_lambda_context(300000)
            result = orchestrate_parallel_processing(ctx)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["mode"] == "parallel"
        assert body["workers_invoked"] == 1
        assert body["workers_failed"] == 0
        assert body["total_resorts"] == 1

    def test_success_multiple_regions(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        resorts = [
            _make_resort(resort_id="whistler", region="na_west"),
            _make_resort(resort_id="vail", region="na_rockies"),
            _make_resort(resort_id="chamonix", region="alps"),
        ]

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = resorts
            mock_lc.invoke.return_value = {"StatusCode": 202}

            result = orchestrate_parallel_processing(_make_lambda_context())

        body = json.loads(result["body"])
        assert body["workers_invoked"] == 3
        assert body["total_resorts"] == 3
        assert set(body["regions"]) == {"na_west", "na_rockies", "alps"}

    def test_lambda_invocation_failure(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        resort = _make_resort(resort_id="whistler", region="na_west")

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_lc.invoke.side_effect = RuntimeError("Lambda throttled")

            result = orchestrate_parallel_processing(_make_lambda_context())

        body = json.loads(result["body"])
        assert body["workers_invoked"] == 0
        assert body["workers_failed"] == 1

    def test_partial_failure(self):
        """One region invocation succeeds, another fails."""
        from handlers.weather_processor import orchestrate_parallel_processing

        resorts = [
            _make_resort(resort_id="whistler", region="na_west"),
            _make_resort(resort_id="chamonix", region="alps"),
        ]

        call_count = 0

        def invoke_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            payload = json.loads(kwargs["Payload"])
            if payload["region"] == "alps":
                raise RuntimeError("Alps region failed")
            return {"StatusCode": 202}

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = resorts
            mock_lc.invoke.side_effect = invoke_side_effect

            result = orchestrate_parallel_processing(_make_lambda_context())

        body = json.loads(result["body"])
        assert body["workers_invoked"] + body["workers_failed"] == 2

    def test_no_resorts_returns_empty(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = []

            result = orchestrate_parallel_processing(_make_lambda_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "No resorts" in body["message"]

    def test_invoke_uses_event_type(self):
        """Lambda should be invoked asynchronously (InvocationType=Event)."""
        from handlers.weather_processor import orchestrate_parallel_processing

        resort = _make_resort(resort_id="whistler", region="na_west")

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_lc.invoke.return_value = {"StatusCode": 202}

            orchestrate_parallel_processing(_make_lambda_context())

        call_kwargs = mock_lc.invoke.call_args[1]
        assert call_kwargs["InvocationType"] == "Event"

    def test_non_202_status_code_treated_as_failure(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        resort = _make_resort(resort_id="whistler", region="na_west")

        with (
            patch(f"{self.MODULE}.dynamodb"),
            patch(f"{self.MODULE}.ResortService") as mock_rs_cls,
            patch(f"{self.MODULE}.lambda_client") as mock_lc,
        ):
            mock_rs_cls.return_value.get_all_resorts.return_value = [resort]
            mock_lc.invoke.return_value = {"StatusCode": 500}

            result = orchestrate_parallel_processing(_make_lambda_context())

        body = json.loads(result["body"])
        assert body["workers_invoked"] == 0
        assert body["workers_failed"] == 1


# ---------------------------------------------------------------------------
# Tests for scheduled_weather_update_handler
# ---------------------------------------------------------------------------


class TestScheduledWeatherUpdateHandler:
    """Tests for the CloudWatch event wrapper handler."""

    MODULE = "handlers.weather_processor"

    def test_valid_cloudwatch_event(self):
        from handlers.weather_processor import scheduled_weather_update_handler

        event = {
            "source": "aws.events",
            "detail-type": "Scheduled Event",
            "detail": {},
        }

        with patch(f"{self.MODULE}.weather_processor_handler") as mock_handler:
            mock_handler.return_value = {
                "statusCode": 200,
                "body": json.dumps({"message": "OK"}),
            }
            ctx = _make_lambda_context()
            result = scheduled_weather_update_handler(event, ctx)

        assert result["statusCode"] == 200
        mock_handler.assert_called_once_with(event, ctx)

    def test_invalid_event_type(self):
        from handlers.weather_processor import scheduled_weather_update_handler

        event = {"source": "custom", "detail-type": "something else"}
        ctx = _make_lambda_context()

        result = scheduled_weather_update_handler(event, ctx)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "Invalid event type" in body["message"]

    def test_empty_event(self):
        from handlers.weather_processor import scheduled_weather_update_handler

        result = scheduled_weather_update_handler({}, _make_lambda_context())

        assert result["statusCode"] == 400

    def test_missing_detail_type(self):
        from handlers.weather_processor import scheduled_weather_update_handler

        event = {"source": "aws.events"}
        result = scheduled_weather_update_handler(event, _make_lambda_context())

        assert result["statusCode"] == 400

    def test_missing_source(self):
        from handlers.weather_processor import scheduled_weather_update_handler

        event = {"detail-type": "Scheduled Event"}
        result = scheduled_weather_update_handler(event, _make_lambda_context())

        assert result["statusCode"] == 400
