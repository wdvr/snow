"""Multi-source weather data merger.

Combines weather data from multiple sources (Open-Meteo, OnTheSnow,
Snow-Forecast, WeatherKit) using outlier detection and majority consensus.

When 3+ sources are available, outlier values (>50% from median) are
dropped and the remaining consensus group is averaged. With only 2
sources, disagreement falls back to weighted average.
"""

import logging
from dataclasses import dataclass, field
from statistics import median as calc_median
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

        # Merge snowfall using outlier detection + majority consensus
        for snowfall_key in ["snowfall_24h_cm", "snowfall_48h_cm", "snowfall_72h_cm"]:
            values_by_source = {
                name: getattr(source, snowfall_key)
                for name, source in available_sources.items()
                if getattr(source, snowfall_key, None) is not None
            }

            if len(values_by_source) > 1:
                merged[snowfall_key] = MultiSourceMerger._merge_snowfall_values(
                    values_by_source, normalized_weights
                )

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

        if source_count >= 2 and len(snowfall_values) >= 2:
            median_val = calc_median(snowfall_values)
            if median_val >= 1.0:
                all_agree = all(
                    abs(v - median_val) / median_val <= 0.5 for v in snowfall_values
                )
            else:
                all_agree = all(v < 1.0 for v in snowfall_values)

            if source_count >= 3 and all_agree:
                merged["source_confidence"] = ConfidenceLevel.HIGH
            elif source_count >= 3:
                # Sources disagree (outlier detected)
                merged["source_confidence"] = ConfidenceLevel.MEDIUM
            elif all_agree:
                merged["source_confidence"] = ConfidenceLevel.HIGH
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
            f"Merged {len(available_sources)} sources: {', '.join(source_names)}"
        )

        return merged

    @staticmethod
    def _weighted_average(
        values_by_source: dict[str, float],
        normalized_weights: dict[str, float],
    ) -> float:
        """Weighted average fallback for when no consensus can be determined."""
        weight_sum = sum(normalized_weights.get(name, 0) for name in values_by_source)
        if weight_sum <= 0:
            return round(sum(values_by_source.values()) / len(values_by_source), 1)
        return round(
            sum(
                val * normalized_weights.get(name, 0) / weight_sum
                for name, val in values_by_source.items()
            ),
            1,
        )

    @staticmethod
    def _merge_snowfall_values(
        values_by_source: dict[str, float],
        normalized_weights: dict[str, float],
    ) -> float:
        """Merge snowfall using outlier detection + majority consensus.

        Strategy:
        - 1 source: use its value
        - 2 sources: if they agree (within 30%), average; else weighted avg
        - 3+ sources: detect outliers via median, drop them, average consensus
        """
        if len(values_by_source) == 1:
            return round(next(iter(values_by_source.values())), 1)

        all_vals = sorted(values_by_source.values())

        if len(values_by_source) == 2:
            v1, v2 = all_vals
            max_val = max(abs(v1), abs(v2))
            # Both near zero or within 30%: simple average
            if max_val < 1.0 or (max_val > 0 and abs(v1 - v2) / max_val <= 0.3):
                return round((v1 + v2) / 2, 1)
            # Can't determine majority with 2 — weighted average tiebreaker
            return MultiSourceMerger._weighted_average(
                values_by_source, normalized_weights
            )

        # 3+ sources: outlier detection via median
        median_val = calc_median(all_vals)

        if median_val < 1.0:
            # Near-zero median: use absolute threshold
            consensus = {n: v for n, v in values_by_source.items() if v <= 1.0}
        else:
            # Standard: >50% deviation from median = outlier
            consensus = {
                n: v
                for n, v in values_by_source.items()
                if abs(v - median_val) / median_val <= 0.5
            }

        if len(consensus) >= 2:
            # Majority agrees — average the consensus group
            return round(sum(consensus.values()) / len(consensus), 1)

        # No clear consensus — weighted average fallback
        return MultiSourceMerger._weighted_average(values_by_source, normalized_weights)
