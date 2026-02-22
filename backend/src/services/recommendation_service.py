"""Recommendation service for finding best snow conditions near user."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from models.resort import Resort
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.ml_scorer import raw_score_to_quality
from services.quality_explanation_service import score_to_100
from utils.geo_utils import haversine_distance


@dataclass
class ResortRecommendation:
    """A resort recommendation with scoring details."""

    resort: Resort
    distance_km: float
    distance_miles: float
    snow_quality: SnowQuality
    snow_score: int | None
    quality_score: float
    distance_score: float
    combined_score: float
    fresh_snow_cm: float
    predicted_snow_72h_cm: float
    current_temp_celsius: float
    confidence_level: ConfidenceLevel
    reason: str
    elevation_conditions: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "resort": self.resort.model_dump()
            if hasattr(self.resort, "model_dump")
            else self.resort,
            "distance_km": self.distance_km,
            "distance_miles": self.distance_miles,
            "snow_quality": self.snow_quality.value
            if isinstance(self.snow_quality, SnowQuality)
            else self.snow_quality,
            "snow_score": self.snow_score,
            "quality_score": self.quality_score,
            "distance_score": self.distance_score,
            "combined_score": self.combined_score,
            "fresh_snow_cm": self.fresh_snow_cm,
            "predicted_snow_72h_cm": self.predicted_snow_72h_cm,
            "current_temp_celsius": self.current_temp_celsius,
            "confidence_level": self.confidence_level.value
            if isinstance(self.confidence_level, ConfidenceLevel)
            else self.confidence_level,
            "reason": self.reason,
            "elevation_conditions": self.elevation_conditions,
        }


class RecommendationService:
    """Service for generating resort recommendations based on location and conditions."""

    # Scoring weights
    DISTANCE_WEIGHT = 0.3  # How much distance affects score (lower = better)
    QUALITY_WEIGHT = 0.5  # How much snow quality affects score
    FRESH_SNOW_WEIGHT = 0.2  # How much fresh/predicted snow affects score

    # Distance decay parameters
    MAX_PRACTICAL_DISTANCE_KM = 500  # Distance beyond which score drops significantly
    IDEAL_DISTANCE_KM = 50  # Distance considered "close"

    # Quality score mapping
    QUALITY_SCORES = {
        SnowQuality.EXCELLENT: 1.0,
        SnowQuality.GOOD: 0.8,
        SnowQuality.FAIR: 0.6,
        SnowQuality.POOR: 0.4,
        SnowQuality.BAD: 0.2,
        SnowQuality.HORRIBLE: 0.0,
        SnowQuality.UNKNOWN: 0.3,  # Slight penalty for unknown
    }

    def __init__(self, resort_service, weather_service):
        """Initialize the recommendation service.

        Args:
            resort_service: ResortService instance for fetching resorts
            weather_service: WeatherService instance for fetching conditions
        """
        self.resort_service = resort_service
        self.weather_service = weather_service

    def get_recommendations(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 500,
        limit: int = 10,
        min_quality: SnowQuality | None = None,
    ) -> list[ResortRecommendation]:
        """
        Get resort recommendations based on user location and snow conditions.

        The algorithm scores resorts based on:
        1. Distance from user (closer is better, with diminishing returns)
        2. Current snow quality (excellent > good > fair > poor)
        3. Fresh/predicted snow (more fresh snow = higher score)

        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Maximum search radius in kilometers (default 500)
            limit: Maximum number of recommendations (default 10)
            min_quality: Minimum snow quality to include (optional filter)

        Returns:
            List of ResortRecommendation objects sorted by combined score
        """
        import logging
        import time

        logger = logging.getLogger(__name__)
        start_time = time.time()

        # Get nearby resorts
        nearby_start = time.time()
        nearby_resorts = self.resort_service.get_nearby_resorts(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=100,  # Get more than needed for filtering
        )
        logger.info(
            f"[PERF] get_nearby_resorts took {time.time() - nearby_start:.2f}s, found {len(nearby_resorts)} resorts"
        )

        if not nearby_resorts:
            return []

        # Build lookup maps for nearby resorts
        resort_distances: dict[str, float] = {}
        resort_map: dict[str, any] = {}
        for resort, distance_km in nearby_resorts:
            resort_distances[resort.resort_id] = distance_km
            resort_map[resort.resort_id] = resort

        # Fetch ALL conditions in a single batch query (optimized)
        conditions_start = time.time()
        all_conditions = self.weather_service.get_all_latest_conditions()
        logger.info(
            f"[PERF] get_all_latest_conditions took {time.time() - conditions_start:.2f}s, got conditions for {len(all_conditions)} resorts"
        )

        # Filter to only nearby resorts
        conditions_map = {
            resort_id: conditions
            for resort_id, conditions in all_conditions.items()
            if resort_id in resort_map
        }

        recommendations = []

        for resort_id, conditions in conditions_map.items():
            resort = resort_map.get(resort_id)
            distance_km = resort_distances.get(resort_id, 0)

            if not resort or not conditions:
                continue

            # Calculate aggregate metrics across elevations
            weighted_quality = self._get_weighted_overall_quality(conditions)
            snow_score = self._get_weighted_snow_score(conditions)
            avg_fresh_snow = self._get_average_fresh_snow(conditions)
            total_predicted_snow = self._get_total_predicted_snow(conditions)
            avg_temp = self._get_average_temperature(conditions)
            best_confidence = self._get_best_confidence(conditions)

            # Apply minimum quality filter
            if min_quality and self._quality_rank(
                weighted_quality
            ) < self._quality_rank(min_quality):
                continue

            # Calculate scores
            quality_score = self._calculate_quality_score(weighted_quality)
            distance_score = self._calculate_distance_score(distance_km)
            fresh_snow_score = self._calculate_fresh_snow_score(
                avg_fresh_snow, total_predicted_snow
            )

            # Combined score (weighted average)
            combined_score = (
                self.QUALITY_WEIGHT * quality_score
                + self.DISTANCE_WEIGHT * distance_score
                + self.FRESH_SNOW_WEIGHT * fresh_snow_score
            )

            # Build elevation conditions summary
            elevation_conditions = self._build_elevation_summary(conditions)

            # Generate recommendation reason
            reason = self._generate_reason(
                resort=resort,
                distance_km=distance_km,
                best_quality=weighted_quality,
                avg_fresh_snow=avg_fresh_snow,
                total_predicted_snow=total_predicted_snow,
            )

            recommendations.append(
                ResortRecommendation(
                    resort=resort,
                    distance_km=round(distance_km, 1),
                    distance_miles=round(distance_km * 0.621371, 1),
                    snow_quality=weighted_quality,
                    snow_score=snow_score,
                    quality_score=round(quality_score, 3),
                    distance_score=round(distance_score, 3),
                    combined_score=round(combined_score, 3),
                    fresh_snow_cm=round(avg_fresh_snow, 1),
                    predicted_snow_72h_cm=round(total_predicted_snow, 1),
                    current_temp_celsius=round(avg_temp, 1),
                    confidence_level=best_confidence,
                    reason=reason,
                    elevation_conditions=elevation_conditions,
                )
            )

        # Sort by combined score (descending), then fresh snow as tiebreaker
        recommendations.sort(
            key=lambda r: (r.combined_score, r.fresh_snow_cm), reverse=True
        )

        logger.info(
            f"[PERF] get_recommendations total took {time.time() - start_time:.2f}s, returning {min(limit, len(recommendations))} recommendations"
        )
        return recommendations[:limit]

    def get_best_conditions_globally(
        self,
        limit: int = 10,
        min_quality: SnowQuality | None = None,
    ) -> list[ResortRecommendation]:
        """
        Get resorts with the best snow conditions globally (no location bias).

        Uses a single batch query to fetch all conditions efficiently.

        Args:
            limit: Maximum number of results
            min_quality: Minimum snow quality filter

        Returns:
            List of recommendations sorted by snow quality
        """
        import logging
        import time

        logger = logging.getLogger(__name__)
        start_time = time.time()

        # Get all resorts
        resorts_start = time.time()
        all_resorts = self.resort_service.get_all_resorts()
        logger.info(
            f"[PERF] get_all_resorts took {time.time() - resorts_start:.2f}s, found {len(all_resorts)} resorts"
        )

        # Fetch ALL conditions in a single batch query (optimized)
        conditions_start = time.time()
        conditions_map = self.weather_service.get_all_latest_conditions()
        logger.info(
            f"[PERF] get_all_latest_conditions took {time.time() - conditions_start:.2f}s, got conditions for {len(conditions_map)} resorts"
        )

        recommendations = []
        resort_map = {r.resort_id: r for r in all_resorts}

        for resort_id, conditions in conditions_map.items():
            resort = resort_map.get(resort_id)
            if not resort or not conditions:
                continue

            weighted_quality = self._get_weighted_overall_quality(conditions)
            snow_score = self._get_weighted_snow_score(conditions)

            if min_quality and self._quality_rank(
                weighted_quality
            ) < self._quality_rank(min_quality):
                continue

            avg_fresh_snow = self._get_average_fresh_snow(conditions)
            total_predicted_snow = self._get_total_predicted_snow(conditions)
            avg_temp = self._get_average_temperature(conditions)
            best_confidence = self._get_best_confidence(conditions)

            quality_score = self._calculate_quality_score(weighted_quality)
            fresh_snow_score = self._calculate_fresh_snow_score(
                avg_fresh_snow, total_predicted_snow
            )

            # For global ranking, quality + fresh snow weighted by resort significance
            base_score = 0.7 * quality_score + 0.3 * fresh_snow_score
            significance = self._calculate_significance(resort)
            combined_score = base_score * significance

            elevation_conditions = self._build_elevation_summary(conditions)

            reason = self._generate_global_reason(
                resort=resort,
                best_quality=weighted_quality,
                avg_fresh_snow=avg_fresh_snow,
                total_predicted_snow=total_predicted_snow,
            )

            recommendations.append(
                ResortRecommendation(
                    resort=resort,
                    distance_km=0,  # N/A for global
                    distance_miles=0,
                    snow_quality=weighted_quality,
                    snow_score=snow_score,
                    quality_score=round(quality_score, 3),
                    distance_score=1.0,  # N/A for global
                    combined_score=round(combined_score, 3),
                    fresh_snow_cm=round(avg_fresh_snow, 1),
                    predicted_snow_72h_cm=round(total_predicted_snow, 1),
                    current_temp_celsius=round(avg_temp, 1),
                    confidence_level=best_confidence,
                    reason=reason,
                    elevation_conditions=elevation_conditions,
                )
            )

        # Sort by combined score (descending), then fresh snow as tiebreaker
        recommendations.sort(
            key=lambda r: (r.combined_score, r.fresh_snow_cm), reverse=True
        )
        logger.info(
            f"[PERF] get_best_conditions_globally total took {time.time() - start_time:.2f}s, returning {min(limit, len(recommendations))} recommendations"
        )
        return recommendations[:limit]

    def _get_resort_conditions(self, resort_id: str) -> list[WeatherCondition]:
        """Get latest conditions for a resort."""
        try:
            return self.weather_service.get_conditions_for_resort(
                resort_id, hours_back=6
            )
        except Exception:
            return []

    def _get_best_quality(self, conditions: list[WeatherCondition]) -> SnowQuality:
        """Get the best snow quality across all elevations (used for ranking)."""
        if not conditions:
            return SnowQuality.UNKNOWN

        best = SnowQuality.UNKNOWN
        best_rank = -1

        for condition in conditions:
            rank = self._quality_rank(condition.snow_quality)
            if rank > best_rank:
                best_rank = rank
                best = condition.snow_quality

        return best

    def _get_weighted_snow_score(
        self, conditions: list[WeatherCondition]
    ) -> int | None:
        """Compute weighted 0-100 snow score using same elevation weights as batch endpoint."""
        elevation_weights = {"top": 0.50, "mid": 0.35, "base": 0.15}
        weighted_raw = 0.0
        total_w = 0.0

        for c in conditions:
            if c.quality_score is not None:
                w = elevation_weights.get(c.elevation_level, 0.15)
                weighted_raw += c.quality_score * w
                total_w += w

        if total_w == 0:
            return None

        overall_raw = weighted_raw / total_w
        return score_to_100(overall_raw)

    def _get_weighted_overall_quality(
        self, conditions: list[WeatherCondition]
    ) -> SnowQuality:
        """Compute weighted overall quality using same logic as batch/detail endpoints.

        Uses elevation weights: top 50%, mid 35%, base 15%.
        Falls back to best quality if raw scores not available.
        """
        if not conditions:
            return SnowQuality.UNKNOWN

        elevation_weights = {"top": 0.50, "mid": 0.35, "base": 0.15}
        weighted_raw = 0.0
        total_w = 0.0

        for c in conditions:
            if c.quality_score is not None:
                w = elevation_weights.get(c.elevation_level, 0.15)
                weighted_raw += c.quality_score * w
                total_w += w

        if total_w == 0:
            return self._get_best_quality(conditions)

        overall_raw = weighted_raw / total_w
        return raw_score_to_quality(overall_raw)

    def _quality_rank(self, quality: SnowQuality | str) -> int:
        """Convert quality to numeric rank for comparison."""
        # Handle both enum and string values
        if isinstance(quality, str):
            try:
                quality = SnowQuality(quality)
            except ValueError:
                return 0

        ranks = {
            SnowQuality.EXCELLENT: 6,
            SnowQuality.GOOD: 5,
            SnowQuality.FAIR: 4,
            SnowQuality.POOR: 3,
            SnowQuality.BAD: 2,
            SnowQuality.HORRIBLE: 1,
            SnowQuality.UNKNOWN: 0,
        }
        return ranks.get(quality, 0)

    def _get_average_fresh_snow(self, conditions: list[WeatherCondition]) -> float:
        """Get average fresh snow across elevations."""
        if not conditions:
            return 0.0

        # Use snowfall_after_freeze_cm if available, otherwise fresh_snow_cm
        # NOTE: must use `is not None` — 0.0 is a valid value (no snow since freeze)
        total = sum(
            c.snowfall_after_freeze_cm
            if c.snowfall_after_freeze_cm is not None
            else (c.fresh_snow_cm if c.fresh_snow_cm is not None else 0.0)
            for c in conditions
        )
        return total / len(conditions)

    def _get_total_predicted_snow(self, conditions: list[WeatherCondition]) -> float:
        """Get total predicted snow in next 72h (max across elevations)."""
        if not conditions:
            return 0.0

        return max((c.predicted_snow_72h_cm or 0) for c in conditions)

    def _get_average_temperature(self, conditions: list[WeatherCondition]) -> float:
        """Get average temperature across elevations."""
        if not conditions:
            return 0.0

        return sum(c.current_temp_celsius for c in conditions) / len(conditions)

    def _get_best_confidence(
        self, conditions: list[WeatherCondition]
    ) -> ConfidenceLevel:
        """Get the best confidence level from conditions."""
        if not conditions:
            return ConfidenceLevel.VERY_LOW

        confidence_ranks = {
            ConfidenceLevel.VERY_HIGH: 5,
            ConfidenceLevel.HIGH: 4,
            ConfidenceLevel.MEDIUM: 3,
            ConfidenceLevel.LOW: 2,
            ConfidenceLevel.VERY_LOW: 1,
        }

        best = ConfidenceLevel.VERY_LOW
        best_rank = 0

        for condition in conditions:
            rank = confidence_ranks.get(condition.confidence_level, 0)
            if rank > best_rank:
                best_rank = rank
                best = condition.confidence_level

        return best

    def _calculate_quality_score(self, quality: SnowQuality) -> float:
        """Calculate quality score (0-1)."""
        return self.QUALITY_SCORES.get(quality, 0.3)

    def _calculate_distance_score(self, distance_km: float) -> float:
        """
        Calculate distance score (0-1, closer is better).

        Uses exponential decay:
        - Score = 1.0 at distance = 0
        - Score = 0.5 at distance = MAX_PRACTICAL_DISTANCE_KM
        - Score approaches 0 as distance increases
        """
        if distance_km <= self.IDEAL_DISTANCE_KM:
            return 1.0

        # Exponential decay
        import math

        decay_rate = math.log(2) / (
            self.MAX_PRACTICAL_DISTANCE_KM - self.IDEAL_DISTANCE_KM
        )
        adjusted_distance = distance_km - self.IDEAL_DISTANCE_KM
        return math.exp(-decay_rate * adjusted_distance)

    def _calculate_fresh_snow_score(
        self, fresh_cm: float, predicted_cm: float
    ) -> float:
        """
        Calculate fresh/predicted snow score (0-1) using logarithmic scale.

        Uses log scale so there's always meaningful differentiation between
        resorts with different amounts of snow, even at high values.

        Approximate scores:
        - 0 cm = 0.0
        - 5 cm = 0.30
        - 10 cm = 0.46
        - 20 cm = 0.61
        - 50 cm = 0.79
        - 100 cm = 0.91
        - 150+ cm = 1.0
        """
        import math

        # Combine fresh and predicted (predicted counts less)
        combined_cm = fresh_cm + (predicted_cm * 0.5)

        if combined_cm <= 0:
            return 0.0

        # Log scale: log(1 + x/5) normalized so 150cm = 1.0
        max_reference = 150.0  # cm at which score reaches 1.0
        score = math.log(1 + combined_cm / 5) / math.log(1 + max_reference / 5)
        return min(1.0, score)

    def _calculate_significance(self, resort: Resort) -> float:
        """Calculate resort significance weight based on vertical drop.

        Larger resorts with more vertical are weighted higher in global rankings
        to prevent tiny resorts from dominating when they happen to have good snow.

        Scale: 0.15 (tiny, <200m drop) to 1.0 (major, 2000m+ drop).
        """
        if not resort.elevation_points or len(resort.elevation_points) < 2:
            return 0.5  # Unknown size, neutral weight

        elevations = [p.elevation_meters for p in resort.elevation_points]
        vertical_drop = max(elevations) - min(elevations)

        # Linear scale: 200m = 0.15, 2000m = 1.0
        return min(1.0, 0.15 + (vertical_drop / 2000.0) * 0.85)

    def _build_elevation_summary(
        self, conditions: list[WeatherCondition]
    ) -> dict[str, dict[str, Any]]:
        """Build elevation conditions summary."""
        summary = {}
        for condition in conditions:
            summary[condition.elevation_level] = {
                "quality": condition.snow_quality.value
                if isinstance(condition.snow_quality, SnowQuality)
                else condition.snow_quality,
                "temp_celsius": condition.current_temp_celsius,
                "fresh_snow_cm": condition.snowfall_after_freeze_cm
                or condition.fresh_snow_cm,
                "snowfall_24h_cm": condition.snowfall_24h_cm,
                "predicted_24h_cm": condition.predicted_snow_24h_cm or 0,
            }
        return summary

    def _generate_reason(
        self,
        resort: Resort,
        distance_km: float,
        best_quality: SnowQuality | str,
        avg_fresh_snow: float,
        total_predicted_snow: float,
    ) -> str:
        """Generate a human-readable recommendation reason."""
        parts = []

        # Quality - handle both enum and string values
        quality_value = (
            best_quality.value if hasattr(best_quality, "value") else str(best_quality)
        )

        if quality_value == "excellent":
            parts.append("Excellent powder conditions")
        elif quality_value == "good":
            parts.append("Good snow conditions")
        elif quality_value == "fair":
            parts.append("Fair conditions")
        else:
            parts.append(f"{quality_value.title()} conditions")

        # Fresh snow
        if avg_fresh_snow >= 10:
            parts.append(f"{avg_fresh_snow:.0f}cm of fresh snow")
        elif avg_fresh_snow >= 5:
            parts.append(f"{avg_fresh_snow:.0f}cm fresh")

        # Predicted snow
        if total_predicted_snow >= 20:
            parts.append(f"{total_predicted_snow:.0f}cm expected in next 72h")
        elif total_predicted_snow >= 10:
            parts.append(f"More snow coming ({total_predicted_snow:.0f}cm)")

        # Distance
        if distance_km <= 100:
            parts.append(f"only {distance_km:.0f}km away")
        elif distance_km <= 200:
            parts.append(f"{distance_km:.0f}km drive")

        return ". ".join(parts) + "." if parts else "Recommended resort."

    def _generate_global_reason(
        self,
        resort: Resort,
        best_quality: SnowQuality,
        avg_fresh_snow: float,
        total_predicted_snow: float,
    ) -> str:
        """Generate reason for global recommendation (no distance)."""
        parts = []

        if best_quality == SnowQuality.EXCELLENT:
            parts.append("Top-rated powder conditions")
        elif best_quality == SnowQuality.GOOD:
            parts.append("Good snow conditions")
        elif best_quality == SnowQuality.FAIR:
            parts.append("Fair conditions")

        if avg_fresh_snow >= 15:
            parts.append(f"{avg_fresh_snow:.0f}cm of fresh snow")
        elif avg_fresh_snow >= 5:
            parts.append(f"{avg_fresh_snow:.0f}cm fresh snow")

        if total_predicted_snow >= 30:
            parts.append(f"Major storm incoming ({total_predicted_snow:.0f}cm)")
        elif total_predicted_snow >= 15:
            parts.append(f"More snow expected ({total_predicted_snow:.0f}cm)")

        # Add location context - attach to last part to avoid "at" starting a sentence
        location = f"at {resort.name}, {resort.country}"
        if parts:
            return ". ".join(parts) + f" {location}."
        else:
            return f"Recommended resort: {resort.name}, {resort.country}."
