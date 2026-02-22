"""Chat data models for AI assistant conversations."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message text content")
    message_id: str = Field(..., description="Unique message identifier (ULID)")
    created_at: str = Field(..., description="ISO timestamp when message was created")
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Tool calls made during this message"
    )


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(
        ..., min_length=1, max_length=2000, description="User message text"
    )
    conversation_id: str | None = Field(
        None, description="Existing conversation ID, or None to start new"
    )


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    conversation_id: str = Field(..., description="Conversation identifier")
    response: str = Field(..., description="Assistant response text")
    message_id: str = Field(..., description="Response message identifier (ULID)")


class ConversationSummary(BaseModel):
    """Summary of a conversation for listing."""

    conversation_id: str = Field(..., description="Conversation identifier")
    title: str = Field(..., description="Conversation title (from first message)")
    last_message_at: str = Field(..., description="ISO timestamp of last message")
    message_count: int = Field(..., description="Total messages in conversation")
