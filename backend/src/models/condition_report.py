"""Condition report data models for user-submitted snow condition reports."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConditionType(str, Enum):
    """Types of snow conditions users can report."""

    POWDER = "powder"
    PACKED_POWDER = "packed_powder"
    SOFT = "soft"
    ICE = "ice"
    CRUD = "crud"
    SPRING = "spring"
    HARDPACK = "hardpack"
    WINDBLOWN = "windblown"


class ConditionReport(BaseModel):
    """Stored condition report record."""

    resort_id: str
    report_id: str
    user_id: str
    condition_type: ConditionType
    score: int = Field(ge=1, le=10)
    comment: str | None = None
    elevation_level: str | None = None
    created_at: str
    expires_at: int


class ConditionReportRequest(BaseModel):
    """Request body for submitting a condition report."""

    condition_type: ConditionType
    score: int = Field(ge=1, le=10)
    comment: str | None = Field(None, max_length=500)
    elevation_level: str | None = Field(None, pattern="^(base|mid|top)$")


class ConditionReportResponse(BaseModel):
    """Response model for a condition report."""

    report_id: str
    resort_id: str
    condition_type: ConditionType
    score: int
    comment: str | None
    elevation_level: str | None
    created_at: str
    user_display_name: str | None = None
