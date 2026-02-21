"""Tests for SnowSummaryService."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from services.snow_summary_service import SnowSummaryService


class TestSnowSummaryService:
    """Test cases for SnowSummaryService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {}
        table.get_item.return_value = {}
        table.update_item.return_value = {}
        return table

    @pytest.fixture
    def service(self, mock_table):
        """Create a SnowSummaryService instance with mocked table."""
        return SnowSummaryService(mock_table)

    @pytest.fixture
    def sample_dynamo_item(self):
        """Create a sample DynamoDB item with Decimal values."""
        return {
            "resort_id": "big-white",
            "elevation_level": "mid",
            "last_freeze_date": "2026-01-15T06:00:00+00:00",
            "snowfall_since_freeze_cm": Decimal("45.50"),
            "total_season_snowfall_cm": Decimal("120.75"),
            "season_start_date": "2025-11-01",
            "last_updated": "2026-02-01T12:00:00+00:00",
            "last_snowfall_24h_cm": Decimal("8.20"),
        }

    # ---------------------------------------------------------------
    # get_summary tests
    # ---------------------------------------------------------------

    def test_get_summary_returns_item(self, service, mock_table, sample_dynamo_item):
        """Test successful retrieval of an existing snow summary."""
        mock_table.get_item.return_value = {"Item": sample_dynamo_item}

        result = service.get_summary("big-white", "mid")

        assert result is not None
        assert result["resort_id"] == "big-white"
        assert result["elevation_level"] == "mid"
        assert result["snowfall_since_freeze_cm"] == 45.50
        assert result["total_season_snowfall_cm"] == 120.75
        assert result["last_snowfall_24h_cm"] == 8.20
        assert isinstance(result["snowfall_since_freeze_cm"], float)
        mock_table.get_item.assert_called_once_with(
            Key={"resort_id": "big-white", "elevation_level": "mid"}
        )

    def test_get_summary_not_found(self, service, mock_table):
        """Test get_summary returns None when no item exists."""
        mock_table.get_item.return_value = {}

        result = service.get_summary("non-existent", "base")

        assert result is None

    def test_get_summary_item_is_none(self, service, mock_table):
        """Test get_summary returns None when Item key is present but None."""
        mock_table.get_item.return_value = {"Item": None}

        result = service.get_summary("big-white", "base")

        assert result is None

    def test_get_summary_dynamo_error(self, service, mock_table):
        """Test get_summary returns None on DynamoDB ClientError."""
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "get_item",
        )

        result = service.get_summary("big-white", "mid")

        assert result is None

    # ---------------------------------------------------------------
    # update_summary tests
    # ---------------------------------------------------------------

    def test_update_summary_success_all_fields(self, service, mock_table):
        """Test successful update with all fields provided."""
        result = service.update_summary(
            resort_id="big-white",
            elevation_level="top",
            last_freeze_date="2026-01-20T08:00:00+00:00",
            snowfall_since_freeze_cm=30.5,
            total_season_snowfall_cm=150.0,
            last_updated="2026-02-01T10:00:00+00:00",
            season_start_date="2025-11-01",
            last_snowfall_24h_cm=12.3,
        )

        assert result is True
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["resort_id"] == "big-white"
        assert item["elevation_level"] == "top"
        assert item["last_freeze_date"] == "2026-01-20T08:00:00+00:00"
        assert item["snowfall_since_freeze_cm"] == Decimal("30.5")
        assert item["total_season_snowfall_cm"] == Decimal("150.0")
        assert item["last_updated"] == "2026-02-01T10:00:00+00:00"
        assert item["season_start_date"] == "2025-11-01"
        assert item["last_snowfall_24h_cm"] == Decimal("12.3")

    def test_update_summary_without_optional_fields(self, service, mock_table):
        """Test update with only required fields (no freeze date, no season start, no 24h snowfall)."""
        result = service.update_summary(
            resort_id="whistler",
            elevation_level="base",
            last_freeze_date=None,
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=50.0,
            last_updated="2026-02-01T10:00:00+00:00",
        )

        assert result is True
        item = mock_table.put_item.call_args[1]["Item"]
        assert "last_freeze_date" not in item
        assert "season_start_date" not in item
        assert "last_snowfall_24h_cm" not in item

    def test_update_summary_rounds_decimals(self, service, mock_table):
        """Test that float values are rounded to 2 decimal places."""
        service.update_summary(
            resort_id="big-white",
            elevation_level="mid",
            last_freeze_date=None,
            snowfall_since_freeze_cm=10.12345,
            total_season_snowfall_cm=99.99999,
            last_updated="2026-02-01T10:00:00+00:00",
            last_snowfall_24h_cm=3.456,
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["snowfall_since_freeze_cm"] == Decimal("10.12")
        assert item["total_season_snowfall_cm"] == Decimal("100.0")
        assert item["last_snowfall_24h_cm"] == Decimal("3.46")

    def test_update_summary_with_zero_24h_snowfall(self, service, mock_table):
        """Test that last_snowfall_24h_cm=0.0 is still written (not None)."""
        service.update_summary(
            resort_id="big-white",
            elevation_level="mid",
            last_freeze_date=None,
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=0.0,
            last_updated="2026-02-01T10:00:00+00:00",
            last_snowfall_24h_cm=0.0,
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "last_snowfall_24h_cm" in item
        assert item["last_snowfall_24h_cm"] == Decimal("0.0")

    def test_update_summary_dynamo_error(self, service, mock_table):
        """Test update_summary returns False on DynamoDB ClientError."""
        mock_table.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Throttled",
                }
            },
            "put_item",
        )

        result = service.update_summary(
            resort_id="big-white",
            elevation_level="mid",
            last_freeze_date=None,
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=0.0,
            last_updated="2026-02-01T10:00:00+00:00",
        )

        assert result is False

    # ---------------------------------------------------------------
    # record_freeze_event tests
    # ---------------------------------------------------------------

    def test_record_freeze_event_success(self, service, mock_table):
        """Test successful recording of a freeze event."""
        result = service.record_freeze_event(
            resort_id="big-white",
            elevation_level="top",
            freeze_date="2026-02-10T03:00:00+00:00",
        )

        assert result is True
        mock_table.update_item.assert_called_once()

        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {
            "resort_id": "big-white",
            "elevation_level": "top",
        }
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":freeze_date"] == "2026-02-10T03:00:00+00:00"
        assert expr_values[":zero"] == Decimal("0")
        assert ":now" in expr_values

    def test_record_freeze_event_resets_accumulation(self, service, mock_table):
        """Test that freeze event resets snowfall_since_freeze_cm to zero."""
        service.record_freeze_event(
            resort_id="big-white",
            elevation_level="mid",
            freeze_date="2026-02-10T03:00:00+00:00",
        )

        call_kwargs = mock_table.update_item.call_args[1]
        update_expr = call_kwargs["UpdateExpression"]
        assert "snowfall_since_freeze_cm = :zero" in update_expr
        assert "last_freeze_date = :freeze_date" in update_expr
        assert "last_updated = :now" in update_expr

    def test_record_freeze_event_dynamo_error(self, service, mock_table):
        """Test record_freeze_event returns False on DynamoDB ClientError."""
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "update_item",
        )

        result = service.record_freeze_event(
            resort_id="big-white",
            elevation_level="base",
            freeze_date="2026-02-10T03:00:00+00:00",
        )

        assert result is False

    # ---------------------------------------------------------------
    # add_snowfall tests
    # ---------------------------------------------------------------

    def test_add_snowfall_success(self, service, mock_table):
        """Test successful snowfall addition."""
        result = service.add_snowfall(
            resort_id="big-white",
            elevation_level="top",
            new_snowfall_cm=15.5,
        )

        assert result is True
        mock_table.update_item.assert_called_once()

        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {
            "resort_id": "big-white",
            "elevation_level": "top",
        }
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":snow"] == Decimal("15.5")
        assert expr_values[":zero"] == Decimal("0")

    def test_add_snowfall_updates_both_accumulators(self, service, mock_table):
        """Test that snowfall is added to both since-freeze and season totals."""
        service.add_snowfall(
            resort_id="big-white",
            elevation_level="mid",
            new_snowfall_cm=10.0,
        )

        call_kwargs = mock_table.update_item.call_args[1]
        update_expr = call_kwargs["UpdateExpression"]
        assert "snowfall_since_freeze_cm" in update_expr
        assert "total_season_snowfall_cm" in update_expr
        assert "last_updated" in update_expr

    def test_add_snowfall_zero_does_nothing(self, service, mock_table):
        """Test that adding zero snowfall skips the DynamoDB call."""
        result = service.add_snowfall(
            resort_id="big-white",
            elevation_level="mid",
            new_snowfall_cm=0.0,
        )

        assert result is True
        mock_table.update_item.assert_not_called()

    def test_add_snowfall_negative_does_nothing(self, service, mock_table):
        """Test that adding negative snowfall skips the DynamoDB call."""
        result = service.add_snowfall(
            resort_id="big-white",
            elevation_level="mid",
            new_snowfall_cm=-5.0,
        )

        assert result is True
        mock_table.update_item.assert_not_called()

    def test_add_snowfall_rounds_value(self, service, mock_table):
        """Test that snowfall value is rounded to 2 decimals."""
        service.add_snowfall(
            resort_id="big-white",
            elevation_level="mid",
            new_snowfall_cm=7.777,
        )

        expr_values = mock_table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert expr_values[":snow"] == Decimal("7.78")

    def test_add_snowfall_dynamo_error(self, service, mock_table):
        """Test add_snowfall returns False on DynamoDB ClientError."""
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "update_item",
        )

        result = service.add_snowfall(
            resort_id="big-white",
            elevation_level="mid",
            new_snowfall_cm=10.0,
        )

        assert result is False

    # ---------------------------------------------------------------
    # get_or_create_summary tests
    # ---------------------------------------------------------------

    def test_get_or_create_summary_returns_existing(
        self, service, mock_table, sample_dynamo_item
    ):
        """Test get_or_create returns existing summary without creating a new one."""
        mock_table.get_item.return_value = {"Item": sample_dynamo_item}

        result = service.get_or_create_summary("big-white", "mid")

        assert result["resort_id"] == "big-white"
        assert result["elevation_level"] == "mid"
        assert result["snowfall_since_freeze_cm"] == 45.50
        # Should NOT have called put_item since it already exists
        mock_table.put_item.assert_not_called()

    def test_get_or_create_summary_creates_new(self, service, mock_table):
        """Test get_or_create creates a default summary when none exists."""
        mock_table.get_item.return_value = {}

        result = service.get_or_create_summary("whistler", "base")

        assert result["resort_id"] == "whistler"
        assert result["elevation_level"] == "base"
        assert result["last_freeze_date"] is None
        assert result["snowfall_since_freeze_cm"] == 0.0
        assert result["total_season_snowfall_cm"] == 0.0
        assert "season_start_date" in result
        assert "last_updated" in result
        # Should have called put_item to persist defaults
        mock_table.put_item.assert_called_once()

    def test_get_or_create_summary_default_has_current_date(self, service, mock_table):
        """Test that new summary uses current date for season_start_date."""
        mock_table.get_item.return_value = {}

        with patch("services.snow_summary_service.datetime") as mock_datetime:
            mock_now = datetime(2026, 1, 15, 10, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            result = service.get_or_create_summary("big-white", "top")

        assert result["season_start_date"] == "2026-01-15"
        assert result["last_updated"] == mock_now.isoformat()

    def test_get_or_create_summary_persists_defaults(self, service, mock_table):
        """Test that created defaults are written to DynamoDB via update_summary."""
        mock_table.get_item.return_value = {}

        service.get_or_create_summary("big-white", "base")

        # Verify put_item was called with correct item structure
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["resort_id"] == "big-white"
        assert item["elevation_level"] == "base"
        assert item["snowfall_since_freeze_cm"] == Decimal("0.0")
        assert item["total_season_snowfall_cm"] == Decimal("0.0")

    def test_get_or_create_summary_returns_defaults_even_if_save_fails(
        self, service, mock_table
    ):
        """Test that defaults are returned even if persisting them fails."""
        mock_table.get_item.return_value = {}
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "put_item",
        )

        result = service.get_or_create_summary("big-white", "mid")

        # Should still return the default summary dict
        assert result["resort_id"] == "big-white"
        assert result["snowfall_since_freeze_cm"] == 0.0

    # ---------------------------------------------------------------
    # _convert_decimals tests
    # ---------------------------------------------------------------

    def test_convert_decimals_basic(self, service):
        """Test conversion of Decimal values to floats."""
        item = {
            "snowfall": Decimal("15.5"),
            "total": Decimal("100.0"),
            "name": "big-white",
        }

        result = service._convert_decimals(item)

        assert result["snowfall"] == 15.5
        assert isinstance(result["snowfall"], float)
        assert result["total"] == 100.0
        assert isinstance(result["total"], float)
        assert result["name"] == "big-white"
        assert isinstance(result["name"], str)

    def test_convert_decimals_nested_dict(self, service):
        """Test conversion of nested dict with Decimal values."""
        item = {
            "resort_id": "big-white",
            "stats": {
                "snow_cm": Decimal("25.0"),
                "temp_celsius": Decimal("-5.5"),
            },
        }

        result = service._convert_decimals(item)

        assert result["stats"]["snow_cm"] == 25.0
        assert isinstance(result["stats"]["snow_cm"], float)
        assert result["stats"]["temp_celsius"] == -5.5

    def test_convert_decimals_no_decimals(self, service):
        """Test conversion when no Decimal values exist."""
        item = {
            "resort_id": "whistler",
            "elevation_level": "top",
            "season_start_date": "2025-11-01",
        }

        result = service._convert_decimals(item)

        assert result == item

    def test_convert_decimals_empty_dict(self, service):
        """Test conversion of empty dict."""
        result = service._convert_decimals({})
        assert result == {}

    def test_convert_decimals_integer_decimal(self, service):
        """Test conversion of Decimal with integer value."""
        item = {"count": Decimal("0")}

        result = service._convert_decimals(item)

        assert result["count"] == 0.0
        assert isinstance(result["count"], float)

    def test_convert_decimals_preserves_none(self, service):
        """Test that None values are preserved."""
        item = {"last_freeze_date": None, "snowfall": Decimal("10")}

        result = service._convert_decimals(item)

        assert result["last_freeze_date"] is None
        assert result["snowfall"] == 10.0

    def test_convert_decimals_deeply_nested(self, service):
        """Test conversion with deeply nested dicts."""
        item = {
            "level1": {
                "level2": {
                    "value": Decimal("42.42"),
                    "text": "hello",
                }
            }
        }

        result = service._convert_decimals(item)

        assert result["level1"]["level2"]["value"] == 42.42
        assert result["level1"]["level2"]["text"] == "hello"

    # ---------------------------------------------------------------
    # reset_for_new_season tests
    # ---------------------------------------------------------------

    def test_reset_for_new_season_success(self, service, mock_table):
        """Test successful season reset."""
        result = service.reset_for_new_season(
            resort_id="big-white",
            elevation_level="mid",
            season_start_date="2026-11-01",
        )

        assert result is True
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["resort_id"] == "big-white"
        assert item["elevation_level"] == "mid"
        assert item["last_freeze_date"] is None
        assert item["snowfall_since_freeze_cm"] == Decimal("0")
        assert item["total_season_snowfall_cm"] == Decimal("0")
        assert item["season_start_date"] == "2026-11-01"
        assert "last_updated" in item

    def test_reset_for_new_season_dynamo_error(self, service, mock_table):
        """Test reset_for_new_season returns False on DynamoDB ClientError."""
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "put_item",
        )

        result = service.reset_for_new_season(
            resort_id="big-white",
            elevation_level="mid",
            season_start_date="2026-11-01",
        )

        assert result is False

    # ---------------------------------------------------------------
    # Integration-style tests (method interactions)
    # ---------------------------------------------------------------

    def test_full_flow_new_summary_then_add_snowfall(self, service, mock_table):
        """Test creating a summary then adding snowfall."""
        # First call: no summary exists
        mock_table.get_item.return_value = {}
        summary = service.get_or_create_summary("big-white", "top")
        assert summary["snowfall_since_freeze_cm"] == 0.0

        # Add snowfall
        result = service.add_snowfall("big-white", "top", 15.0)
        assert result is True
        mock_table.update_item.assert_called_once()

    def test_full_flow_freeze_then_add_snowfall(self, service, mock_table):
        """Test recording a freeze event then adding new snowfall."""
        # Record freeze
        result = service.record_freeze_event(
            "big-white", "mid", "2026-02-10T03:00:00+00:00"
        )
        assert result is True

        # Add new snowfall after freeze
        result = service.add_snowfall("big-white", "mid", 5.0)
        assert result is True

        # update_item should have been called twice (once for freeze, once for snow)
        assert mock_table.update_item.call_count == 2

    def test_service_initialization(self, mock_table):
        """Test that service stores the table reference."""
        service = SnowSummaryService(mock_table)
        assert service.table is mock_table

    def test_get_summary_converts_all_decimal_fields(self, service, mock_table):
        """Test that get_summary properly converts all Decimal fields from DynamoDB."""
        dynamo_item = {
            "resort_id": "whistler",
            "elevation_level": "top",
            "snowfall_since_freeze_cm": Decimal("0"),
            "total_season_snowfall_cm": Decimal("200.55"),
            "last_updated": "2026-02-01T12:00:00+00:00",
        }
        mock_table.get_item.return_value = {"Item": dynamo_item}

        result = service.get_summary("whistler", "top")

        assert isinstance(result["snowfall_since_freeze_cm"], float)
        assert isinstance(result["total_season_snowfall_cm"], float)
        assert result["snowfall_since_freeze_cm"] == 0.0
        assert result["total_season_snowfall_cm"] == 200.55
        # String fields should remain strings
        assert isinstance(result["resort_id"], str)

    def test_update_summary_includes_freeze_date_only_when_provided(
        self, service, mock_table
    ):
        """Test that last_freeze_date is only included in item when not None."""
        # With freeze date
        service.update_summary(
            resort_id="r1",
            elevation_level="mid",
            last_freeze_date="2026-01-01T00:00:00+00:00",
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=0.0,
            last_updated="2026-02-01T00:00:00+00:00",
        )
        item_with = mock_table.put_item.call_args[1]["Item"]
        assert "last_freeze_date" in item_with

        mock_table.reset_mock()

        # Without freeze date
        service.update_summary(
            resort_id="r1",
            elevation_level="mid",
            last_freeze_date=None,
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=0.0,
            last_updated="2026-02-01T00:00:00+00:00",
        )
        item_without = mock_table.put_item.call_args[1]["Item"]
        assert "last_freeze_date" not in item_without

    def test_add_snowfall_uses_if_not_exists(self, service, mock_table):
        """Test that add_snowfall uses if_not_exists for atomic safety."""
        service.add_snowfall("big-white", "mid", 5.0)

        call_kwargs = mock_table.update_item.call_args[1]
        update_expr = call_kwargs["UpdateExpression"]
        assert "if_not_exists(snowfall_since_freeze_cm, :zero)" in update_expr
        assert "if_not_exists(total_season_snowfall_cm, :zero)" in update_expr

    def test_record_freeze_event_sets_now_timestamp(self, service, mock_table):
        """Test that record_freeze_event sets last_updated to current time."""
        with patch("services.snow_summary_service.datetime") as mock_datetime:
            mock_now = datetime(2026, 2, 15, 14, 30, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            service.record_freeze_event("big-white", "mid", "2026-02-15T14:00:00+00:00")

        expr_values = mock_table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert expr_values[":now"] == mock_now.isoformat()
