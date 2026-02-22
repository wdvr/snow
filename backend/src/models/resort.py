"""Resort data models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ElevationLevel(str, Enum):
    """Elevation levels for ski resorts."""

    BASE = "base"
    MID = "mid"
    TOP = "top"


class ElevationPoint(BaseModel):
    """Represents a specific elevation point at a ski resort."""

    level: ElevationLevel
    elevation_meters: int = Field(
        ..., description="Elevation in meters above sea level"
    )
    elevation_feet: int = Field(..., description="Elevation in feet above sea level")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    weather_station_id: str | None = Field(
        None, description="External weather station ID if available"
    )


class Resort(BaseModel):
    """Ski resort data model."""

    resort_id: str = Field(..., description="Unique identifier for the resort")
    name: str = Field(..., description="Resort display name")
    country: str = Field(..., description="Country code (US, CA)")
    region: str = Field(..., description="State/Province")
    elevation_points: list[ElevationPoint] = Field(
        ..., description="Base, mid, top elevation data"
    )
    timezone: str = Field(
        ..., description="Resort timezone (e.g., 'America/Vancouver')"
    )
    official_website: str | None = Field(None, description="Resort official website")
    trail_map_url: str | None = Field(None, description="URL to trail map image or PDF")
    green_runs_pct: int | None = Field(
        None, description="Percentage of beginner/green runs"
    )
    blue_runs_pct: int | None = Field(
        None, description="Percentage of intermediate/blue runs"
    )
    black_runs_pct: int | None = Field(
        None, description="Percentage of advanced/black runs"
    )
    weather_sources: list[str] = Field(
        default_factory=list, description="Available weather data sources"
    )
    created_at: str | None = Field(
        None, description="ISO timestamp when resort was added"
    )
    updated_at: str | None = Field(
        None, description="ISO timestamp when resort was last updated"
    )
    # Scraper metadata
    source: str | None = Field(
        None, description="Data source (manual, skiresort.info, wikipedia)"
    )
    scraped_at: str | None = Field(
        None, description="ISO timestamp when resort was last scraped"
    )

    model_config = ConfigDict(use_enum_values=True)

    @property
    def display_location(self) -> str:
        """Get display-friendly location string."""
        country_names = {"CA": "Canada", "US": "United States"}
        country_name = country_names.get(self.country, self.country)
        return f"{self.region}, {country_name}"

    @property
    def elevation_range(self) -> str:
        """Get elevation range string."""
        elevations = sorted([p.elevation_feet for p in self.elevation_points])
        if elevations:
            return f"{elevations[0]} - {elevations[-1]} ft"
        return "Unknown"

    @property
    def base_elevation(self) -> ElevationPoint | None:
        """Get base elevation point."""
        return self.elevation_point(ElevationLevel.BASE)

    @property
    def mid_elevation(self) -> ElevationPoint | None:
        """Get mid elevation point."""
        return self.elevation_point(ElevationLevel.MID)

    @property
    def top_elevation(self) -> ElevationPoint | None:
        """Get top elevation point."""
        return self.elevation_point(ElevationLevel.TOP)

    def elevation_point(self, level: ElevationLevel) -> ElevationPoint | None:
        """Get elevation point by level."""
        for point in self.elevation_points:
            if point.level == level:
                return point
        return None
