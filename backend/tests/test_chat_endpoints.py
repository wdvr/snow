"""Tests for chat API endpoints.

Tests the FastAPI routes for chat functionality, including authentication
requirements and response formatting.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from models.chat import ChatMessage, ChatResponse, ConversationSummary
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


# ---------------------------------------------------------------------------
# POST /api/v1/chat
# ---------------------------------------------------------------------------


@patch("handlers.api_handler.get_auth_service")
class TestSendChatMessage:
    """Tests for the POST /api/v1/chat endpoint."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_chat_service")
    def test_send_message_success(self, mock_chat_svc, mock_auth, client):
        """Should return chat response on success."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.chat.return_value = ChatResponse(
            conversation_id="conv_abc123",
            response="Big White has excellent conditions!",
            message_id="01HXYZ",
        )
        mock_chat_svc.return_value = svc

        resp = client.post(
            "/api/v1/chat",
            json={"message": "How is Big White?"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv_abc123"
        assert data["response"] == "Big White has excellent conditions!"
        assert data["message_id"] == "01HXYZ"

    @patch("handlers.api_handler.get_chat_service")
    def test_send_message_with_conversation_id(self, mock_chat_svc, mock_auth, client):
        """Should pass conversation_id to service."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.chat.return_value = ChatResponse(
            conversation_id="conv_existing",
            response="Response",
            message_id="01ABC",
        )
        mock_chat_svc.return_value = svc

        resp = client.post(
            "/api/v1/chat",
            json={"message": "Follow up", "conversation_id": "conv_existing"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        svc.chat.assert_called_once_with(
            "Follow up", "conv_existing", "test_user", user_lat=None, user_lon=None
        )

    @patch("handlers.api_handler.get_chat_service")
    def test_send_empty_message_rejected(self, mock_chat_svc, mock_auth, client):
        """Empty message should be rejected by validation."""
        self._mock_auth(mock_auth)

        resp = client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers=_auth_header(),
        )
        assert resp.status_code == 422  # Validation error

    @patch("handlers.api_handler._check_anonymous_chat_limit")
    @patch("handlers.api_handler._get_remaining_anonymous_messages")
    @patch("handlers.api_handler.get_chat_service")
    def test_send_message_no_auth_anonymous(
        self, mock_chat_svc, mock_remaining, mock_limit, mock_auth, client
    ):
        """Should allow anonymous chat without auth header."""
        # Auth returns None for anonymous
        mock_auth.return_value = MagicMock()
        mock_limit.return_value = True
        mock_remaining.return_value = 4

        svc = MagicMock()
        svc.chat.return_value = ChatResponse(
            conversation_id="conv_anon",
            response="Whistler is great!",
            message_id="01ANON",
        )
        mock_chat_svc.return_value = svc

        resp = client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv_anon"
        assert data["remaining_messages"] == 4
        # Verify service called with anon user ID
        call_args = svc.chat.call_args
        assert call_args[0][2].startswith("anon_")

    @patch("handlers.api_handler._check_anonymous_chat_limit")
    def test_send_message_anonymous_rate_limited(self, mock_limit, mock_auth, client):
        """Should return 429 when anonymous rate limit exceeded."""
        mock_auth.return_value = MagicMock()
        mock_limit.return_value = False

        resp = client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code == 429
        assert "Chat limit reached" in resp.json()["detail"]

    @patch("handlers.api_handler.get_chat_service")
    def test_send_message_service_error(self, mock_chat_svc, mock_auth, client):
        """Should return 500 on service error."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.chat.side_effect = Exception("Bedrock timeout")
        mock_chat_svc.return_value = svc

        resp = client.post(
            "/api/v1/chat",
            json={"message": "Hello"},
            headers=_auth_header(),
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/chat/conversations
# ---------------------------------------------------------------------------


@patch("handlers.api_handler.get_auth_service")
class TestListConversations:
    """Tests for the GET /api/v1/chat/conversations endpoint."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_chat_service")
    def test_list_conversations_success(self, mock_chat_svc, mock_auth, client):
        """Should return list of conversations."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.list_conversations.return_value = [
            ConversationSummary(
                conversation_id="conv_1",
                title="Best powder",
                last_message_at="2026-02-21T10:00:00Z",
                message_count=4,
            ),
            ConversationSummary(
                conversation_id="conv_2",
                title="Whistler conditions",
                last_message_at="2026-02-20T08:00:00Z",
                message_count=2,
            ),
        ]
        mock_chat_svc.return_value = svc

        resp = client.get("/api/v1/chat/conversations", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["conversations"]) == 2
        assert data["conversations"][0]["conversation_id"] == "conv_1"
        assert data["conversations"][0]["title"] == "Best powder"

    @patch("handlers.api_handler.get_chat_service")
    def test_list_conversations_empty(self, mock_chat_svc, mock_auth, client):
        """Should return empty list when no conversations."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.list_conversations.return_value = []
        mock_chat_svc.return_value = svc

        resp = client.get("/api/v1/chat/conversations", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["conversations"] == []

    def test_list_conversations_no_auth(self, mock_auth, client):
        """Should return 401 without auth header."""
        auth = MagicMock()
        auth.verify_access_token.side_effect = Exception("Invalid")
        mock_auth.return_value = auth

        resp = client.get("/api/v1/chat/conversations")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@patch("handlers.api_handler.get_auth_service")
class TestGetConversation:
    """Tests for the GET /api/v1/chat/conversations/{id} endpoint."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_chat_service")
    def test_get_conversation_success(self, mock_chat_svc, mock_auth, client):
        """Should return conversation messages."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_conversation.return_value = [
            ChatMessage(
                role="user",
                content="How is Big White?",
                message_id="01A",
                created_at="2026-02-20T10:00:00Z",
            ),
            ChatMessage(
                role="assistant",
                content="Big White has great conditions!",
                message_id="01B",
                created_at="2026-02-20T10:01:00Z",
            ),
        ]
        mock_chat_svc.return_value = svc

        resp = client.get("/api/v1/chat/conversations/conv_1", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv_1"
        assert data["count"] == 2
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"

    @patch("handlers.api_handler.get_chat_service")
    def test_get_conversation_not_found(self, mock_chat_svc, mock_auth, client):
        """Should return 404 for missing conversation."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.get_conversation.side_effect = ValueError("Conversation not found")
        mock_chat_svc.return_value = svc

        resp = client.get(
            "/api/v1/chat/conversations/conv_nonexistent",
            headers=_auth_header(),
        )
        assert resp.status_code == 404

    def test_get_conversation_no_auth(self, mock_auth, client):
        """Should return 401 without auth header."""
        auth = MagicMock()
        auth.verify_access_token.side_effect = Exception("Invalid")
        mock_auth.return_value = auth

        resp = client.get("/api/v1/chat/conversations/conv_1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/v1/chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@patch("handlers.api_handler.get_auth_service")
class TestDeleteConversation:
    """Tests for the DELETE /api/v1/chat/conversations/{id} endpoint."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_chat_service")
    def test_delete_conversation_success(self, mock_chat_svc, mock_auth, client):
        """Should return status deleted."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.delete_conversation.return_value = None
        mock_chat_svc.return_value = svc

        resp = client.delete(
            "/api/v1/chat/conversations/conv_1", headers=_auth_header()
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}

    @patch("handlers.api_handler.get_chat_service")
    def test_delete_conversation_not_found(self, mock_chat_svc, mock_auth, client):
        """Should return 404 for missing conversation."""
        self._mock_auth(mock_auth)
        svc = MagicMock()
        svc.delete_conversation.side_effect = ValueError("Conversation not found")
        mock_chat_svc.return_value = svc

        resp = client.delete(
            "/api/v1/chat/conversations/conv_nonexistent",
            headers=_auth_header(),
        )
        assert resp.status_code == 404

    def test_delete_conversation_no_auth(self, mock_auth, client):
        """Should return 401 without auth header."""
        auth = MagicMock()
        auth.verify_access_token.side_effect = Exception("Invalid")
        mock_auth.return_value = auth

        resp = client.delete("/api/v1/chat/conversations/conv_1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Conversation ownership verification
# ---------------------------------------------------------------------------


@patch("handlers.api_handler.get_auth_service")
class TestConversationOwnership:
    """Tests that verify conversation ownership is enforced."""

    def _mock_auth(self, mock_auth_svc, user_id="test_user"):
        auth = MagicMock()
        auth.verify_access_token.return_value = user_id
        mock_auth_svc.return_value = auth

    @patch("handlers.api_handler.get_chat_service")
    def test_get_other_users_conversation(self, mock_chat_svc, mock_auth, client):
        """Should not be able to access another user's conversation."""
        self._mock_auth(mock_auth, user_id="user_a")
        svc = MagicMock()
        svc.get_conversation.side_effect = ValueError("Conversation not found")
        mock_chat_svc.return_value = svc

        resp = client.get(
            "/api/v1/chat/conversations/conv_user_b",
            headers=_auth_header("user_a"),
        )
        assert resp.status_code == 404

    @patch("handlers.api_handler.get_chat_service")
    def test_delete_other_users_conversation(self, mock_chat_svc, mock_auth, client):
        """Should not be able to delete another user's conversation."""
        self._mock_auth(mock_auth, user_id="user_a")
        svc = MagicMock()
        svc.delete_conversation.side_effect = ValueError("Conversation not found")
        mock_chat_svc.return_value = svc

        resp = client.delete(
            "/api/v1/chat/conversations/conv_user_b",
            headers=_auth_header("user_a"),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Anonymous chat rate limiting
# ---------------------------------------------------------------------------


class TestAnonymousChatRateLimit:
    """Tests for anonymous IP-based chat rate limiting."""

    @patch("handlers.api_handler.get_auth_service")
    @patch("handlers.api_handler._check_anonymous_chat_limit")
    @patch("handlers.api_handler._get_remaining_anonymous_messages")
    @patch("handlers.api_handler.get_chat_service")
    def test_anonymous_chat_includes_remaining_messages(
        self, mock_chat_svc, mock_remaining, mock_limit, mock_auth, client
    ):
        """Anonymous response should include remaining_messages field."""
        mock_auth.return_value = MagicMock()
        mock_limit.return_value = True
        mock_remaining.return_value = 3

        svc = MagicMock()
        svc.chat.return_value = ChatResponse(
            conversation_id="conv_1",
            response="Great snow!",
            message_id="01X",
        )
        mock_chat_svc.return_value = svc

        resp = client.post("/api/v1/chat", json={"message": "How is Whistler?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_messages"] == 3

    @patch("handlers.api_handler.get_auth_service")
    @patch("handlers.api_handler.get_chat_service")
    def test_authenticated_chat_no_remaining_messages(
        self, mock_chat_svc, mock_auth, client
    ):
        """Authenticated response should not include remaining_messages."""
        auth = MagicMock()
        auth.verify_access_token.return_value = "test_user"
        mock_auth.return_value = auth

        svc = MagicMock()
        svc.chat.return_value = ChatResponse(
            conversation_id="conv_1",
            response="Great snow!",
            message_id="01X",
        )
        mock_chat_svc.return_value = svc

        resp = client.post(
            "/api/v1/chat",
            json={"message": "How is Whistler?"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("remaining_messages") is None

    @patch("handlers.api_handler.get_auth_service")
    @patch("handlers.api_handler._check_anonymous_chat_limit")
    def test_anonymous_rate_limit_returns_429(self, mock_limit, mock_auth, client):
        """Should return 429 with helpful message when limit reached."""
        mock_auth.return_value = MagicMock()
        mock_limit.return_value = False

        resp = client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code == 429
        data = resp.json()
        assert "Sign in" in data["detail"]
        assert "try again later" in data["detail"]


# ---------------------------------------------------------------------------
# Rate limit helper unit tests
# ---------------------------------------------------------------------------


class TestCheckAnonymousChatLimit:
    """Tests for the _check_anonymous_chat_limit helper."""

    @patch.dict("os.environ", {"CHAT_RATE_LIMIT_TABLE_NAME": ""}, clear=False)
    def test_no_table_configured_allows_request(self):
        """Should allow request when table not configured."""
        from handlers.api_handler import _check_anonymous_chat_limit

        assert _check_anonymous_chat_limit("1.2.3.4") is True

    @patch("handlers.api_handler.boto3")
    @patch.dict(
        "os.environ",
        {"CHAT_RATE_LIMIT_TABLE_NAME": "test-rate-limit"},
        clear=False,
    )
    def test_first_message_allowed(self, mock_boto3):
        """Should allow first message from a new IP."""
        from handlers.api_handler import _check_anonymous_chat_limit

        table = MagicMock()
        table.get_item.return_value = {}  # No existing item
        mock_boto3.resource.return_value.Table.return_value = table

        assert _check_anonymous_chat_limit("1.2.3.4") is True
        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["ip_address"] == "1.2.3.4"
        assert item["message_count"] == 1

    @patch("handlers.api_handler.boto3")
    @patch.dict(
        "os.environ",
        {"CHAT_RATE_LIMIT_TABLE_NAME": "test-rate-limit"},
        clear=False,
    )
    def test_under_limit_allowed(self, mock_boto3):
        """Should allow when under the limit."""
        import time

        from handlers.api_handler import _check_anonymous_chat_limit

        now = int(time.time())
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {
                "ip_address": "1.2.3.4",
                "timestamps": [now - 100, now - 50],
                "message_count": 2,
            }
        }
        mock_boto3.resource.return_value.Table.return_value = table

        assert _check_anonymous_chat_limit("1.2.3.4") is True

    @patch("handlers.api_handler.boto3")
    @patch.dict(
        "os.environ",
        {"CHAT_RATE_LIMIT_TABLE_NAME": "test-rate-limit"},
        clear=False,
    )
    def test_at_limit_rejected(self, mock_boto3):
        """Should reject when at the limit."""
        import time

        from handlers.api_handler import _check_anonymous_chat_limit

        now = int(time.time())
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {
                "ip_address": "1.2.3.4",
                "timestamps": [now - 500, now - 400, now - 300, now - 200, now - 100],
                "message_count": 5,
            }
        }
        mock_boto3.resource.return_value.Table.return_value = table

        assert _check_anonymous_chat_limit("1.2.3.4") is False

    @patch("handlers.api_handler.boto3")
    @patch.dict(
        "os.environ",
        {"CHAT_RATE_LIMIT_TABLE_NAME": "test-rate-limit"},
        clear=False,
    )
    def test_expired_timestamps_not_counted(self, mock_boto3):
        """Should not count timestamps outside the window."""
        import time

        from handlers.api_handler import _check_anonymous_chat_limit

        now = int(time.time())
        old = now - (7 * 3600)  # 7 hours ago (outside 6h window)
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {
                "ip_address": "1.2.3.4",
                "timestamps": [old, old, old, old, old],  # All expired
                "message_count": 5,
            }
        }
        mock_boto3.resource.return_value.Table.return_value = table

        assert _check_anonymous_chat_limit("1.2.3.4") is True

    @patch("handlers.api_handler.boto3")
    @patch.dict(
        "os.environ",
        {"CHAT_RATE_LIMIT_TABLE_NAME": "test-rate-limit"},
        clear=False,
    )
    def test_dynamo_error_fails_open(self, mock_boto3):
        """Should allow request if DynamoDB errors (fail open)."""
        from handlers.api_handler import _check_anonymous_chat_limit

        table = MagicMock()
        table.get_item.side_effect = Exception("DynamoDB timeout")
        mock_boto3.resource.return_value.Table.return_value = table

        assert _check_anonymous_chat_limit("1.2.3.4") is True


# ---------------------------------------------------------------------------
# GET /api/v1/chat/suggestions
# ---------------------------------------------------------------------------


class TestGetChatSuggestions:
    """Tests for the GET /api/v1/chat/suggestions endpoint."""

    @patch("handlers.api_handler.get_dynamodb")
    def test_returns_suggestions_from_dynamodb(self, mock_dynamodb, client):
        """Should return active suggestions from DynamoDB sorted by priority."""
        table = MagicMock()
        table.scan.return_value = {
            "Items": [
                {
                    "suggestion_id": "s2",
                    "text": "Which resort has the most fresh snow?",
                    "category": "general",
                    "priority": 2,
                    "active": True,
                },
                {
                    "suggestion_id": "s1",
                    "text": "What are the snow conditions like today?",
                    "category": "general",
                    "priority": 1,
                    "active": True,
                },
            ]
        }
        mock_dynamodb.return_value.Table.return_value = table

        resp = client.get("/api/v1/chat/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggestions"]) == 2
        # Should be sorted by priority
        assert data["suggestions"][0]["id"] == "s1"
        assert data["suggestions"][1]["id"] == "s2"
        assert (
            data["suggestions"][0]["text"] == "What are the snow conditions like today?"
        )

    @patch("handlers.api_handler.get_dynamodb")
    def test_returns_defaults_when_table_empty(self, mock_dynamodb, client):
        """Should return hardcoded defaults when no items in table."""
        table = MagicMock()
        table.scan.return_value = {"Items": []}
        mock_dynamodb.return_value.Table.return_value = table

        resp = client.get("/api/v1/chat/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggestions"]) == 16
        assert data["suggestions"][0]["id"] == "s1"

    @patch("handlers.api_handler.get_dynamodb")
    def test_returns_defaults_on_dynamodb_error(self, mock_dynamodb, client):
        """Should return hardcoded defaults when DynamoDB errors."""
        table = MagicMock()
        table.scan.side_effect = Exception("DynamoDB timeout")
        mock_dynamodb.return_value.Table.return_value = table

        resp = client.get("/api/v1/chat/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggestions"]) == 16

    def test_no_auth_required(self, client):
        """Should not require authentication."""
        # The endpoint uses get_dynamodb which will fail in test context,
        # but it should still return 200 with defaults (not 401).
        resp = client.get("/api/v1/chat/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        # Falls back to defaults since no real DynamoDB in test
        assert len(data["suggestions"]) == 16

    @patch("handlers.api_handler.get_dynamodb")
    def test_suggestion_has_expected_fields(self, mock_dynamodb, client):
        """Each suggestion should have id, text, and category fields."""
        table = MagicMock()
        table.scan.return_value = {
            "Items": [
                {
                    "suggestion_id": "s5",
                    "text": "How's the powder at {resort_name} today?",
                    "category": "favorites_aware",
                    "priority": 5,
                    "active": True,
                }
            ]
        }
        mock_dynamodb.return_value.Table.return_value = table

        resp = client.get("/api/v1/chat/suggestions")
        data = resp.json()
        suggestion = data["suggestions"][0]
        assert "id" in suggestion
        assert "text" in suggestion
        assert "category" in suggestion
        assert suggestion["category"] == "favorites_aware"

    @patch("handlers.api_handler.get_dynamodb")
    def test_default_suggestions_include_all_categories(self, mock_dynamodb, client):
        """Default suggestions should include general, location_aware, and favorites_aware."""
        table = MagicMock()
        table.scan.return_value = {"Items": []}
        mock_dynamodb.return_value.Table.return_value = table

        resp = client.get("/api/v1/chat/suggestions")
        data = resp.json()
        categories = {s["category"] for s in data["suggestions"]}
        assert "general" in categories
        assert "location_aware" in categories
        assert "favorites_aware" in categories


class TestGetClientIp:
    """Tests for the _get_client_ip helper."""

    def test_x_forwarded_for(self):
        """Should extract first IP from X-Forwarded-For header."""
        from handlers.api_handler import _get_client_ip

        request = MagicMock()
        request.headers.get.return_value = "1.2.3.4, 5.6.7.8"
        result = _get_client_ip(request)
        assert result == "1.2.3.4"

    def test_single_x_forwarded_for(self):
        """Should handle single IP in X-Forwarded-For."""
        from handlers.api_handler import _get_client_ip

        request = MagicMock()
        request.headers.get.return_value = "1.2.3.4"
        result = _get_client_ip(request)
        assert result == "1.2.3.4"

    def test_no_forwarded_header(self):
        """Should fall back to client host."""
        from handlers.api_handler import _get_client_ip

        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "10.0.0.1"
        result = _get_client_ip(request)
        assert result == "10.0.0.1"

    def test_no_client(self):
        """Should return 'unknown' if no client info."""
        from handlers.api_handler import _get_client_ip

        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None
        result = _get_client_ip(request)
        assert result == "unknown"
