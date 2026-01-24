"""Feedback data models."""

from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackSubmission(BaseModel):
    """Model for user feedback submission."""

    subject: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=10, max_length=2000)
    email: str | None = Field(None, max_length=100)
    app_version: str = Field(..., min_length=1, max_length=20)
    build_number: str = Field(..., min_length=1, max_length=20)
    device_model: str | None = Field(None, max_length=50)
    ios_version: str | None = Field(None, max_length=20)


class Feedback(BaseModel):
    """Stored feedback record."""

    feedback_id: str
    user_id: str | None = None
    subject: str
    message: str
    email: str | None = None
    app_version: str
    build_number: str
    device_model: str | None = None
    ios_version: str | None = None
    status: str = "new"  # new, reviewed, resolved, archived
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
