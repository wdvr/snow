"""Tests for the Snow-Forecast prefetch Lambda handler.

Tests cover:
- Handler success flow (scrape all resorts, write to S3)
- Stats tracking (hits, misses, errors, duration)
- Graceful timeout handling
- Empty resort list
- S3 write verification
- Error handling (scraper failures, S3 failures)
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# Patch module-level AWS clients before import
with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
    from handlers.snowforecast_prefetch import (
        CACHE_S3_KEY,
        MIN_TIME_BUFFER_MS,
        REQUEST_DELAY_SECONDS,
        get_remaining_time_ms,
        snowforecast_prefetch_handler,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resort(resort_id: str) -> Mock:
    """Create a mock resort object."""
    resort = Mock()
    resort.resort_id = resort_id
    resort.name = resort_id.replace("-", " ").title()
    return resort


def _make_context(remaining_ms: int = 600000) -> Mock:
    """Create a mock Lambda context."""
    context = Mock()
    context.get_remaining_time_in_millis.return_value = remaining_ms
    return context


def _make_snow_forecast_data(resort_id: str, **overrides) -> Mock:
    """Create a mock SnowForecastData."""
    data = Mock()
    data.resort_id = resort_id
    data.snowfall_24h_cm = overrides.get("snowfall_24h_cm", 10.0)
    data.snowfall_48h_cm = overrides.get("snowfall_48h_cm", 20.0)
    data.snowfall_72h_cm = overrides.get("snowfall_72h_cm", 30.0)
    data.upper_depth_cm = overrides.get("upper_depth_cm", 200.0)
    data.lower_depth_cm = overrides.get("lower_depth_cm", 100.0)
    data.surface_conditions = overrides.get("surface_conditions", "Packed Powder")
    data.source_url = overrides.get(
        "source_url",
        f"https://www.snow-forecast.com/resorts/{resort_id}/6day/mid",
    )
    return data


# ---------------------------------------------------------------------------
# Tests for get_remaining_time_ms
# ---------------------------------------------------------------------------


class TestGetRemainingTimeMs:
    """Tests for the get_remaining_time_ms helper."""

    def test_with_valid_context(self):
        """Returns remaining time from Lambda context."""
        context = _make_context(300000)
        assert get_remaining_time_ms(context) == 300000

    def test_with_none_context(self):
        """Returns default when context is None."""
        assert get_remaining_time_ms(None) == 600000

    def test_with_no_method(self):
        """Returns default when context lacks the method."""
        context = Mock(spec=[])
        assert get_remaining_time_ms(context) == 600000


# ---------------------------------------------------------------------------
# Tests for snowforecast_prefetch_handler
# ---------------------------------------------------------------------------


class TestPrefetchHandlerSuccess:
    """Tests for successful prefetch runs."""

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_scrapes_all_resorts_and_writes_s3(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Handler scrapes all resorts and writes cache to S3."""
        # Setup resorts
        resorts = [_make_resort("big-white"), _make_resort("chamonix")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts

        # Setup scraper
        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.get_snow_report.side_effect = [
            _make_snow_forecast_data("big-white"),
            _make_snow_forecast_data("chamonix", snowfall_24h_cm=15.0),
        ]

        context = _make_context(600000)
        result = snowforecast_prefetch_handler({}, context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["stats"]["resorts_total"] == 2
        assert body["stats"]["resorts_scraped"] == 2
        assert body["stats"]["hits"] == 2
        assert body["stats"]["misses"] == 0
        assert body["stats"]["errors"] == 0
        assert body["stats"]["timeout_graceful"] is False
        assert "duration_seconds" in body["stats"]

        # Verify S3 write
        mock_s3.put_object.assert_called_once()
        s3_call = mock_s3.put_object.call_args
        assert s3_call.kwargs["Key"] == CACHE_S3_KEY
        assert s3_call.kwargs["ContentType"] == "application/json"

        # Verify cache content
        cache_data = json.loads(s3_call.kwargs["Body"])
        assert cache_data["resort_count"] == 2
        assert "big-white" in cache_data["resorts"]
        assert "chamonix" in cache_data["resorts"]
        assert cache_data["resorts"]["big-white"]["snowfall_24h_cm"] == 10.0
        assert cache_data["resorts"]["chamonix"]["snowfall_24h_cm"] == 15.0

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_rate_limiting_between_requests(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Handler sleeps between requests to avoid rate limiting."""
        resorts = [_make_resort("r1"), _make_resort("r2"), _make_resort("r3")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = None

        snowforecast_prefetch_handler({}, _make_context())

        # Should sleep after each resort
        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(REQUEST_DELAY_SECONDS)


class TestPrefetchHandlerMisses:
    """Tests for resorts where scraping returns no data."""

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_none_result_counted_as_miss(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Resorts returning None are counted as misses."""
        resorts = [_make_resort("r1"), _make_resort("r2")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = None

        result = snowforecast_prefetch_handler({}, _make_context())
        body = json.loads(result["body"])

        assert body["stats"]["hits"] == 0
        assert body["stats"]["misses"] == 2

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_mixed_hits_and_misses(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Stats correctly track mix of hits and misses."""
        resorts = [_make_resort("hit"), _make_resort("miss"), _make_resort("hit2")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.get_snow_report.side_effect = [
            _make_snow_forecast_data("hit"),
            None,
            _make_snow_forecast_data("hit2"),
        ]

        result = snowforecast_prefetch_handler({}, _make_context())
        body = json.loads(result["body"])

        assert body["stats"]["hits"] == 2
        assert body["stats"]["misses"] == 1


class TestPrefetchHandlerErrors:
    """Tests for error handling."""

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_scraper_exception_counted_as_error(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Exceptions during scraping are caught and counted as errors."""
        resorts = [_make_resort("r1"), _make_resort("r2")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.get_snow_report.side_effect = [
            Exception("Connection refused"),
            _make_snow_forecast_data("r2"),
        ]

        result = snowforecast_prefetch_handler({}, _make_context())
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["stats"]["errors"] == 1
        assert body["stats"]["hits"] == 1
        assert body["stats"]["resorts_scraped"] == 2

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_s3_write_failure_returns_500(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """S3 write failure causes handler to return 500."""
        resorts = [_make_resort("r1")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = (
            _make_snow_forecast_data("r1")
        )
        mock_s3.put_object.side_effect = Exception("Access Denied")

        result = snowforecast_prefetch_handler({}, _make_context())

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Access Denied" in body["error"]


class TestPrefetchHandlerTimeout:
    """Tests for graceful timeout handling."""

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_graceful_timeout(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Handler stops gracefully when approaching timeout."""
        resorts = [_make_resort("r1"), _make_resort("r2"), _make_resort("r3")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = (
            _make_snow_forecast_data("r1")
        )

        # Context returns enough time for first resort, then times out
        context = Mock()
        context.get_remaining_time_in_millis.side_effect = [
            120000,  # First resort: plenty of time
            30000,  # Second resort: below threshold, stop
        ]

        result = snowforecast_prefetch_handler({}, context)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["stats"]["timeout_graceful"] is True
        assert body["stats"]["resorts_scraped"] == 1
        assert "timeout" in body["message"].lower()


class TestPrefetchHandlerEmptyResorts:
    """Tests for when no resorts exist."""

    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_no_resorts_returns_early(
        self, mock_dynamodb, mock_resort_service_cls, mock_s3
    ):
        """Handler returns early when no resorts found."""
        mock_resort_service_cls.return_value.get_all_resorts.return_value = []

        result = snowforecast_prefetch_handler({}, _make_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "No resorts" in body["message"]
        assert body["stats"]["resorts_total"] == 0
        mock_s3.put_object.assert_not_called()


class TestPrefetchCacheContent:
    """Tests for the S3 cache file content structure."""

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_cache_includes_all_fields(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """S3 cache includes all expected fields per resort."""
        resorts = [_make_resort("test-resort")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = (
            _make_snow_forecast_data(
                "test-resort",
                snowfall_24h_cm=5.0,
                snowfall_48h_cm=12.0,
                snowfall_72h_cm=18.0,
                upper_depth_cm=250.0,
                lower_depth_cm=100.0,
                surface_conditions="Fresh Powder",
            )
        )

        snowforecast_prefetch_handler({}, _make_context())

        cache_data = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
        resort_data = cache_data["resorts"]["test-resort"]

        assert resort_data["snowfall_24h_cm"] == 5.0
        assert resort_data["snowfall_48h_cm"] == 12.0
        assert resort_data["snowfall_72h_cm"] == 18.0
        assert resort_data["upper_depth_cm"] == 250.0
        assert resort_data["lower_depth_cm"] == 100.0
        assert resort_data["surface_conditions"] == "Fresh Powder"
        assert "source_url" in resort_data

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_cache_has_metadata(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """S3 cache includes generation timestamp and resort count."""
        resorts = [_make_resort("r1")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper_cls.return_value.get_snow_report.return_value = (
            _make_snow_forecast_data("r1")
        )

        snowforecast_prefetch_handler({}, _make_context())

        cache_data = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
        assert "generated_at" in cache_data
        assert cache_data["resort_count"] == 1

    @patch("handlers.snowforecast_prefetch.time.sleep")
    @patch("handlers.snowforecast_prefetch.s3_client")
    @patch("handlers.snowforecast_prefetch.SnowForecastScraper")
    @patch("handlers.snowforecast_prefetch.ResortService")
    @patch("handlers.snowforecast_prefetch.dynamodb")
    def test_only_successful_scrapes_in_cache(
        self,
        mock_dynamodb,
        mock_resort_service_cls,
        mock_scraper_cls,
        mock_s3,
        mock_sleep,
    ):
        """Only resorts with successful scrapes appear in the cache."""
        resorts = [_make_resort("ok"), _make_resort("fail"), _make_resort("miss")]
        mock_resort_service_cls.return_value.get_all_resorts.return_value = resorts
        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.get_snow_report.side_effect = [
            _make_snow_forecast_data("ok"),
            Exception("Timeout"),
            None,
        ]

        snowforecast_prefetch_handler({}, _make_context())

        cache_data = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
        assert cache_data["resort_count"] == 1
        assert "ok" in cache_data["resorts"]
        assert "fail" not in cache_data["resorts"]
        assert "miss" not in cache_data["resorts"]
