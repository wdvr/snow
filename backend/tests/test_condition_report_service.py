"""Tests for ConditionReportService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from models.condition_report import (
    ConditionReport,
    ConditionReportRequest,
    ConditionType,
)
from services.condition_report_service import (
    MAX_REPORTS_PER_DAY,
    REPORT_TTL_DAYS,
    ConditionReportService,
)


class TestConditionReportService:
    """Test cases for ConditionReportService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {}
        table.get_item.return_value = {"Item": None}
        table.query.return_value = {"Items": []}
        table.delete_item.return_value = {}
        return table

    @pytest.fixture
    def service(self, mock_table):
        """Create a ConditionReportService with mocked table."""
        return ConditionReportService(table=mock_table)

    @pytest.fixture
    def sample_request(self):
        """Create a sample condition report request."""
        return ConditionReportRequest(
            condition_type=ConditionType.POWDER,
            score=8,
            comment="Fresh powder everywhere!",
            elevation_level="top",
        )

    @pytest.fixture
    def sample_report_item(self):
        """Create a sample DynamoDB item for a condition report."""
        return {
            "resort_id": "big-white",
            "report_id": "01HXYZ123456789ABCDEFGHIJ",
            "user_id": "user_123",
            "condition_type": "powder",
            "score": Decimal("8"),
            "comment": "Fresh powder everywhere!",
            "elevation_level": "top",
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": Decimal(
                str(int((datetime.now(UTC) + timedelta(days=365)).timestamp()))
            ),
        }

    # -----------------------------------------------------------------------
    # submit_report
    # -----------------------------------------------------------------------

    def test_submit_report_success(self, service, mock_table, sample_request):
        """Test successful report submission."""
        # Not rate limited
        mock_table.query.return_value = {"Items": []}

        report = service.submit_report("big-white", "user_123", sample_request)

        assert report.resort_id == "big-white"
        assert report.user_id == "user_123"
        assert report.condition_type == ConditionType.POWDER
        assert report.score == 8
        assert report.comment == "Fresh powder everywhere!"
        assert report.elevation_level == "top"
        assert report.report_id  # ULID should be generated
        assert report.created_at  # Should be set
        assert report.expires_at > 0  # Should be set to future timestamp
        mock_table.put_item.assert_called_once()

    def test_submit_report_minimal(self, service, mock_table):
        """Test submitting a report with only required fields."""
        mock_table.query.return_value = {"Items": []}

        request = ConditionReportRequest(
            condition_type=ConditionType.ICE,
            score=3,
        )
        report = service.submit_report("whistler", "user_456", request)

        assert report.resort_id == "whistler"
        assert report.condition_type == ConditionType.ICE
        assert report.score == 3
        assert report.comment is None
        assert report.elevation_level is None

    def test_submit_report_expires_at_set_correctly(
        self, service, mock_table, sample_request
    ):
        """Test that expires_at is set to approximately 1 year from now."""
        mock_table.query.return_value = {"Items": []}

        report = service.submit_report("big-white", "user_123", sample_request)

        expected_expiry = datetime.now(UTC) + timedelta(days=REPORT_TTL_DAYS)
        # Allow 10 seconds tolerance
        assert abs(report.expires_at - int(expected_expiry.timestamp())) < 10

    def test_submit_report_rate_limited(self, service, mock_table, sample_request):
        """Test that rate limiting works when limit is exceeded."""
        # Return enough items to exceed the rate limit
        mock_table.query.return_value = {
            "Items": [{"report_id": f"report_{i}"} for i in range(MAX_REPORTS_PER_DAY)]
        }

        with pytest.raises(ValueError, match="Rate limit exceeded"):
            service.submit_report("big-white", "user_123", sample_request)

        # Should NOT have called put_item
        mock_table.put_item.assert_not_called()

    def test_submit_report_just_under_rate_limit(
        self, service, mock_table, sample_request
    ):
        """Test submitting when at one below the rate limit."""
        # First call is rate limit check, second is the actual query
        mock_table.query.side_effect = [
            {
                "Items": [
                    {"report_id": f"report_{i}"} for i in range(MAX_REPORTS_PER_DAY - 1)
                ]
            },
        ]

        report = service.submit_report("big-white", "user_123", sample_request)
        assert report is not None
        mock_table.put_item.assert_called_once()

    def test_submit_report_ulid_is_unique(self, service, mock_table, sample_request):
        """Test that each report gets a unique ULID."""
        mock_table.query.return_value = {"Items": []}

        report1 = service.submit_report("big-white", "user_123", sample_request)
        report2 = service.submit_report("big-white", "user_123", sample_request)

        assert report1.report_id != report2.report_id

    def test_submit_report_db_error(self, service, mock_table, sample_request):
        """Test handling of DynamoDB errors during submission."""
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
            "PutItem",
        )

        with pytest.raises(Exception, match="Failed to submit condition report"):
            service.submit_report("big-white", "user_123", sample_request)

    # -----------------------------------------------------------------------
    # get_reports_for_resort
    # -----------------------------------------------------------------------

    def test_get_reports_for_resort_empty(self, service, mock_table):
        """Test getting reports when none exist."""
        mock_table.query.return_value = {"Items": []}

        reports = service.get_reports_for_resort("big-white")
        assert reports == []

    def test_get_reports_for_resort_success(
        self, service, mock_table, sample_report_item
    ):
        """Test getting reports for a resort."""
        mock_table.query.return_value = {"Items": [sample_report_item]}

        reports = service.get_reports_for_resort("big-white")

        assert len(reports) == 1
        assert reports[0].resort_id == "big-white"
        assert reports[0].condition_type == ConditionType.POWDER
        assert reports[0].score == 8

    def test_get_reports_for_resort_with_limit(self, service, mock_table):
        """Test that limit is passed to DynamoDB query."""
        mock_table.query.return_value = {"Items": []}

        service.get_reports_for_resort("big-white", limit=5)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 5

    def test_get_reports_for_resort_sorted_descending(self, service, mock_table):
        """Test that reports are queried in descending order (most recent first)."""
        mock_table.query.return_value = {"Items": []}

        service.get_reports_for_resort("big-white")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_get_reports_for_resort_db_error(self, service, mock_table):
        """Test handling of DynamoDB errors."""
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
            "Query",
        )

        with pytest.raises(Exception, match="Failed to get reports"):
            service.get_reports_for_resort("big-white")

    # -----------------------------------------------------------------------
    # get_reports_by_user
    # -----------------------------------------------------------------------

    def test_get_reports_by_user_empty(self, service, mock_table):
        """Test getting reports when user has none."""
        mock_table.query.return_value = {"Items": []}

        reports = service.get_reports_by_user("user_123")
        assert reports == []

    def test_get_reports_by_user_success(self, service, mock_table, sample_report_item):
        """Test getting reports by user."""
        mock_table.query.return_value = {"Items": [sample_report_item]}

        reports = service.get_reports_by_user("user_123")

        assert len(reports) == 1
        assert reports[0].user_id == "user_123"

    def test_get_reports_by_user_uses_gsi(self, service, mock_table):
        """Test that user query uses the GSI."""
        mock_table.query.return_value = {"Items": []}

        service.get_reports_by_user("user_123")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "UserIdIndex"

    def test_get_reports_by_user_with_limit(self, service, mock_table):
        """Test that limit is passed to the query."""
        mock_table.query.return_value = {"Items": []}

        service.get_reports_by_user("user_123", limit=10)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 10

    # -----------------------------------------------------------------------
    # delete_report
    # -----------------------------------------------------------------------

    def test_delete_report_success(self, service, mock_table):
        """Test successful report deletion."""
        result = service.delete_report("big-white", "report_123", "user_123")
        assert result is True
        mock_table.delete_item.assert_called_once()

    def test_delete_report_verifies_ownership(self, service, mock_table):
        """Test that delete checks user ownership."""
        service.delete_report("big-white", "report_123", "user_123")

        call_kwargs = mock_table.delete_item.call_args[1]
        assert "user_id = :uid" in call_kwargs["ConditionExpression"]
        assert call_kwargs["ExpressionAttributeValues"][":uid"] == "user_123"

    def test_delete_report_not_found(self, service, mock_table):
        """Test deleting a non-existent report."""
        mock_table.delete_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Condition not met",
                }
            },
            "DeleteItem",
        )

        result = service.delete_report("big-white", "report_123", "user_123")
        assert result is False

    def test_delete_report_wrong_user(self, service, mock_table):
        """Test that deleting someone else's report fails."""
        mock_table.delete_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Condition not met",
                }
            },
            "DeleteItem",
        )

        result = service.delete_report("big-white", "report_123", "wrong_user")
        assert result is False

    def test_delete_report_db_error(self, service, mock_table):
        """Test handling of unexpected DynamoDB errors during deletion."""
        mock_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
            "DeleteItem",
        )

        with pytest.raises(Exception, match="Failed to delete condition report"):
            service.delete_report("big-white", "report_123", "user_123")

    # -----------------------------------------------------------------------
    # get_report_summary
    # -----------------------------------------------------------------------

    def test_get_report_summary_no_reports(self, service, mock_table):
        """Test summary when no reports exist."""
        mock_table.query.return_value = {"Items": []}

        summary = service.get_report_summary("big-white")

        assert summary["average_score"] is None
        assert summary["most_common_type"] is None
        assert summary["report_count"] == 0
        assert summary["last_7_days"] is True

    def test_get_report_summary_with_reports(self, service, mock_table):
        """Test summary calculation with multiple reports."""
        now = datetime.now(UTC)
        items = [
            {
                "resort_id": "big-white",
                "report_id": f"report_{i}",
                "user_id": f"user_{i}",
                "condition_type": "powder",
                "score": Decimal("8"),
                "comment": None,
                "elevation_level": "top",
                "created_at": now.isoformat(),
                "expires_at": Decimal("9999999999"),
            }
            for i in range(3)
        ] + [
            {
                "resort_id": "big-white",
                "report_id": "report_extra",
                "user_id": "user_extra",
                "condition_type": "packed_powder",
                "score": Decimal("6"),
                "comment": None,
                "elevation_level": "mid",
                "created_at": now.isoformat(),
                "expires_at": Decimal("9999999999"),
            }
        ]
        mock_table.query.return_value = {"Items": items}

        summary = service.get_report_summary("big-white")

        assert summary["report_count"] == 4
        assert summary["average_score"] == 7.5  # (8+8+8+6)/4
        assert summary["most_common_type"] == "powder"  # 3 vs 1
        assert summary["last_7_days"] is True

    def test_get_report_summary_excludes_old_reports(self, service, mock_table):
        """Test that summary excludes reports older than 7 days."""
        now = datetime.now(UTC)
        old_date = (now - timedelta(days=10)).isoformat()
        recent_date = now.isoformat()

        items = [
            {
                "resort_id": "big-white",
                "report_id": "old_report",
                "user_id": "user_1",
                "condition_type": "ice",
                "score": Decimal("2"),
                "comment": None,
                "elevation_level": None,
                "created_at": old_date,
                "expires_at": Decimal("9999999999"),
            },
            {
                "resort_id": "big-white",
                "report_id": "recent_report",
                "user_id": "user_2",
                "condition_type": "powder",
                "score": Decimal("9"),
                "comment": None,
                "elevation_level": "top",
                "created_at": recent_date,
                "expires_at": Decimal("9999999999"),
            },
        ]
        mock_table.query.return_value = {"Items": items}

        summary = service.get_report_summary("big-white")

        assert summary["report_count"] == 1
        assert summary["average_score"] == 9.0
        assert summary["most_common_type"] == "powder"

    def test_get_report_summary_single_type(self, service, mock_table):
        """Test summary when all reports have the same type."""
        now = datetime.now(UTC)
        items = [
            {
                "resort_id": "big-white",
                "report_id": f"report_{i}",
                "user_id": f"user_{i}",
                "condition_type": "spring",
                "score": Decimal(str(5 + i)),
                "comment": None,
                "elevation_level": None,
                "created_at": now.isoformat(),
                "expires_at": Decimal("9999999999"),
            }
            for i in range(3)
        ]
        mock_table.query.return_value = {"Items": items}

        summary = service.get_report_summary("big-white")

        assert summary["most_common_type"] == "spring"
        assert summary["report_count"] == 3
        assert summary["average_score"] == 6.0  # (5+6+7)/3

    def test_get_report_summary_uses_limit(self, service, mock_table):
        """Verify summary query uses Limit to prevent unbounded reads."""
        mock_table.query.return_value = {"Items": []}

        service.get_report_summary("big-white")

        call_kwargs = mock_table.query.call_args[1]
        assert "Limit" in call_kwargs
        assert call_kwargs["Limit"] == 100

    def test_get_report_summary_empty_condition_types(self, service, mock_table):
        """Summary handles reports with empty/missing condition_type gracefully."""
        now = datetime.now(UTC)
        items = [
            {
                "resort_id": "big-white",
                "report_id": "report_1",
                "user_id": "user_1",
                "condition_type": "",
                "score": Decimal("5"),
                "comment": None,
                "elevation_level": None,
                "created_at": now.isoformat(),
                "expires_at": Decimal("9999999999"),
            }
        ]
        mock_table.query.return_value = {"Items": items}

        summary = service.get_report_summary("big-white")

        assert summary["report_count"] == 1
        assert summary["average_score"] == 5.0
        # Empty string is still a valid type count entry
        assert summary["most_common_type"] == ""

    # -----------------------------------------------------------------------
    # _is_rate_limited
    # -----------------------------------------------------------------------

    def test_rate_limit_not_exceeded(self, service, mock_table):
        """Test that rate limit check passes when under limit."""
        mock_table.query.return_value = {"Items": [{"report_id": "r1"}]}

        assert service._is_rate_limited("big-white", "user_123") is False

    def test_rate_limit_exceeded(self, service, mock_table):
        """Test that rate limit check fails when at limit."""
        mock_table.query.return_value = {
            "Items": [{"report_id": f"r{i}"} for i in range(MAX_REPORTS_PER_DAY)]
        }

        assert service._is_rate_limited("big-white", "user_123") is True

    def test_rate_limit_fails_open_on_error(self, service, mock_table):
        """Test that rate limit check allows on error (fail open)."""
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
            "Query",
        )

        # Should allow the request when check fails
        assert service._is_rate_limited("big-white", "user_123") is False


class TestConditionReportModel:
    """Test cases for condition report Pydantic models."""

    def test_condition_report_request_valid(self):
        """Test creating a valid request."""
        request = ConditionReportRequest(
            condition_type=ConditionType.POWDER,
            score=8,
            comment="Great snow!",
            elevation_level="top",
        )
        assert request.condition_type == ConditionType.POWDER
        assert request.score == 8

    def test_condition_report_request_minimal(self):
        """Test creating a request with only required fields."""
        request = ConditionReportRequest(
            condition_type=ConditionType.ICE,
            score=2,
        )
        assert request.comment is None
        assert request.elevation_level is None

    def test_condition_report_request_score_too_low(self):
        """Test that score below 1 is rejected."""
        with pytest.raises(ValidationError):
            ConditionReportRequest(
                condition_type=ConditionType.POWDER,
                score=0,
            )

    def test_condition_report_request_score_too_high(self):
        """Test that score above 10 is rejected."""
        with pytest.raises(ValidationError):
            ConditionReportRequest(
                condition_type=ConditionType.POWDER,
                score=11,
            )

    def test_condition_report_request_invalid_elevation(self):
        """Test that invalid elevation level is rejected."""
        with pytest.raises(ValidationError):
            ConditionReportRequest(
                condition_type=ConditionType.POWDER,
                score=8,
                elevation_level="summit",  # Not base/mid/top
            )

    def test_condition_report_request_comment_too_long(self):
        """Test that comment exceeding 500 chars is rejected."""
        with pytest.raises(ValidationError):
            ConditionReportRequest(
                condition_type=ConditionType.POWDER,
                score=8,
                comment="x" * 501,
            )

    def test_condition_type_enum_values(self):
        """Test all condition type enum values."""
        expected = {
            "powder",
            "packed_powder",
            "soft",
            "ice",
            "crud",
            "spring",
            "hardpack",
            "windblown",
        }
        actual = {ct.value for ct in ConditionType}
        assert actual == expected

    def test_condition_report_all_elevation_levels(self):
        """Test all valid elevation levels."""
        for level in ["base", "mid", "top"]:
            request = ConditionReportRequest(
                condition_type=ConditionType.POWDER,
                score=7,
                elevation_level=level,
            )
            assert request.elevation_level == level
