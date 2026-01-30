"""Recommendation service for finding best snow conditions near user."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from models.resort import Resort
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from utils.geo_utils import haversine_distance


@dataclass
class ResortRecommendation:
    """A resort recommendation with scoring details."""

    resort: Resort
    distance_km: float
    distance_miles: float
    snow_quality: SnowQuality
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
            "resort": self.resort.model_dump() if hasattr(self.resort, "model_dump") else self.resort,
            "distance_km": self.distance_km,
            "distance_miles": self.distance_miles,
            "snow_quality": self.snow_quality.value if isinstance(self.snow_quality, SnowQuality) else self.snow_quality,
            "quality_score": self.quality_score,
            "distance_score": self.distance_score,
            "combined_score": self.combined_score,
            "fresh_snow_cm": self.fresh_snow_cm,
            "predicted_snow_72h_cm": self.predicted_snow_72h_cm,
            "current_temp_celsius": self.current_temp_celsius,
            "confidence_level": self.confidence_level.value if isinstance(self.confidence_level, ConfidenceLevel) else self.confidence_level,
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
        # Get nearby resorts
        nearby_resorts = self.resort_service.get_nearby_resorts(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=100,  # Get more than needed for filtering
        )

        if not nearby_resorts:
            return []

        recommendations = []

        for resort, distance_km in nearby_resorts:
            # Get latest conditions for all elevations
            conditions = self._get_resort_conditions(resort.resort_id)

            if not conditions:
                # Skip resorts with no condition data
                continue

            # Calculate aggregate metrics across elevations
            best_quality = self._get_best_quality(conditions)
            avg_fresh_snow = self._get_average_fresh_snow(conditions)
            total_predicted_snow = self._get_total_predicted_snow(conditions)
            avg_temp = self._get_average_temperature(conditions)
            best_confidence = self._get_best_confidence(conditions)

            # Apply minimum quality filter
            if min_quality and self._quality_rank(best_quality) < self._quality_rank(min_quality):
                continue

            # Calculate scores
            quality_score = self._calculate_quality_score(best_quality)
            distance_score = self._calculate_distance_score(distance_km)
            fresh_snow_score = self._calculate_fresh_snow_score(avg_fresh_snow, total_predicted_snow)

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
                best_quality=best_quality,
                avg_fresh_snow=avg_fresh_snow,
                total_predicted_snow=total_predicted_snow,
            )

            recommendations.append(
                ResortRecommendation(
                    resort=resort,
                    distance_km=round(distance_km, 1),
                    distance_miles=round(distance_km * 0.621371, 1),
                    snow_quality=best_quality,
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

        # Sort by combined score (descending)
        recommendations.sort(key=lambda r: r.combined_score, reverse=True)

        return recommendations[:limit]

    def get_best_conditions_globally(
        self,
        limit: int = 10,
        min_quality: SnowQuality | None = None,
    ) -> list[ResortRecommendation]:
        """
        Get resorts with the best snow conditions globally (no location bias).

        Optimized to fetch all conditions in a single batch query instead of
        making individual queries per resort.

        Args:
            limit: Maximum number of results
            min_quality: Minimum snow quality filter

        Returns:
            List of recommendations sorted by snow quality
        """
        # Get all resorts
        all_resorts = self.resort_service.get_all_resorts()
        resort_map = {r.resort_id: r for r in all_resorts}

        # Fetch ALL conditions in a single batch query (much faster than N queries)
        all_conditions = self.weather_service.get_all_latest_conditions()

        recommendations = []

        for resort_id, conditions in all_conditions.items():
            resort = resort_map.get(resort_id)
            if not resort or not conditions:
                continue

            best_quality = self._get_best_quality(conditions)

            if min_quality and self._quality_rank(best_quality) < self._quality_rank(min_quality):
                continue

            avg_fresh_snow = self._get_average_fresh_snow(conditions)
            total_predicted_snow = self._get_total_predicted_snow(conditions)
            avg_temp = self._get_average_temperature(conditions)
            best_confidence = self._get_best_confidence(conditions)

            quality_score = self._calculate_quality_score(best_quality)
            fresh_snow_score = self._calculate_fresh_snow_score(avg_fresh_snow, total_predicted_snow)

            # For global ranking, only quality matters
            combined_score = 0.7 * quality_score + 0.3 * fresh_snow_score

            elevation_conditions = self._build_elevation_summary(conditions)

            reason = self._generate_global_reason(
                resort=resort,
                best_quality=best_quality,
                avg_fresh_snow=avg_fresh_snow,
                total_predicted_snow=total_predicted_snow,
            )

            recommendations.append(
                ResortRecommendation(
                    resort=resort,
                    distance_km=0,  # N/A for global
                    distance_miles=0,
                    snow_quality=best_quality,
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

        recommendations.sort(key=lambda r: r.combined_score, reverse=True)
        return recommendations[:limit]

    def _get_resort_conditions(self, resort_id: str) -> list[WeatherCondition]:
        """Get latest conditions for a resort."""
        try:
            return self.weather_service.get_conditions_for_resort(resort_id, hours_back=6)
        except Exception:
            return []

    def _get_best_quality(self, conditions: list[WeatherCondition]) -> SnowQuality:
        """Get the best snow quality across all elevations."""
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
        total = sum(
            c.snowfall_after_freeze_cm if c.snowfall_after_freeze_cm else c.fresh_snow_cm
            for c in conditions
        )
        return total / len(conditions)

    def _get_total_predicted_snow(self, conditions: list[WeatherCondition]) -> float:
        """Get total predicted snow in next 72h (max across elevations)."""
        if not conditions:
            return 0.0

        return max(
            (c.predicted_snow_72h_cm or 0) for c in conditions
        )

    def _get_average_temperature(self, conditions: list[WeatherCondition]) -> float:
        """Get average temperature across elevations."""
        if not conditions:
            return 0.0

        return sum(c.current_temp_celsius for c in conditions) / len(conditions)

    def _get_best_confidence(self, conditions: list[WeatherCondition]) -> ConfidenceLevel:
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
        decay_rate = math.log(2) / (self.MAX_PRACTICAL_DISTANCE_KM - self.IDEAL_DISTANCE_KM)
        adjusted_distance = distance_km - self.IDEAL_DISTANCE_KM
        return math.exp(-decay_rate * adjusted_distance)

    def _calculate_fresh_snow_score(self, fresh_cm: float, predicted_cm: float) -> float:
        """
        Calculate fresh/predicted snow score (0-1).

        Scoring:
        - 0 cm = 0.0
        - 10 cm = 0.5
        - 20+ cm = 1.0
        """
        # Combine fresh and predicted (predicted counts less)
        combined_cm = fresh_cm + (predicted_cm * 0.5)

        if combined_cm >= 20:
            return 1.0
        elif combined_cm <= 0:
            return 0.0
        else:
            return combined_cm / 20.0

    def _build_elevation_summary(self, conditions: list[WeatherCondition]) -> dict[str, dict[str, Any]]:
        """Build elevation conditions summary."""
        summary = {}
        for condition in conditions:
            summary[condition.elevation_level] = {
                "quality": condition.snow_quality.value if isinstance(condition.snow_quality, SnowQuality) else condition.snow_quality,
                "temp_celsius": condition.current_temp_celsius,
                "fresh_snow_cm": condition.snowfall_after_freeze_cm or condition.fresh_snow_cm,
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
        quality_value = best_quality.value if hasattr(best_quality, "value") else str(best_quality)

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
            parts.append("Excellent snow coverage")

        if avg_fresh_snow >= 15:
            parts.append(f"{avg_fresh_snow:.0f}cm of fresh powder")
        elif avg_fresh_snow >= 5:
            parts.append(f"{avg_fresh_snow:.0f}cm fresh snow")

        if total_predicted_snow >= 30:
            parts.append(f"Major storm incoming ({total_predicted_snow:.0f}cm)")
        elif total_predicted_snow >= 15:
            parts.append(f"More snow expected ({total_predicted_snow:.0f}cm)")

        # Add location context
        parts.append(f"at {resort.name}, {resort.country}")

        return ". ".join(parts) + "."
