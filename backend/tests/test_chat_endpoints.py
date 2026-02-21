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
        svc.chat.assert_called_once_with("Follow up", "conv_existing", "test_user")

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

    def test_send_message_no_auth(self, mock_auth, client):
        """Should return 401 without auth header."""
        auth = MagicMock()
        auth.verify_access_token.side_effect = Exception("Invalid token")
        mock_auth.return_value = auth

        resp = client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code == 401

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
