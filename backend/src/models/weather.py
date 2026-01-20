"""Weather and snow condition data models."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ConfidenceLevel(str, Enum):
    """Confidence levels for snow quality predictions."""
    VERY_HIGH = "very_high"    # Resort reports, direct measurements
    HIGH = "high"              # Slopes app, user reports
    MEDIUM = "medium"          # snow-report.com, specialized sources
    LOW = "low"                # weatherapi.com, general weather APIs
    VERY_LOW = "very_low"      # Apple Weather, basic sources


class SnowQuality(str, Enum):
    """Snow condition quality levels."""
    EXCELLENT = "excellent"    # Fresh powder, no ice, <2h since snowfall
    GOOD = "good"              # Fresh powder, minimal ice, 2-6h since snowfall
    FAIR = "fair"              # Some ice formation, 6-12h since snowfall
    POOR = "poor"              # Significant ice, 12-24h with warm temps
    BAD = "bad"                # Mostly ice, >24h with sustained warm temps
    UNKNOWN = "unknown"        # Insufficient data


class WeatherCondition(BaseModel):
    """Weather condition data for a specific resort elevation point."""
    resort_id: str = Field(..., description="Resort identifier")
    elevation_level: str = Field(..., description="base, mid, or top")
    timestamp: str = Field(..., description="ISO timestamp of the observation")

    # Temperature data
    current_temp_celsius: float = Field(..., description="Current temperature in Celsius")
    min_temp_celsius: float = Field(..., description="Minimum temperature in last 24h")
    max_temp_celsius: float = Field(..., description="Maximum temperature in last 24h")

    # Precipitation data
    snowfall_24h_cm: float = Field(default=0.0, description="Snowfall in last 24 hours (cm)")
    snowfall_48h_cm: float = Field(default=0.0, description="Snowfall in last 48 hours (cm)")
    snowfall_72h_cm: float = Field(default=0.0, description="Snowfall in last 72 hours (cm)")

    # Ice formation factors
    hours_above_ice_threshold: float = Field(default=0.0, description="Hours above ice formation temp in last 24h")
    max_consecutive_warm_hours: float = Field(default=0.0, description="Max consecutive hours above threshold")

    # Weather conditions
    humidity_percent: Optional[float] = Field(None, description="Relative humidity percentage")
    wind_speed_kmh: Optional[float] = Field(None, description="Wind speed in km/h")
    weather_description: Optional[str] = Field(None, description="General weather description")

    # Snow quality assessment
    snow_quality: SnowQuality = Field(..., description="Calculated snow quality")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence in the assessment")
    fresh_snow_cm: float = Field(default=0.0, description="Estimated fresh (non-iced) snow depth")

    # Data source tracking
    data_source: str = Field(..., description="Primary data source")
    source_confidence: ConfidenceLevel = Field(..., description="Confidence in data source")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw weather API response")

    # TTL for DynamoDB
    ttl: Optional[int] = Field(None, description="Unix timestamp for record expiration")

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class SnowQualityAlgorithm(BaseModel):
    """Configuration for snow quality assessment algorithm."""

    # Temperature thresholds
    ice_formation_temp_celsius: float = Field(default=3.0, description="Temperature threshold for ice formation")
    optimal_temp_celsius: float = Field(default=-5.0, description="Optimal temperature for powder")

    # Time thresholds
    ice_formation_hours: float = Field(default=4.0, description="Hours at ice temp to significantly degrade snow")
    fresh_snow_validity_hours: float = Field(default=48.0, description="Hours fresh snow stays optimal")

    # Quality scoring weights
    temperature_weight: float = Field(default=0.4, description="Temperature factor weight")
    time_weight: float = Field(default=0.3, description="Time since snowfall weight")
    snowfall_weight: float = Field(default=0.3, description="Snowfall amount weight")

    # Confidence adjustments
    source_confidence_multiplier: Dict[ConfidenceLevel, float] = Field(
        default={
            ConfidenceLevel.VERY_HIGH: 1.0,
            ConfidenceLevel.HIGH: 0.9,
            ConfidenceLevel.MEDIUM: 0.7,
            ConfidenceLevel.LOW: 0.5,
            ConfidenceLevel.VERY_LOW: 0.3
        },
        description="Multipliers for different data source confidence levels"
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True