"""Tests for the timeline feature (OpenMeteoService.get_timeline_data and API endpoint)."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.weather import ConfidenceLevel, SnowQuality
from services.openmeteo_service import OpenMeteoService

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
