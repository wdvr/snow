"""Tests for DailyHistoryService."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from services.daily_history_service import DailyHistoryService


class TestDailyHistoryService:
    """Test cases for DailyHistoryService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {}
        table.query.return_value = {"Items": []}
        return table

    @pytest.fixture
    def service(self, mock_table):
        """Create a DailyHistoryService instance with mocked table."""
        return DailyHistoryService(mock_table)

    @pytest.fixture
    def sample_dynamo_items(self):
        """Create sample DynamoDB items with Decimal values."""
        return [
            {
                "resort_id": "whistler-blackcomb",
                "date": "2026-02-18",
                "snowfall_24h_cm": Decimal("12.5"),
                "snow_depth_cm": Decimal("245.0"),
                "temp_min_c": Decimal("-8.2"),
                "temp_max_c": Decimal("-2.1"),
                "quality_score": Decimal("4.80"),
                "snow_quality": "excellent",
                "updated_at": "2026-02-18T12:00:00+00:00",
            },
            {
                "resort_id": "whistler-blackcomb",
                "date": "2026-02-19",
                "snowfall_24h_cm": Decimal("0.0"),
                "temp_min_c": Decimal("-5.1"),
                "temp_max_c": Decimal("1.0"),
                "quality_score": Decimal("3.20"),
                "snow_quality": "good",
                "updated_at": "2026-02-19T12:00:00+00:00",
            },
            {
                "resort_id": "whistler-blackcomb",
                "date": "2026-02-20",
                "snowfall_24h_cm": Decimal("5.3"),
                "snow_depth_cm": Decimal("248.0"),
                "temp_min_c": Decimal("-6.0"),
                "temp_max_c": Decimal("-1.5"),
                "quality_score": Decimal("4.10"),
                "snow_quality": "good",
                "wind_speed_kmh": Decimal("15.0"),
                "updated_at": "2026-02-20T12:00:00+00:00",
            },
        ]

    # ---------------------------------------------------------------
    # record_daily_snapshot tests
    # ---------------------------------------------------------------

    def test_record_daily_snapshot_success(self, service, mock_table):
        """Test successful recording of a daily snapshot."""
        result = service.record_daily_snapshot(
            resort_id="whistler-blackcomb",
            date="2026-02-20",
            snowfall_24h_cm=12.5,
            snow_depth_cm=245.0,
            temp_min_c=-8.2,
            temp_max_c=-2.1,
            quality_score=4.8,
            snow_quality="excellent",
            wind_speed_kmh=10.5,
        )

        assert result is True
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["resort_id"] == "whistler-blackcomb"
        assert item["date"] == "2026-02-20"
        assert item["snowfall_24h_cm"] == Decimal("12.5")
        assert item["snow_depth_cm"] == Decimal("245.0")
        assert item["temp_min_c"] == Decimal("-8.2")
        assert item["temp_max_c"] == Decimal("-2.1")
        assert item["quality_score"] == Decimal("4.80")
        assert item["snow_quality"] == "excellent"
        assert item["wind_speed_kmh"] == Decimal("10.5")
        assert "updated_at" in item

    def test_record_daily_snapshot_minimal(self, service, mock_table):
        """Test recording with minimal fields (no optional fields)."""
        result = service.record_daily_snapshot(
            resort_id="vail",
            date="2026-02-20",
            snowfall_24h_cm=0.0,
            snow_depth_cm=None,
            temp_min_c=-3.0,
            temp_max_c=2.0,
            quality_score=None,
            snow_quality="fair",
        )

        assert result is True
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["resort_id"] == "vail"
        assert "snow_depth_cm" not in item
        assert "quality_score" not in item
        assert "wind_speed_kmh" not in item

    def test_record_daily_snapshot_client_error(self, service, mock_table):
        """Test handling of DynamoDB client error."""
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "PutItem",
        )

        result = service.record_daily_snapshot(
            resort_id="vail",
            date="2026-02-20",
            snowfall_24h_cm=0.0,
            snow_depth_cm=None,
            temp_min_c=-3.0,
            temp_max_c=2.0,
            quality_score=None,
            snow_quality="fair",
        )

        assert result is False

    # ---------------------------------------------------------------
    # get_history tests
    # ---------------------------------------------------------------

    def test_get_history_with_date_range(
        self, service, mock_table, sample_dynamo_items
    ):
        """Test getting history with explicit date range."""
        mock_table.query.return_value = {"Items": sample_dynamo_items}

        history = service.get_history(
            resort_id="whistler-blackcomb",
            start_date="2026-02-18",
            end_date="2026-02-20",
        )

        assert len(history) == 3
        assert history[0]["date"] == "2026-02-18"
        assert history[0]["snowfall_24h_cm"] == 12.5
        assert history[0]["snow_depth_cm"] == 245.0
        assert isinstance(history[0]["snowfall_24h_cm"], float)
        assert isinstance(history[0]["temp_min_c"], float)

        # Verify query was called with between condition
        mock_table.query.assert_called_once()

    def test_get_history_without_end_date(
        self, service, mock_table, sample_dynamo_items
    ):
        """Test getting history with only start_date (no end_date)."""
        mock_table.query.return_value = {"Items": sample_dynamo_items}

        history = service.get_history(
            resort_id="whistler-blackcomb",
            start_date="2026-02-18",
        )

        assert len(history) == 3
        mock_table.query.assert_called_once()

    def test_get_history_default_dates(self, service, mock_table):
        """Test getting history with default date range (90 days)."""
        mock_table.query.return_value = {"Items": []}

        history = service.get_history(resort_id="whistler-blackcomb")

        assert history == []
        mock_table.query.assert_called_once()
        # Verify ScanIndexForward=True (ascending)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is True
        assert call_kwargs["Limit"] == 90

    def test_get_history_empty_result(self, service, mock_table):
        """Test getting history when no data exists."""
        mock_table.query.return_value = {"Items": []}

        history = service.get_history(
            resort_id="nonexistent-resort",
            start_date="2026-02-01",
        )

        assert history == []

    def test_get_history_client_error(self, service, mock_table):
        """Test handling of DynamoDB client error during query."""
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "Query",
        )

        history = service.get_history(
            resort_id="whistler-blackcomb",
            start_date="2026-02-01",
        )

        assert history == []

    # ---------------------------------------------------------------
    # get_season_summary tests
    # ---------------------------------------------------------------

    def test_get_season_summary(self, service, mock_table, sample_dynamo_items):
        """Test season summary calculation."""
        mock_table.query.return_value = {"Items": sample_dynamo_items}

        summary = service.get_season_summary(
            resort_id="whistler-blackcomb",
            season_start="2025-10-01",
        )

        assert summary["total_snowfall_cm"] == 17.8  # 12.5 + 0.0 + 5.3
        assert summary["snow_days"] == 2  # 12.5 and 5.3 are >= 1.0
        assert summary["avg_quality_score"] is not None
        assert summary["best_day"] is not None
        assert summary["best_day"]["date"] == "2026-02-18"  # 12.5 is highest
        assert summary["days_tracked"] == 3

    def test_get_season_summary_empty(self, service, mock_table):
        """Test season summary with no data."""
        mock_table.query.return_value = {"Items": []}

        summary = service.get_season_summary(
            resort_id="whistler-blackcomb",
            season_start="2025-10-01",
        )

        assert summary["total_snowfall_cm"] == 0
        assert summary["snow_days"] == 0
        assert summary["avg_quality_score"] is None
        assert summary["best_day"] is None
        assert summary["days_tracked"] == 0

    def test_get_season_summary_no_quality_scores(self, service, mock_table):
        """Test season summary when no quality scores are available."""
        items = [
            {
                "resort_id": "vail",
                "date": "2026-02-20",
                "snowfall_24h_cm": Decimal("3.0"),
                "temp_min_c": Decimal("-5.0"),
                "temp_max_c": Decimal("1.0"),
                "snow_quality": "fair",
                "updated_at": "2026-02-20T12:00:00+00:00",
            },
        ]
        mock_table.query.return_value = {"Items": items}

        summary = service.get_season_summary(
            resort_id="vail",
            season_start="2025-10-01",
        )

        assert summary["avg_quality_score"] is None
        assert summary["snow_days"] == 1
        assert summary["total_snowfall_cm"] == 3.0

    # ---------------------------------------------------------------
    # _convert_decimals tests
    # ---------------------------------------------------------------

    def test_convert_decimals(self, service):
        """Test Decimal to float conversion."""
        item = {
            "resort_id": "vail",
            "snowfall_24h_cm": Decimal("12.5"),
            "temp_min_c": Decimal("-8.2"),
            "nested": {
                "value": Decimal("3.14"),
            },
            "string_field": "hello",
            "int_field": 42,
        }

        result = service._convert_decimals(item)

        assert result["snowfall_24h_cm"] == 12.5
        assert isinstance(result["snowfall_24h_cm"], float)
        assert result["temp_min_c"] == -8.2
        assert isinstance(result["temp_min_c"], float)
        assert result["nested"]["value"] == 3.14
        assert isinstance(result["nested"]["value"], float)
        assert result["string_field"] == "hello"
        assert result["int_field"] == 42

    def test_convert_decimals_empty(self, service):
        """Test conversion of empty dict."""
        result = service._convert_decimals({})
        assert result == {}
