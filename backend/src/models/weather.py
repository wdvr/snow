"""Weather and snow condition data models."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .resort import ElevationLevel


class ConfidenceLevel(str, Enum):
    """Confidence levels for snow quality predictions."""

    VERY_HIGH = "very_high"  # Resort reports, direct measurements
    HIGH = "high"  # Slopes app, user reports
    MEDIUM = "medium"  # snow-report.com, specialized sources
    LOW = "low"  # weatherapi.com, general weather APIs
    VERY_LOW = "very_low"  # Apple Weather, basic sources


class SnowQuality(str, Enum):
    """Snow condition quality levels."""

    EXCELLENT = "excellent"  # Fresh powder, no ice, <2h since snowfall
    GOOD = "good"  # Fresh powder, minimal ice, 2-6h since snowfall
    FAIR = "fair"  # Some ice formation, 6-12h since snowfall
    POOR = "poor"  # Significant ice, 12-24h with warm temps
    BAD = "bad"  # Mostly ice, >24h with sustained warm temps
    UNKNOWN = "unknown"  # Insufficient data


class WeatherCondition(BaseModel):
    """Weather condition data for a specific resort elevation point."""

    resort_id: str = Field(..., description="Resort identifier")
    elevation_level: str = Field(..., description="base, mid, or top")
    timestamp: str = Field(..., description="ISO timestamp of the observation")

    # Temperature data
    current_temp_celsius: float = Field(
        ..., description="Current temperature in Celsius"
    )
    min_temp_celsius: float = Field(..., description="Minimum temperature in last 24h")
    max_temp_celsius: float = Field(..., description="Maximum temperature in last 24h")

    # Precipitation data (past snowfall)
    snowfall_24h_cm: float = Field(
        default=0.0, description="Snowfall in last 24 hours (cm)"
    )
    snowfall_48h_cm: float = Field(
        default=0.0, description="Snowfall in last 48 hours (cm)"
    )
    snowfall_72h_cm: float = Field(
        default=0.0, description="Snowfall in last 72 hours (cm)"
    )

    # Snow predictions (future snowfall)
    predicted_snow_24h_cm: float = Field(
        default=0.0, description="Predicted snowfall in next 24 hours (cm)"
    )
    predicted_snow_48h_cm: float = Field(
        default=0.0, description="Predicted snowfall in next 48 hours (cm)"
    )
    predicted_snow_72h_cm: float = Field(
        default=0.0, description="Predicted snowfall in next 72 hours (cm)"
    )

    # Ice formation factors
    hours_above_ice_threshold: float = Field(
        default=0.0, description="Hours above ice formation temp in last 24h"
    )
    max_consecutive_warm_hours: float = Field(
        default=0.0, description="Max consecutive hours above threshold"
    )

    # Weather conditions
    humidity_percent: float | None = Field(
        None, description="Relative humidity percentage"
    )
    wind_speed_kmh: float | None = Field(None, description="Wind speed in km/h")
    weather_description: str | None = Field(
        None, description="General weather description"
    )

    # Snow quality assessment (set after initial creation by snow quality service)
    snow_quality: SnowQuality = Field(
        default=SnowQuality.UNKNOWN, description="Calculated snow quality"
    )
    confidence_level: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW, description="Confidence in the assessment"
    )
    fresh_snow_cm: float = Field(
        default=0.0, description="Estimated fresh (non-iced) snow depth"
    )

    # Data source tracking
    data_source: str = Field(..., description="Primary data source")
    source_confidence: ConfidenceLevel = Field(
        ..., description="Confidence in data source"
    )
    raw_data: dict[str, Any] | None = Field(
        None, description="Raw weather API response"
    )

    # TTL for DynamoDB
    ttl: int | None = Field(None, description="Unix timestamp for record expiration")

    model_config = ConfigDict(use_enum_values=True)

    @property
    def elevation_level_enum(self) -> ElevationLevel | None:
        """Get elevation level as enum."""
        try:
            return ElevationLevel(self.elevation_level)
        except ValueError:
            return None

    @property
    def current_temp_fahrenheit(self) -> float:
        """Get current temperature in Fahrenheit."""
        return self.current_temp_celsius * 9.0 / 5.0 + 32.0

    @property
    def formatted_current_temp(self) -> str:
        """Get formatted temperature string."""
        return (
            f"{self.current_temp_celsius:.0f}°C ({self.current_temp_fahrenheit:.0f}°F)"
        )

    @property
    def formatted_snowfall_24h(self) -> str:
        """Get formatted 24h snowfall string."""
        return f"{self.snowfall_24h_cm:.1f}cm"

    @property
    def formatted_fresh_snow(self) -> str:
        """Get formatted fresh snow string."""
        return f"{self.fresh_snow_cm:.1f}cm fresh"


class SnowQualityAlgorithm(BaseModel):
    """Configuration for snow quality assessment algorithm."""

    # Temperature thresholds
    ice_formation_temp_celsius: float = Field(
        default=3.0, description="Temperature threshold for ice formation"
    )
    optimal_temp_celsius: float = Field(
        default=-5.0, description="Optimal temperature for powder"
    )

    # Time thresholds
    ice_formation_hours: float = Field(
        default=4.0, description="Hours at ice temp to significantly degrade snow"
    )
    fresh_snow_validity_hours: float = Field(
        default=48.0, description="Hours fresh snow stays optimal"
    )

    # Quality scoring weights
    temperature_weight: float = Field(
        default=0.4, description="Temperature factor weight"
    )
    time_weight: float = Field(default=0.3, description="Time since snowfall weight")
    snowfall_weight: float = Field(default=0.3, description="Snowfall amount weight")

    # Confidence adjustments
    source_confidence_multiplier: dict[ConfidenceLevel, float] = Field(
        default={
            ConfidenceLevel.VERY_HIGH: 1.0,
            ConfidenceLevel.HIGH: 0.9,
            ConfidenceLevel.MEDIUM: 0.7,
            ConfidenceLevel.LOW: 0.5,
            ConfidenceLevel.VERY_LOW: 0.3,
        },
        description="Multipliers for different data source confidence levels",
    )

    model_config = ConfigDict(use_enum_values=True)
