"""Snow quality assessment service."""

from datetime import datetime
from typing import Dict, List

from ..models.weather import (
    ConfidenceLevel,
    SnowQuality,
    SnowQualityAlgorithm,
    WeatherCondition,
)


class SnowQualityService:
    """Service for assessing snow quality based on weather conditions."""

    def __init__(self, algorithm_config: SnowQualityAlgorithm = None):
        """Initialize the service with algorithm configuration."""
        self.algorithm = algorithm_config or SnowQualityAlgorithm()

    def assess_snow_quality(
        self, weather: WeatherCondition
    ) -> tuple[SnowQuality, float, ConfidenceLevel]:
        """
        Assess snow quality based on weather conditions.

        Returns:
            tuple: (snow_quality, fresh_snow_estimate_cm, confidence_level)
        """
        # Calculate temperature impact
        temp_score = self._calculate_temperature_score(
            weather.current_temp_celsius,
            weather.max_temp_celsius,
            weather.hours_above_ice_threshold,
        )

        # Calculate time-based degradation
        time_score = self._calculate_time_degradation_score(weather.timestamp)

        # Calculate snowfall benefit
        snowfall_score = self._calculate_snowfall_score(
            weather.snowfall_24h_cm, weather.snowfall_48h_cm, weather.snowfall_72h_cm
        )

        # Combine scores with weights
        overall_score = (
            self.algorithm.temperature_weight * temp_score
            + self.algorithm.time_weight * time_score
            + self.algorithm.snowfall_weight * snowfall_score
        )

        # Apply source confidence multiplier
        source_multiplier = self.algorithm.source_confidence_multiplier.get(
            weather.source_confidence, 0.5
        )
        adjusted_score = overall_score * source_multiplier

        # Determine quality level
        snow_quality = self._score_to_quality(adjusted_score)

        # Estimate fresh snow amount
        fresh_snow_cm = self._estimate_fresh_snow(weather, temp_score, time_score)

        # Calculate confidence level
        confidence = self._calculate_confidence_level(weather, source_multiplier)

        return snow_quality, fresh_snow_cm, confidence

    def _calculate_temperature_score(
        self, current_temp: float, max_temp: float, hours_above_threshold: float
    ) -> float:
        """Calculate score based on temperature conditions (0.0 = worst, 1.0 = best)."""
        # Optimal temperature range: -10°C to -2°C
        if -10 <= current_temp <= -2:
            temp_score = 1.0
        elif current_temp < -10:
            # Too cold, but still good
            temp_score = 0.8
        elif current_temp <= 0:
            # Getting warmer, slight degradation
            temp_score = 0.7 - (current_temp + 2) * 0.1
        else:
            # Above freezing, rapid degradation
            temp_score = max(0.0, 0.5 - current_temp * 0.1)

        # Penalize for time spent above ice formation threshold
        if hours_above_threshold > 0:
            ice_penalty = min(
                0.8, hours_above_threshold / self.algorithm.ice_formation_hours
            )
            temp_score *= 1.0 - ice_penalty

        # Additional penalty for high maximum temperatures
        if max_temp > self.algorithm.ice_formation_temp_celsius:
            max_temp_penalty = min(
                0.5, (max_temp - self.algorithm.ice_formation_temp_celsius) * 0.1
            )
            temp_score *= 1.0 - max_temp_penalty

        return max(0.0, min(1.0, temp_score))

    def _calculate_time_degradation_score(self, timestamp: str) -> float:
        """Calculate score based on time since conditions were recorded."""
        try:
            condition_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(condition_time.tzinfo)
            hours_since = (now - condition_time).total_seconds() / 3600

            # Fresh conditions get full score
            if hours_since <= 1:
                return 1.0
            # Linear degradation over 48 hours
            elif hours_since <= self.algorithm.fresh_snow_validity_hours:
                return (
                    1.0
                    - (hours_since - 1)
                    / (self.algorithm.fresh_snow_validity_hours - 1)
                    * 0.7
                )
            else:
                # Old conditions get low score
                return 0.1

        except (ValueError, TypeError):
            # Invalid timestamp, assume old data
            return 0.3

    def _calculate_snowfall_score(
        self, snow_24h: float, snow_48h: float, snow_72h: float
    ) -> float:
        """Calculate score based on recent snowfall amounts."""
        # Handle None values by using available data
        snow_24h = snow_24h or 0.0
        snow_48h = snow_48h if snow_48h is not None else snow_24h
        snow_72h = snow_72h if snow_72h is not None else snow_48h

        # Weight recent snowfall more heavily
        weighted_snowfall = (
            snow_24h * 0.6 + (snow_48h - snow_24h) * 0.3 + (snow_72h - snow_48h) * 0.1
        )

        # Score based on snowfall amount
        if weighted_snowfall >= 20:  # Excellent snowfall
            return 1.0
        elif weighted_snowfall >= 10:  # Good snowfall
            return 0.7 + (weighted_snowfall - 10) * 0.03
        elif weighted_snowfall >= 5:  # Fair snowfall
            return 0.4 + (weighted_snowfall - 5) * 0.06
        elif weighted_snowfall > 0:  # Some snowfall
            return 0.2 + weighted_snowfall * 0.04
        else:  # No snowfall
            return 0.0

    def _score_to_quality(self, score: float) -> SnowQuality:
        """Convert numerical score to snow quality enum."""
        if score >= 0.8:
            return SnowQuality.EXCELLENT
        elif score >= 0.6:
            return SnowQuality.GOOD
        elif score >= 0.4:
            return SnowQuality.FAIR
        elif score >= 0.2:
            return SnowQuality.POOR
        else:
            return SnowQuality.BAD

    def _estimate_fresh_snow(
        self, weather: WeatherCondition, temp_score: float, time_score: float
    ) -> float:
        """Estimate amount of fresh (non-iced) snow in cm."""
        base_snow = weather.snowfall_24h_cm or 0.0
        snowfall_48h = weather.snowfall_48h_cm or 0.0

        # Apply degradation based on temperature and time
        degradation_factor = temp_score * 0.6 + time_score * 0.4

        # Estimate how much snow remains fresh
        fresh_snow = base_snow * degradation_factor

        # Add some from 48h snowfall if recent enough
        if snowfall_48h > base_snow and time_score > 0.3:
            additional_fresh = (snowfall_48h - base_snow) * degradation_factor * 0.5
            fresh_snow += additional_fresh

        return round(max(0.0, fresh_snow), 1)

    def _calculate_confidence_level(
        self, weather: WeatherCondition, source_multiplier: float
    ) -> ConfidenceLevel:
        """Calculate overall confidence in the assessment."""
        base_confidence = weather.source_confidence

        # Adjust based on data completeness
        data_completeness = self._assess_data_completeness(weather)

        if data_completeness < 0.5:
            # Downgrade confidence for incomplete data
            confidence_levels = list(ConfidenceLevel)
            current_index = confidence_levels.index(base_confidence)
            new_index = min(len(confidence_levels) - 1, current_index + 1)
            return confidence_levels[new_index]
        elif data_completeness > 0.8 and source_multiplier > 0.8:
            # Upgrade confidence for complete, reliable data
            confidence_levels = list(ConfidenceLevel)
            current_index = confidence_levels.index(base_confidence)
            new_index = max(0, current_index - 1)
            return confidence_levels[new_index]
        else:
            return base_confidence

    def _assess_data_completeness(self, weather: WeatherCondition) -> float:
        """Assess how complete the weather data is (0.0 to 1.0)."""
        required_fields = [
            weather.current_temp_celsius is not None,
            weather.min_temp_celsius is not None,
            weather.max_temp_celsius is not None,
            weather.snowfall_24h_cm is not None,
            weather.hours_above_ice_threshold is not None,
        ]

        optional_fields = [
            weather.snowfall_48h_cm is not None and weather.snowfall_48h_cm > 0,
            weather.humidity_percent is not None,
            weather.wind_speed_kmh is not None,
            weather.weather_description is not None,
        ]

        required_score = sum(required_fields) / len(required_fields)
        optional_score = sum(optional_fields) / len(optional_fields)

        # Weight required fields more heavily
        return required_score * 0.8 + optional_score * 0.2

    def bulk_assess_resort_conditions(
        self, conditions: list[WeatherCondition]
    ) -> dict[str, list[tuple]]:
        """
        Assess snow quality for multiple elevation points at a resort.

        Returns:
            Dict mapping elevation levels to (quality, fresh_snow, confidence) tuples
        """
        results = {}
        for condition in conditions:
            quality, fresh_snow, confidence = self.assess_snow_quality(condition)
            if condition.elevation_level not in results:
                results[condition.elevation_level] = []
            results[condition.elevation_level].append((quality, fresh_snow, confidence))

        return results
