"""Unit tests for API handler route functions.

Tests individual handler functions by mocking the service layer.
Focuses on request parsing, response formatting, error handling,
and query parameter validation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from models.feedback import Feedback, FeedbackSubmission
from models.resort import ElevationLevel, ElevationPoint, Resort
from models.trip import Trip, TripCreate, TripStatus, TripUpdate
from models.user import UserPreferences
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from utils.cache import clear_all_caches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear all API caches before and after each test."""
    clear_all_caches()
    yield
    clear_all_caches()


@pytest.fixture()
def client():
    """Create a FastAPI TestClient with services reset."""
    from handlers.api_handler import app, reset_services

    reset_services()
    return TestClient(app)


def _make_resort(
    resort_id="test-resort",
    name="Test Resort",
    country="CA",
    region="BC",
    lat=49.0,
    lon=-120.0,
) -> Resort:
    """Helper to build a Resort with sensible defaults."""
    return Resort(
        resort_id=resort_id,
        name=name,
        country=country,
        region=region,
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=lat,
                longitude=lon,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1800,
                elevation_feet=5906,
                latitude=lat + 0.01,
                longitude=lon + 0.01,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2200,
                elevation_feet=7218,
                latitude=lat + 0.02,
                longitude=lon + 0.02,
            ),
        ],
        timezone="America/Vancouver",
        official_website="https://test-resort.com",
        weather_sources=["weatherapi"],
        created_at="2026-01-20T08:00:00Z",
        updated_at="2026-01-20T08:00:00Z",
    )


def _make_condition(
    resort_id="test-resort",
    elevation_level="mid",
    quality=SnowQuality.GOOD,
    quality_score=4.0,
    temp=-5.0,
    snowfall_24h=10.0,
    fresh_snow=8.0,
) -> WeatherCondition:
    """Helper to build a WeatherCondition with sensible defaults."""
    return WeatherCondition(
        resort_id=resort_id,
        elevation_level=elevation_level,
        timestamp=datetime.now(UTC).isoformat(),
        current_temp_celsius=temp,
        min_temp_celsius=temp - 3,
        max_temp_celsius=temp + 3,
        snowfall_24h_cm=snowfall_24h,
        snowfall_48h_cm=snowfall_24h * 1.5,
        snowfall_72h_cm=snowfall_24h * 2,
        hours_above_ice_threshold=0.0,
        max_consecutive_warm_hours=0.0,
        snowfall_after_freeze_cm=fresh_snow,
        hours_since_last_snowfall=2.0,
        last_freeze_thaw_hours_ago=72.0,
        currently_warming=False,
        humidity_percent=80.0,
        wind_speed_kmh=10.0,
        weather_description="Light snow",
        snow_quality=quality,
        quality_score=quality_score,
        confidence_level=ConfidenceLevel.HIGH,
        fresh_snow_cm=fresh_snow,
        data_source="test-api",
        source_confidence=ConfidenceLevel.HIGH,
        ttl=int(datetime.now(UTC).timestamp()) + 86400,
    )


# JWT helper ----------------------------------------------------------------

TEST_JWT_SECRET = "unit-test-secret-key"


def _create_token(user_id: str = "test_user") -> str:
    """Create a valid JWT token for testing authenticated endpoints."""
    from jose import jwt

    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _auth_header(user_id: str = "test_user") -> dict:
    """Return an Authorization header dict."""
    return {"Authorization": f"Bearer {_create_token(user_id)}"}


# ===========================================================================
# Health Check
# ===========================================================================


class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_keys(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data


# ===========================================================================
# Resort Endpoints
# ===========================================================================


class TestGetResorts:
    """Tests for GET /api/v1/resorts."""

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_returns_resorts_list(self, mock_cached, client):
        resort = _make_resort()
        mock_cached.return_value = [resort]

        resp = client.get("/api/v1/resorts")
        assert resp.status_code == 200
        data = resp.json()
        assert "resorts" in data
        assert len(data["resorts"]) == 1
        assert data["resorts"][0]["resort_id"] == "test-resort"

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_empty_resorts(self, mock_cached, client):
        mock_cached.return_value = []
        resp = client.get("/api/v1/resorts")
        assert resp.status_code == 200
        assert resp.json()["resorts"] == []

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_filter_by_country(self, mock_cached, client):
        ca_resort = _make_resort(resort_id="ca-resort", country="CA")
        us_resort = _make_resort(resort_id="us-resort", country="US")
        mock_cached.return_value = [ca_resort, us_resort]

        resp = client.get("/api/v1/resorts?country=CA")
        assert resp.status_code == 200
        ids = [r["resort_id"] for r in resp.json()["resorts"]]
        assert "ca-resort" in ids
        assert "us-resort" not in ids

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_filter_by_country_case_insensitive(self, mock_cached, client):
        resort = _make_resort(country="CA")
        mock_cached.return_value = [resort]

        resp = client.get("/api/v1/resorts?country=ca")
        assert resp.status_code == 200
        assert len(resp.json()["resorts"]) == 1

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_filter_by_region(self, mock_cached, client):
        # lon=-120 + country=CA -> na_west
        west = _make_resort(resort_id="west", country="CA", lon=-120.0)
        # lon=-110 + country=US -> na_rockies
        rockies = _make_resort(resort_id="rockies", country="US", lon=-110.0)
        mock_cached.return_value = [west, rockies]

        resp = client.get("/api/v1/resorts?region=na_west")
        assert resp.status_code == 200
        ids = [r["resort_id"] for r in resp.json()["resorts"]]
        assert "west" in ids
        assert "rockies" not in ids

    def test_invalid_region(self, client):
        resp = client.get("/api/v1/resorts?region=invalid_region")
        assert resp.status_code == 400
        assert "Invalid region" in resp.json()["detail"]

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_excludes_zero_coords_by_default(self, mock_cached, client):
        good = _make_resort(resort_id="good", lat=49.0, lon=-120.0)
        bad = Resort(
            resort_id="bad",
            name="No Coords",
            country="CA",
            region="BC",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.BASE,
                    elevation_meters=1500,
                    elevation_feet=4921,
                    latitude=0.0,
                    longitude=0.0,
                )
            ],
            timezone="America/Vancouver",
        )
        mock_cached.return_value = [good, bad]

        resp = client.get("/api/v1/resorts")
        assert resp.status_code == 200
        ids = [r["resort_id"] for r in resp.json()["resorts"]]
        assert "good" in ids
        assert "bad" not in ids

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_include_no_coords(self, mock_cached, client):
        bad = Resort(
            resort_id="bad",
            name="No Coords",
            country="CA",
            region="BC",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.BASE,
                    elevation_meters=1500,
                    elevation_feet=4921,
                    latitude=0.0,
                    longitude=0.0,
                )
            ],
            timezone="America/Vancouver",
        )
        mock_cached.return_value = [bad]

        resp = client.get("/api/v1/resorts?include_no_coords=true")
        assert resp.status_code == 200
        assert len(resp.json()["resorts"]) == 1

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_service_exception_returns_500(self, mock_cached, client):
        mock_cached.side_effect = RuntimeError("DB down")
        resp = client.get("/api/v1/resorts")
        assert resp.status_code == 500
        assert "Failed to retrieve resorts" in resp.json()["detail"]


class TestGetResortById:
    """Tests for GET /api/v1/resorts/{resort_id}."""

    @patch("handlers.api_handler._get_resort_cached")
    def test_found(self, mock_cached, client):
        mock_cached.return_value = _make_resort()
        resp = client.get("/api/v1/resorts/test-resort")
        assert resp.status_code == 200
        assert resp.json()["resort_id"] == "test-resort"

    @patch("handlers.api_handler._get_resort_cached")
    def test_not_found(self, mock_cached, client):
        mock_cached.return_value = None
        resp = client.get("/api/v1/resorts/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("handlers.api_handler._get_resort_cached")
    def test_service_error(self, mock_cached, client):
        mock_cached.side_effect = RuntimeError("DB error")
        resp = client.get("/api/v1/resorts/test-resort")
        assert resp.status_code == 500


class TestGetNearbyResorts:
    """Tests for GET /api/v1/resorts/nearby."""

    @patch("handlers.api_handler.get_resort_service")
    def test_nearby_success(self, mock_svc, client):
        resort = _make_resort()
        svc = MagicMock()
        svc.get_nearby_resorts.return_value = [(resort, 25.3)]
        mock_svc.return_value = svc

        resp = client.get("/api/v1/resorts/nearby?lat=49.0&lon=-120.0&radius=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert "distance_km" in data["resorts"][0]
        assert "distance_miles" in data["resorts"][0]
        assert data["search_center"]["latitude"] == 49.0
        assert data["search_radius_km"] == 50.0

    def test_missing_params(self, client):
        resp = client.get("/api/v1/resorts/nearby")
        assert resp.status_code == 422

    def test_invalid_latitude(self, client):
        resp = client.get("/api/v1/resorts/nearby?lat=100&lon=0")
        assert resp.status_code == 422

    def test_invalid_longitude(self, client):
        resp = client.get("/api/v1/resorts/nearby?lat=0&lon=200")
        assert resp.status_code == 422

    def test_radius_too_large(self, client):
        resp = client.get("/api/v1/resorts/nearby?lat=49&lon=-123&radius=3000")
        assert resp.status_code == 422

    def test_radius_too_small(self, client):
        resp = client.get("/api/v1/resorts/nearby?lat=49&lon=-123&radius=0")
        assert resp.status_code == 422


# ===========================================================================
# Regions
# ===========================================================================


class TestGetRegions:
    """Tests for GET /api/v1/regions."""

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_returns_regions(self, mock_cached, client):
        # CA resort with lon=-120 => na_west
        mock_cached.return_value = [_make_resort(country="CA", lon=-120.0)]
        resp = client.get("/api/v1/regions")
        assert resp.status_code == 200
        data = resp.json()
        assert "regions" in data
        assert len(data["regions"]) >= 1
        region = data["regions"][0]
        assert "id" in region
        assert "name" in region
        assert "display_name" in region
        assert "resort_count" in region

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_empty_regions(self, mock_cached, client):
        mock_cached.return_value = []
        resp = client.get("/api/v1/regions")
        assert resp.status_code == 200
        assert resp.json()["regions"] == []

    @patch("handlers.api_handler._get_all_resorts_cached")
    def test_service_error(self, mock_cached, client):
        mock_cached.side_effect = RuntimeError("boom")
        resp = client.get("/api/v1/regions")
        assert resp.status_code == 500


# ===========================================================================
# Conditions Endpoints
# ===========================================================================


class TestGetResortConditions:
    """Tests for GET /api/v1/resorts/{resort_id}/conditions."""

    @patch("handlers.api_handler._get_conditions_cached")
    @patch("handlers.api_handler._get_resort_cached")
    def test_conditions_success(self, mock_resort, mock_cond, client):
        mock_resort.return_value = _make_resort()
        cond = _make_condition()
        mock_cond.return_value = [cond]

        resp = client.get("/api/v1/resorts/test-resort/conditions")
        assert resp.status_code == 200
        data = resp.json()
        assert "conditions" in data
        assert data["resort_id"] == "test-resort"
        assert "last_updated" in data

    @patch("handlers.api_handler._get_resort_cached")
    def test_resort_not_found(self, mock_resort, client):
        mock_resort.return_value = None
        resp = client.get("/api/v1/resorts/nonexistent/conditions")
        assert resp.status_code == 404

    def test_hours_validation_too_low(self, client):
        resp = client.get("/api/v1/resorts/test/conditions?hours=0")
        assert resp.status_code == 422

    def test_hours_validation_too_high(self, client):
        resp = client.get("/api/v1/resorts/test/conditions?hours=200")
        assert resp.status_code == 422

    @patch("handlers.api_handler._get_conditions_cached")
    @patch("handlers.api_handler._get_resort_cached")
    def test_empty_conditions(self, mock_resort, mock_cond, client):
        mock_resort.return_value = _make_resort()
        mock_cond.return_value = []

        resp = client.get("/api/v1/resorts/test-resort/conditions")
        assert resp.status_code == 200
        assert resp.json()["conditions"] == []


class TestGetElevationCondition:
    """Tests for GET /api/v1/resorts/{resort_id}/conditions/{elevation_level}."""

    @patch("handlers.api_handler._get_latest_condition_cached")
    @patch("handlers.api_handler._get_resort_cached")
    def test_success(self, mock_resort, mock_cond, client):
        mock_resort.return_value = _make_resort()
        mock_cond.return_value = _make_condition(elevation_level="base")

        resp = client.get("/api/v1/resorts/test-resort/conditions/base")
        assert resp.status_code == 200

    @patch("handlers.api_handler._get_resort_cached")
    def test_invalid_elevation_level(self, mock_resort, client):
        mock_resort.return_value = _make_resort()
        resp = client.get("/api/v1/resorts/test-resort/conditions/invalid")
        assert resp.status_code == 400
        assert "Invalid elevation level" in resp.json()["detail"]

    @patch("handlers.api_handler._get_resort_cached")
    def test_resort_not_found(self, mock_resort, client):
        mock_resort.return_value = None
        resp = client.get("/api/v1/resorts/nonexistent/conditions/base")
        assert resp.status_code == 404

    @patch("handlers.api_handler._get_latest_condition_cached")
    @patch("handlers.api_handler._get_resort_cached")
    def test_no_condition_data(self, mock_resort, mock_cond, client):
        mock_resort.return_value = _make_resort()
        mock_cond.return_value = None

        resp = client.get("/api/v1/resorts/test-resort/conditions/base")
        assert resp.status_code == 404
        assert "No conditions found" in resp.json()["detail"]


# ===========================================================================
# Batch Conditions
# ===========================================================================


class TestBatchConditions:
    """Tests for GET /api/v1/conditions/batch."""

    @patch("handlers.api_handler._get_conditions_cached")
    def test_batch_success(self, mock_cond, client):
        cond = _make_condition()
        mock_cond.return_value = [cond]

        resp = client.get("/api/v1/conditions/batch?resort_ids=a,b")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "resort_count" in data
        assert data["resort_count"] == 2

    def test_empty_resort_ids(self, client):
        resp = client.get("/api/v1/conditions/batch?resort_ids=")
        assert resp.status_code == 400
        assert "No resort IDs" in resp.json()["detail"]

    def test_too_many_resort_ids(self, client):
        ids = ",".join([f"r{i}" for i in range(51)])
        resp = client.get(f"/api/v1/conditions/batch?resort_ids={ids}")
        assert resp.status_code == 400
        assert "Maximum 50" in resp.json()["detail"]

    def test_missing_resort_ids_param(self, client):
        resp = client.get("/api/v1/conditions/batch")
        assert resp.status_code == 422

    @patch("handlers.api_handler._get_conditions_cached")
    def test_individual_resort_error_captured(self, mock_cond, client):
        """If one resort fails, its error is captured in the result."""
        mock_cond.side_effect = RuntimeError("Weather service down")

        resp = client.get("/api/v1/conditions/batch?resort_ids=bad-resort")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"]["bad-resort"]["error"] is not None
        assert data["results"]["bad-resort"]["conditions"] == []


# ===========================================================================
# Snow Quality Summary
# ===========================================================================


class TestSnowQualitySummary:
    """Tests for GET /api/v1/resorts/{resort_id}/snow-quality."""

    @patch("handlers.api_handler.get_weather_service")
    @patch("handlers.api_handler._get_resort_cached")
    def test_no_conditions(self, mock_resort, mock_weather_svc, client):
        mock_resort.return_value = _make_resort()
        svc = MagicMock()
        svc.get_latest_conditions_all_elevations.return_value = []
        mock_weather_svc.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/snow-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resort_id"] == "test-resort"
        assert data["overall_quality"] == "unknown"
        assert data["elevations"] == {}
        assert data["last_updated"] is None

    @patch("handlers.api_handler._get_resort_cached")
    def test_resort_not_found(self, mock_resort, client):
        mock_resort.return_value = None
        resp = client.get("/api/v1/resorts/nonexistent/snow-quality")
        assert resp.status_code == 404

    @patch("handlers.api_handler.generate_overall_explanation")
    @patch("handlers.api_handler.generate_quality_explanation")
    @patch("handlers.api_handler.score_to_100")
    @patch("handlers.api_handler.raw_score_to_quality")
    @patch("handlers.api_handler.get_weather_service")
    @patch("handlers.api_handler._get_resort_cached")
    def test_with_conditions(
        self,
        mock_resort,
        mock_weather_svc,
        mock_raw_to_quality,
        mock_score_100,
        mock_gen_explanation,
        mock_gen_overall,
        client,
    ):
        mock_resort.return_value = _make_resort()
        conditions = [
            _make_condition(elevation_level="top", quality_score=5.0),
            _make_condition(elevation_level="mid", quality_score=4.0),
            _make_condition(elevation_level="base", quality_score=3.0),
        ]
        svc = MagicMock()
        svc.get_latest_conditions_all_elevations.return_value = conditions
        mock_weather_svc.return_value = svc
        mock_raw_to_quality.return_value = SnowQuality.GOOD
        mock_score_100.return_value = 72
        mock_gen_explanation.return_value = "Good conditions"
        mock_gen_overall.return_value = "Overall good"

        resp = client.get("/api/v1/resorts/test-resort/snow-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resort_id"] == "test-resort"
        assert "elevations" in data
        assert "top" in data["elevations"]
        assert "mid" in data["elevations"]
        assert "base" in data["elevations"]
        assert data["overall_quality"] == "good"
        assert data["overall_snow_score"] == 72
        assert "quality_info" in data
        assert "last_updated" in data


# ===========================================================================
# Batch Snow Quality
# ===========================================================================


class TestBatchSnowQuality:
    """Tests for GET /api/v1/snow-quality/batch."""

    @patch("handlers.api_handler._get_static_snow_quality_from_s3")
    @patch("handlers.api_handler._get_snow_quality_for_resort")
    def test_batch_success_dynamodb(self, mock_quality, mock_s3, client):
        mock_s3.return_value = None  # No S3 static data
        mock_quality.return_value = {
            "resort_id": "resort-a",
            "overall_quality": "good",
            "snow_score": 70,
        }

        resp = client.get("/api/v1/snow-quality/batch?resort_ids=resort-a,resort-b")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["source"] == "dynamodb"
        assert data["resort_count"] >= 1

    @patch("handlers.api_handler._get_static_snow_quality_from_s3")
    def test_batch_success_static(self, mock_s3, client):
        mock_s3.return_value = {
            "resort-a": {"overall_quality": "excellent", "snow_score": 90},
            "resort-b": {"overall_quality": "good", "snow_score": 70},
        }

        resp = client.get("/api/v1/snow-quality/batch?resort_ids=resort-a,resort-b")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "static"
        assert data["resort_count"] == 2

    def test_empty_ids(self, client):
        resp = client.get("/api/v1/snow-quality/batch?resort_ids=")
        assert resp.status_code == 400
        assert "No resort IDs" in resp.json()["detail"]

    def test_too_many_ids(self, client):
        ids = ",".join([f"r{i}" for i in range(201)])
        resp = client.get(f"/api/v1/snow-quality/batch?resort_ids={ids}")
        assert resp.status_code == 400
        assert "Maximum 200" in resp.json()["detail"]

    def test_missing_param(self, client):
        resp = client.get("/api/v1/snow-quality/batch")
        assert resp.status_code == 422


# ===========================================================================
# Quality Explanations
# ===========================================================================


class TestQualityExplanations:
    """Tests for GET /api/v1/quality-explanations."""

    def test_returns_all_qualities(self, client):
        resp = client.get("/api/v1/quality-explanations")
        assert resp.status_code == 200
        data = resp.json()
        assert "explanations" in data
        assert "algorithm_info" in data
        for q in SnowQuality:
            assert q.value in data["explanations"]
            entry = data["explanations"][q.value]
            assert "title" in entry
            assert "description" in entry
            assert "criteria" in entry


# ===========================================================================
# Timeline
# ===========================================================================


class TestResortTimeline:
    """Tests for GET /api/v1/resorts/{resort_id}/timeline."""

    @patch("handlers.api_handler.get_timeline_cache")
    @patch("handlers.api_handler.OpenMeteoService")
    @patch("handlers.api_handler._get_resort_cached")
    def test_timeline_success(self, mock_resort, mock_service_cls, mock_cache, client):
        mock_resort.return_value = _make_resort()
        mock_cache.return_value = {}  # Empty cache -> miss
        mock_instance = MagicMock()
        mock_instance.get_timeline_data.return_value = {
            "timeline": [],
            "elevation_level": "mid",
            "elevation_meters": 1800,
        }
        mock_service_cls.return_value = mock_instance

        resp = client.get("/api/v1/resorts/test-resort/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "timeline" in data
        assert data["resort_id"] == "test-resort"

    @patch("handlers.api_handler._get_resort_cached")
    def test_invalid_elevation(self, mock_resort, client):
        mock_resort.return_value = _make_resort()
        resp = client.get("/api/v1/resorts/test-resort/timeline?elevation=invalid")
        assert resp.status_code == 400
        assert "Invalid elevation level" in resp.json()["detail"]

    @patch("handlers.api_handler._get_resort_cached")
    def test_resort_not_found(self, mock_resort, client):
        mock_resort.return_value = None
        resp = client.get("/api/v1/resorts/nonexistent/timeline")
        assert resp.status_code == 404

    @patch("handlers.api_handler.get_timeline_cache")
    @patch("handlers.api_handler._get_resort_cached")
    def test_cache_hit(self, mock_resort, mock_cache, client):
        mock_resort.return_value = _make_resort()
        cached = {
            "test-resort:mid": {
                "timeline": [{"date": "2026-01-20"}],
                "elevation_level": "mid",
                "elevation_meters": 1800,
                "resort_id": "test-resort",
            }
        }
        mock_cache.return_value = cached

        resp = client.get("/api/v1/resorts/test-resort/timeline?elevation=mid")
        assert resp.status_code == 200
        assert resp.headers.get("X-Cache") == "HIT"


# ===========================================================================
# User Preferences (authenticated)
# ===========================================================================


@patch("handlers.api_handler.get_auth_service")
class TestUserPreferences:
    """Tests for user preference endpoints (require auth)."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_user_service")
    def test_get_preferences_existing(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        prefs = UserPreferences(
            user_id="test_user",
            favorite_resorts=["big-white"],
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        mock_user_svc.return_value = svc

        resp = client.get("/api/v1/user/preferences", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test_user"
        assert "favorite_resorts" in data

    @patch("handlers.api_handler.get_user_service")
    def test_get_preferences_new_user(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        resp = client.get("/api/v1/user/preferences", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test_user"
        assert data["favorite_resorts"] == []

    @patch("handlers.api_handler.get_user_service")
    def test_update_preferences(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.save_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        payload = {
            "user_id": "test_user",
            "favorite_resorts": ["big-white"],
            "notification_preferences": {"snow_alerts": True},
            "preferred_units": {"temperature": "celsius"},
            "quality_threshold": "good",
            "created_at": "2026-01-20T08:00:00Z",
            "updated_at": "2026-01-20T08:00:00Z",
        }
        resp = client.put(
            "/api/v1/user/preferences", json=payload, headers=_auth_header()
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

    def test_no_auth_returns_401(self, mock_auth, client):
        from services.auth_service import AuthenticationError

        auth = MagicMock()
        auth.verify_access_token.side_effect = AuthenticationError("Invalid token")
        mock_auth.return_value = auth

        resp = client.get(
            "/api/v1/user/preferences",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401

    def test_missing_auth_header(self, mock_auth, client):
        resp = client.get("/api/v1/user/preferences")
        assert resp.status_code == 401


# ===========================================================================
# Feedback
# ===========================================================================


class TestFeedback:
    """Tests for POST /api/v1/feedback."""

    @patch("handlers.api_handler.get_feedback_table")
    def test_submit_feedback_success(self, mock_table, client):
        table = MagicMock()
        table.put_item.return_value = {}
        mock_table.return_value = table

        payload = {
            "subject": "Great app!",
            "message": "I love the snow quality feature, works really well.",
            "email": "test@example.com",
            "app_version": "1.0.0",
            "build_number": "42",
            "device_model": "iPhone 15",
            "ios_version": "18.0",
        }
        resp = client.post("/api/v1/feedback", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert "id" in data

    def test_submit_feedback_missing_required_fields(self, client):
        resp = client.post("/api/v1/feedback", json={"subject": "Hi"})
        assert resp.status_code == 422

    def test_submit_feedback_message_too_short(self, client):
        payload = {
            "subject": "Hi",
            "message": "Short",  # < 10 chars
            "app_version": "1.0",
            "build_number": "1",
        }
        resp = client.post("/api/v1/feedback", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# Authentication Endpoints
# ===========================================================================


class TestAuthEndpoints:
    """Tests for auth endpoints."""

    @patch("handlers.api_handler.get_auth_service")
    def test_guest_auth_success(self, mock_auth_svc, client):
        user = MagicMock()
        user.to_dict.return_value = {"user_id": "guest_123", "is_guest": True}
        user.is_new_user = True

        auth = MagicMock()
        auth.create_guest_session.return_value = user
        auth.create_session_tokens.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
        }
        mock_auth_svc.return_value = auth

        resp = client.post("/api/v1/auth/guest", json={"device_id": "dev-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "tokens" in data
        assert "is_new_user" in data

    @patch("handlers.api_handler.get_auth_service")
    def test_guest_auth_error(self, mock_auth_svc, client):
        from services.auth_service import AuthenticationError

        auth = MagicMock()
        auth.create_guest_session.side_effect = AuthenticationError("fail")
        mock_auth_svc.return_value = auth

        resp = client.post("/api/v1/auth/guest", json={"device_id": "dev-123"})
        assert resp.status_code == 401

    @patch("handlers.api_handler.get_auth_service")
    def test_refresh_token_success(self, mock_auth_svc, client):
        auth = MagicMock()
        auth.refresh_tokens.return_value = {
            "access_token": "new_at",
            "refresh_token": "new_rt",
        }
        mock_auth_svc.return_value = auth

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "old_rt"})
        assert resp.status_code == 200
        assert "tokens" in resp.json()

    @patch("handlers.api_handler.get_auth_service")
    def test_refresh_token_invalid(self, mock_auth_svc, client):
        from services.auth_service import AuthenticationError

        auth = MagicMock()
        auth.refresh_tokens.side_effect = AuthenticationError("expired")
        mock_auth_svc.return_value = auth

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad_rt"})
        assert resp.status_code == 401

    @patch("handlers.api_handler.get_user_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_get_current_user(self, mock_auth_svc, mock_user_svc, client):
        auth = MagicMock()
        auth.verify_access_token.return_value = "user_123"
        mock_auth_svc.return_value = auth

        prefs = UserPreferences(
            user_id="user_123",
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        mock_user_svc.return_value = svc

        resp = client.get("/api/v1/auth/me", headers=_auth_header("user_123"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user_123"
        assert "preferences" in data

    @patch("handlers.api_handler.get_auth_service")
    def test_apple_signin_success(self, mock_auth_svc, client):
        user = MagicMock()
        user.to_dict.return_value = {"user_id": "apple_123"}
        user.is_new_user = False

        auth = MagicMock()
        auth.verify_apple_token.return_value = user
        auth.create_session_tokens.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
        }
        mock_auth_svc.return_value = auth

        resp = client.post(
            "/api/v1/auth/apple",
            json={"identity_token": "eyJ..."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "tokens" in data
        assert data["is_new_user"] is False

    @patch("handlers.api_handler.get_auth_service")
    def test_apple_signin_auth_error(self, mock_auth_svc, client):
        from services.auth_service import AuthenticationError

        auth = MagicMock()
        auth.verify_apple_token.side_effect = AuthenticationError("Invalid token")
        mock_auth_svc.return_value = auth

        resp = client.post(
            "/api/v1/auth/apple",
            json={"identity_token": "invalid"},
        )
        assert resp.status_code == 401


# ===========================================================================
# Recommendations
# ===========================================================================


class TestRecommendations:
    """Tests for recommendation endpoints."""

    @patch("handlers.api_handler.get_recommendation_service")
    def test_get_recommendations_success(self, mock_svc, client):
        rec = MagicMock()
        rec.to_dict.return_value = {
            "resort_id": "big-white",
            "name": "Big White",
            "quality": "excellent",
            "distance_km": 50,
        }

        svc = MagicMock()
        svc.get_recommendations.return_value = [rec]
        mock_svc.return_value = svc

        resp = client.get("/api/v1/recommendations?lat=49.0&lng=-120.0")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert data["count"] == 1
        assert "search_center" in data
        assert "generated_at" in data

    def test_missing_params(self, client):
        resp = client.get("/api/v1/recommendations")
        assert resp.status_code == 422

    @patch("handlers.api_handler.get_recommendation_service")
    def test_invalid_min_quality(self, mock_svc, client):
        resp = client.get(
            "/api/v1/recommendations?lat=49&lng=-120&min_quality=nonexistent"
        )
        assert resp.status_code == 400
        assert "Invalid quality filter" in resp.json()["detail"]

    @patch("handlers.api_handler.get_recommendations_cache")
    @patch("handlers.api_handler.get_recommendation_service")
    def test_best_conditions_success(self, mock_svc, mock_cache, client):
        mock_cache.return_value = {}
        rec = MagicMock()
        rec.to_dict.return_value = {
            "resort_id": "whistler",
            "quality": "excellent",
        }
        svc = MagicMock()
        svc.get_best_conditions_globally.return_value = [rec]
        mock_svc.return_value = svc

        resp = client.get("/api/v1/recommendations/best")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert "generated_at" in data

    @patch("handlers.api_handler.get_recommendations_cache")
    def test_best_conditions_cache_hit(self, mock_cache, client):
        cached_result = {
            "best_conditions_10_none": {
                "recommendations": [],
                "count": 0,
                "generated_at": "2026-01-20T00:00:00Z",
            }
        }
        mock_cache.return_value = cached_result

        resp = client.get("/api/v1/recommendations/best")
        assert resp.status_code == 200
        assert resp.headers.get("X-Cache") == "HIT"

    @patch("handlers.api_handler.get_recommendations_cache")
    def test_best_conditions_invalid_quality(self, mock_cache, client):
        mock_cache.return_value = {}
        resp = client.get("/api/v1/recommendations/best?min_quality=nonsense")
        assert resp.status_code == 400


# ===========================================================================
# Trip Endpoints (authenticated)
# ===========================================================================


@patch("handlers.api_handler.get_auth_service")
class TestTripEndpoints:
    """Tests for trip CRUD endpoints."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    def _make_trip(self, trip_id="trip-1", user_id="test_user"):
        return Trip(
            trip_id=trip_id,
            user_id=user_id,
            resort_id="big-white",
            resort_name="Big White",
            start_date="2026-03-01",
            end_date="2026-03-05",
            status=TripStatus.PLANNED,
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )

    @patch("handlers.api_handler.get_trip_service")
    def test_create_trip(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        trip = self._make_trip()
        svc = MagicMock()
        svc.create_trip.return_value = trip
        mock_trip_svc.return_value = svc

        payload = {
            "resort_id": "big-white",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
        }
        resp = client.post("/api/v1/trips", json=payload, headers=_auth_header())
        assert resp.status_code == 201
        data = resp.json()
        assert data["trip_id"] == "trip-1"
        assert data["resort_id"] == "big-white"

    @patch("handlers.api_handler.get_trip_service")
    def test_create_trip_validation_error(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.create_trip.side_effect = ValueError("Resort not found")
        mock_trip_svc.return_value = svc

        payload = {
            "resort_id": "nonexistent",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
        }
        resp = client.post("/api/v1/trips", json=payload, headers=_auth_header())
        assert resp.status_code == 400

    @patch("handlers.api_handler.get_trip_service")
    def test_get_user_trips(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        trips = [self._make_trip()]
        svc = MagicMock()
        svc.get_user_trips.return_value = trips
        mock_trip_svc.return_value = svc

        resp = client.get("/api/v1/trips", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert "trips" in data

    @patch("handlers.api_handler.get_trip_service")
    def test_get_user_trips_with_status_filter(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_user_trips.return_value = []
        mock_trip_svc.return_value = svc

        resp = client.get("/api/v1/trips?status=planned", headers=_auth_header())
        assert resp.status_code == 200
        svc.get_user_trips.assert_called_once_with(
            user_id="test_user",
            status=TripStatus.PLANNED,
            include_past=True,
        )

    @patch("handlers.api_handler.get_trip_service")
    def test_get_user_trips_invalid_status(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        resp = client.get("/api/v1/trips?status=invalid", headers=_auth_header())
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["detail"]

    @patch("handlers.api_handler.get_trip_service")
    def test_get_trip_by_id(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        trip = self._make_trip()
        svc = MagicMock()
        svc.get_trip.return_value = trip
        mock_trip_svc.return_value = svc

        resp = client.get("/api/v1/trips/trip-1", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["trip_id"] == "trip-1"

    @patch("handlers.api_handler.get_trip_service")
    def test_get_trip_not_found(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_trip.return_value = None
        mock_trip_svc.return_value = svc

        resp = client.get("/api/v1/trips/nonexistent", headers=_auth_header())
        assert resp.status_code == 404

    @patch("handlers.api_handler.get_trip_service")
    def test_update_trip(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        updated = self._make_trip()
        svc = MagicMock()
        svc.update_trip.return_value = updated
        mock_trip_svc.return_value = svc

        payload = {"notes": "Bring extra layers"}
        resp = client.put("/api/v1/trips/trip-1", json=payload, headers=_auth_header())
        assert resp.status_code == 200

    @patch("handlers.api_handler.get_trip_service")
    def test_update_trip_not_found(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.update_trip.side_effect = ValueError("Trip not found")
        mock_trip_svc.return_value = svc

        payload = {"notes": "update"}
        resp = client.put("/api/v1/trips/trip-1", json=payload, headers=_auth_header())
        assert resp.status_code == 404

    @patch("handlers.api_handler.get_trip_service")
    def test_delete_trip(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.delete_trip.return_value = True
        mock_trip_svc.return_value = svc

        resp = client.delete("/api/v1/trips/trip-1", headers=_auth_header())
        assert resp.status_code == 204

    @patch("handlers.api_handler.get_trip_service")
    def test_delete_trip_not_found(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.delete_trip.return_value = False
        mock_trip_svc.return_value = svc

        resp = client.delete("/api/v1/trips/trip-1", headers=_auth_header())
        assert resp.status_code == 404

    def test_trips_require_auth(self, mock_auth, client):
        resp = client.get("/api/v1/trips")
        assert resp.status_code == 401

    @patch("handlers.api_handler.get_trip_service")
    def test_refresh_trip_conditions(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        trip = self._make_trip()
        svc = MagicMock()
        svc.update_trip_conditions.return_value = trip
        mock_trip_svc.return_value = svc

        resp = client.post(
            "/api/v1/trips/trip-1/refresh-conditions", headers=_auth_header()
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trip_id"] == "trip-1"
        assert "unread_alerts" in data

    @patch("handlers.api_handler.get_trip_service")
    def test_refresh_trip_conditions_not_found(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.update_trip_conditions.side_effect = ValueError("Trip not found")
        mock_trip_svc.return_value = svc

        resp = client.post(
            "/api/v1/trips/trip-1/refresh-conditions", headers=_auth_header()
        )
        assert resp.status_code == 404

    @patch("handlers.api_handler.get_trip_service")
    def test_mark_alerts_read(self, mock_trip_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.mark_alerts_read.return_value = 3
        mock_trip_svc.return_value = svc

        resp = client.post("/api/v1/trips/trip-1/alerts/read", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["marked_read"] == 3


# ===========================================================================
# Resort Events
# ===========================================================================


class TestResortEvents:
    """Tests for resort event endpoints."""

    @patch("handlers.api_handler.get_resort_events_table")
    def test_get_events_success(self, mock_table, client):
        table = MagicMock()
        table.query.return_value = {
            "Items": [
                {
                    "event_id": "evt-1",
                    "resort_id": "big-white",
                    "title": "Free Demo Day",
                    "event_date": "2026-02-15",
                }
            ]
        }
        mock_table.return_value = table

        resp = client.get("/api/v1/resorts/big-white/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resort_id"] == "big-white"
        assert data["count"] == 1
        assert "events" in data

    @patch("handlers.api_handler.get_resort_events_table")
    def test_get_events_empty(self, mock_table, client):
        table = MagicMock()
        table.query.return_value = {"Items": []}
        mock_table.return_value = table

        resp = client.get("/api/v1/resorts/big-white/events")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @patch("handlers.api_handler.get_auth_service")
    @patch("handlers.api_handler.get_resort_events_table")
    def test_create_event(self, mock_table, mock_auth, client):
        auth = MagicMock()
        auth.verify_access_token.return_value = "admin_user"
        mock_auth.return_value = auth

        table = MagicMock()
        table.put_item.return_value = {}
        mock_table.return_value = table

        payload = {
            "event_type": "free_store",
            "title": "Free Demo Day",
            "event_date": "2026-02-15",
        }
        resp = client.post(
            "/api/v1/resorts/big-white/events",
            json=payload,
            headers=_auth_header("admin_user"),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "event_id" in data
        assert data["resort_id"] == "big-white"

    @patch("handlers.api_handler.get_auth_service")
    @patch("handlers.api_handler.get_resort_events_table")
    def test_delete_event(self, mock_table, mock_auth, client):
        auth = MagicMock()
        auth.verify_access_token.return_value = "admin_user"
        mock_auth.return_value = auth

        table = MagicMock()
        table.delete_item.return_value = {}
        mock_table.return_value = table

        resp = client.delete(
            "/api/v1/resorts/big-white/events/evt-1",
            headers=_auth_header("admin_user"),
        )
        assert resp.status_code == 204


# ===========================================================================
# Device Tokens
# ===========================================================================


@patch("handlers.api_handler.get_auth_service")
class TestDeviceTokens:
    """Tests for device token endpoints."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_notification_service")
    def test_register_device_token(self, mock_notif_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        from models.notification import DeviceToken

        token = DeviceToken(
            user_id="test_user",
            device_id="dev-123",
            token="apns-token-abc",
            platform="ios",
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.register_device_token.return_value = token
        mock_notif_svc.return_value = svc

        payload = {
            "device_id": "dev-123",
            "token": "apns-token-abc",
            "platform": "ios",
        }
        resp = client.post(
            "/api/v1/user/device-tokens",
            json=payload,
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        assert resp.json()["device_id"] == "dev-123"

    @patch("handlers.api_handler.get_notification_service")
    def test_unregister_device_token(self, mock_notif_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.unregister_device_token.return_value = None
        mock_notif_svc.return_value = svc

        resp = client.delete(
            "/api/v1/user/device-tokens/dev-123",
            headers=_auth_header(),
        )
        assert resp.status_code == 204

    @patch("handlers.api_handler.get_notification_service")
    def test_get_device_tokens(self, mock_notif_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        from models.notification import DeviceToken

        tokens = [
            DeviceToken(
                user_id="test_user",
                device_id="dev-123",
                token="apns-token-abc",
                platform="ios",
                app_version="1.0.0",
                created_at="2026-01-20T08:00:00Z",
                updated_at="2026-01-20T08:00:00Z",
            )
        ]
        svc = MagicMock()
        svc.get_user_device_tokens.return_value = tokens
        mock_notif_svc.return_value = svc

        resp = client.get("/api/v1/user/device-tokens", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["tokens"][0]["device_id"] == "dev-123"


# ===========================================================================
# Notification Settings
# ===========================================================================


@patch("handlers.api_handler.get_auth_service")
class TestNotificationSettings:
    """Tests for notification settings endpoints."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_user_service")
    def test_get_notification_settings_existing(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        prefs = UserPreferences(
            user_id="test_user",
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        mock_user_svc.return_value = svc

        resp = client.get("/api/v1/user/notification-settings", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications_enabled" in data
        assert "fresh_snow_alerts" in data

    @patch("handlers.api_handler.get_user_service")
    def test_get_notification_settings_new_user(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        resp = client.get("/api/v1/user/notification-settings", headers=_auth_header())
        assert resp.status_code == 200

    @patch("handlers.api_handler.get_user_service")
    def test_update_notification_settings(self, mock_user_svc, mock_auth, client):
        self._mock_auth(mock_auth)
        prefs = UserPreferences(
            user_id="test_user",
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        svc.save_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        payload = {"fresh_snow_alerts": False, "weekly_summary": True}
        resp = client.put(
            "/api/v1/user/notification-settings",
            json=payload,
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

    @patch("handlers.api_handler.get_user_service")
    def test_update_resort_notification_settings(
        self, mock_user_svc, mock_auth, client
    ):
        self._mock_auth(mock_auth)
        prefs = UserPreferences(
            user_id="test_user",
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        svc.save_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        payload = {"fresh_snow_enabled": True, "fresh_snow_threshold_cm": 5.0}
        resp = client.put(
            "/api/v1/user/notification-settings/resorts/big-white",
            json=payload,
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert "big-white" in resp.json()["message"]

    @patch("handlers.api_handler.get_user_service")
    def test_delete_resort_notification_settings(
        self, mock_user_svc, mock_auth, client
    ):
        self._mock_auth(mock_auth)
        from models.notification import (
            ResortNotificationSettings,
            UserNotificationPreferences,
        )

        notif_settings = UserNotificationPreferences(
            resort_settings={
                "big-white": ResortNotificationSettings(
                    resort_id="big-white",
                    fresh_snow_threshold_cm=5.0,
                )
            }
        )
        prefs = UserPreferences(
            user_id="test_user",
            notification_settings=notif_settings,
            created_at="2026-01-20T08:00:00Z",
            updated_at="2026-01-20T08:00:00Z",
        )
        svc = MagicMock()
        svc.get_user_preferences.return_value = prefs
        svc.save_user_preferences.return_value = None
        mock_user_svc.return_value = svc

        resp = client.delete(
            "/api/v1/user/notification-settings/resorts/big-white",
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert "removed" in resp.json()["message"].lower()


# ===========================================================================
# infer_resort_region helper
# ===========================================================================


class TestInferResortRegion:
    """Tests for the infer_resort_region helper function."""

    def test_canada_west(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="CA", lon=-120.0)
        assert infer_resort_region(resort) == "na_west"

    def test_canada_rockies(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="CA", lon=-110.0)
        assert infer_resort_region(resort) == "na_rockies"

    def test_us_east(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="US", lon=-80.0)
        assert infer_resort_region(resort) == "na_east"

    def test_france_alps(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="FR", lon=6.8)
        assert infer_resort_region(resort) == "alps"

    def test_japan(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="JP", lon=140.0)
        assert infer_resort_region(resort) == "japan"

    def test_new_zealand_oceania(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="NZ", lon=168.0)
        assert infer_resort_region(resort) == "oceania"

    def test_chile_south_america(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="CL", lon=-70.0)
        assert infer_resort_region(resort) == "south_america"

    def test_sweden_scandinavia(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="SE", lon=13.0)
        assert infer_resort_region(resort) == "scandinavia"

    def test_unknown_country_defaults_to_alps(self):
        from handlers.api_handler import infer_resort_region

        resort = _make_resort(country="XX", lon=0.0)
        assert infer_resort_region(resort) == "alps"

    def test_na_no_elevation_points_defaults_to_rockies(self):
        from handlers.api_handler import infer_resort_region

        resort = Resort(
            resort_id="test",
            name="Test",
            country="CA",
            region="BC",
            elevation_points=[],
            timezone="America/Vancouver",
        )
        assert infer_resort_region(resort) == "na_rockies"


# ===========================================================================
# _has_valid_coordinates helper
# ===========================================================================


class TestHasValidCoordinates:
    """Tests for the _has_valid_coordinates helper."""

    def test_valid_coordinates(self):
        from handlers.api_handler import _has_valid_coordinates

        resort = _make_resort(lat=49.0, lon=-120.0)
        assert _has_valid_coordinates(resort) is True

    def test_zero_coordinates(self):
        from handlers.api_handler import _has_valid_coordinates

        resort = Resort(
            resort_id="test",
            name="Test",
            country="CA",
            region="BC",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.BASE,
                    elevation_meters=1500,
                    elevation_feet=4921,
                    latitude=0.0,
                    longitude=0.0,
                )
            ],
            timezone="America/Vancouver",
        )
        assert _has_valid_coordinates(resort) is False

    def test_no_elevation_points(self):
        from handlers.api_handler import _has_valid_coordinates

        resort = Resort(
            resort_id="test",
            name="Test",
            country="CA",
            region="BC",
            elevation_points=[],
            timezone="America/Vancouver",
        )
        assert _has_valid_coordinates(resort) is False


# ===========================================================================
# Error Handlers
# ===========================================================================


class TestErrorHandlers:
    """Test global error handlers."""

    def test_404_for_unknown_path(self, client):
        resp = client.get("/api/v1/nonexistent-endpoint")
        assert resp.status_code in (404, 405)

    def test_openapi_schema(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema
