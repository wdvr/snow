"""Multi-source weather data merger.

Combines weather data from multiple sources (Open-Meteo, OnTheSnow,
Snow-Forecast, WeatherKit) using weighted averaging with normalized
weights when sources are missing.

Replaces the inline 70/30 merge logic in OnTheSnow scraper with a
generic multi-source approach.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from models.weather import ConfidenceLevel

logger = logging.getLogger(__name__)

# Default source weights (must sum to 1.0)
DEFAULT_WEIGHTS = {
    "open-meteo": 0.50,
    "onthesnow": 0.25,
    "snowforecast": 0.15,
    "weatherkit": 0.10,
}

# Priority order for snow depth (resort-reported overrides model estimates)
DEPTH_PRIORITY = ["onthesnow", "snowforecast", "open-meteo"]


@dataclass
class SourceData:
    """Weather data from a single source."""

    source_name: str
    snowfall_24h_cm: float | None = None
    snowfall_48h_cm: float | None = None
    snowfall_72h_cm: float | None = None
    snow_depth_cm: float | None = None
    temperature_c: float | None = None
    surface_conditions: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


class MultiSourceMerger:
    """Merges weather data from multiple sources using weighted averaging."""

    def __init__(self, weights: dict[str, float] | None = None):
        """Initialize with optional custom weights.

        Args:
            weights: Dict of source_name -> weight. If None, uses DEFAULT_WEIGHTS.
        """
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    @staticmethod
    def merge(
        base_weather_data: dict[str, Any],
        sources: list[SourceData],
        weights: dict[str, float] | None = None,
        elevation_level: str = "mid",
    ) -> dict[str, Any]:
        """Merge multiple weather data sources into base weather data.

        Args:
            base_weather_data: Open-Meteo weather data dict (always present)
            sources: List of supplementary SourceData from other sources
            weights: Optional custom weights. If None, uses DEFAULT_WEIGHTS.
            elevation_level: "base", "mid", or "top" for depth selection

        Returns:
            Merged weather data dict with updated values
        """
        if not sources:
            return base_weather_data

        active_weights = weights or DEFAULT_WEIGHTS.copy()
        merged = base_weather_data.copy()

        # Build list of all available sources (Open-Meteo is always present)
        available_sources: dict[str, SourceData] = {}
        open_meteo_source = SourceData(
            source_name="open-meteo",
            snowfall_24h_cm=base_weather_data.get("snowfall_24h_cm"),
            snowfall_48h_cm=base_weather_data.get("snowfall_48h_cm"),
            snowfall_72h_cm=base_weather_data.get("snowfall_72h_cm"),
            snow_depth_cm=base_weather_data.get("snow_depth_cm"),
            temperature_c=base_weather_data.get("temperature_c"),
        )
        available_sources["open-meteo"] = open_meteo_source

        for source in sources:
            available_sources[source.source_name] = source

        # Calculate normalized weights for available sources
        available_weight_sum = sum(
            active_weights.get(name, 0.0) for name in available_sources
        )
        if available_weight_sum <= 0:
            return merged

        normalized_weights = {
            name: active_weights.get(name, 0.0) / available_weight_sum
            for name in available_sources
        }

        # Merge snowfall using weighted average
        for snowfall_key in ["snowfall_24h_cm", "snowfall_48h_cm", "snowfall_72h_cm"]:
            sources_with_data = {
                name: source
                for name, source in available_sources.items()
                if getattr(source, snowfall_key, None) is not None
            }

            if len(sources_with_data) > 1:
                # Multiple sources have data - weighted average
                data_weight_sum = sum(
                    normalized_weights[name] for name in sources_with_data
                )
                if data_weight_sum > 0:
                    weighted_sum = sum(
                        getattr(source, snowfall_key)
                        * normalized_weights[name]
                        / data_weight_sum
                        for name, source in sources_with_data.items()
                    )
                    merged[snowfall_key] = round(weighted_sum, 1)

        # Snow depth: use priority-based override (resort-reported > model)
        for priority_source in DEPTH_PRIORITY:
            if priority_source in available_sources:
                source = available_sources[priority_source]
                if source.snow_depth_cm is not None:
                    merged["snow_depth_cm"] = source.snow_depth_cm
                    break

        # Determine confidence level based on source agreement
        source_count = len(available_sources)
        snowfall_values = [
            getattr(s, "snowfall_24h_cm", None)
            for s in available_sources.values()
            if getattr(s, "snowfall_24h_cm", None) is not None
        ]

        if source_count >= 3 and len(snowfall_values) >= 3:
            merged["source_confidence"] = ConfidenceLevel.HIGH
        elif source_count >= 2 and len(snowfall_values) >= 2:
            # Check if sources agree (within 50% of mean)
            mean_val = (
                sum(snowfall_values) / len(snowfall_values) if snowfall_values else 0
            )
            if mean_val > 0:
                agreement = all(
                    abs(v - mean_val) / mean_val < 0.5 for v in snowfall_values
                )
                merged["source_confidence"] = (
                    ConfidenceLevel.HIGH if agreement else ConfidenceLevel.MEDIUM
                )
            else:
                merged["source_confidence"] = ConfidenceLevel.MEDIUM
        # 1 source = keep existing confidence (baseline)

        # Build data_source string
        source_names = sorted(available_sources.keys())
        merged["data_source"] = " + ".join(
            f"{name}.com" if name != "weatherkit" else "weatherkit.apple.com"
            for name in source_names
        )

        # Store raw data from all supplementary sources for debugging
        if "raw_data" not in merged:
            merged["raw_data"] = {}
        for source in sources:
            merged["raw_data"][f"scraped_{source.source_name}"] = source.raw_data

        logger.info(
            f"Merged {len(available_sources)} sources: "
            f"{', '.join(f'{n}(w={normalized_weights[n]:.2f})' for n in source_names)}"
        )

        return merged
