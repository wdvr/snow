"""Resort data models."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ElevationLevel(str, Enum):
    """Elevation levels for ski resorts."""
    BASE = "base"
    MID = "mid"
    TOP = "top"


class ElevationPoint(BaseModel):
    """Represents a specific elevation point at a ski resort."""
    level: ElevationLevel
    elevation_meters: int = Field(..., description="Elevation in meters above sea level")
    elevation_feet: int = Field(..., description="Elevation in feet above sea level")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    weather_station_id: Optional[str] = Field(None, description="External weather station ID if available")


class Resort(BaseModel):
    """Ski resort data model."""
    resort_id: str = Field(..., description="Unique identifier for the resort")
    name: str = Field(..., description="Resort display name")
    country: str = Field(..., description="Country code (US, CA)")
    region: str = Field(..., description="State/Province")
    elevation_points: List[ElevationPoint] = Field(..., description="Base, mid, top elevation data")
    timezone: str = Field(..., description="Resort timezone (e.g., 'America/Vancouver')")
    official_website: Optional[str] = Field(None, description="Resort official website")
    weather_sources: List[str] = Field(default_factory=list, description="Available weather data sources")
    created_at: Optional[str] = Field(None, description="ISO timestamp when resort was added")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when resort was last updated")

    class Config:
        """Pydantic configuration."""
        use_enum_values = True