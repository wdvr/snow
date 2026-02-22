"""Tests for the ChatService."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from models.chat import ChatResponse, ConversationSummary
from models.resort import ElevationLevel, ElevationPoint, Resort
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.chat_service import (
    MAX_TOOL_ITERATIONS,
    MESSAGE_TTL_DAYS,
    RESORT_ALIASES,
    SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    ChatService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_chat_table():
    """Create a mock DynamoDB table for chat messages."""
    table = Mock()
    table.put_item.return_value = {}
    table.query.return_value = {"Items": []}
    table.batch_writer.return_value.__enter__ = Mock(return_value=Mock())
    table.batch_writer.return_value.__exit__ = Mock(return_value=False)
    return table


@pytest.fixture
def mock_resort_service():
    """Create a mock ResortService."""
    service = Mock()
    service.get_resort.return_value = Resort(
        resort_id="big-white",
        name="Big White Ski Resort",
        country="CA",
        region="BC",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=1800,
                elevation_feet=5906,
                latitude=49.72,
                longitude=-118.93,
            ),
        ],
        timezone="America/Vancouver",
    )
    service.search_resorts.return_value = [
        Resort(
            resort_id="big-white",
            name="Big White Ski Resort",
            country="CA",
            region="BC",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.MID,
                    elevation_meters=1800,
                    elevation_feet=5906,
                    latitude=49.72,
                    longitude=-118.93,
                ),
            ],
            timezone="America/Vancouver",
        )
    ]
    service.get_nearby_resorts.return_value = []
    return service


@pytest.fixture
def mock_weather_service():
    """Create a mock WeatherService."""
    service = Mock()
    service.get_conditions_for_resort.return_value = [
        WeatherCondition(
            resort_id="big-white",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-5.0,
            min_temp_celsius=-10.0,
            max_temp_celsius=-2.0,
            snowfall_24h_cm=10.0,
            snowfall_48h_cm=20.0,
            snowfall_72h_cm=30.0,
            predicted_snow_72h_cm=15.0,
            snowfall_after_freeze_cm=10.0,
            snow_quality=SnowQuality.EXCELLENT,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=10.0,
            data_source="test",
            source_confidence=ConfidenceLevel.HIGH,
        )
    ]
    return service


@pytest.fixture
def mock_quality_service():
    """Create a mock SnowQualityService."""
    return Mock()


@pytest.fixture
def mock_recommendation_service():
    """Create a mock RecommendationService."""
    service = Mock()
    service.get_best_conditions_globally.return_value = []
    return service


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client with a simple text response."""
    client = Mock()
    # Default response: simple text, no tool use
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": "Big White has excellent conditions today!"}]
            }
        },
        "stopReason": "end_turn",
    }
    return client


@pytest.fixture
def mock_condition_report_service():
    """Create a mock ConditionReportService."""
    service = Mock()
    service.get_reports_for_resort.return_value = []
    return service


@pytest.fixture
def chat_service(
    mock_chat_table,
    mock_resort_service,
    mock_weather_service,
    mock_quality_service,
    mock_recommendation_service,
    mock_condition_report_service,
    mock_bedrock_client,
):
    """Create a ChatService with all mocked dependencies."""
    service = ChatService(
        chat_table=mock_chat_table,
        resort_service=mock_resort_service,
        weather_service=mock_weather_service,
        snow_quality_service=mock_quality_service,
        recommendation_service=mock_recommendation_service,
        condition_report_service=mock_condition_report_service,
    )
    service.bedrock = mock_bedrock_client
    return service


# ---------------------------------------------------------------------------
# ChatService.chat() tests
# ---------------------------------------------------------------------------


class TestChat:
    """Test cases for ChatService.chat()."""

    def test_new_conversation_generates_id(self, chat_service):
        """New conversation should generate a conv_ prefixed ID."""
        result = chat_service.chat("Hello", None, "user_123")
        assert result.conversation_id.startswith("conv_")
        assert len(result.conversation_id) > 5

    def test_existing_conversation_reuses_id(self, chat_service):
        """Existing conversation ID should be preserved."""
        result = chat_service.chat("Hello", "conv_existing123", "user_123")
        assert result.conversation_id == "conv_existing123"

    def test_returns_chat_response(self, chat_service):
        """Should return a ChatResponse with all fields."""
        result = chat_service.chat("How is Big White?", None, "user_123")
        assert isinstance(result, ChatResponse)
        assert result.response == "Big White has excellent conditions today!"
        assert result.message_id  # Should have a ULID

    def test_saves_user_message(self, chat_service, mock_chat_table):
        """User message should be saved to DynamoDB."""
        chat_service.chat("Hello", None, "user_123")

        # Should have been called twice: once for user, once for assistant
        assert mock_chat_table.put_item.call_count == 2

        # First call is user message
        user_item = mock_chat_table.put_item.call_args_list[0][1]["Item"]
        assert user_item["role"] == "user"
        assert user_item["content"] == "Hello"
        assert user_item["user_id"] == "user_123"

    def test_saves_assistant_message(self, chat_service, mock_chat_table):
        """Assistant message should be saved to DynamoDB."""
        chat_service.chat("Hello", None, "user_123")

        # Second call is assistant message
        assistant_item = mock_chat_table.put_item.call_args_list[1][1]["Item"]
        assert assistant_item["role"] == "assistant"
        assert assistant_item["content"] == "Big White has excellent conditions today!"

    def test_message_has_ttl(self, chat_service, mock_chat_table):
        """Messages should have an expires_at TTL field."""
        chat_service.chat("Hello", None, "user_123")

        user_item = mock_chat_table.put_item.call_args_list[0][1]["Item"]
        assert "expires_at" in user_item
        # TTL should be roughly 30 days from now
        expected_ttl = int(
            (datetime.now(UTC) + timedelta(days=MESSAGE_TTL_DAYS)).timestamp()
        )
        assert abs(user_item["expires_at"] - expected_ttl) < 60  # within 60 seconds

    def test_first_message_generates_title(self, chat_service, mock_chat_table):
        """First message in a new conversation should generate a title."""
        mock_chat_table.query.return_value = {"Items": []}  # No history
        chat_service.chat("What are conditions at Whistler?", None, "user_123")

        user_item = mock_chat_table.put_item.call_args_list[0][1]["Item"]
        assert "title" in user_item
        assert user_item["title"] == "What are conditions at Whistler?"

    def test_subsequent_message_no_title(self, chat_service, mock_chat_table):
        """Subsequent messages should not have a title."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "role": "user",
                    "content": "Hello",
                    "message_id": "01HXY",
                    "user_id": "user_123",
                    "created_at": "2026-02-20T10:00:00Z",
                }
            ]
        }
        chat_service.chat("Follow up question", "conv_abc", "user_123")

        user_item = mock_chat_table.put_item.call_args_list[0][1]["Item"]
        assert "title" not in user_item

    def test_bedrock_called_with_correct_params(
        self, chat_service, mock_bedrock_client
    ):
        """Bedrock converse should be called with system prompt and tools."""
        chat_service.chat("Hello", None, "user_123")

        mock_bedrock_client.converse.assert_called_once()
        call_kwargs = mock_bedrock_client.converse.call_args[1]
        assert call_kwargs["modelId"] == "us.anthropic.claude-sonnet-4-6"
        assert call_kwargs["system"] == [{"text": SYSTEM_PROMPT}]
        assert call_kwargs["toolConfig"]["tools"] == TOOL_DEFINITIONS
        assert call_kwargs["inferenceConfig"]["maxTokens"] == 1024
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.3

    def test_conversation_history_loaded(
        self, chat_service, mock_chat_table, mock_bedrock_client
    ):
        """Previous messages should be included in Bedrock call."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "role": "assistant",
                    "content": "I can help with that!",
                    "message_id": "01HXY2",
                    "user_id": "user_123",
                    "created_at": "2026-02-20T10:01:00Z",
                },
                {
                    "role": "user",
                    "content": "How is Big White?",
                    "message_id": "01HXY1",
                    "user_id": "user_123",
                    "created_at": "2026-02-20T10:00:00Z",
                },
            ]
        }

        chat_service.chat("What about Whistler?", "conv_abc", "user_123")

        call_kwargs = mock_bedrock_client.converse.call_args[1]
        messages = call_kwargs["messages"]
        # Should have: history (2 messages reversed) + new user message
        assert len(messages) == 3
        assert messages[0]["content"][0]["text"] == "How is Big White?"
        assert messages[1]["content"][0]["text"] == "I can help with that!"
        assert messages[2]["content"][0]["text"] == "What about Whistler?"


# ---------------------------------------------------------------------------
# Tool execution tests
# ---------------------------------------------------------------------------


class TestToolExecution:
    """Test cases for tool execution in ChatService."""

    def test_tool_use_loop(self, chat_service, mock_bedrock_client):
        """Should handle tool_use stop reason and re-call Bedrock."""
        # First call returns tool_use, second returns final text
        mock_bedrock_client.converse.side_effect = [
            {
                "output": {
                    "message": {
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool_1",
                                    "name": "get_resort_conditions",
                                    "input": {"resort_id": "big-white"},
                                }
                            }
                        ]
                    }
                },
                "stopReason": "tool_use",
            },
            {
                "output": {
                    "message": {"content": [{"text": "Big White has 10cm fresh snow!"}]}
                },
                "stopReason": "end_turn",
            },
        ]

        result = chat_service.chat("How is Big White?", None, "user_123")
        assert result.response == "Big White has 10cm fresh snow!"
        assert mock_bedrock_client.converse.call_count == 2

    def test_tool_result_included_in_messages(
        self, chat_service, mock_bedrock_client, mock_weather_service
    ):
        """Tool results should be passed back as user message."""
        mock_bedrock_client.converse.side_effect = [
            {
                "output": {
                    "message": {
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool_1",
                                    "name": "get_resort_conditions",
                                    "input": {"resort_id": "big-white"},
                                }
                            }
                        ]
                    }
                },
                "stopReason": "tool_use",
            },
            {
                "output": {"message": {"content": [{"text": "Conditions are great!"}]}},
                "stopReason": "end_turn",
            },
        ]

        chat_service.chat("Conditions?", None, "user_123")

        # The second call should include the tool result
        second_call = mock_bedrock_client.converse.call_args_list[1]
        messages = second_call[1]["messages"]

        # Should include: user msg, assistant tool_use, user tool_result
        assert len(messages) == 3
        # Last message should be tool result
        last_msg = messages[-1]
        assert last_msg["role"] == "user"
        assert "toolResult" in last_msg["content"][0]

    def test_max_iterations_respected(self, chat_service, mock_bedrock_client):
        """Should stop after MAX_TOOL_ITERATIONS to prevent infinite loops."""
        # Always return tool_use
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool_1",
                                "name": "search_resorts",
                                "input": {"query": "snow"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        result = chat_service.chat("Find snow", None, "user_123")
        assert mock_bedrock_client.converse.call_count == MAX_TOOL_ITERATIONS
        assert "trouble processing" in result.response

    def test_tool_error_handled_gracefully(
        self, chat_service, mock_bedrock_client, mock_weather_service
    ):
        """Tool execution errors should return error result, not crash."""
        mock_weather_service.get_conditions_for_resort.side_effect = Exception(
            "DB error"
        )

        mock_bedrock_client.converse.side_effect = [
            {
                "output": {
                    "message": {
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool_1",
                                    "name": "get_resort_conditions",
                                    "input": {"resort_id": "big-white"},
                                }
                            }
                        ]
                    }
                },
                "stopReason": "tool_use",
            },
            {
                "output": {
                    "message": {
                        "content": [{"text": "Sorry, I couldn't fetch the conditions."}]
                    }
                },
                "stopReason": "end_turn",
            },
        ]

        result = chat_service.chat("Check Big White", None, "user_123")
        # Should still get a response (model handles the error gracefully)
        assert result.response == "Sorry, I couldn't fetch the conditions."

    def test_search_resorts_tool(self, chat_service, mock_resort_service):
        """search_resorts tool should call resort_service.search_resorts."""
        result = chat_service._execute_tool("search_resorts", {"query": "white"})
        mock_resort_service.search_resorts.assert_called_once_with("white")
        assert result["count"] == 1
        assert result["results"][0]["resort_id"] == "big-white"

    def test_get_resort_info_tool(self, chat_service, mock_resort_service):
        """get_resort_info tool should return resort metadata."""
        result = chat_service._execute_tool(
            "get_resort_info", {"resort_id": "big-white"}
        )
        assert result["resort_id"] == "big-white"
        assert result["name"] == "Big White Ski Resort"
        assert "elevation_points" in result

    def test_get_resort_info_not_found(self, chat_service, mock_resort_service):
        """get_resort_info should return error for unknown resort."""
        mock_resort_service.get_resort.return_value = None
        result = chat_service._execute_tool(
            "get_resort_info", {"resort_id": "nonexistent"}
        )
        assert "error" in result

    def test_get_resort_conditions_tool(self, chat_service, mock_weather_service):
        """get_resort_conditions tool should return conditions data."""
        result = chat_service._execute_tool(
            "get_resort_conditions", {"resort_id": "big-white"}
        )
        assert result["resort_id"] == "big-white"
        assert "mid" in result["elevations"]
        assert result["elevations"]["mid"]["temperature_celsius"] == -5.0

    def test_get_resort_conditions_no_data(self, chat_service, mock_weather_service):
        """get_resort_conditions should return error when no data."""
        mock_weather_service.get_conditions_for_resort.return_value = []
        result = chat_service._execute_tool(
            "get_resort_conditions", {"resort_id": "big-white"}
        )
        assert "error" in result

    def test_get_nearby_resorts_tool(self, chat_service, mock_resort_service):
        """get_nearby_resorts tool should return nearby resorts."""
        result = chat_service._execute_tool(
            "get_nearby_resorts",
            {"latitude": 49.0, "longitude": -118.0, "radius_km": 100},
        )
        assert "results" in result
        assert result["count"] == 0  # Mock returns empty list

    def test_get_best_conditions_tool(self, chat_service, mock_recommendation_service):
        """get_best_conditions tool should return recommendations."""
        result = chat_service._execute_tool("get_best_conditions", {"limit": 5})
        assert "results" in result
        assert result["count"] == 0

    def test_get_condition_reports_tool_empty(self, chat_service):
        """get_condition_reports should return empty when no reports."""
        result = chat_service._execute_tool(
            "get_condition_reports", {"resort_id": "big-white"}
        )
        assert result["resort_id"] == "big-white"
        assert result["reports"] == []

    def test_get_condition_reports_tool_with_data(
        self, chat_service, mock_condition_report_service
    ):
        """get_condition_reports should return user reports."""
        mock_report = Mock()
        mock_report.condition_type = Mock(value="powder")
        mock_report.score = 5
        mock_report.comment = "Amazing fresh powder today!"
        mock_report.elevation_level = "top"
        mock_report.created_at = "2026-02-22T08:00:00Z"
        mock_condition_report_service.get_reports_for_resort.return_value = [
            mock_report
        ]

        result = chat_service._execute_tool(
            "get_condition_reports", {"resort_id": "big-white"}
        )
        assert result["count"] == 1
        assert result["reports"][0]["condition_type"] == "powder"
        assert result["reports"][0]["comment"] == "Amazing fresh powder today!"

    def test_get_condition_reports_no_service(self):
        """get_condition_reports should handle missing service gracefully."""
        service = ChatService(
            chat_table=Mock(),
            resort_service=Mock(),
            weather_service=Mock(),
            snow_quality_service=Mock(),
            recommendation_service=Mock(),
            condition_report_service=None,
        )
        result = service._tool_get_condition_reports("big-white")
        assert result["reports"] == []

    def test_unknown_tool_raises(self, chat_service):
        """Unknown tool should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            chat_service._execute_tool("nonexistent_tool", {})


# ---------------------------------------------------------------------------
# Title generation tests
# ---------------------------------------------------------------------------


class TestTitleGeneration:
    """Test cases for conversation title generation."""

    def test_short_message_is_title(self, chat_service):
        """Short messages become the title directly."""
        assert (
            chat_service._generate_title("Best powder today?") == "Best powder today?"
        )

    def test_first_sentence_as_title(self, chat_service):
        """First sentence (under 50 chars) is used as title when message is longer than 50."""
        msg = "How is Whistler? I want to go this weekend and check the fresh powder conditions."
        assert chat_service._generate_title(msg) == "How is Whistler?"

    def test_long_message_truncated(self, chat_service):
        """Long messages without a sentence break are truncated at word boundary."""
        msg = "I want to know about the snow conditions at Big White and whether it is worth driving up there"
        title = chat_service._generate_title(msg)
        assert len(title) <= 55  # 50 + "..."
        assert title.endswith("...")

    def test_exactly_50_chars(self, chat_service):
        """Message of exactly 50 chars should not be truncated."""
        msg = "A" * 50
        assert chat_service._generate_title(msg) == msg


# ---------------------------------------------------------------------------
# Conversation management tests
# ---------------------------------------------------------------------------


class TestListConversations:
    """Test cases for listing conversations."""

    def test_list_empty(self, chat_service, mock_chat_table):
        """Empty result should return empty list."""
        mock_chat_table.query.return_value = {"Items": []}
        result = chat_service.list_conversations("user_123")
        assert result == []

    def test_list_groups_by_conversation(self, chat_service, mock_chat_table):
        """Messages should be grouped by conversation_id."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_1",
                    "message_id": "01A",
                    "user_id": "user_123",
                    "role": "user",
                    "content": "Hello",
                    "created_at": "2026-02-20T10:00:00Z",
                    "title": "Hello",
                },
                {
                    "conversation_id": "conv_1",
                    "message_id": "01B",
                    "user_id": "user_123",
                    "role": "assistant",
                    "content": "Hi!",
                    "created_at": "2026-02-20T10:01:00Z",
                },
                {
                    "conversation_id": "conv_2",
                    "message_id": "01C",
                    "user_id": "user_123",
                    "role": "user",
                    "content": "Conditions?",
                    "created_at": "2026-02-21T08:00:00Z",
                    "title": "Conditions?",
                },
            ]
        }

        result = chat_service.list_conversations("user_123")
        assert len(result) == 2
        assert all(isinstance(s, ConversationSummary) for s in result)

    def test_list_sorted_by_last_message(self, chat_service, mock_chat_table):
        """Conversations should be sorted by last_message_at descending."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_old",
                    "message_id": "01A",
                    "user_id": "user_123",
                    "role": "user",
                    "content": "Old",
                    "created_at": "2026-02-19T10:00:00Z",
                    "title": "Old",
                },
                {
                    "conversation_id": "conv_new",
                    "message_id": "01B",
                    "user_id": "user_123",
                    "role": "user",
                    "content": "New",
                    "created_at": "2026-02-21T10:00:00Z",
                    "title": "New",
                },
            ]
        }

        result = chat_service.list_conversations("user_123")
        assert result[0].conversation_id == "conv_new"
        assert result[1].conversation_id == "conv_old"


class TestGetConversation:
    """Test cases for getting a conversation."""

    def test_get_existing_conversation(self, chat_service, mock_chat_table):
        """Should return messages for a valid conversation."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_1",
                    "message_id": "01A",
                    "user_id": "user_123",
                    "role": "user",
                    "content": "Hello",
                    "created_at": "2026-02-20T10:00:00Z",
                },
                {
                    "conversation_id": "conv_1",
                    "message_id": "01B",
                    "user_id": "user_123",
                    "role": "assistant",
                    "content": "Hi there!",
                    "created_at": "2026-02-20T10:01:00Z",
                },
            ]
        }

        result = chat_service.get_conversation("conv_1", "user_123")
        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"

    def test_get_nonexistent_conversation(self, chat_service, mock_chat_table):
        """Should raise ValueError for missing conversation."""
        mock_chat_table.query.return_value = {"Items": []}
        with pytest.raises(ValueError, match="not found"):
            chat_service.get_conversation("conv_nonexistent", "user_123")

    def test_get_conversation_wrong_user(self, chat_service, mock_chat_table):
        """Should raise ValueError if user doesn't own conversation."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_1",
                    "message_id": "01A",
                    "user_id": "other_user",
                    "role": "user",
                    "content": "Hello",
                    "created_at": "2026-02-20T10:00:00Z",
                },
            ]
        }

        with pytest.raises(ValueError, match="not found"):
            chat_service.get_conversation("conv_1", "user_123")


class TestDeleteConversation:
    """Test cases for deleting a conversation."""

    def test_delete_existing_conversation(self, chat_service, mock_chat_table):
        """Should delete all messages in conversation."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_1",
                    "message_id": "01A",
                    "user_id": "user_123",
                },
                {
                    "conversation_id": "conv_1",
                    "message_id": "01B",
                    "user_id": "user_123",
                },
            ]
        }

        # Should not raise
        chat_service.delete_conversation("conv_1", "user_123")
        mock_chat_table.batch_writer.assert_called_once()

    def test_delete_nonexistent_conversation(self, chat_service, mock_chat_table):
        """Should raise ValueError for missing conversation."""
        mock_chat_table.query.return_value = {"Items": []}
        with pytest.raises(ValueError, match="not found"):
            chat_service.delete_conversation("conv_nonexistent", "user_123")

    def test_delete_wrong_user(self, chat_service, mock_chat_table):
        """Should raise ValueError if user doesn't own conversation."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "conversation_id": "conv_1",
                    "message_id": "01A",
                    "user_id": "other_user",
                },
            ]
        }
        with pytest.raises(ValueError, match="not found"):
            chat_service.delete_conversation("conv_1", "user_123")


# ---------------------------------------------------------------------------
# History loading tests
# ---------------------------------------------------------------------------


class TestHistoryLoading:
    """Test cases for conversation history loading."""

    def test_loads_last_20_messages(self, chat_service, mock_chat_table):
        """Should query with Limit=20 and reverse order."""
        mock_chat_table.query.return_value = {"Items": []}
        chat_service._load_history("conv_1", "user_123")

        call_kwargs = mock_chat_table.query.call_args[1]
        assert call_kwargs["Limit"] == 20
        assert call_kwargs["ScanIndexForward"] is False

    def test_verifies_ownership(self, chat_service, mock_chat_table):
        """Should return empty list if user doesn't own conversation."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "role": "user",
                    "content": "Hello",
                    "user_id": "other_user",
                    "message_id": "01A",
                    "created_at": "2026-02-20T10:00:00Z",
                }
            ]
        }

        result = chat_service._load_history("conv_1", "user_123")
        assert result == []

    def test_reverses_to_chronological(self, chat_service, mock_chat_table):
        """Messages should be reversed to chronological order."""
        mock_chat_table.query.return_value = {
            "Items": [
                {
                    "role": "assistant",
                    "content": "Response",
                    "user_id": "user_123",
                    "message_id": "01B",
                    "created_at": "2026-02-20T10:01:00Z",
                },
                {
                    "role": "user",
                    "content": "Question",
                    "user_id": "user_123",
                    "message_id": "01A",
                    "created_at": "2026-02-20T10:00:00Z",
                },
            ]
        }

        result = chat_service._load_history("conv_1", "user_123")
        assert len(result) == 2
        assert result[0]["content"] == "Question"
        assert result[1]["content"] == "Response"


# ---------------------------------------------------------------------------
# Auto-detect resort tests
# ---------------------------------------------------------------------------


class TestAutoDetectResorts:
    """Test cases for resort auto-detection in user messages."""

    def test_detects_alias_match(self, chat_service):
        """Should detect resorts by alias (e.g., 'whistler' → whistler-blackcomb)."""
        result = chat_service._auto_detect_resorts("How's Whistler today?")
        assert result is not None
        assert "whistler-blackcomb" in result

    def test_detects_multi_word_alias(self, chat_service):
        """Should detect multi-word aliases like 'big white'."""
        result = chat_service._auto_detect_resorts("Is Big White any good right now?")
        assert result is not None
        assert "big-white" in result

    def test_detects_short_alias(self, chat_service):
        """Should detect short aliases like 'breck'."""
        result = chat_service._auto_detect_resorts("What's breck looking like?")
        assert result is not None
        assert "breckenridge" in result

    def test_no_detection_for_generic_message(self, chat_service):
        """Should return None for messages without resort mentions."""
        result = chat_service._auto_detect_resorts("What's the best snow right now?")
        assert result is None

    def test_detects_multiple_resorts(self, chat_service):
        """Should detect multiple resort mentions."""
        result = chat_service._auto_detect_resorts(
            "Should I go to Whistler or Vail this weekend?"
        )
        assert result is not None
        assert "whistler-blackcomb" in result
        assert "vail" in result

    def test_limits_to_three_resorts(self, chat_service):
        """Should limit pre-fetching to 3 resorts."""
        result = chat_service._auto_detect_resorts(
            "Compare Whistler, Vail, Chamonix, Niseko, and Steamboat"
        )
        assert result is not None
        # Count resort blocks (each starts with "Resort:")
        resort_count = result.count("Resort:")
        assert resort_count <= 3

    def test_case_insensitive(self, chat_service):
        """Detection should be case-insensitive."""
        result = chat_service._auto_detect_resorts("WHISTLER conditions?")
        assert result is not None
        assert "whistler-blackcomb" in result

    def test_word_boundary_matching(self, chat_service):
        """Should not match partial words (e.g., 'vailed' should not match 'vail')."""
        result = chat_service._auto_detect_resorts("I was prevailed upon to ski today")
        # "prevailed" contains "vail" but shouldn't match at word boundary
        assert result is None or "vail" not in (result or "")

    def test_context_includes_conditions(self, chat_service, mock_weather_service):
        """Pre-fetched context should include conditions data."""
        result = chat_service._auto_detect_resorts("How's Whistler?")
        assert result is not None
        assert "Conditions:" in result
        # Should include actual weather data from mock
        mock_weather_service.get_conditions_for_resort.assert_called_with(
            "whistler-blackcomb"
        )

    def test_auto_detect_injected_into_system_prompt(
        self, chat_service, mock_bedrock_client
    ):
        """Auto-detected resort data should be in the system prompt."""
        chat_service.chat("How's Whistler?", None, "user_123")

        call_kwargs = mock_bedrock_client.converse.call_args[1]
        system_text = call_kwargs["system"][0]["text"]
        assert "PRE-FETCHED DATA" in system_text
        assert "whistler-blackcomb" in system_text.lower()

    def test_no_injection_for_generic_message(self, chat_service, mock_bedrock_client):
        """Generic messages should not add context to system prompt."""
        chat_service.chat("Hello", None, "user_123")

        call_kwargs = mock_bedrock_client.converse.call_args[1]
        system_text = call_kwargs["system"][0]["text"]
        assert system_text == SYSTEM_PROMPT

    def test_aliases_dict_has_common_resorts(self):
        """RESORT_ALIASES should include common resort names."""
        assert "whistler" in RESORT_ALIASES
        assert "vail" in RESORT_ALIASES
        assert "mammoth" in RESORT_ALIASES
        assert "chamonix" in RESORT_ALIASES
        assert "niseko" in RESORT_ALIASES
