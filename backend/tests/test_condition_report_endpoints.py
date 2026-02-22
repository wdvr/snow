"""Tests for condition report API endpoints.

Tests the FastAPI endpoints by mocking the service layer.
Follows the same patterns as test_api_handler.py.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from models.condition_report import (
    ConditionReport,
    ConditionReportRequest,
    ConditionType,
)
from models.resort import ElevationLevel, ElevationPoint, Resort
from utils.cache import clear_all_caches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _make_resort(resort_id="test-resort") -> Resort:
    """Helper to build a Resort with sensible defaults."""
    return Resort(
        resort_id=resort_id,
        name="Test Resort",
        country="CA",
        region="BC",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=1500,
                elevation_feet=4921,
                latitude=49.0,
                longitude=-120.0,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1800,
                elevation_feet=5906,
                latitude=49.01,
                longitude=-119.99,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=2200,
                elevation_feet=7218,
                latitude=49.02,
                longitude=-119.98,
            ),
        ],
        timezone="America/Vancouver",
        official_website="https://test-resort.com",
        weather_sources=["weatherapi"],
        created_at="2026-01-20T08:00:00Z",
        updated_at="2026-01-20T08:00:00Z",
    )


def _make_condition_report(
    resort_id="test-resort",
    report_id="01HXYZ123456789ABCDEFGHIJ",
    user_id="test_user",
    condition_type=ConditionType.POWDER,
    score=8,
    comment="Great snow!",
    elevation_level="top",
) -> ConditionReport:
    """Helper to build a ConditionReport."""
    return ConditionReport(
        resort_id=resort_id,
        report_id=report_id,
        user_id=user_id,
        condition_type=condition_type,
        score=score,
        comment=comment,
        elevation_level=elevation_level,
        created_at=datetime.now(UTC).isoformat(),
        expires_at=int((datetime.now(UTC) + timedelta(days=365)).timestamp()),
    )


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


# ===========================================================================
# POST /api/v1/resorts/{resort_id}/condition-reports
# ===========================================================================


class TestSubmitConditionReport:
    """Tests for the submit condition report endpoint."""

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler._get_resort_cached")
    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_success(self, mock_auth, mock_resort, mock_svc_fn, client):
        """Test successful report submission."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        mock_resort.return_value = _make_resort()

        report = _make_condition_report()
        svc = MagicMock()
        svc.submit_report.return_value = report
        mock_svc_fn.return_value = svc

        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "powder",
                "score": 8,
                "comment": "Great snow!",
                "elevation_level": "top",
            },
            headers=_auth_header(),
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["report_id"] == report.report_id
        assert data["resort_id"] == "test-resort"
        assert data["condition_type"] == "powder"
        assert data["score"] == 8
        assert data["comment"] == "Great snow!"
        assert data["elevation_level"] == "top"

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler._get_resort_cached")
    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_minimal(self, mock_auth, mock_resort, mock_svc_fn, client):
        """Test submitting a report with only required fields."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        mock_resort.return_value = _make_resort()

        report = _make_condition_report(comment=None, elevation_level=None)
        svc = MagicMock()
        svc.submit_report.return_value = report
        mock_svc_fn.return_value = svc

        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "ice",
                "score": 3,
            },
            headers=_auth_header(),
        )

        assert resp.status_code == 201

    def test_submit_report_no_auth(self, client):
        """Test that submitting without auth returns 401."""
        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "powder",
                "score": 8,
            },
        )
        assert resp.status_code == 401

    @patch("handlers.api_handler._get_resort_cached")
    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_resort_not_found(self, mock_auth, mock_resort, client):
        """Test submitting to a non-existent resort returns 404."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        mock_resort.return_value = None

        resp = client.post(
            "/api/v1/resorts/nonexistent/condition-reports",
            json={
                "condition_type": "powder",
                "score": 8,
            },
            headers=_auth_header(),
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler._get_resort_cached")
    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_rate_limited(
        self, mock_auth, mock_resort, mock_svc_fn, client
    ):
        """Test that rate limiting returns 429."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        mock_resort.return_value = _make_resort()

        svc = MagicMock()
        svc.submit_report.side_effect = ValueError("Rate limit exceeded")
        mock_svc_fn.return_value = svc

        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "powder",
                "score": 8,
            },
            headers=_auth_header(),
        )

        assert resp.status_code == 429
        assert "rate limit" in resp.json()["detail"].lower()

    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_invalid_score(self, mock_auth, client):
        """Test that invalid score is rejected (422)."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "powder",
                "score": 0,
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 422

    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_invalid_condition_type(self, mock_auth, client):
        """Test that invalid condition type is rejected (422)."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "banana",
                "score": 5,
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 422

    @patch("handlers.api_handler.get_auth_service")
    def test_submit_report_invalid_elevation(self, mock_auth, client):
        """Test that invalid elevation level is rejected (422)."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )
        resp = client.post(
            "/api/v1/resorts/test-resort/condition-reports",
            json={
                "condition_type": "powder",
                "score": 8,
                "elevation_level": "summit",
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 422


# ===========================================================================
# GET /api/v1/resorts/{resort_id}/condition-reports
# ===========================================================================


class TestGetResortConditionReports:
    """Tests for the get resort condition reports endpoint."""

    @patch("handlers.api_handler.get_condition_report_service")
    def test_get_reports_empty(self, mock_svc_fn, client):
        """Test getting reports when none exist."""
        svc = MagicMock()
        svc.get_reports_for_resort.return_value = []
        svc.get_report_summary.return_value = {
            "average_score": None,
            "most_common_type": None,
            "report_count": 0,
            "last_7_days": True,
        }
        mock_svc_fn.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/condition-reports")

        assert resp.status_code == 200
        data = resp.json()
        assert data["reports"] == []
        assert data["summary"]["report_count"] == 0

    @patch("handlers.api_handler.get_condition_report_service")
    def test_get_reports_with_data(self, mock_svc_fn, client):
        """Test getting reports with results."""
        report = _make_condition_report()
        svc = MagicMock()
        svc.get_reports_for_resort.return_value = [report]
        svc.get_report_summary.return_value = {
            "average_score": 8.0,
            "most_common_type": "powder",
            "report_count": 1,
            "last_7_days": True,
        }
        mock_svc_fn.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/condition-reports")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["condition_type"] == "powder"
        assert data["summary"]["average_score"] == 8.0

    @patch("handlers.api_handler.get_condition_report_service")
    def test_get_reports_with_limit(self, mock_svc_fn, client):
        """Test getting reports with custom limit."""
        svc = MagicMock()
        svc.get_reports_for_resort.return_value = []
        svc.get_report_summary.return_value = {
            "average_score": None,
            "most_common_type": None,
            "report_count": 0,
            "last_7_days": True,
        }
        mock_svc_fn.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/condition-reports?limit=5")

        assert resp.status_code == 200
        svc.get_reports_for_resort.assert_called_once_with("test-resort", limit=5)

    def test_get_reports_no_auth_required(self, client):
        """Test that getting reports does not require auth."""
        # This should return 200 even without auth (public endpoint)
        # It may return 500 if service isn't mocked, but NOT 401
        with patch("handlers.api_handler.get_condition_report_service") as mock_svc_fn:
            svc = MagicMock()
            svc.get_reports_for_resort.return_value = []
            svc.get_report_summary.return_value = {
                "average_score": None,
                "most_common_type": None,
                "report_count": 0,
                "last_7_days": True,
            }
            mock_svc_fn.return_value = svc

            resp = client.get("/api/v1/resorts/test-resort/condition-reports")
            assert resp.status_code == 200

    @patch("handlers.api_handler.get_condition_report_service")
    def test_get_reports_service_error(self, mock_svc_fn, client):
        """Test that service errors return 500."""
        svc = MagicMock()
        svc.get_reports_for_resort.side_effect = RuntimeError("DB down")
        mock_svc_fn.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/condition-reports")
        assert resp.status_code == 500

    @patch("handlers.api_handler.get_condition_report_service")
    def test_get_reports_response_structure(self, mock_svc_fn, client):
        """Test the response has the correct structure."""
        report = _make_condition_report()
        svc = MagicMock()
        svc.get_reports_for_resort.return_value = [report]
        svc.get_report_summary.return_value = {
            "average_score": 8.0,
            "most_common_type": "powder",
            "report_count": 1,
            "last_7_days": True,
        }
        mock_svc_fn.return_value = svc

        resp = client.get("/api/v1/resorts/test-resort/condition-reports")
        data = resp.json()

        # Verify report fields
        r = data["reports"][0]
        assert "report_id" in r
        assert "resort_id" in r
        assert "condition_type" in r
        assert "score" in r
        assert "comment" in r
        assert "elevation_level" in r
        assert "created_at" in r

        # Verify summary fields
        s = data["summary"]
        assert "average_score" in s
        assert "most_common_type" in s
        assert "report_count" in s


# ===========================================================================
# GET /api/v1/user/condition-reports
# ===========================================================================


class TestGetUserConditionReports:
    """Tests for the get user's own condition reports endpoint."""

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_get_user_reports_success(self, mock_auth, mock_svc_fn, client):
        """Test getting the user's own reports."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        report = _make_condition_report()
        svc = MagicMock()
        svc.get_reports_by_user.return_value = [report]
        mock_svc_fn.return_value = svc

        resp = client.get(
            "/api/v1/user/condition-reports",
            headers=_auth_header(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reports"]) == 1
        assert data["count"] == 1

    def test_get_user_reports_no_auth(self, client):
        """Test that getting user reports requires auth."""
        resp = client.get("/api/v1/user/condition-reports")
        assert resp.status_code == 401

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_get_user_reports_empty(self, mock_auth, mock_svc_fn, client):
        """Test getting user reports when none exist."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        svc = MagicMock()
        svc.get_reports_by_user.return_value = []
        mock_svc_fn.return_value = svc

        resp = client.get(
            "/api/v1/user/condition-reports",
            headers=_auth_header(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["reports"] == []
        assert data["count"] == 0

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_get_user_reports_with_limit(self, mock_auth, mock_svc_fn, client):
        """Test getting user reports with custom limit."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        svc = MagicMock()
        svc.get_reports_by_user.return_value = []
        mock_svc_fn.return_value = svc

        resp = client.get(
            "/api/v1/user/condition-reports?limit=10",
            headers=_auth_header(),
        )

        assert resp.status_code == 200
        svc.get_reports_by_user.assert_called_once_with("test_user", limit=10)


# ===========================================================================
# DELETE /api/v1/resorts/{resort_id}/condition-reports/{report_id}
# ===========================================================================


class TestDeleteConditionReport:
    """Tests for the delete condition report endpoint."""

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_delete_report_success(self, mock_auth, mock_svc_fn, client):
        """Test successful report deletion."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        svc = MagicMock()
        svc.delete_report.return_value = True
        mock_svc_fn.return_value = svc

        resp = client.delete(
            "/api/v1/resorts/test-resort/condition-reports/report_123",
            headers=_auth_header(),
        )

        assert resp.status_code == 204
        svc.delete_report.assert_called_once_with(
            resort_id="test-resort",
            report_id="report_123",
            user_id="test_user",
        )

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_delete_report_not_found(self, mock_auth, mock_svc_fn, client):
        """Test deleting a non-existent report."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        svc = MagicMock()
        svc.delete_report.return_value = False
        mock_svc_fn.return_value = svc

        resp = client.delete(
            "/api/v1/resorts/test-resort/condition-reports/nonexistent",
            headers=_auth_header(),
        )

        assert resp.status_code == 404

    def test_delete_report_no_auth(self, client):
        """Test that deleting requires auth."""
        resp = client.delete("/api/v1/resorts/test-resort/condition-reports/report_123")
        assert resp.status_code == 401

    @patch("handlers.api_handler.get_condition_report_service")
    @patch("handlers.api_handler.get_auth_service")
    def test_delete_report_service_error(self, mock_auth, mock_svc_fn, client):
        """Test that service errors return 500."""
        mock_auth.return_value = Mock(
            verify_access_token=Mock(return_value="test_user")
        )

        svc = MagicMock()
        svc.delete_report.side_effect = RuntimeError("DB error")
        mock_svc_fn.return_value = svc

        resp = client.delete(
            "/api/v1/resorts/test-resort/condition-reports/report_123",
            headers=_auth_header(),
        )

        assert resp.status_code == 500
