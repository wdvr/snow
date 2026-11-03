"""Tests for chat stream auth and per-user daily limit (chat_stream_handler.chat_stream)."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from handlers import chat_stream_handler
from services.chat_rate_limit import AUTH_CHAT_DAILY_LIMIT, check_user_daily_limit

SECRET = "test-secret"


def _token(token_type="access", sub="user-1", exp_offset=3600):
    return jwt.encode(
        {"sub": sub, "type": token_type, "exp": int(time.time()) + exp_offset},
        SECRET,
        algorithm="HS256",
    )


def _events(response):
    return [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.delenv("CHAT_RATE_LIMIT_TABLE_NAME", raising=False)
    return TestClient(chat_stream_handler.app)


@pytest.fixture
def mock_stream():
    """Replace the Bedrock-backed handler with a canned reply."""

    def fake_handle(q, user_message, conversation_id, user_id, **kwargs):
        q.put(chat_stream_handler._sse({"type": "done", "user_id": user_id}))

    with patch.object(
        chat_stream_handler, "_handle_chat_stream", side_effect=fake_handle
    ) as m:
        yield m


class TestChatStreamAuth:
    def test_no_token_rejected(self, client, mock_stream):
        resp = client.post("/", json={"message": "hi"})
        assert resp.status_code == 401
        assert _events(resp)[0]["type"] == "error"
        mock_stream.assert_not_called()

    def test_invalid_token_rejected(self, client, mock_stream):
        resp = client.post(
            "/", json={"message": "hi"}, headers={"Authorization": "Bearer nope"}
        )
        assert resp.status_code == 401
        mock_stream.assert_not_called()

    def test_refresh_token_rejected(self, client, mock_stream):
        resp = client.post(
            "/",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {_token('refresh')}"},
        )
        assert resp.status_code == 401
        mock_stream.assert_not_called()

    def test_expired_token_rejected(self, client, mock_stream):
        resp = client.post(
            "/",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {_token(exp_offset=-60)}"},
        )
        assert resp.status_code == 401
        mock_stream.assert_not_called()

    def test_access_token_streams(self, client, mock_stream):
        resp = client.post(
            "/",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {_token(sub='user-42')}"},
        )
        assert resp.status_code == 200
        assert _events(resp) == [{"type": "done", "user_id": "user-42"}]
        assert mock_stream.call_args[0][3] == "user-42"

    def test_daily_limit_enforced(self, client, mock_stream, monkeypatch):
        monkeypatch.setenv("CHAT_RATE_LIMIT_TABLE_NAME", "rate-limit")
        now = int(time.time())
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {"timestamps": [now - 60] * AUTH_CHAT_DAILY_LIMIT}
        }
        dynamodb = MagicMock()
        dynamodb.Table.return_value = table
        with patch.object(chat_stream_handler, "_get_dynamodb", return_value=dynamodb):
            resp = client.post(
                "/",
                json={"message": "hi"},
                headers={"Authorization": f"Bearer {_token()}"},
            )
        assert resp.status_code == 429
        assert "limit" in _events(resp)[0]["message"].lower()
        mock_stream.assert_not_called()
        table.put_item.assert_not_called()

    def test_limit_check_failure_fails_open(self, client, mock_stream, monkeypatch):
        monkeypatch.setenv("CHAT_RATE_LIMIT_TABLE_NAME", "rate-limit")
        dynamodb = MagicMock()
        dynamodb.Table.return_value.get_item.side_effect = RuntimeError("ddb down")
        with patch.object(chat_stream_handler, "_get_dynamodb", return_value=dynamodb):
            resp = client.post(
                "/",
                json={"message": "hi"},
                headers={"Authorization": f"Bearer {_token()}"},
            )
        assert resp.status_code == 200
        mock_stream.assert_called_once()


class TestCheckUserDailyLimit:
    def test_first_message(self):
        table = MagicMock()
        table.get_item.return_value = {}
        assert check_user_daily_limit(table, "u") == (True, AUTH_CHAT_DAILY_LIMIT - 1)
        item = table.put_item.call_args[1]["Item"]
        assert item["ip_address"] == "user_u"
        assert item["message_count"] == 1

    def test_old_timestamps_pruned(self):
        now = int(time.time())
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {"timestamps": [now - 25 * 3600] * AUTH_CHAT_DAILY_LIMIT}
        }
        allowed, remaining = check_user_daily_limit(table, "u")
        assert allowed is True
        assert remaining == AUTH_CHAT_DAILY_LIMIT - 1
        assert len(table.put_item.call_args[1]["Item"]["timestamps"]) == 1
