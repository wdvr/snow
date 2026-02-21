"""Comprehensive tests for the OpenMeteoService."""

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import requests

from services.openmeteo_service import (
    MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
    OpenMeteoService,
    _is_retryable_error,
    _request_with_retry,
)

# ---------------------------------------------------------------------------
# Helper: build hourly arrays aligned to a fixed "now"
# ---------------------------------------------------------------------------


def _make_hourly_times(now_dt, past_hours=336, future_hours=72):
    """Generate hourly ISO time strings centred on *now_dt*.

    Returns (times_list, current_index) where current_index is the index
    whose timestamp matches *now_dt* truncated to the hour.
    """
    start = now_dt - timedelta(hours=past_hours)
    times = []
    for h in range(past_hours + future_hours + 1):
        t = start + timedelta(hours=h)
        times.append(t.strftime("%Y-%m-%dT%H:00"))
    current_index = past_hours
    return times, current_index


FIXED_NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)


def _build_hourly(
    past_hours=336,
    future_hours=72,
    default_temp=-5.0,
    default_snowfall=0.0,
    default_snow_depth=None,
    now_dt=None,
):
    """Return (hourly_dict, current_index) with constant values by default."""
    now = now_dt or FIXED_NOW
    times, ci = _make_hourly_times(now, past_hours, future_hours)
    n = len(times)
    hourly = {
        "time": times,
        "temperature_2m": [default_temp] * n,
        "snowfall": [default_snowfall] * n,
        "snow_depth": [default_snow_depth] * n,
    }
    return hourly, ci


# ============================================================================
# 1. _is_retryable_error
# ============================================================================


class TestIsRetryableError(unittest.TestCase):
    def test_timeout_is_retryable(self):
        exc = requests.exceptions.Timeout("timed out")
        self.assertTrue(_is_retryable_error(exc))

    def test_connection_error_is_retryable(self):
        exc = requests.exceptions.ConnectionError("refused")
        self.assertTrue(_is_retryable_error(exc))

    def test_http_error_with_retryable_status(self):
        for code in RETRYABLE_STATUS_CODES:
            resp = Mock()
            resp.status_code = code
            exc = requests.exceptions.HTTPError(response=resp)
            self.assertTrue(
                _is_retryable_error(exc),
                f"Status {code} should be retryable",
            )

    def test_http_error_with_non_retryable_status(self):
        resp = Mock()
        resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=resp)
        self.assertFalse(_is_retryable_error(exc))

    def test_http_error_without_response(self):
        exc = requests.exceptions.HTTPError()
        exc.response = None
        self.assertFalse(_is_retryable_error(exc))

    def test_generic_request_exception_not_retryable(self):
        exc = requests.exceptions.RequestException("some error")
        self.assertFalse(_is_retryable_error(exc))

    def test_non_request_exception_not_retryable(self):
        exc = ValueError("bad value")
        self.assertFalse(_is_retryable_error(exc))


# ============================================================================
# 2. _request_with_retry
# ============================================================================


class TestRequestWithRetry(unittest.TestCase):
    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_success_on_first_try(self, mock_request, mock_sleep):
        resp = Mock()
        resp.raise_for_status = Mock()
        mock_request.return_value = resp

        result = _request_with_retry("GET", "https://example.com")
        self.assertIs(result, resp)
        mock_sleep.assert_not_called()

    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_retries_on_timeout_then_succeeds(self, mock_request, mock_sleep):
        good_resp = Mock()
        good_resp.raise_for_status = Mock()

        mock_request.side_effect = [
            requests.exceptions.Timeout("timeout"),
            good_resp,
        ]

        result = _request_with_retry("GET", "https://example.com")
        self.assertIs(result, good_resp)
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(1)  # first delay

    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_raises_after_max_retries_exhausted(self, mock_request, mock_sleep):
        mock_request.side_effect = requests.exceptions.Timeout("timeout")

        with self.assertRaises(requests.exceptions.Timeout):
            _request_with_retry("GET", "https://example.com")

        self.assertEqual(mock_request.call_count, MAX_RETRIES)
        self.assertEqual(mock_sleep.call_count, MAX_RETRIES - 1)

    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_non_retryable_error_raises_immediately(self, mock_request, mock_sleep):
        resp = Mock()
        resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=resp)
        mock_request.side_effect = exc

        with self.assertRaises(requests.exceptions.HTTPError):
            _request_with_retry("GET", "https://example.com")

        self.assertEqual(mock_request.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_retries_on_503_then_succeeds(self, mock_request, mock_sleep):
        resp_503 = Mock()
        resp_503.status_code = 503
        exc_503 = requests.exceptions.HTTPError(response=resp_503)
        resp_503.raise_for_status.side_effect = exc_503

        good_resp = Mock()
        good_resp.raise_for_status = Mock()

        mock_request.side_effect = [exc_503, good_resp]
        result = _request_with_retry("GET", "https://example.com")
        self.assertIs(result, good_resp)

    @patch("services.openmeteo_service.time.sleep")
    @patch("services.openmeteo_service.requests.request")
    def test_exponential_backoff_delays(self, mock_request, mock_sleep):
        mock_request.side_effect = requests.exceptions.ConnectionError("refused")

        with self.assertRaises(requests.exceptions.ConnectionError):
            _request_with_retry("GET", "https://example.com")

        # Should have slept with delays 1 and 2 (first two retries)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        self.assertEqual(delays, [1, 2])


# ============================================================================
# 3. _weather_code_to_description
# ============================================================================


class TestWeatherCodeToDescription(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    def test_known_codes(self):
        cases = {
            0: "Clear sky",
            1: "Mainly clear",
            3: "Overcast",
            71: "Slight snow fall",
            75: "Heavy snow fall",
            95: "Thunderstorm",
            99: "Thunderstorm with heavy hail",
        }
        for code, expected in cases.items():
            self.assertEqual(
                self.service._weather_code_to_description(code),
                expected,
                f"Failed for code {code}",
            )

    def test_unknown_code(self):
        self.assertEqual(self.service._weather_code_to_description(999), "Unknown")


# ============================================================================
# 4. _calculate_ice_hours
# ============================================================================


class TestCalculateIceHours(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_all_cold_no_hours_above_threshold(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-10.0)
        result = self.service._calculate_ice_hours(hourly, threshold_temp=3.0)
        self.assertEqual(result["hours_above_threshold"], 0.0)
        self.assertEqual(result["max_consecutive"], 0.0)

    @patch("services.openmeteo_service.datetime")
    def test_all_warm_hours_above_threshold(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=5.0)
        result = self.service._calculate_ice_hours(hourly, threshold_temp=3.0)
        # Last 24 hours should all be above threshold
        self.assertEqual(
            result["hours_above_threshold"], 25.0
        )  # start_24h to current_index inclusive
        self.assertEqual(result["max_consecutive"], 25.0)

    @patch("services.openmeteo_service.datetime")
    def test_mixed_temperatures(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        # Set a few hours in the last 24h to be warm
        # Hours above threshold (3.0): 3 hours
        for offset in [5, 6, 7]:
            hourly["temperature_2m"][ci - offset] = 4.0
        result = self.service._calculate_ice_hours(hourly, threshold_temp=3.0)
        self.assertEqual(result["hours_above_threshold"], 3.0)
        # Those 3 are consecutive and above 0, so max_consecutive >= 3
        self.assertEqual(result["max_consecutive"], 3.0)

    @patch("services.openmeteo_service.datetime")
    def test_consecutive_warm_hours_across_cold_gap(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        # Two warm stretches separated by a cold hour
        # Stretch 1: 3 hours warm  (ci-10, ci-9, ci-8)
        for offset in [10, 9, 8]:
            hourly["temperature_2m"][ci - offset] = 2.0  # above 0 but below 3
        # Cold gap: ci-7 stays -5
        # Stretch 2: 5 hours warm (ci-6 .. ci-2)
        for offset in [6, 5, 4, 3, 2]:
            hourly["temperature_2m"][ci - offset] = 1.0
        result = self.service._calculate_ice_hours(hourly, threshold_temp=3.0)
        # None are >= 3.0 so hours_above_threshold should be 0
        self.assertEqual(result["hours_above_threshold"], 0.0)
        # But max_consecutive above 0°C should be 5 (the longer stretch)
        self.assertEqual(result["max_consecutive"], 5.0)

    @patch("services.openmeteo_service.datetime")
    def test_empty_hourly(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        result = self.service._calculate_ice_hours({})
        self.assertEqual(result["hours_above_threshold"], 0.0)
        self.assertEqual(result["max_consecutive"], 0.0)

    @patch("services.openmeteo_service.datetime")
    def test_custom_threshold(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=1.0)
        result = self.service._calculate_ice_hours(hourly, threshold_temp=0.0)
        # All temps are 1.0 >= 0.0
        self.assertEqual(result["hours_above_threshold"], 25.0)

    @patch("services.openmeteo_service.datetime")
    def test_none_temps_ignored(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=5.0)
        # Replace some with None in the last 24h
        hourly["temperature_2m"][ci - 5] = None
        hourly["temperature_2m"][ci - 6] = None
        result = self.service._calculate_ice_hours(hourly, threshold_temp=3.0)
        # 25 hours in window minus 2 None = 23 above threshold
        self.assertEqual(result["hours_above_threshold"], 23.0)


# ============================================================================
# 5. _process_snowfall - rolling windows
# ============================================================================


class TestProcessSnowfallRollingWindows(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_24h_snowfall_summed_correctly(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        # Put 1 cm snowfall at each of the last 24 hours
        for i in range(ci - 23, ci + 1):
            hourly["snowfall"][i] = 1.0
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["snowfall_24h"], 24.0)
        self.assertAlmostEqual(result["snowfall_48h"], 24.0)
        self.assertAlmostEqual(result["snowfall_72h"], 24.0)

    @patch("services.openmeteo_service.datetime")
    def test_48h_includes_24h(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        # 1cm at ci-30 (within 48h but not 24h)
        hourly["snowfall"][ci - 30] = 1.0
        # 2cm at ci-10 (within 24h)
        hourly["snowfall"][ci - 10] = 2.0
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["snowfall_24h"], 2.0)
        self.assertAlmostEqual(result["snowfall_48h"], 3.0)
        self.assertAlmostEqual(result["snowfall_72h"], 3.0)

    @patch("services.openmeteo_service.datetime")
    def test_72h_includes_48h_and_24h(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        hourly["snowfall"][ci - 60] = 3.0  # in 72h only
        hourly["snowfall"][ci - 30] = 2.0  # in 48h
        hourly["snowfall"][ci - 10] = 1.0  # in 24h
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["snowfall_24h"], 1.0)
        self.assertAlmostEqual(result["snowfall_48h"], 3.0)
        self.assertAlmostEqual(result["snowfall_72h"], 6.0)

    @patch("services.openmeteo_service.datetime")
    def test_consistency_enforcement(self, mock_dt):
        """48h >= 24h, 72h >= 48h after processing."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        result = self.service._process_snowfall({}, hourly)
        self.assertGreaterEqual(result["snowfall_48h"], result["snowfall_24h"])
        self.assertGreaterEqual(result["snowfall_72h"], result["snowfall_48h"])


# ============================================================================
# 6. _process_snowfall - predicted snowfall
# ============================================================================


class TestProcessSnowfallPredicted(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_predicted_snowfall_24h(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        # 0.5 cm per hour for next 24 hours (ci+1 .. ci+24 inclusive)
        for i in range(ci + 1, ci + 25):
            hourly["snowfall"][i] = 0.5
        result = self.service._process_snowfall({}, hourly)
        # future_24h = ci+24, loop is range(ci+1, ci+24) => 23 items => 11.5
        self.assertAlmostEqual(result["predicted_24h"], 11.5)
        # predicted_48h includes the 24th hour too => 24 * 0.5 = 12.0
        self.assertAlmostEqual(result["predicted_48h"], 12.0)
        self.assertAlmostEqual(result["predicted_72h"], 12.0)

    @patch("services.openmeteo_service.datetime")
    def test_predicted_snowfall_72h(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        # Put 1cm at ci+10, ci+30, ci+60
        hourly["snowfall"][ci + 10] = 1.0
        hourly["snowfall"][ci + 30] = 2.0
        hourly["snowfall"][ci + 60] = 3.0
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["predicted_24h"], 1.0)
        self.assertAlmostEqual(result["predicted_48h"], 3.0)
        self.assertAlmostEqual(result["predicted_72h"], 6.0)


# ============================================================================
# 7. _process_snowfall - snow depth
# ============================================================================


class TestProcessSnowfallSnowDepth(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_snow_depth_meters_to_cm(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snow_depth=0.5)  # 0.5 meters
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["current_snow_depth"], 50.0)

    @patch("services.openmeteo_service.datetime")
    def test_snow_depth_none_values_skipped(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snow_depth=None)
        # Only set a value a few hours before current
        hourly["snow_depth"][ci - 3] = 0.25
        result = self.service._process_snowfall({}, hourly)
        # Should find the non-None value searching backwards
        self.assertAlmostEqual(result["current_snow_depth"], 25.0)

    @patch("services.openmeteo_service.datetime")
    def test_snow_depth_zero(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snow_depth=0.0)
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["current_snow_depth"], 0.0)


# ============================================================================
# 8. _process_snowfall - freeze-thaw detection
# ============================================================================


class TestProcessSnowfallFreezeThaw(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_freeze_event_3c_3h(self, mock_dt):
        """3 consecutive hours at >= 3.0C should trigger freeze event."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # Place freeze event 10 hours ago: 3 hours at 3.5C
        for offset in [12, 11, 10]:
            hourly["temperature_2m"][ci - offset] = 3.5
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNotNone(result["last_freeze_thaw_hours_ago"])
        self.assertTrue(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_freeze_event_2c_6h(self, mock_dt):
        """6 consecutive hours at >= 2.0C should trigger freeze event."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # 6 hours at 2.5C, ending 5 hours ago
        for offset in range(11, 5, -1):  # offsets 11, 10, 9, 8, 7, 6
            hourly["temperature_2m"][ci - offset] = 2.5
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNotNone(result["last_freeze_thaw_hours_ago"])
        self.assertTrue(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_freeze_event_1c_8h(self, mock_dt):
        """8 consecutive hours at >= 1.0C should trigger freeze event."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # 8 hours at 1.5C, ending 3 hours ago
        for offset in range(11, 3, -1):  # offsets 11..4 = 8 hours
            hourly["temperature_2m"][ci - offset] = 1.5
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNotNone(result["last_freeze_thaw_hours_ago"])
        self.assertTrue(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_freeze_event_0c_4h(self, mock_dt):
        """4 consecutive hours at >= 0.0C should trigger freeze event."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # 4 hours at 0.5C, ending 2 hours ago
        for offset in [6, 5, 4, 3]:
            hourly["temperature_2m"][ci - offset] = 0.5
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNotNone(result["last_freeze_thaw_hours_ago"])
        self.assertTrue(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_no_freeze_event_when_too_few_hours(self, mock_dt):
        """2 hours at 3C is not enough (need 3)."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        hourly["temperature_2m"][ci - 10] = 3.5
        hourly["temperature_2m"][ci - 11] = 3.5
        # Only 2 consecutive hours at 3.5C - not enough for the (3.0, 3) threshold
        # Also not enough for (2.0, 6) or (1.0, 8) or (0.0, 4)
        result = self.service._process_snowfall({}, hourly)
        self.assertFalse(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_snowfall_after_freeze(self, mock_dt):
        """Snow that falls after a freeze event is tracked."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # Freeze event: 3h at 4C, ending at ci-20
        for offset in [22, 21, 20]:
            hourly["temperature_2m"][ci - offset] = 4.0
        # Snowfall after freeze: 2cm at ci-15 and 3cm at ci-10
        hourly["snowfall"][ci - 15] = 2.0
        hourly["snowfall"][ci - 10] = 3.0
        result = self.service._process_snowfall({}, hourly)
        self.assertAlmostEqual(result["snowfall_after_freeze_cm"], 5.0)

    @patch("services.openmeteo_service.datetime")
    def test_no_freeze_all_snow_is_after_freeze(self, mock_dt):
        """When no freeze event, all historical snow counts as after-freeze."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-10.0, default_snowfall=0.0)
        hourly["snowfall"][ci - 100] = 5.0
        hourly["snowfall"][ci - 50] = 3.0
        hourly["snowfall"][ci - 10] = 2.0
        result = self.service._process_snowfall({}, hourly)
        # No freeze detected, so all snow in the range counts
        self.assertAlmostEqual(result["snowfall_after_freeze_cm"], 10.0)

    @patch("services.openmeteo_service.datetime")
    def test_known_freeze_date_older_than_14_days(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_dt.fromisoformat = datetime.fromisoformat
        hourly, ci = _build_hourly(default_temp=-10.0, default_snowfall=0.0)
        # Snow in the last few hours
        hourly["snowfall"][ci - 5] = 4.0
        # Known freeze was 20 days (480 hours) ago
        old_freeze = (FIXED_NOW - timedelta(days=20)).isoformat()
        result = self.service._process_snowfall(
            {}, hourly, last_known_freeze_date=old_freeze
        )
        # Known freeze > 336h, so all snow in window is after freeze
        self.assertAlmostEqual(result["snowfall_after_freeze_cm"], 4.0)
        self.assertFalse(result["freeze_event_detected"])

    @patch("services.openmeteo_service.datetime")
    def test_detected_freeze_date_stored(self, mock_dt):
        """The ISO timestamp of the detected freeze event is stored."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # Freeze event 10 hours ago
        for offset in [12, 11, 10]:
            hourly["temperature_2m"][ci - offset] = 4.0
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNotNone(result["detected_freeze_date"])
        # The date should be the timestamp at ci-10
        self.assertEqual(result["detected_freeze_date"], hourly["time"][ci - 10])

    @patch("services.openmeteo_service.datetime")
    def test_new_freeze_more_recent_than_known(self, mock_dt):
        """If detected freeze is more recent than known, freeze_event_detected=True."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_dt.fromisoformat = datetime.fromisoformat
        hourly, ci = _build_hourly(default_temp=-5.0, default_snowfall=0.0)
        # Freeze event 5 hours ago
        for offset in [7, 6, 5]:
            hourly["temperature_2m"][ci - offset] = 4.0
        # Known freeze was 48 hours ago
        known_freeze = (FIXED_NOW - timedelta(hours=48)).isoformat()
        result = self.service._process_snowfall(
            {}, hourly, last_known_freeze_date=known_freeze
        )
        self.assertTrue(result["freeze_event_detected"])


# ============================================================================
# 9. _process_snowfall - currently_warming
# ============================================================================


class TestProcessSnowfallCurrentlyWarming(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_currently_warming_true(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        hourly["temperature_2m"][ci] = 2.0  # >= 1.0 threshold
        result = self.service._process_snowfall({}, hourly)
        self.assertTrue(result["currently_warming"])

    @patch("services.openmeteo_service.datetime")
    def test_currently_warming_false(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        result = self.service._process_snowfall({}, hourly)
        self.assertFalse(result["currently_warming"])

    @patch("services.openmeteo_service.datetime")
    def test_currently_warming_at_boundary(self, mock_dt):
        """Exactly 1.0C should be warming."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        hourly["temperature_2m"][ci] = 1.0
        result = self.service._process_snowfall({}, hourly)
        self.assertTrue(result["currently_warming"])

    @patch("services.openmeteo_service.datetime")
    def test_currently_warming_none_temp(self, mock_dt):
        """None at current hour should not be warming."""
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-5.0)
        hourly["temperature_2m"][ci] = None
        result = self.service._process_snowfall({}, hourly)
        self.assertFalse(result["currently_warming"])


# ============================================================================
# 10. _process_snowfall - hours since last snowfall
# ============================================================================


class TestProcessSnowfallHoursSince(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_hours_since_last_snowfall(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        hourly["snowfall"][ci - 7] = 0.5
        result = self.service._process_snowfall({}, hourly)
        self.assertEqual(result["hours_since_last_snowfall"], 7.0)

    @patch("services.openmeteo_service.datetime")
    def test_hours_since_last_snowfall_at_current(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        hourly["snowfall"][ci] = 1.0
        result = self.service._process_snowfall({}, hourly)
        self.assertEqual(result["hours_since_last_snowfall"], 0.0)

    @patch("services.openmeteo_service.datetime")
    def test_hours_since_no_snowfall(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_snowfall=0.0)
        result = self.service._process_snowfall({}, hourly)
        self.assertIsNone(result["hours_since_last_snowfall"])


# ============================================================================
# 11. _process_snowfall - min/max temp
# ============================================================================


class TestProcessSnowfallMinMaxTemp(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_min_max_temp_24h(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        hourly, ci = _build_hourly(default_temp=-3.0)
        hourly["temperature_2m"][ci - 5] = -10.0
        hourly["temperature_2m"][ci - 3] = 5.0
        result = self.service._process_snowfall({}, hourly)
        self.assertEqual(result["min_temp_24h"], -10.0)
        self.assertEqual(result["max_temp_24h"], 5.0)


# ============================================================================
# 12. _process_snowfall - daily fallback
# ============================================================================


class TestProcessSnowfallDailyFallback(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_daily_fallback_when_hourly_empty(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        today_str = FIXED_NOW.strftime("%Y-%m-%d")
        yesterday = (FIXED_NOW - timedelta(days=1)).strftime("%Y-%m-%d")
        day_before = (FIXED_NOW - timedelta(days=2)).strftime("%Y-%m-%d")
        daily = {
            "time": [day_before, yesterday, today_str],
            "snowfall_sum": [5.0, 3.0, 2.0],
            "temperature_2m_min": [-8.0, -6.0, -4.0],
            "temperature_2m_max": [-1.0, 0.0, 1.0],
        }
        # Empty hourly -> should fall back to daily
        result = self.service._process_snowfall(daily, {})
        # today_index=2, snowfall_24h = daily[2] + daily[1] = 5.0
        self.assertAlmostEqual(result["snowfall_24h"], 5.0)
        self.assertEqual(result["min_temp_24h"], -4.0)
        self.assertEqual(result["max_temp_24h"], 1.0)


# ============================================================================
# 13. _process_snowfall - empty data
# ============================================================================


class TestProcessSnowfallEmptyData(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    def test_completely_empty(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = self.service._process_snowfall({}, {})
        self.assertEqual(result["snowfall_24h"], 0.0)
        self.assertEqual(result["snowfall_48h"], 0.0)
        self.assertEqual(result["snowfall_72h"], 0.0)
        self.assertIsNone(result["hours_since_last_snowfall"])
        self.assertFalse(result["freeze_event_detected"])


# ============================================================================
# 14. get_current_weather
# ============================================================================


class TestGetCurrentWeather(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service.datetime")
    @patch("services.openmeteo_service._request_with_retry")
    def test_success(self, mock_request, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        hourly, ci = _build_hourly(
            default_temp=-5.0, default_snowfall=0.5, default_snow_depth=0.3
        )
        today_str = FIXED_NOW.strftime("%Y-%m-%d")

        api_response = {
            "current": {
                "temperature_2m": -5.0,
                "relative_humidity_2m": 80.0,
                "wind_speed_10m": 15.0,
                "weather_code": 71,
            },
            "hourly": hourly,
            "daily": {
                "time": [today_str],
                "snowfall_sum": [5.0],
                "temperature_2m_min": [-8.0],
                "temperature_2m_max": [-2.0],
            },
            "elevation": 1800,
        }
        resp = Mock()
        resp.json.return_value = api_response
        mock_request.return_value = resp

        result = self.service.get_current_weather(49.72, -118.93, 1800)
        self.assertEqual(result["current_temp_celsius"], -5.0)
        self.assertEqual(result["humidity_percent"], 80.0)
        self.assertEqual(result["wind_speed_kmh"], 15.0)
        self.assertEqual(result["weather_description"], "Slight snow fall")
        self.assertEqual(result["data_source"], "open-meteo.com")

    @patch("services.openmeteo_service._request_with_retry")
    def test_request_failure_raises(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("refused")
        with self.assertRaises(Exception) as ctx:
            self.service.get_current_weather(49.72, -118.93, 1800)
        self.assertIn("Failed to fetch weather data", str(ctx.exception))


# ============================================================================
# 15. validate_api
# ============================================================================


class TestValidateApi(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service._request_with_retry")
    def test_validate_api_success(self, mock_request):
        resp = Mock()
        resp.json.return_value = {"current": {"temperature_2m": 5.0}}
        mock_request.return_value = resp
        self.assertTrue(self.service.validate_api())

    @patch("services.openmeteo_service._request_with_retry")
    def test_validate_api_failure(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("nope")
        self.assertFalse(self.service.validate_api())


# ============================================================================
# 16. _get_era5_snow_depth
# ============================================================================


class TestGetEra5SnowDepth(unittest.TestCase):
    def setUp(self):
        self.service = OpenMeteoService()

    @patch("services.openmeteo_service._request_with_retry")
    def test_era5_returns_cm(self, mock_request):
        resp = Mock()
        resp.json.return_value = {"daily": {"snow_depth_max": [None, 0.5, 0.8]}}
        mock_request.return_value = resp
        result = self.service._get_era5_snow_depth(49.72, -118.93)
        self.assertAlmostEqual(result, 80.0)  # 0.8m * 100

    @patch("services.openmeteo_service._request_with_retry")
    def test_era5_all_none(self, mock_request):
        resp = Mock()
        resp.json.return_value = {"daily": {"snow_depth_max": [None, None]}}
        mock_request.return_value = resp
        result = self.service._get_era5_snow_depth(49.72, -118.93)
        self.assertIsNone(result)

    @patch("services.openmeteo_service._request_with_retry")
    def test_era5_error_returns_none(self, mock_request):
        mock_request.side_effect = requests.exceptions.Timeout("timeout")
        result = self.service._get_era5_snow_depth(49.72, -118.93)
        self.assertIsNone(result)


class TestSmoothTimelineSnowDepth(unittest.TestCase):
    """Tests for _smooth_timeline_snow_depth."""

    def _import_fn(self):
        from services.openmeteo_service import _smooth_timeline_snow_depth

        return _smooth_timeline_snow_depth

    def test_no_smoothing_needed(self):
        """Gradual depth changes should not be modified."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 7, "snow_depth_cm": 100.0},
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": 95.0},
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 90.0},
        ]
        smooth(points)
        assert points[1]["snow_depth_cm"] == 95.0
        assert points[2]["snow_depth_cm"] == 90.0

    def test_smooth_impossible_drop(self):
        """A 115cm drop in 5 hours should be capped."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 7, "snow_depth_cm": 165.0},
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": 50.0},
        ]
        smooth(points)
        # 5 hours × 2cm/hour = 10cm max drop → 165 - 10 = 155
        assert points[1]["snow_depth_cm"] == 155.0

    def test_increases_not_modified(self):
        """Snow depth increases (new snowfall) should never be smoothed."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 7, "snow_depth_cm": 50.0},
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": 120.0},
        ]
        smooth(points)
        assert points[1]["snow_depth_cm"] == 120.0

    def test_none_depths_skipped(self):
        """None depth values should be left alone."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 7, "snow_depth_cm": 100.0},
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": None},
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 90.0},
        ]
        smooth(points)
        assert points[1]["snow_depth_cm"] is None
        assert points[2]["snow_depth_cm"] == 90.0

    def test_cross_day_boundary(self):
        """Smoothing should work across day boundaries."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 150.0},
            {"date": "2026-02-22", "hour": 7, "snow_depth_cm": 10.0},
        ]
        smooth(points)
        # (24 - 16) + 7 = 15 hours × 2cm/hour = 30cm max drop → 150 - 30 = 120
        assert points[1]["snow_depth_cm"] == 120.0

    def test_short_cross_day_gap(self):
        """Short overnight gaps should still be smoothed if drop is too large."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 200.0},
            {"date": "2026-02-22", "hour": 7, "snow_depth_cm": 10.0},
        ]
        smooth(points)
        # 15 hours × 2cm/hour = 30cm max drop → 200 - 30 = 170
        assert points[1]["snow_depth_cm"] == 170.0

    def test_cascading_smoothing(self):
        """Multiple consecutive impossible drops should be smoothed in sequence."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 7, "snow_depth_cm": 200.0},
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": 100.0},
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 20.0},
        ]
        smooth(points)
        # First: 200 → 100 (100cm drop in 5h, max 10) → smoothed to 190
        assert points[1]["snow_depth_cm"] == 190.0
        # Second: 190 → 20 (170cm drop in 4h, max 8) → smoothed to 182
        assert points[2]["snow_depth_cm"] == 182.0

    def test_empty_and_single_point(self):
        """Edge cases: empty list and single point should not crash."""
        smooth = self._import_fn()
        smooth([])  # No error
        smooth([{"date": "2026-02-21", "hour": 7, "snow_depth_cm": 100.0}])  # No error

    def test_moderate_drops_smoothed(self):
        """Drops of 10cm/h that look like model artifacts should be smoothed.

        Regression test for Jackson Hole production data where 50cm/5h and
        40cm/4h drops (exactly 10cm/h) slipped through the old 10cm/h cap.
        """
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-23", "hour": 7, "snow_depth_cm": 192.0},
            {"date": "2026-02-23", "hour": 12, "snow_depth_cm": 142.0},  # -50 in 5h
            {"date": "2026-02-23", "hour": 16, "snow_depth_cm": 102.0},  # -40 in 4h
            {"date": "2026-02-24", "hour": 7, "snow_depth_cm": 17.0},  # -85 in 15h
        ]
        smooth(points)
        # 5h × 2cm/h = 10 max drop → 192 - 10 = 182
        assert points[1]["snow_depth_cm"] == 182.0
        # 4h × 2cm/h = 8 max drop → 182 - 8 = 174
        assert points[2]["snow_depth_cm"] == 174.0
        # 15h × 2cm/h = 30 max drop → 174 - 30 = 144
        assert points[3]["snow_depth_cm"] == 144.0

    def test_depth_never_goes_negative(self):
        """Smoothed depth should never go below 0."""
        smooth = self._import_fn()
        points = [
            {"date": "2026-02-21", "hour": 12, "snow_depth_cm": 5.0},
            {"date": "2026-02-21", "hour": 16, "snow_depth_cm": 0.0},
        ]
        smooth(points)
        assert points[1]["snow_depth_cm"] >= 0


if __name__ == "__main__":
    unittest.main()
