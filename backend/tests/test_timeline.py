"""Tests for the timeline feature (OpenMeteoService.get_timeline_data and API endpoint)."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.weather import ConfidenceLevel, SnowQuality
from services.openmeteo_service import (
    OpenMeteoService,
    _smooth_hourly_snow_depth,
    _smooth_timeline_scores,
    _smooth_timeline_snow_depth,
)

# ---------------------------------------------------------------------------
# Helpers to build realistic mock Open-Meteo hourly data (14 days * 24 hours)
# ---------------------------------------------------------------------------

NUM_HOURS = 336  # 7 past days + 7 forecast days = 14 days * 24h


def _build_hourly_times(base_time: datetime | None = None) -> list[str]:
    """Build 336 hourly ISO-like timestamps starting at midnight 7 days before *base_time*.

    We start at midnight so that all hours (including 07:00 for morning) are
    present on the first day, which matches the real Open-Meteo API behaviour.
    """
    if base_time is None:
        base_time = datetime.now(UTC)
    # Start at midnight 7 days ago
    start = (base_time - timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return [
        (start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00")
        for h in range(NUM_HOURS)
    ]


def _build_mock_openmeteo_response(
    hourly_times: list[str] | None = None,
    base_temp: float = -5.0,
    snowfall_value: float = 0.2,
    snow_depth_m: float = 0.45,
    wind_speed: float = 12.0,
    weather_code: int = 71,
) -> dict:
    """Return a dict that looks like an Open-Meteo JSON response."""
    if hourly_times is None:
        hourly_times = _build_hourly_times()

    n = len(hourly_times)
    return {
        "hourly": {
            "time": hourly_times,
            "temperature_2m": [base_temp + (i % 5) for i in range(n)],
            "snowfall": [snowfall_value if i % 6 == 0 else 0.0 for i in range(n)],
            "snow_depth": [snow_depth_m for _ in range(n)],
            "wind_speed_10m": [wind_speed for _ in range(n)],
            "weather_code": [weather_code for _ in range(n)],
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def openmeteo_service():
    """Create an OpenMeteoService instance."""
    return OpenMeteoService()


@pytest.fixture
def sample_resort():
    """Create a sample resort for timeline endpoint tests."""
    return Resort(
        resort_id="big-white",
        name="Big White Ski Resort",
        country="CA",
        region="BC",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1508,
                elevation_feet=4947,
                latitude=49.7167,
                longitude=-118.9333,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1800,
                elevation_feet=5906,
                latitude=49.7200,
                longitude=-118.9300,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2319,
                elevation_feet=7608,
                latitude=49.7233,
                longitude=-118.9267,
            ),
        ],
        timezone="America/Vancouver",
        official_website="https://www.bigwhite.com",
        weather_sources=["weatherapi", "snow-report"],
        created_at="2026-01-20T08:00:00Z",
        updated_at="2026-01-20T08:00:00Z",
    )


@pytest.fixture
def sample_timeline_data():
    """Create sample timeline response data (as returned by get_timeline_data)."""
    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    def _point(date, time_label, hour, is_forecast):
        return {
            "date": date,
            "time_label": time_label,
            "hour": hour,
            "timestamp": f"{date}T{hour:02d}:00",
            "temperature_c": -5.0,
            "wind_speed_kmh": 12.0,
            "snowfall_cm": 0.4,
            "snow_depth_cm": 45.0,
            "snow_quality": "good",
            "weather_code": 71,
            "weather_description": "Slight snow fall",
            "is_forecast": is_forecast,
        }

    timeline = []
    for date, forecast in [(yesterday, False), (today, False), (tomorrow, True)]:
        timeline.append(_point(date, "morning", 7, forecast))
        timeline.append(_point(date, "midday", 12, forecast))
        timeline.append(_point(date, "afternoon", 16, forecast))

    return {
        "timeline": timeline,
        "elevation_level": "mid",
        "elevation_meters": 1800,
    }


# ---------------------------------------------------------------------------
# 1. test_get_timeline_data
# ---------------------------------------------------------------------------


class TestGetTimelineData:
    """Tests for OpenMeteoService.get_timeline_data()."""

    @patch("services.openmeteo_service._request_with_retry")
    def test_get_timeline_data(self, mock_request, openmeteo_service):
        """Mock the Open-Meteo API response, call get_timeline_data(), verify shape."""
        hourly_times = _build_hourly_times()
        mock_api_data = _build_mock_openmeteo_response(hourly_times=hourly_times)

        mock_response = Mock()
        mock_response.json.return_value = mock_api_data
        mock_request.return_value = mock_response

        result = openmeteo_service.get_timeline_data(
            latitude=49.72,
            longitude=-118.93,
            elevation_meters=1800,
            elevation_level="mid",
            timezone="GMT",
        )

        # Top-level keys
        assert "timeline" in result
        assert "elevation_level" in result
        assert "elevation_meters" in result
        assert result["elevation_level"] == "mid"
        assert result["elevation_meters"] == 1800

        timeline = result["timeline"]
        assert len(timeline) > 0

        # 3 points per day (morning, midday, afternoon)
        dates_in_timeline = sorted({p["date"] for p in timeline})
        for date_str in dates_in_timeline:
            day_points = [p for p in timeline if p["date"] == date_str]
            assert len(day_points) == 3, (
                f"Expected 3 points for {date_str}, got {len(day_points)}"
            )
            labels = [p["time_label"] for p in day_points]
            assert labels == ["morning", "midday", "afternoon"]

        # Check hours
        hours_by_label = {p["time_label"]: p["hour"] for p in timeline[:3]}
        assert hours_by_label["morning"] == 7
        assert hours_by_label["midday"] == 12
        assert hours_by_label["afternoon"] == 16

        # Each point has the required fields
        required_fields = {
            "date",
            "time_label",
            "hour",
            "timestamp",
            "temperature_c",
            "wind_speed_kmh",
            "snowfall_cm",
            "snow_depth_cm",
            "snow_quality",
            "weather_code",
            "weather_description",
            "is_forecast",
        }
        for point in timeline:
            assert required_fields.issubset(point.keys()), (
                f"Missing fields: {required_fields - point.keys()}"
            )

        # Points in the past should have is_forecast=False,
        # points in the future should have is_forecast=True
        now = datetime.now(UTC)
        for point in timeline:
            ts = point["timestamp"]
            pt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if pt.tzinfo is None:
                pt = pt.replace(tzinfo=UTC)
            if pt > now:
                assert point["is_forecast"] is True, (
                    f"Future point {ts} should be is_forecast=True"
                )
            else:
                assert point["is_forecast"] is False, (
                    f"Past point {ts} should be is_forecast=False"
                )


# ---------------------------------------------------------------------------
# 2. test_timeline_data_snowfall_windows
# ---------------------------------------------------------------------------


class TestTimelineSnowfallWindows:
    """Verify snowfall is summed correctly across morning/midday/afternoon windows."""

    @patch("services.openmeteo_service._request_with_retry")
    def test_timeline_data_snowfall_windows(self, mock_request, openmeteo_service):
        """Morning sums h5-9, midday sums h10-14, afternoon sums h14-18."""
        base_time = datetime.now(UTC)
        hourly_times = _build_hourly_times(base_time)
        n = len(hourly_times)

        # Build snowfall array: 1.0 cm for every hour so sums are easy to verify
        snowfall = [1.0] * n

        mock_api_data = {
            "hourly": {
                "time": hourly_times,
                "temperature_2m": [-5.0] * n,
                "snowfall": snowfall,
                "snow_depth": [0.5] * n,
                "wind_speed_10m": [10.0] * n,
                "weather_code": [71] * n,
            },
        }

        mock_response = Mock()
        mock_response.json.return_value = mock_api_data
        mock_request.return_value = mock_response

        result = openmeteo_service.get_timeline_data(
            latitude=49.72,
            longitude=-118.93,
            elevation_meters=1800,
            elevation_level="mid",
            timezone="GMT",
        )

        timeline = result["timeline"]
        assert len(timeline) > 0

        # Pick any complete day (use the first day that has all 3 points)
        dates = sorted({p["date"] for p in timeline})
        for date_str in dates:
            day_points = [p for p in timeline if p["date"] == date_str]
            if len(day_points) != 3:
                continue

            points_by_label = {p["time_label"]: p for p in day_points}

            # Morning window: hours 5-9 inclusive = 5 hours of 1.0 cm each = 5.0
            assert points_by_label["morning"]["snowfall_cm"] == pytest.approx(5.0), (
                f"Morning snowfall should be 5.0, got {points_by_label['morning']['snowfall_cm']}"
            )

            # Midday window: hours 10-14 inclusive = 5 hours of 1.0 cm each = 5.0
            assert points_by_label["midday"]["snowfall_cm"] == pytest.approx(5.0), (
                f"Midday snowfall should be 5.0, got {points_by_label['midday']['snowfall_cm']}"
            )

            # Afternoon window: hours 14-18 inclusive = 5 hours of 1.0 cm each = 5.0
            assert points_by_label["afternoon"]["snowfall_cm"] == pytest.approx(5.0), (
                f"Afternoon snowfall should be 5.0, got {points_by_label['afternoon']['snowfall_cm']}"
            )

            # One day verified is enough
            break


# ---------------------------------------------------------------------------
# 3. test_timeline_endpoint_success
# ---------------------------------------------------------------------------


class TestTimelineEndpoint:
    """Tests for the /api/v1/resorts/{resort_id}/timeline endpoint."""

    @patch("handlers.api_handler._get_resort_cached")
    @patch("handlers.api_handler.OpenMeteoService")
    def test_timeline_endpoint_success(
        self, mock_service_cls, mock_get_resort, sample_resort, sample_timeline_data
    ):
        """Test the API endpoint returns 200 with correct data and cache header."""
        mock_get_resort.return_value = sample_resort

        mock_service_instance = Mock()
        mock_service_instance.get_timeline_data.return_value = sample_timeline_data
        mock_service_cls.return_value = mock_service_instance

        from handlers.api_handler import app

        client = TestClient(app)

        resp = client.get("/api/v1/resorts/big-white/timeline?elevation=mid")

        assert resp.status_code == 200

        data = resp.json()
        assert "timeline" in data
        assert "elevation_level" in data
        assert "elevation_meters" in data
        assert "resort_id" in data
        assert data["resort_id"] == "big-white"
        assert data["elevation_level"] == "mid"
        assert data["elevation_meters"] == 1800
        assert len(data["timeline"]) == 9  # 3 days * 3 points

        # Cache-Control header
        assert resp.headers.get("cache-control") == "public, max-age=1800"

    # -------------------------------------------------------------------
    # 4. test_timeline_endpoint_invalid_resort
    # -------------------------------------------------------------------

    @patch("handlers.api_handler._get_resort_cached")
    def test_timeline_endpoint_invalid_resort(self, mock_get_resort):
        """Test 404 for nonexistent resort."""
        mock_get_resort.return_value = None

        from handlers.api_handler import app

        client = TestClient(app)

        resp = client.get("/api/v1/resorts/nonexistent-resort/timeline?elevation=mid")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # -------------------------------------------------------------------
    # 5. test_timeline_endpoint_invalid_elevation
    # -------------------------------------------------------------------

    def test_timeline_endpoint_invalid_elevation(self):
        """Test 400 for invalid elevation parameter."""
        from handlers.api_handler import app

        client = TestClient(app)

        resp = client.get("/api/v1/resorts/big-white/timeline?elevation=summit")

        assert resp.status_code == 400
        assert "invalid elevation" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. Temperature-aware timeline snow depth smoothing
# ---------------------------------------------------------------------------


class TestTimelineSnowDepthSmoothing:
    """Tests for temperature-aware snow depth smoothing in the timeline.

    Verifies that _smooth_timeline_snow_depth uses temperature to determine
    melt rates, matching the ML scorer logic:
    - Sub-zero temps: max 3cm/day (sublimation only)
    - Above-zero temps: max 15cm/day (active melt)
    - Forecast points enforce a floor from last observed depth
    """

    def test_subzero_prevents_unrealistic_drop(self):
        """The core bug: 144cm should not drop to 11cm in 4 days at sub-zero."""
        points = [
            {
                "date": "2026-02-20",
                "hour": 12,
                "snow_depth_cm": 144.0,
                "temperature_c": -8.0,
                "is_forecast": False,
            },
            {
                "date": "2026-02-21",
                "hour": 12,
                "snow_depth_cm": 120.0,
                "temperature_c": -6.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-22",
                "hour": 12,
                "snow_depth_cm": 80.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-23",
                "hour": 12,
                "snow_depth_cm": 40.0,
                "temperature_c": -7.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-24",
                "hour": 12,
                "snow_depth_cm": 11.0,
                "temperature_c": -6.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        # Sub-zero: max 3cm/day. After 4 days: 144 - 12 = 132 floor minimum
        # All forecast points should be well above 100cm
        assert points[1]["snow_depth_cm"] >= 140.0
        assert points[2]["snow_depth_cm"] >= 137.0
        assert points[3]["snow_depth_cm"] >= 134.0
        assert points[4]["snow_depth_cm"] >= 130.0

    def test_above_zero_allows_more_melt(self):
        """Above-zero temps should allow up to 15cm/day loss."""
        points = [
            {
                "date": "2026-02-20",
                "hour": 12,
                "snow_depth_cm": 100.0,
                "temperature_c": 3.0,
                "is_forecast": False,
            },
            {
                "date": "2026-02-21",
                "hour": 12,
                "snow_depth_cm": 60.0,
                "temperature_c": 5.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-22",
                "hour": 12,
                "snow_depth_cm": 30.0,
                "temperature_c": 4.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        # Above-zero: 15cm/day
        # Day 1: 100 - 15 = 85 (floor), pair smoothing also caps at 15cm
        assert points[1]["snow_depth_cm"] == 85.0
        # Day 2: 100 - 30 = 70 (floor from observed), pair from 85 → 85-15=70
        assert points[2]["snow_depth_cm"] == 70.0

    def test_snow_increase_not_smoothed(self):
        """Snow depth increases from new snowfall should never be modified."""
        points = [
            {
                "date": "2026-02-21",
                "hour": 7,
                "snow_depth_cm": 50.0,
                "temperature_c": -5.0,
                "is_forecast": False,
            },
            {
                "date": "2026-02-21",
                "hour": 12,
                "snow_depth_cm": 80.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-21",
                "hour": 16,
                "snow_depth_cm": 110.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        assert points[1]["snow_depth_cm"] == 80.0
        assert points[2]["snow_depth_cm"] == 110.0

    def test_mixed_observed_and_forecast(self):
        """Only forecast points get the global floor; observed points use pair smoothing only."""
        points = [
            {
                "date": "2026-02-21",
                "hour": 7,
                "snow_depth_cm": 100.0,
                "temperature_c": -5.0,
                "is_forecast": False,
            },
            {
                "date": "2026-02-21",
                "hour": 12,
                "snow_depth_cm": 98.0,
                "temperature_c": -5.0,
                "is_forecast": False,
            },
            # Forecast starts here - Open-Meteo drops it
            {
                "date": "2026-02-22",
                "hour": 7,
                "snow_depth_cm": 20.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        # Last observed: 98cm at 2026-02-21 hour 12
        # Forecast point: 19h later, sub-zero floor = 98 - (19/24)*3 = 95.6
        # Pair smoothing: 19h × 0.125 = 2.375 → 98 - 2.4 = 95.6
        assert points[2]["snow_depth_cm"] >= 95.0

    def test_no_observed_points_still_smooths(self):
        """If all points are forecast, pair smoothing still works (no floor applied)."""
        points = [
            {
                "date": "2026-02-22",
                "hour": 7,
                "snow_depth_cm": 100.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
            {
                "date": "2026-02-22",
                "hour": 12,
                "snow_depth_cm": 10.0,
                "temperature_c": -5.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        # Pair smoothing still limits drop: 5h × 0.125 = 0.625 → 100 - 0.6 = 99.4
        # No observed depth → no floor applied
        assert points[1]["snow_depth_cm"] == 99.4

    def test_multiday_subzero_forecast_stays_stable(self):
        """A 7-day forecast at sub-zero should only lose ~21cm total (3cm/day)."""
        points = [
            {
                "date": "2026-02-20",
                "hour": 12,
                "snow_depth_cm": 150.0,
                "temperature_c": -10.0,
                "is_forecast": False,
            },
        ]
        # Add 7 days of forecast points
        for day_offset in range(1, 8):
            d = f"2026-02-{20 + day_offset:02d}"
            points.append(
                {
                    "date": d,
                    "hour": 12,
                    "snow_depth_cm": 50.0,
                    "temperature_c": -10.0,
                    "is_forecast": True,
                }
            )

        _smooth_timeline_snow_depth(points)

        # After 7 days at sub-zero: 150 - 7*3 = 129 floor
        assert points[-1]["snow_depth_cm"] >= 129.0
        # Should not have lost more than ~21cm
        assert points[-1]["snow_depth_cm"] >= 128.0

    def test_transition_from_cold_to_warm(self):
        """When temp transitions from sub-zero to above-zero, rate should increase."""
        points = [
            {
                "date": "2026-02-21",
                "hour": 12,
                "snow_depth_cm": 100.0,
                "temperature_c": -5.0,
                "is_forecast": False,
            },
            # Next day: warm spell
            {
                "date": "2026-02-22",
                "hour": 12,
                "snow_depth_cm": 50.0,
                "temperature_c": 5.0,
                "is_forecast": True,
            },
        ]
        _smooth_timeline_snow_depth(points)

        # avg_temp = (-5+5)/2 = 0.0, which is >= 0 → above-zero rate
        # 24h × 0.625 = 15 max pair drop → 100 - 15 = 85
        # Floor: above-zero 100 - 1*15 = 85
        assert points[1]["snow_depth_cm"] == 85.0


# ---------------------------------------------------------------------------
# 7. Timeline score smoothing
# ---------------------------------------------------------------------------


class TestTimelineScoreSmoothing:
    """Tests for _smooth_timeline_scores which caps step-to-step score changes.

    Verifies that unrealistic score jumps caused by Open-Meteo snow depth
    splicing are smoothed to produce a more realistic timeline.
    """

    def _make_point(
        self, score, snowfall=0.0, quality_score=3.5, quality="decent", forecast=False
    ):
        """Helper to build a minimal timeline point for score smoothing tests."""
        return {
            "snow_score": score,
            "quality_score": quality_score,
            "snow_quality": quality,
            "snowfall_cm": snowfall,
            "is_forecast": forecast,
        }

    def test_caps_large_improvement(self):
        """Score jump of +19 (Big White bug) should be capped to +8."""
        points = [
            self._make_point(60, quality_score=3.39),
            self._make_point(79, quality_score=4.28),  # +19 jump
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 68  # 60 + 8
        assert points[1]["quality_score"] < 4.28  # adjusted down

    def test_caps_large_decline(self):
        """Score drop of -23 should be capped to -10."""
        points = [
            self._make_point(61, quality_score=3.40),
            self._make_point(38, quality_score=2.87),  # -23 drop
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 51  # 61 - 10
        assert points[1]["quality_score"] > 2.87  # adjusted up

    def test_allows_small_changes(self):
        """Changes within +-8/10 should not be modified."""
        points = [
            self._make_point(60, quality_score=3.39),
            self._make_point(65, quality_score=3.50),  # +5
            self._make_point(58, quality_score=3.30),  # -7
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 65  # unchanged
        assert points[2]["snow_score"] == 58  # unchanged

    def test_snowfall_relaxes_improvement_cap(self):
        """With >= 2cm snowfall, improvement cap is relaxed to +15."""
        points = [
            self._make_point(50, quality_score=3.00),
            self._make_point(70, snowfall=5.0, quality_score=4.00),  # +20 with snowfall
        ]
        _smooth_timeline_scores(points)

        # With 5cm snowfall, cap is +15, so 50 + 15 = 65
        assert points[1]["snow_score"] == 65

    def test_snowfall_below_threshold_uses_normal_cap(self):
        """With < 2cm snowfall, normal +8 cap applies."""
        points = [
            self._make_point(50, quality_score=3.00),
            self._make_point(
                70, snowfall=0.1, quality_score=4.00
            ),  # +20 with tiny snowfall
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 58  # 50 + 8

    def test_cascading_smoothing(self):
        """Multiple consecutive jumps should all be smoothed."""
        points = [
            self._make_point(50, quality_score=3.00),
            self._make_point(75, quality_score=4.20),  # +25
            self._make_point(100, quality_score=5.50),  # +25
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 58  # 50 + 8
        assert points[2]["snow_score"] == 66  # 58 + 8

    def test_cascading_decline(self):
        """Multiple consecutive drops should all be capped."""
        points = [
            self._make_point(80, quality_score=4.50),
            self._make_point(50, quality_score=3.00),  # -30
            self._make_point(20, quality_score=1.50),  # -30
        ]
        _smooth_timeline_scores(points)

        assert points[1]["snow_score"] == 70  # 80 - 10
        assert points[2]["snow_score"] == 60  # 70 - 10

    def test_quality_label_updated(self):
        """Snow quality label should be re-derived from smoothed quality_score."""
        points = [
            self._make_point(60, quality_score=3.39, quality="decent"),
            self._make_point(79, quality_score=4.28, quality="great"),  # +19 jump
        ]
        _smooth_timeline_scores(points)

        # After smoothing, quality_score should be lower than 4.0 (great threshold)
        # so quality label should change from "great" to something lower
        assert points[1]["snow_quality"] != "great"

    def test_single_point_no_error(self):
        """Single point should not cause errors."""
        points = [self._make_point(60)]
        _smooth_timeline_scores(points)
        assert points[0]["snow_score"] == 60

    def test_empty_list_no_error(self):
        """Empty list should not cause errors."""
        _smooth_timeline_scores([])

    def test_big_white_scenario(self):
        """Reproduce the exact Big White Feb 16->17 jump scenario."""
        points = [
            # Feb 16 afternoon: decent conditions, score 60
            self._make_point(60, snowfall=0.0, quality_score=3.39, quality="decent"),
            # Feb 17 morning: snow depth jumped +8cm but only 0.1cm snowfall
            self._make_point(79, snowfall=0.1, quality_score=4.28, quality="great"),
            # Feb 17 midday: still high
            self._make_point(75, snowfall=0.0, quality_score=4.08, quality="great"),
            # Feb 17 afternoon: still high
            self._make_point(77, snowfall=0.0, quality_score=4.16, quality="great"),
            # Feb 18 morning: drops back
            self._make_point(64, snowfall=0.1, quality_score=3.48, quality="decent"),
        ]
        _smooth_timeline_scores(points)

        # The +19 jump should be smoothed to max +8
        assert points[1]["snow_score"] <= 68
        # Subsequent points cascade from the smoothed value
        assert points[2]["snow_score"] <= 76
        assert points[3]["snow_score"] <= 84
        # No jump should exceed 8 between consecutive points
        for i in range(1, len(points)):
            delta = points[i]["snow_score"] - points[i - 1]["snow_score"]
            assert delta <= 8, f"Step {i}: delta={delta} exceeds +8 cap"
            assert delta >= -10, f"Step {i}: delta={delta} exceeds -10 cap"


# ---------------------------------------------------------------------------
# 8. Hourly snow depth smoothing (pre-ML scoring)
# ---------------------------------------------------------------------------


class TestSmoothHourlySnowDepth:
    """Tests for _smooth_hourly_snow_depth which smooths the raw hourly
    snow_depth array from Open-Meteo before it is fed to the ML scorer.

    This prevents unrealistic snow depth jumps (both increases and decreases)
    from causing ML score artifacts in the timeline.
    """

    def test_caps_unrealistic_increase(self):
        """Snow depth should not increase more than snowfall justifies.

        Big White scenario: +8cm overnight with only 0.1cm snowfall.
        The function should cap the increase.
        """
        # 5 hours, steady at 1.34m, then jumps to 1.42m
        snow_depth = [1.34, 1.34, 1.34, 1.34, 1.42]
        snowfall = [0.0, 0.0, 0.0, 0.0, 0.1]  # only 0.1cm snowfall
        temps = [-8.0, -8.0, -8.0, -8.0, -8.0]

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # Max gain at hour 4: 0.1 * 1.5 + 0.5 = 0.65cm = 0.0065m
        # So max depth: 1.34 + 0.0065 = 1.3465m
        assert result[4] < 1.35  # much less than the original 1.42
        assert result[4] >= 1.34  # at least as much as previous

    def test_allows_increase_with_snowfall(self):
        """Legitimate snowfall should allow depth increases."""
        snow_depth = [1.00, 1.00, 1.10]  # +10cm in one hour
        snowfall = [0.0, 0.0, 8.0]  # 8cm snowfall
        temps = [-5.0, -5.0, -5.0]

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # Max gain: 8.0 * 1.5 + 0.5 = 12.5cm = 0.125m
        # 10cm gain is within limit, should not be modified
        assert result[2] == 1.10

    def test_caps_unrealistic_decrease_subzero(self):
        """Large hourly drops at sub-zero should be capped to 0.125cm/hour."""
        snow_depth = [1.50, 1.40]  # -10cm in one hour at sub-zero
        snowfall = [0.0, 0.0]
        temps = [-10.0, -10.0]

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # Max drop: 3cm/day / 24 = 0.125cm/hour = 0.00125m
        # 1.50 - 0.00125 = 1.49875
        assert result[1] >= 1.498

    def test_allows_decrease_above_zero(self):
        """Above-zero temps allow faster melting (15cm/day = 0.625cm/hour)."""
        snow_depth = [1.00, 0.995]  # -0.5cm in one hour
        snowfall = [0.0, 0.0]
        temps = [3.0, 3.0]

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # Max drop: 0.625cm/hour = 0.00625m
        # 0.5cm drop is within limit
        assert result[1] == 0.995  # unchanged

    def test_preserves_none_values(self):
        """None values in the array should be preserved."""
        snow_depth = [1.0, None, 1.0]
        snowfall = [0.0, 0.0, 0.0]
        temps = [-5.0, -5.0, -5.0]

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        assert result[1] is None
        assert result[0] == 1.0
        assert result[2] == 1.0

    def test_empty_list_returns_empty(self):
        """Empty input should return empty output."""
        result = _smooth_hourly_snow_depth([], [], [])
        assert result == []

    def test_single_value_unchanged(self):
        """Single-element list should be returned unchanged."""
        result = _smooth_hourly_snow_depth([1.5], [0.0], [-5.0])
        assert result == [1.5]

    def test_does_not_modify_input(self):
        """The original list should not be modified."""
        original = [1.34, 1.42]
        snowfall = [0.0, 0.0]
        temps = [-5.0, -5.0]

        _smooth_hourly_snow_depth(original, snowfall, temps)

        assert original == [1.34, 1.42]

    def test_big_white_full_scenario(self):
        """Simulate the Big White Feb 16-17 pattern over 24 hours.

        Snow depth at 134cm, then Open-Meteo model splice causes jump to 142cm
        overnight with negligible snowfall. The smoothing should keep depth
        close to 134cm + accumulated snowfall.
        """
        # 24 hours: steady at 1.34m for 16h, then jumps to 1.42m at hour 17
        snow_depth = [1.34] * 17 + [1.42] * 7
        snowfall = [0.0] * 16 + [0.1] + [0.0] * 7  # 0.1cm at hour 16
        temps = [-8.0] * 24

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # At hour 17, max gain from 1.34: 0.1*1.5 + 0.5 = 0.65cm = 0.0065m
        # So depth should be ~1.3465m, not 1.42m
        assert result[17] < 1.36  # well below the 1.42 artifact
        # Hours 18-23 should cascade from the smoothed value
        for h in range(17, 24):
            assert result[h] < 1.40  # none should reach 1.42

    def test_gradual_accumulation_preserved(self):
        """Gradual accumulation over many hours with steady snowfall
        should be preserved (each hour within limits).
        """
        # 10 hours, each gaining ~1cm with 0.5cm snowfall
        snow_depth = [1.00 + i * 0.01 for i in range(10)]  # +1cm/hour
        snowfall = [0.5] * 10  # 0.5cm per hour
        temps = [-5.0] * 10

        result = _smooth_hourly_snow_depth(snow_depth, snowfall, temps)

        # Each hour gain: 1cm. Limit: 0.5*1.5 + 0.5 = 1.25cm. So all within limits.
        for i in range(10):
            assert result[i] == pytest.approx(snow_depth[i], abs=0.001)
