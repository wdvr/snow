"""Resort data models."""

import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    latitude: float | None = Field(
        None, ge=-90, le=90, description="Latitude coordinate"
    )
    longitude: float | None = Field(
        None, ge=-180, le=180, description="Longitude coordinate"
    )
    weather_station_id: str | None = Field(
        None, description="External weather station ID if available"
    )


class Resort(BaseModel):
    """Ski resort data model."""

    resort_id: str = Field(..., description="Unique identifier for the resort")
    name: str = Field(..., description="Resort display name")
    country: str = Field(..., description="Country code (US, CA)")
    region: str = Field(..., description="State/Province")
    city: str | None = Field(None, description="Nearest city or town")
    state_province: str | None = Field(
        None, description="State/province abbreviation or name"
    )
    elevation_points: list[ElevationPoint] = Field(
        ..., description="Base, mid, top elevation data"
    )
    timezone: str = Field(
        ..., description="Resort timezone (e.g., 'America/Vancouver')"
    )
    official_website: str | None = Field(None, description="Resort official website")
    logo_url: str | None = Field(None, description="URL to resort logo image")
    trail_map_url: str | None = Field(None, description="URL to trail map image or PDF")
    webcam_url: str | None = Field(None, description="URL to webcam page")
    green_runs_pct: int | None = Field(
        None, description="Percentage of beginner/green runs"
    )
    blue_runs_pct: int | None = Field(
        None, description="Percentage of intermediate/blue runs"
    )
    black_runs_pct: int | None = Field(
        None, description="Percentage of advanced/black runs"
    )
    double_black_runs_pct: int | None = Field(
        None, description="Percentage of double-black/expert runs"
    )
    has_snowmaking: bool | None = Field(
        None, description="Resort has snowmaking capability"
    )
    day_ticket_price_min_usd: int | None = Field(
        None, description="Minimum adult day ticket price in USD"
    )
    day_ticket_price_max_usd: int | None = Field(
        None, description="Maximum adult day ticket price in USD"
    )
    annual_snowfall_cm: int | None = Field(
        None, description="Average annual snowfall in cm"
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
    # Pass affiliations
    epic_pass: str | None = Field(
        None, description="Epic Pass access (e.g., 'Unlimited', '7 days', '5 days')"
    )
    ikon_pass: str | None = Field(
        None, description="Ikon Pass access (e.g., 'Unlimited', '7 days', '5 days')"
    )
    mountain_collective: str | None = Field(
        None, description="Mountain Collective access level"
    )
    indy_pass: str | None = Field(None, description="Indy Pass access level")
    # Resort labels
    family_friendly: bool | None = Field(None, description="Suitable for families")
    expert_terrain: bool | None = Field(
        None, description="Known for expert/advanced terrain"
    )
    large_resort: bool | None = Field(
        None, description="Large resort (>100km piste or >1000m vertical)"
    )
    ski_in_out: bool | None = Field(
        None, description="Ski-in/ski-out accommodation available"
    )
    # Scraper metadata
    source: str | None = Field(
        None, description="Data source (manual, skiresort.info, wikipedia)"
    )
    scraped_at: str | None = Field(
        None, description="ISO timestamp when resort was last scraped"
    )
    # Season-aware polling overrides. When both are set, they override the
    # hemisphere-default window. Format: "MM-DD". See utils/season_utils.py.
    season_start_month_day: str | None = Field(
        None, description="Season start override (MM-DD)"
    )
    season_end_month_day: str | None = Field(
        None, description="Season end override (MM-DD)"
    )
    year_round: bool = Field(
        False,
        description="If true, resort is polled year-round regardless of latitude",
    )

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("season_start_month_day", "season_end_month_day")
    @classmethod
    def _validate_month_day(cls, v: str | None) -> str | None:
        """Validate 'MM-DD' format and that the date is real."""
        if v is None:
            return v
        if not isinstance(v, str) or not re.fullmatch(r"\d{2}-\d{2}", v):
            raise ValueError(f"season_*_month_day must match 'MM-DD' format, got {v!r}")
        month = int(v[0:2])
        day = int(v[3:5])
        # Validate via a real date in a leap year to allow Feb 29.
        from datetime import date as _date

        try:
            _date(2000, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid month-day value {v!r}: {e}") from e
        return v

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
