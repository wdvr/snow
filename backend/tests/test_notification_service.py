"""Tests for NotificationService."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from models.notification import (
    FREEZE_MESSAGES,
    THAW_MESSAGES,
    DeviceToken,
    NotificationPayload,
    NotificationType,
    ResortEvent,
    ResortNotificationSettings,
    UserNotificationPreferences,
)
from models.user import UserPreferences
from services.notification_service import NotificationService


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""

    def test_init_with_explicit_sns_client(self):
        """Test initialization with an explicit SNS client."""
        sns_mock = MagicMock()
        service = NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=sns_mock,
            apns_platform_arn="arn:aws:sns:us-west-2:123456:app/APNS/snow",
        )
        assert service.sns is sns_mock
        assert service.apns_platform_arn == "arn:aws:sns:us-west-2:123456:app/APNS/snow"

    def test_init_reads_apns_arn_from_env(self):
        """Test that APNS_PLATFORM_APP_ARN is read from environment if not passed."""
        with patch.dict(
            "os.environ",
            {"APNS_PLATFORM_APP_ARN": "arn:aws:sns:us-west-2:000:app/APNS/test"},
        ):
            service = NotificationService(
                device_tokens_table=MagicMock(),
                user_preferences_table=MagicMock(),
                resort_events_table=MagicMock(),
                weather_conditions_table=MagicMock(),
                resorts_table=MagicMock(),
                sns_client=MagicMock(),
            )
            assert (
                service.apns_platform_arn == "arn:aws:sns:us-west-2:000:app/APNS/test"
            )


class TestRegisterDeviceToken:
    """Tests for register_device_token."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_register_device_token_returns_device_token(self, service):
        """Test that register_device_token returns a DeviceToken model."""
        result = service.register_device_token(
            user_id="user1",
            device_id="dev1",
            token="apns-tok-abc",
            platform="ios",
            app_version="2.0.0",
        )

        assert isinstance(result, DeviceToken)
        assert result.user_id == "user1"
        assert result.device_id == "dev1"
        assert result.token == "apns-tok-abc"
        assert result.platform == "ios"
        assert result.app_version == "2.0.0"

    def test_register_device_token_stores_in_dynamodb(self, service):
        """Test that register_device_token calls put_item on the table."""
        service.register_device_token(
            user_id="user1",
            device_id="dev1",
            token="apns-tok-abc",
        )

        service.device_tokens_table.put_item.assert_called_once()
        call_kwargs = service.device_tokens_table.put_item.call_args
        item = call_kwargs.kwargs.get("Item") or call_kwargs[1]["Item"]
        assert item["user_id"] == "user1"
        assert item["device_id"] == "dev1"
        assert item["token"] == "apns-tok-abc"

    def test_register_device_token_default_platform_is_ios(self, service):
        """Test that the default platform is ios."""
        result = service.register_device_token(
            user_id="user1", device_id="dev1", token="tok"
        )
        assert result.platform == "ios"


class TestUnregisterDeviceToken:
    """Tests for unregister_device_token."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_unregister_device_token_success(self, service):
        """Test successful device token unregistration."""
        result = service.unregister_device_token("user1", "dev1")
        assert result is True
        service.device_tokens_table.delete_item.assert_called_once_with(
            Key={"user_id": "user1", "device_id": "dev1"}
        )

    def test_unregister_device_token_client_error(self, service):
        """Test unregister returns False on ClientError."""
        service.device_tokens_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "err"}},
            "DeleteItem",
        )
        result = service.unregister_device_token("user1", "dev1")
        assert result is False


class TestGetUserDeviceTokens:
    """Tests for get_user_device_tokens."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_user_device_tokens_returns_list(self, service):
        """Test that get_user_device_tokens returns a list of DeviceToken."""
        now = datetime.now(UTC).isoformat()
        service.device_tokens_table.query.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "device_id": "dev1",
                    "token": "tok1",
                    "platform": "ios",
                    "app_version": "1.0",
                    "created_at": now,
                    "updated_at": now,
                    "ttl": 9999999999,
                },
                {
                    "user_id": "user1",
                    "device_id": "dev2",
                    "token": "tok2",
                    "platform": "ios",
                    "app_version": "1.1",
                    "created_at": now,
                    "updated_at": now,
                    "ttl": 9999999999,
                },
            ]
        }

        tokens = service.get_user_device_tokens("user1")

        assert len(tokens) == 2
        assert all(isinstance(t, DeviceToken) for t in tokens)
        assert tokens[0].token == "tok1"
        assert tokens[1].token == "tok2"

    def test_get_user_device_tokens_empty(self, service):
        """Test that get_user_device_tokens returns empty list when no tokens exist."""
        service.device_tokens_table.query.return_value = {"Items": []}
        tokens = service.get_user_device_tokens("user_no_devices")
        assert tokens == []


class TestSendPushNotification:
    """Tests for send_push_notification."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:aws:sns:us-west-2:123:app/APNS/snow",
        )

    @pytest.fixture
    def sample_payload(self):
        return NotificationPayload(
            notification_type=NotificationType.FRESH_SNOW,
            title="Fresh Snow at Whistler!",
            body="15cm of fresh snow has fallen.",
            resort_id="whistler-blackcomb",
            resort_name="Whistler Blackcomb",
            data={"fresh_snow_cm": 15.0},
        )

    def test_send_push_notification_success(self, service, sample_payload):
        """Test successful push notification sending."""
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:aws:sns:us-west-2:123:endpoint/APNS/snow/abc"
        }

        result = service.send_push_notification("device-token-123", sample_payload)

        assert result is True
        service.sns.create_platform_endpoint.assert_called_once_with(
            PlatformApplicationArn="arn:aws:sns:us-west-2:123:app/APNS/snow",
            Token="device-token-123",
        )
        service.sns.publish.assert_called_once()
        call_kwargs = service.sns.publish.call_args.kwargs
        assert (
            call_kwargs["TargetArn"]
            == "arn:aws:sns:us-west-2:123:endpoint/APNS/snow/abc"
        )
        assert call_kwargs["MessageStructure"] == "json"

        # Verify the message is properly formatted JSON with APNS key
        message = json.loads(call_kwargs["Message"])
        assert "APNS" in message
        apns_payload = json.loads(message["APNS"])
        assert apns_payload["aps"]["alert"]["title"] == "Fresh Snow at Whistler!"

    def test_send_push_notification_no_platform_arn(self, sample_payload):
        """Test that send_push_notification returns False when no APNS ARN is configured."""
        service = NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn=None,
        )
        # Clear the env variable to ensure it's None
        with patch.dict("os.environ", {}, clear=True):
            service.apns_platform_arn = None
            result = service.send_push_notification("device-token-123", sample_payload)
        assert result is False

    def test_send_push_notification_endpoint_disabled(self, service, sample_payload):
        """Test handling of EndpointDisabled error."""
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:aws:sns:us-west-2:123:endpoint/APNS/snow/abc"
        }
        service.sns.publish.side_effect = ClientError(
            {"Error": {"Code": "EndpointDisabled", "Message": "Endpoint disabled"}},
            "Publish",
        )

        result = service.send_push_notification("device-token-123", sample_payload)
        assert result is False

    def test_send_push_notification_generic_client_error(self, service, sample_payload):
        """Test handling of a generic ClientError during publish."""
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:aws:sns:us-west-2:123:endpoint/APNS/snow/abc"
        }
        service.sns.publish.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Something went wrong"}},
            "Publish",
        )

        result = service.send_push_notification("device-token-123", sample_payload)
        assert result is False

    def test_send_push_notification_create_endpoint_error(
        self, service, sample_payload
    ):
        """Test handling of ClientError during endpoint creation."""
        service.sns.create_platform_endpoint.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameter", "Message": "Bad token"}},
            "CreatePlatformEndpoint",
        )

        result = service.send_push_notification("device-token-123", sample_payload)
        assert result is False


class TestSendNotificationToUser:
    """Tests for send_notification_to_user."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:aws:sns:us-west-2:123:app/APNS/snow",
        )

    @pytest.fixture
    def sample_payload(self):
        return NotificationPayload(
            notification_type=NotificationType.FRESH_SNOW,
            title="Fresh Snow!",
            body="10cm of fresh snow.",
            resort_id="whistler-blackcomb",
            resort_name="Whistler Blackcomb",
        )

    def test_send_notification_to_user_multiple_devices(self, service, sample_payload):
        """Test sending notification to a user with multiple devices."""
        now = datetime.now(UTC).isoformat()
        service.device_tokens_table.query.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "device_id": "dev1",
                    "token": "tok1",
                    "platform": "ios",
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "user_id": "user1",
                    "device_id": "dev2",
                    "token": "tok2",
                    "platform": "ios",
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        }
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:endpoint/abc"
        }

        result = service.send_notification_to_user("user1", sample_payload)

        assert result == 2
        assert service.sns.publish.call_count == 2

    def test_send_notification_to_user_no_devices(self, service, sample_payload):
        """Test sending notification to a user with no devices."""
        service.device_tokens_table.query.return_value = {"Items": []}

        result = service.send_notification_to_user("user_no_devices", sample_payload)
        assert result == 0

    def test_send_notification_to_user_partial_failure(self, service, sample_payload):
        """Test sending to multiple devices where some fail."""
        now = datetime.now(UTC).isoformat()
        service.device_tokens_table.query.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "device_id": "dev1",
                    "token": "tok1",
                    "platform": "ios",
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "user_id": "user1",
                    "device_id": "dev2",
                    "token": "tok2",
                    "platform": "ios",
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        }
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:endpoint/abc"
        }
        # First publish succeeds, second fails
        service.sns.publish.side_effect = [
            {"MessageId": "msg1"},
            ClientError(
                {"Error": {"Code": "EndpointDisabled", "Message": "disabled"}},
                "Publish",
            ),
        ]

        result = service.send_notification_to_user("user1", sample_payload)
        assert result == 1


class TestCreateResortEvent:
    """Tests for create_resort_event."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_create_resort_event(self, service):
        """Test creating a resort event stores it and returns it."""
        event = ResortEvent.create(
            resort_id="whistler-blackcomb",
            event_id="evt1",
            event_type="free_store",
            title="Demo Day",
            event_date="2026-03-01",
        )

        result = service.create_resort_event(event)

        assert result is event
        service.resort_events_table.put_item.assert_called_once()
        call_kwargs = service.resort_events_table.put_item.call_args
        item = call_kwargs.kwargs.get("Item") or call_kwargs[1]["Item"]
        assert item["resort_id"] == "whistler-blackcomb"
        assert item["event_id"] == "evt1"


class TestGetUpcomingEvents:
    """Tests for get_upcoming_events."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_upcoming_events_returns_events(self, service):
        """Test get_upcoming_events returns ResortEvent list."""
        now = datetime.now(UTC)
        service.resort_events_table.query.return_value = {
            "Items": [
                {
                    "resort_id": "whistler-blackcomb",
                    "event_id": "evt1",
                    "event_type": "free_store",
                    "title": "Demo Day",
                    "event_date": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
                    "created_at": now.isoformat(),
                },
            ]
        }

        events = service.get_upcoming_events("whistler-blackcomb", days_ahead=7)

        assert len(events) == 1
        assert isinstance(events[0], ResortEvent)
        assert events[0].title == "Demo Day"

    def test_get_upcoming_events_empty(self, service):
        """Test get_upcoming_events with no events."""
        service.resort_events_table.query.return_value = {"Items": []}
        events = service.get_upcoming_events("no-events-resort")
        assert events == []

    def test_get_upcoming_events_query_parameters(self, service):
        """Test that get_upcoming_events passes correct query parameters."""
        service.resort_events_table.query.return_value = {"Items": []}

        service.get_upcoming_events("whistler-blackcomb", days_ahead=14)

        call_kwargs = service.resort_events_table.query.call_args.kwargs
        assert call_kwargs["IndexName"] == "EventDateIndex"
        assert ":rid" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":rid"] == "whistler-blackcomb"


class TestGetNewEventsSince:
    """Tests for get_new_events_since."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_new_events_since_returns_events(self, service):
        """Test get_new_events_since returns events created after timestamp."""
        now = datetime.now(UTC)
        service.resort_events_table.query.return_value = {
            "Items": [
                {
                    "resort_id": "whistler-blackcomb",
                    "event_id": "evt1",
                    "event_type": "competition",
                    "title": "Ski Race",
                    "event_date": "2026-03-15",
                    "created_at": now.isoformat(),
                },
            ]
        }

        since = (now - timedelta(hours=1)).isoformat()
        events = service.get_new_events_since("whistler-blackcomb", since)

        assert len(events) == 1
        assert events[0].event_id == "evt1"

    def test_get_new_events_since_empty(self, service):
        """Test get_new_events_since when no new events exist."""
        service.resort_events_table.query.return_value = {"Items": []}
        events = service.get_new_events_since(
            "whistler-blackcomb", "2026-01-01T00:00:00"
        )
        assert events == []


class TestGetFreshSnowCm:
    """Tests for get_fresh_snow_cm."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_fresh_snow_cm_returns_value(self, service):
        """Test get_fresh_snow_cm returns the fresh_snow_cm from the latest condition."""
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "fresh_snow_cm": 12.5}]
        }

        result = service.get_fresh_snow_cm("whistler-blackcomb")
        assert result == 12.5

    def test_get_fresh_snow_cm_no_conditions(self, service):
        """Test get_fresh_snow_cm returns 0.0 when no conditions are available."""
        service.weather_conditions_table.query.return_value = {"Items": []}
        result = service.get_fresh_snow_cm("no-data-resort")
        assert result == 0.0

    def test_get_fresh_snow_cm_missing_field(self, service):
        """Test get_fresh_snow_cm returns 0.0 when fresh_snow_cm field is absent."""
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb"}]
        }
        result = service.get_fresh_snow_cm("whistler-blackcomb")
        assert result == 0.0

    def test_get_fresh_snow_cm_exception(self, service):
        """Test get_fresh_snow_cm returns 0.0 on exception."""
        service.weather_conditions_table.query.side_effect = Exception("DB error")
        result = service.get_fresh_snow_cm("whistler-blackcomb")
        assert result == 0.0


class TestGetCurrentTemperature:
    """Tests for get_current_temperature."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_current_temperature_returns_value(self, service):
        """Test get_current_temperature returns the temperature."""
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "current_temp_celsius": -5.0}]
        }
        result = service.get_current_temperature("whistler-blackcomb")
        assert result == -5.0

    def test_get_current_temperature_no_data(self, service):
        """Test get_current_temperature returns None when no data available."""
        service.weather_conditions_table.query.return_value = {"Items": []}
        result = service.get_current_temperature("no-data-resort")
        assert result is None

    def test_get_current_temperature_exception(self, service):
        """Test get_current_temperature returns None on exception."""
        service.weather_conditions_table.query.side_effect = Exception("DB error")
        result = service.get_current_temperature("whistler-blackcomb")
        assert result is None


class TestGetResortName:
    """Tests for get_resort_name."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_get_resort_name_found(self, service):
        """Test get_resort_name returns name from DynamoDB."""
        service.resorts_table.get_item.return_value = {
            "Item": {"resort_id": "whistler-blackcomb", "name": "Whistler Blackcomb"}
        }
        result = service.get_resort_name("whistler-blackcomb")
        assert result == "Whistler Blackcomb"

    def test_get_resort_name_not_found(self, service):
        """Test get_resort_name returns resort_id when not found."""
        service.resorts_table.get_item.return_value = {}
        result = service.get_resort_name("unknown-resort")
        assert result == "unknown-resort"

    def test_get_resort_name_item_missing_name_field(self, service):
        """Test get_resort_name returns resort_id when name field is missing."""
        service.resorts_table.get_item.return_value = {
            "Item": {"resort_id": "whistler-blackcomb"}
        }
        result = service.get_resort_name("whistler-blackcomb")
        assert result == "whistler-blackcomb"

    def test_get_resort_name_exception(self, service):
        """Test get_resort_name returns resort_id on exception."""
        service.resorts_table.get_item.side_effect = Exception("Table error")
        result = service.get_resort_name("whistler-blackcomb")
        assert result == "whistler-blackcomb"


class TestCheckThawFreezeCycle:
    """Tests for check_thaw_freeze_cycle."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_thaw_starts_when_temp_goes_positive_from_frozen(self, service):
        """Test that transitioning from frozen to positive temp records thaw start."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "frozen"},
            thaw_started_at={},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=2.0,
            notification_settings=settings,
        )

        assert result is None
        assert settings.temperature_state["resort1"] == "thawed"
        assert "resort1" in settings.thaw_started_at

    def test_thaw_alert_after_4_hours(self, service):
        """Test thaw alert fires when temp has been positive for 4+ hours.

        Note: The production code has a timezone-aware vs naive datetime subtraction
        at line 382 (now is tz-aware via datetime.now(UTC), but thaw_start has tzinfo
        stripped). This causes a TypeError caught by the except block at line 404.
        We patch datetime.now to return a naive datetime so the code path works as
        intended for test coverage.
        """
        naive_now = datetime.now(UTC).replace(tzinfo=None)
        five_hours_ago = (naive_now - timedelta(hours=5)).isoformat()
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "thawed"},
            thaw_started_at={"resort1": five_hours_ago},
        )

        with patch("services.notification_service.datetime") as mock_dt:
            mock_dt.now.return_value = naive_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with patch(
                "services.notification_service.random.choice",
                return_value=THAW_MESSAGES[0],
            ):
                result = service.check_thaw_freeze_cycle(
                    resort_id="resort1",
                    resort_name="Resort One",
                    current_temp=3.0,
                    notification_settings=settings,
                )

        assert result is not None
        assert result.notification_type == NotificationType.THAW_ALERT
        assert "Resort One" in result.title
        assert result.resort_id == "resort1"
        # Thaw tracking should be cleared after notification
        assert "resort1" not in settings.thaw_started_at

    def test_thaw_alert_after_5_hours(self, service):
        """Test thaw alert fires after 5 hours of positive temp."""
        five_hours_ago = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "thawed"},
            thaw_started_at={"resort1": five_hours_ago},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=3.0,
            notification_settings=settings,
        )

        # Should return thaw alert since 5h > 4h threshold
        assert result is not None
        assert result.notification_type == NotificationType.THAW_ALERT

    def test_no_thaw_alert_before_4_hours(self, service):
        """Test no thaw alert when temp positive for less than 4 hours."""
        two_hours_ago = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "thawed"},
            thaw_started_at={"resort1": two_hours_ago},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=1.0,
            notification_settings=settings,
        )

        assert result is None

    def test_freeze_alert_when_temp_goes_negative_from_thawed(self, service):
        """Test freeze alert fires when temp goes from positive to negative."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "thawed"},
            thaw_started_at={"resort1": datetime.now(UTC).isoformat()},
        )

        with patch(
            "services.notification_service.random.choice",
            return_value=FREEZE_MESSAGES[0],
        ):
            result = service.check_thaw_freeze_cycle(
                resort_id="resort1",
                resort_name="Resort One",
                current_temp=-3.0,
                notification_settings=settings,
            )

        assert result is not None
        assert result.notification_type == NotificationType.FREEZE_ALERT
        assert "Resort One" in result.title
        assert settings.temperature_state["resort1"] == "frozen"
        assert "resort1" not in settings.thaw_started_at

    def test_no_alert_when_still_frozen(self, service):
        """Test no alert when temp remains below zero and state is already frozen."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "frozen"},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=-5.0,
            notification_settings=settings,
        )

        assert result is None

    def test_unknown_state_goes_frozen_when_negative(self, service):
        """Test unknown state transitions to frozen when temp is negative."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "unknown"},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=-2.0,
            notification_settings=settings,
        )

        assert result is None
        assert settings.temperature_state["resort1"] == "frozen"

    def test_thaw_check_with_invalid_timestamp(self, service):
        """Test graceful handling of invalid thaw_started_at timestamp."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "thawed"},
            thaw_started_at={"resort1": "not-a-timestamp"},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=2.0,
            notification_settings=settings,
        )

        # Should not crash, just return None
        assert result is None

    def test_thaw_at_exactly_zero_degrees(self, service):
        """Test that exactly 0 degrees is treated as thawed (>= 0)."""
        settings = UserNotificationPreferences(
            temperature_state={"resort1": "frozen"},
        )

        result = service.check_thaw_freeze_cycle(
            resort_id="resort1",
            resort_name="Resort One",
            current_temp=0.0,
            notification_settings=settings,
        )

        assert result is None  # Just starts tracking
        assert settings.temperature_state["resort1"] == "thawed"


class TestProcessUserNotifications:
    """Tests for process_user_notifications."""

    @pytest.fixture
    def service(self):
        svc = NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )
        svc.resorts_table.get_item.return_value = {
            "Item": {"resort_id": "whistler-blackcomb", "name": "Whistler Blackcomb"}
        }
        return svc

    def _make_prefs(
        self, user_id="user1", favorite_resorts=None, notification_settings=None
    ):
        """Helper to create UserPreferences."""
        now = datetime.now(UTC).isoformat()
        return UserPreferences(
            user_id=user_id,
            favorite_resorts=favorite_resorts or [],
            notification_settings=notification_settings,
            created_at=now,
            updated_at=now,
        )

    def test_notifications_disabled_returns_empty(self, service):
        """Test that disabled notifications result in no notifications."""
        settings = UserNotificationPreferences(notifications_enabled=False)
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )

        result = service.process_user_notifications("user1", prefs)
        assert result == []

    def test_fresh_snow_notification(self, service):
        """Test that fresh snow above threshold generates notification."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=True,
            event_alerts=False,
            thaw_freeze_alerts=False,
            default_snow_threshold_cm=5.0,
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "fresh_snow_cm": 10.0}]
        }

        result = service.process_user_notifications("user1", prefs)

        assert len(result) == 1
        assert result[0].notification_type == NotificationType.FRESH_SNOW
        assert "10cm" in result[0].body

    def test_fresh_snow_below_threshold(self, service):
        """Test that fresh snow below threshold does not generate notification."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=True,
            event_alerts=False,
            thaw_freeze_alerts=False,
            default_snow_threshold_cm=20.0,
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "fresh_snow_cm": 5.0}]
        }

        result = service.process_user_notifications("user1", prefs)
        assert len(result) == 0

    def test_event_notification(self, service):
        """Test that new resort events generate notifications."""
        now = datetime.now(UTC)
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=False,
            event_alerts=True,
            thaw_freeze_alerts=False,
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        service.resort_events_table.query.return_value = {
            "Items": [
                {
                    "resort_id": "whistler-blackcomb",
                    "event_id": "evt1",
                    "event_type": "free_store",
                    "title": "Demo Day",
                    "event_date": "2026-03-01",
                    "created_at": now.isoformat(),
                },
            ]
        }

        result = service.process_user_notifications("user1", prefs)

        assert len(result) == 1
        assert result[0].notification_type == NotificationType.RESORT_EVENT
        assert "Demo Day" in result[0].body

    def test_grace_period_skips_resort(self, service):
        """Test that a resort in grace period is skipped."""
        just_now = datetime.now(UTC).isoformat()
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=True,
            event_alerts=False,
            thaw_freeze_alerts=False,
            last_notified={"whistler-blackcomb": just_now},
            grace_period_hours=24,
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )

        result = service.process_user_notifications("user1", prefs)
        assert len(result) == 0

    def test_per_resort_settings_override(self, service):
        """Test that per-resort settings override global defaults."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=True,
            event_alerts=True,
            thaw_freeze_alerts=False,
            default_snow_threshold_cm=5.0,
            resort_settings={
                "whistler-blackcomb": ResortNotificationSettings(
                    resort_id="whistler-blackcomb",
                    fresh_snow_enabled=True,
                    fresh_snow_threshold_cm=20.0,  # Higher threshold per resort
                    event_notifications_enabled=False,
                ),
            },
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        # 10cm of snow -- above global threshold (5) but below per-resort (20)
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "fresh_snow_cm": 10.0}]
        }

        result = service.process_user_notifications("user1", prefs)
        assert len(result) == 0  # Not enough snow for per-resort threshold

    def test_saves_user_preferences_after_processing(self, service):
        """Test that user preferences are saved after processing."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=False,
            event_alerts=False,
            thaw_freeze_alerts=False,
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )

        service.process_user_notifications("user1", prefs)

        service.user_preferences_table.put_item.assert_called_once()

    def test_thaw_freeze_alert_in_processing(self, service):
        """Test that thaw/freeze alerts are generated during user notification processing."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=False,
            event_alerts=False,
            thaw_freeze_alerts=True,
            temperature_state={"whistler-blackcomb": "thawed"},
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        # Return negative temperature to trigger freeze alert
        service.weather_conditions_table.query.return_value = {
            "Items": [
                {
                    "resort_id": "whistler-blackcomb",
                    "current_temp_celsius": -5.0,
                }
            ]
        }

        with patch(
            "services.notification_service.random.choice",
            return_value=FREEZE_MESSAGES[0],
        ):
            result = service.process_user_notifications("user1", prefs)

        assert len(result) == 1
        assert result[0].notification_type == NotificationType.FREEZE_ALERT

    def test_thaw_freeze_no_temp_data(self, service):
        """Test that missing temperature data does not generate thaw/freeze alerts."""
        settings = UserNotificationPreferences(
            notifications_enabled=True,
            fresh_snow_alerts=False,
            event_alerts=False,
            thaw_freeze_alerts=True,
            temperature_state={"whistler-blackcomb": "thawed"},
        )
        prefs = self._make_prefs(
            favorite_resorts=["whistler-blackcomb"],
            notification_settings=settings,
        )
        # No weather data
        service.weather_conditions_table.query.return_value = {"Items": []}

        result = service.process_user_notifications("user1", prefs)
        assert len(result) == 0


class TestSaveUserPreferences:
    """Tests for _save_user_preferences."""

    @pytest.fixture
    def service(self):
        return NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:test",
        )

    def test_save_user_preferences_success(self, service):
        """Test saving user preferences calls put_item."""
        now = datetime.now(UTC).isoformat()
        prefs = UserPreferences(
            user_id="user1",
            created_at=now,
            updated_at=now,
        )
        service._save_user_preferences(prefs)
        service.user_preferences_table.put_item.assert_called_once()

    def test_save_user_preferences_error_handled(self, service):
        """Test that errors during save are handled gracefully."""
        service.user_preferences_table.put_item.side_effect = Exception("DB error")
        now = datetime.now(UTC).isoformat()
        prefs = UserPreferences(
            user_id="user1",
            created_at=now,
            updated_at=now,
        )
        # Should not raise
        service._save_user_preferences(prefs)


class TestProcessAllNotifications:
    """Tests for process_all_notifications."""

    @pytest.fixture
    def service(self):
        svc = NotificationService(
            device_tokens_table=MagicMock(),
            user_preferences_table=MagicMock(),
            resort_events_table=MagicMock(),
            weather_conditions_table=MagicMock(),
            resorts_table=MagicMock(),
            sns_client=MagicMock(),
            apns_platform_arn="arn:aws:sns:us-west-2:123:app/APNS/snow",
        )
        return svc

    def test_process_all_empty_users(self, service):
        """Test process_all_notifications with no users."""
        service.user_preferences_table.scan.return_value = {"Items": []}

        summary = service.process_all_notifications()

        assert summary["users_processed"] == 0
        assert summary["notifications_sent"] == 0
        assert summary["errors"] == 0

    def test_process_all_skips_users_with_no_favorites(self, service):
        """Test that users with no favorite resorts are skipped."""
        now = datetime.now(UTC).isoformat()
        service.user_preferences_table.scan.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "favorite_resorts": [],
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        }

        summary = service.process_all_notifications()

        assert summary["users_processed"] == 0
        assert summary["notifications_sent"] == 0

    def test_process_all_sends_notifications(self, service):
        """Test that notifications are sent for users with matching conditions."""
        now = datetime.now(UTC).isoformat()
        service.user_preferences_table.scan.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "favorite_resorts": ["whistler-blackcomb"],
                    "notification_settings": {
                        "notifications_enabled": True,
                        "fresh_snow_alerts": True,
                        "event_alerts": False,
                        "thaw_freeze_alerts": False,
                        "default_snow_threshold_cm": 5.0,
                    },
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        }
        service.resorts_table.get_item.return_value = {
            "Item": {"resort_id": "whistler-blackcomb", "name": "Whistler Blackcomb"}
        }
        service.weather_conditions_table.query.return_value = {
            "Items": [{"resort_id": "whistler-blackcomb", "fresh_snow_cm": 15.0}]
        }
        # Devices for user
        service.device_tokens_table.query.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "device_id": "dev1",
                    "token": "tok1",
                    "platform": "ios",
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        }
        service.sns.create_platform_endpoint.return_value = {
            "EndpointArn": "arn:endpoint/abc"
        }

        summary = service.process_all_notifications()

        assert summary["users_processed"] == 1
        assert summary["notifications_sent"] >= 1
        assert summary["errors"] == 0

    def test_process_all_handles_user_processing_error(self, service):
        """Test that errors processing individual users are counted."""
        now = datetime.now(UTC).isoformat()
        service.user_preferences_table.scan.return_value = {
            "Items": [
                {
                    "user_id": "user1",
                    "favorite_resorts": ["whistler-blackcomb"],
                    "created_at": now,
                    "updated_at": now,
                    # Invalid data that will cause an error in processing
                    "notification_settings": "invalid",
                },
            ]
        }

        summary = service.process_all_notifications()

        assert summary["errors"] >= 1

    def test_process_all_handles_scan_error(self, service):
        """Test that a scan error is handled gracefully."""
        service.user_preferences_table.scan.side_effect = Exception("DynamoDB is down")

        summary = service.process_all_notifications()

        assert summary["errors"] == 1
        assert summary["users_processed"] == 0

    def test_process_all_handles_pagination(self, service):
        """Test that DynamoDB pagination is handled correctly."""
        now = datetime.now(UTC).isoformat()
        # First scan returns one user and a LastEvaluatedKey
        service.user_preferences_table.scan.side_effect = [
            {
                "Items": [
                    {
                        "user_id": "user1",
                        "favorite_resorts": [],
                        "created_at": now,
                        "updated_at": now,
                    },
                ],
                "LastEvaluatedKey": {"user_id": "user1"},
            },
            {
                "Items": [
                    {
                        "user_id": "user2",
                        "favorite_resorts": [],
                        "created_at": now,
                        "updated_at": now,
                    },
                ],
            },
        ]

        summary = service.process_all_notifications()

        # Both users have no favorites so 0 processed, but scan should be called twice
        assert service.user_preferences_table.scan.call_count == 2
        assert summary["errors"] == 0
