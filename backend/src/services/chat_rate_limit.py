"""Per-user daily chat rate limiting.

Shared by the API chat endpoint (handlers/api_handler.py) and the streaming
chat Lambda (handlers/chat_stream_handler.py) so both paths enforce the same
budget against the same DynamoDB table.
"""

import logging
import time

logger = logging.getLogger(__name__)

AUTH_CHAT_DAILY_LIMIT = 100  # Authenticated users: 100 messages per day
AUTH_CHAT_WINDOW_SECONDS = 24 * 3600


def check_user_daily_limit(table, user_id: str) -> tuple[bool, int]:
    """Record a chat message for user_id and check the 24h sliding window.

    Items are keyed as ``user_<id>`` in the ``ip_address`` hash key of the
    chat rate limit table.

    Returns (allowed, remaining_messages). Raises on DynamoDB errors so the
    caller can decide whether to fail open or closed.
    """
    now = int(time.time())
    window_start = now - AUTH_CHAT_WINDOW_SECONDS
    expires_at = now + AUTH_CHAT_WINDOW_SECONDS

    key = f"user_{user_id}"
    response = table.get_item(Key={"ip_address": key})
    item = response.get("Item")

    recent = []
    if item:
        timestamps = item.get("timestamps", [])
        recent = [t for t in timestamps if t > window_start]
        if len(recent) >= AUTH_CHAT_DAILY_LIMIT:
            return False, 0

    recent.append(now)
    table.put_item(
        Item={
            "ip_address": key,
            "timestamps": recent,
            "message_count": len(recent),
            "expires_at": expires_at,
        }
    )
    return True, max(0, AUTH_CHAT_DAILY_LIMIT - len(recent))
