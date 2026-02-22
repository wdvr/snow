"""Shared constants for the Snow Quality Tracker backend."""

# Elevation weighting for overall quality calculations.
# Top (summit) conditions matter most since that's where most skiing happens.
# Must be consistent across: api_handler.py, static_json_generator.py,
# recommendation_service.py, snow_quality_service.py
ELEVATION_WEIGHTS: dict[str, float] = {"top": 0.50, "mid": 0.35, "base": 0.15}

# Default weight for unknown elevation levels
DEFAULT_ELEVATION_WEIGHT: float = 0.15
