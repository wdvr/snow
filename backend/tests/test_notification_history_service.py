"""Tests for NotificationHistoryService."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, call

import pytest
from botocore.exceptions import ClientError

from models.notification import (
    NotificationPayload,
    NotificationRecord,
    NotificationType,
)
from services.notification_history_service import NotificationHistoryService


class TestNotificationHistoryService:
    """Test cases for NotificationHistoryService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {}
        table.query.return_value = {"Items": [], "Count": 0}
        table.update_item.return_value = {}
        return table

    @pytest.fixture
    def service(self, mock_table):
        """Create a NotificationHistoryService with mocked table."""
        return NotificationHistoryService(table=mock_table)

    @pytest.fixture
    def sample_payload(self):
        """Create a sample notification payload."""
        return NotificationPayload(
            notification_type=NotificationType.POWDER_ALERT,
            title="Powder Day!",
            body="Whistler got 30cm of fresh snow overnight!",
            resort_id="whistler-blackcomb",
            resort_name="Whistler Blackcomb",
            data={"snow_cm": 30},
        )

    @pytest.fixture
    def sample_db_item(self):
        """Create a sample DynamoDB item for a notification."""
        return {
            "user_id": "user_123",
            "notification_id": "01HXYZ123456789ABCDEFGHIJ",
            "notification_type": "powder_alert",
            "resort_id": "whistler-blackcomb",
            "resort_name": "Whistler Blackcomb",
            "title": "Powder Day!",
            "body": "Whistler got 30cm of fresh snow overnight!",
            "sent_at": "2026-03-01T10:00:00+00:00",
            "read_at": None,
            "expires_at": Decimal("1743500400"),
            "data": {"snow_cm": Decimal("30")},
        }

    # ---- store_notification ----

    def test_store_notification(self, service, mock_table, sample_payload):
        """Test storing a notification record."""
        record = service.store_notification("user_123", sample_payload)

        assert record.user_id == "user_123"
        assert record.notification_type == NotificationType.POWDER_ALERT
        assert record.title == "Powder Day!"
        assert record.body == "Whistler got 30cm of fresh snow overnight!"
        assert record.resort_id == "whistler-blackcomb"
        assert record.resort_name == "Whistler Blackcomb"
        assert record.read_at is None
        assert record.expires_at is not None
        assert record.notification_id  # ULID should be set
        assert record.sent_at  # timestamp should be set

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["user_id"] == "user_123"
        assert item["notification_type"] == "powder_alert"

    def test_store_notification_sets_ttl(self, service, mock_table, sample_payload):
        """Test that stored notifications have a 30-day TTL."""
        record = service.store_notification("user_123", sample_payload)

        now_epoch = int(datetime.now(UTC).timestamp())
        thirty_days = 30 * 24 * 60 * 60
        assert abs(record.expires_at - (now_epoch + thirty_days)) < 5

    def test_store_notification_db_error(self, service, mock_table, sample_payload):
        """Test handling of DynamoDB error during store."""
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
            "PutItem",
        )

        with pytest.raises(ClientError):
            service.store_notification("user_123", sample_payload)

    # ---- get_notifications ----

    def test_get_notifications_empty(self, service, mock_table):
        """Test getting notifications when none exist."""
        result = service.get_notifications("user_123")

        assert result["notifications"] == []
        assert "cursor" not in result
        mock_table.query.assert_called_once()

    def test_get_notifications_returns_records(
        self, service, mock_table, sample_db_item
    ):
        """Test getting notifications returns parsed records."""
        mock_table.query.return_value = {"Items": [sample_db_item]}

        result = service.get_notifications("user_123")

        assert len(result["notifications"]) == 1
        n = result["notifications"][0]
        assert isinstance(n, NotificationRecord)
        assert n.notification_id == "01HXYZ123456789ABCDEFGHIJ"
        assert n.notification_type == NotificationType.POWDER_ALERT
        assert n.resort_name == "Whistler Blackcomb"

    def test_get_notifications_pagination_cursor(
        self, service, mock_table, sample_db_item
    ):
        """Test pagination with cursor."""
        mock_table.query.return_value = {
            "Items": [sample_db_item],
            "LastEvaluatedKey": {
                "user_id": "user_123",
                "notification_id": "01HXYZ_LAST",
            },
        }

        result = service.get_notifications("user_123", limit=10)

        assert result["cursor"] == "01HXYZ_LAST"

    def test_get_notifications_with_cursor_param(self, service, mock_table):
        """Test that cursor is passed as ExclusiveStartKey."""
        mock_table.query.return_value = {"Items": []}

        service.get_notifications("user_123", cursor="01HXYZ_CURSOR")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ExclusiveStartKey"] == {
            "user_id": "user_123",
            "notification_id": "01HXYZ_CURSOR",
        }

    def test_get_notifications_newest_first(self, service, mock_table):
        """Test that notifications are queried in descending order."""
        mock_table.query.return_value = {"Items": []}

        service.get_notifications("user_123")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_get_notifications_respects_limit(self, service, mock_table):
        """Test that limit is passed to query."""
        mock_table.query.return_value = {"Items": []}

        service.get_notifications("user_123", limit=5)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 5

    # ---- mark_as_read ----

    def test_mark_as_read_success(self, service, mock_table):
        """Test marking a notification as read."""
        result = service.mark_as_read("user_123", "notif_001")

        assert result is True
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {
            "user_id": "user_123",
            "notification_id": "notif_001",
        }
        assert "read_at" in call_kwargs["UpdateExpression"]

    def test_mark_as_read_not_found(self, service, mock_table):
        """Test marking a non-existent notification as read."""
        mock_table.update_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Not found",
                }
            },
            "UpdateItem",
        )

        result = service.mark_as_read("user_123", "notif_nonexistent")

        assert result is False

    # ---- mark_all_as_read ----

    def test_mark_all_as_read_no_unread(self, service, mock_table):
        """Test marking all as read when none are unread."""
        mock_table.query.return_value = {"Items": []}

        count = service.mark_all_as_read("user_123")

        assert count == 0

    def test_mark_all_as_read_updates_each(self, service, mock_table):
        """Test that mark_all_as_read updates each unread notification."""
        mock_table.query.return_value = {
            "Items": [
                {"user_id": "user_123", "notification_id": "notif_001"},
                {"user_id": "user_123", "notification_id": "notif_002"},
            ]
        }

        count = service.mark_all_as_read("user_123")

        assert count == 2
        assert mock_table.update_item.call_count == 2

    def test_mark_all_as_read_partial_failure(self, service, mock_table):
        """Test that partial failures are handled gracefully."""
        mock_table.query.return_value = {
            "Items": [
                {"user_id": "user_123", "notification_id": "notif_001"},
                {"user_id": "user_123", "notification_id": "notif_002"},
            ]
        }
        # First update succeeds, second fails
        mock_table.update_item.side_effect = [
            {},
            ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "DB error"}},
                "UpdateItem",
            ),
        ]

        count = service.mark_all_as_read("user_123")

        assert count == 1  # Only first one succeeded

    # ---- get_unread_count ----

    def test_get_unread_count_zero(self, service, mock_table):
        """Test getting unread count when all are read."""
        mock_table.query.return_value = {"Count": 0}

        count = service.get_unread_count("user_123")

        assert count == 0

    def test_get_unread_count_with_unread(self, service, mock_table):
        """Test getting unread count with unread notifications."""
        mock_table.query.return_value = {"Count": 5}

        count = service.get_unread_count("user_123")

        assert count == 5

    def test_get_unread_count_uses_select_count(self, service, mock_table):
        """Test that unread count uses SELECT COUNT for efficiency."""
        mock_table.query.return_value = {"Count": 0}

        service.get_unread_count("user_123")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Select"] == "COUNT"

    # ---- NotificationRecord.create ----

    def test_notification_record_create(self, sample_payload):
        """Test creating a NotificationRecord from a payload."""
        record = NotificationRecord.create(
            user_id="user_123",
            payload=sample_payload,
        )

        assert record.user_id == "user_123"
        assert record.notification_type == NotificationType.POWDER_ALERT
        assert record.title == "Powder Day!"
        assert record.body == "Whistler got 30cm of fresh snow overnight!"
        assert record.resort_id == "whistler-blackcomb"
        assert record.resort_name == "Whistler Blackcomb"
        assert record.read_at is None
        assert record.expires_at is not None
        assert len(record.notification_id) == 26  # ULID length

    def test_notification_record_create_unique_ids(self, sample_payload):
        """Test that each create() call generates a unique ID."""
        r1 = NotificationRecord.create(user_id="user_123", payload=sample_payload)
        r2 = NotificationRecord.create(user_id="user_123", payload=sample_payload)

        assert r1.notification_id != r2.notification_id
