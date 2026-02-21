"""Snow quality assessment service."""

from datetime import datetime
from typing import Dict, List

from models.weather import (
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
        self, weather: WeatherCondition, elevation_m: float | None = None
    ) -> tuple[SnowQuality, float, ConfidenceLevel, float]:
        """
        Assess snow quality based on weather conditions.

        Uses ML model (v2 neural network) as primary scorer when available,
        falls back to heuristic algorithm.

        Returns:
            tuple: (snow_quality, fresh_snow_estimate_cm, confidence_level, raw_score)
            raw_score is on 1.0-6.0 scale (1=horrible, 6=excellent)
        """
        # Try ML-based scoring when we have raw hourly data (exact features).
        # The model was trained on features computed from raw Open-Meteo hourly data,
        # so it's only reliable when we can extract the same exact features.
        # Without raw_data, fall through to the heuristic algorithm.
        try:
            from services.ml_scorer import (
                extract_features_from_raw_data,
                predict_quality,
            )

            raw_features = extract_features_from_raw_data(weather, elevation_m)
            if raw_features is not None:
                ml_quality, ml_score = predict_quality(weather, elevation_m)
                if ml_quality != SnowQuality.UNKNOWN:
                    # Post-ML adjustments for features the model doesn't see.
                    # snow_depth_cm (scraped base depth) isn't a model feature.
                    # Apply a floor: confirmed deep base means skiing IS possible.
                    snow_depth = getattr(weather, "snow_depth_cm", None)
                    if snow_depth is not None and snow_depth >= 50:
                        if ml_quality == SnowQuality.HORRIBLE:
                            ml_quality = SnowQuality.BAD
                        if snow_depth >= 100 and ml_quality == SnowQuality.BAD:
                            ml_quality = SnowQuality.POOR

                    fresh_snow_cm = self._estimate_fresh_snow_simple(weather)
                    confidence = self._calculate_confidence_level(
                        weather,
                        self.algorithm.source_confidence_multiplier.get(
                            weather.source_confidence, 0.5
                        ),
                    )
                    return ml_quality, fresh_snow_cm, confidence, ml_score
        except Exception as e:
            import logging

            logging.getLogger("snow_quality_service.ml").warning(
                "ML failed for %s: %s",
                getattr(weather, "resort_id", "?"),
                e,
            )

        # Heuristic fallback
        # Calculate temperature impact
        temp_score = self._calculate_temperature_score(
            weather.current_temp_celsius,
            weather.max_temp_celsius,
            weather.hours_above_ice_threshold,
        )

        # Calculate time-based degradation
        time_score = self._calculate_time_degradation_score(weather.timestamp)

        # Calculate snowfall benefit (using new fresh powder metrics if available)
        snowfall_after_freeze = getattr(weather, "snowfall_after_freeze_cm", 0.0) or 0.0
        hours_since_snowfall = getattr(weather, "hours_since_last_snowfall", None)

        # Use snowfall-after-freeze for scoring if available (more accurate)
        if snowfall_after_freeze > 0:
            snowfall_score = self._calculate_fresh_powder_score(
                snowfall_after_freeze,
                hours_since_snowfall,
                weather.current_temp_celsius,
            )
        else:
            # Fallback to traditional snowfall scoring
            snowfall_score = self._calculate_snowfall_score(
                weather.snowfall_24h_cm,
                weather.snowfall_48h_cm,
                weather.snowfall_72h_cm,
            )

        # Combine scores with weights
        overall_score = (
            self.algorithm.temperature_weight * temp_score
            + self.algorithm.time_weight * time_score
            + self.algorithm.snowfall_weight * snowfall_score
        )

        # Source confidence is used for the confidence_level field only,
        # NOT as a multiplier on quality score. Quality should reflect
        # actual conditions; confidence separately indicates data reliability.
        source_multiplier = self.algorithm.source_confidence_multiplier.get(
            weather.source_confidence, 0.5
        )
        adjusted_score = overall_score

        # Temperature adjustment - be conservative with "not skiable" designation
        # Warm temps degrade conditions but don't make skiing impossible if base exists
        current_temp = weather.current_temp_celsius
        snow_depth = getattr(weather, "snow_depth_cm", None)
        currently_warming = getattr(weather, "currently_warming", False)

        # Determine if the model snow_depth is reliable enough for hard caps.
        # Open-Meteo forecast model snow_depth is grid-level (~10-25km resolution)
        # and often wildly inaccurate for mountain terrain (e.g., reporting 11cm
        # when actual depth is 200cm+). Don't let it override strong fresh snow evidence.
        snow_depth_reliable = True
        if snow_depth is not None:
            # Consistency check: if accumulated fresh snow exceeds the model's
            # total depth estimate, the model is clearly wrong
            if snowfall_after_freeze > 0 and snow_depth < snowfall_after_freeze:
                snow_depth_reliable = False
            # For medium/low confidence sources (weather models), snow_depth
            # is a rough estimate - don't use it for hard quality caps
            source_conf = getattr(weather, "source_confidence", None)
            if source_conf in (
                ConfidenceLevel.MEDIUM,
                ConfidenceLevel.LOW,
                ConfidenceLevel.VERY_LOW,
            ):
                snow_depth_reliable = False

        # CRITICAL: Only mark as NOT SKIABLE when we KNOW there's no snow
        # Require both model AND snowfall data to agree on "no snow"
        # Also require reliable depth data - Open-Meteo often reports 0cm when
        # there is clearly snow (e.g., Vail base/mid in February)
        if snow_depth is not None and snow_depth <= 0 and snow_depth_reliable:
            if snowfall_after_freeze <= 0 and (weather.snowfall_24h_cm or 0) <= 0:
                adjusted_score = 0.0  # HORRIBLE - confirmed no snow
        if current_temp >= 20.0:
            # True summer temps (>20°C) - extremely unlikely to have snow
            adjusted_score = min(adjusted_score, 0.02)  # HORRIBLE
        elif current_temp >= 15.0 and snow_depth is None:
            # Very warm, unknown snow depth - probably no skiable conditions
            # But cap at BAD, not HORRIBLE, since we're not certain
            adjusted_score = min(adjusted_score, 0.15)

        # Snow depth quality adjustment - base depth affects ski quality
        # Only apply hard caps when snow_depth data is reliable (resort-reported
        # or consistent with observed snowfall). Weather model snow_depth is too
        # inaccurate for mountain terrain to use as a hard cap.
        if snow_depth is not None and snow_depth > 0 and snow_depth_reliable:
            if snow_depth < 20:
                # Very thin cover (<20cm/8") - rocks and grass likely exposed
                # Dangerous conditions, cap at BAD (Icy)
                adjusted_score = min(adjusted_score, 0.15)
            elif snow_depth < 50:
                # Thin cover (20-50cm/8-20") - adequate but not ideal
                # Cap at FAIR - conditions are skiable but marginal
                adjusted_score = min(adjusted_score, 0.45)
            elif snow_depth >= 100:
                # Deep base (100cm+/40"+) - excellent coverage
                # Boost score slightly for deep powder base
                adjusted_score = min(1.0, adjusted_score * 1.1)

            # Floor: substantial reliable snow depth means skiing IS possible,
            # even if conditions are degraded (warm, icy, no fresh snow).
            # 50+cm confirmed base should never be HORRIBLE (not skiable).
            if snow_depth >= 50:
                adjusted_score = max(adjusted_score, 0.20)  # At least POOR

        # Apply gradual degradation for warm temps (but don't go to HORRIBLE)
        # Warm temps mean softer snow, but skiing is still possible with base
        if current_temp >= 10.0:
            # Warm spring-like conditions - cap at POOR
            adjusted_score = min(adjusted_score, 0.25)
        elif current_temp >= 5.0:
            # Moderately warm - cap at FAIR (conditions are degrading but skiable)
            adjusted_score = min(adjusted_score, 0.45)

        # Fresh powder assessment - affects quality but not skiability
        # No fresh snow = harder/icier surface, but still skiable
        last_freeze_hours = getattr(weather, "last_freeze_thaw_hours_ago", None)
        if snowfall_after_freeze <= 0 and (weather.snowfall_24h_cm or 0) <= 0:
            # No fresh snow at all = harder surface conditions
            if last_freeze_hours is not None and last_freeze_hours >= 336:
                # No freeze-thaw in 14+ days: snow is aged but never refrozen
                # This is packed/groomed powder, not icy.
                if current_temp <= 0:
                    # Below freezing, never refrozen - cold packed powder
                    adjusted_score = min(adjusted_score, 0.45)  # FAIR
                else:
                    # Above freezing - softening old snow
                    adjusted_score = min(adjusted_score, 0.25)  # POOR
            else:
                # Recent freeze-thaw occurred - snow texture depends on temp
                # Use smooth gradient around 0°C instead of hard cutoff
                if current_temp > 2.0:
                    # Clearly above freezing = SOFT/SLUSHY
                    adjusted_score = min(adjusted_score, 0.25)  # POOR
                elif current_temp > 0.0:
                    # Transition zone (0-2°C): blend between icy and soft
                    # Linear interpolation: 0°C→0.15 (BAD), 2°C→0.25 (POOR)
                    blend = current_temp / 2.0
                    cap = 0.15 + blend * 0.10
                    adjusted_score = min(adjusted_score, cap)
                else:
                    # Below freezing = HARD/ICY (frozen after thaw)
                    adjusted_score = min(adjusted_score, 0.15)  # BAD = "Icy"
        elif snowfall_after_freeze < 5.08:  # Less than 2 inches
            # Thin-to-moderate fresh snow on a base - use smooth gradient.
            # Old code had a cliff at 2.54cm: <2.54→BAD, >=2.54→EXCELLENT.
            # Fix: continuous gradient from BAD at 0cm through FAIR at 2.54cm
            # to GOOD at 5.08cm, eliminating quality jumps from tiny differences.
            if last_freeze_hours is not None and last_freeze_hours < 336:
                # Recent freeze-thaw: fresh snow gradually covers refrozen base
                if snowfall_after_freeze < 2.54:
                    # 0-1 inch: BAD→FAIR gradient
                    blend = snowfall_after_freeze / 2.54
                    if current_temp <= 0:
                        cap = 0.15 + blend * 0.30  # 0→0.15(BAD), 2.54→0.45(FAIR)
                    else:
                        cap = 0.20 + blend * 0.10  # 0→0.20(POOR), 2.54→0.30(POOR)
                else:
                    # 1-2 inches: FAIR→GOOD gradient
                    blend = (snowfall_after_freeze - 2.54) / (5.08 - 2.54)
                    if current_temp <= 0:
                        cap = 0.45 + blend * 0.25  # 2.54→0.45(FAIR), 5.08→0.70(GOOD)
                    else:
                        cap = 0.30 + blend * 0.15  # 2.54→0.30(POOR), 5.08→0.45(FAIR)
                adjusted_score = min(adjusted_score, cap)
            else:
                # No recent freeze: fresh on packed powder base
                if current_temp <= 0:
                    adjusted_score = min(adjusted_score, 0.45)  # FAIR
                else:
                    adjusted_score = min(adjusted_score, 0.25)  # POOR (Soft)

        # Determine quality level
        snow_quality = self._score_to_quality(adjusted_score)

        # Estimate fresh snow amount
        fresh_snow_cm = self._estimate_fresh_snow(weather, temp_score, time_score)

        # Calculate confidence level
        confidence = self._calculate_confidence_level(weather, source_multiplier)

        # Convert heuristic 0-1 score to ML-equivalent 1-6 scale
        raw_score = adjusted_score * 5.0 + 1.0

        return snow_quality, fresh_snow_cm, confidence, raw_score

    def _calculate_fresh_powder_score(
        self,
        snowfall_after_freeze: float,
        hours_since_snowfall: float | None,
        current_temp: float,
    ) -> float:
        """Calculate score based on non-refrozen snow.

        This is the key metric - snow that fell AFTER the last ice formation event.
        Ice forms with multiple thresholds: 3h@+3°C, 6h@+2°C, or 8h@+1°C.

        Snow quality ratings based on fresh powder depth (in inches):
        - Excellent: 3+ inches (7.62+ cm)
        - Good: 2+ inches (5.08+ cm)
        - Fair: 1+ inch (2.54+ cm)
        - Bad: <1 inch (<2.54 cm)

        Higher scores for:
        - More snow since the last ice event (non-refrozen coverage)
        - Colder current temperatures (not currently forming ice)
        """
        # Convert thresholds from inches to cm
        EXCELLENT_CM = 7.62  # 3 inches
        GOOD_CM = 5.08  # 2 inches
        FAIR_CM = 2.54  # 1 inch

        # Base score from amount of non-refrozen snow
        if snowfall_after_freeze >= EXCELLENT_CM:  # 3+ inches = excellent
            amount_score = 1.0
        elif snowfall_after_freeze >= GOOD_CM:  # 2-3 inches = good
            # Linear interpolation from 0.75 to 1.0
            amount_score = (
                0.75
                + (snowfall_after_freeze - GOOD_CM) / (EXCELLENT_CM - GOOD_CM) * 0.25
            )
        elif snowfall_after_freeze >= FAIR_CM:  # 1-2 inches = fair
            # Linear interpolation from 0.5 to 0.75
            amount_score = (
                0.5 + (snowfall_after_freeze - FAIR_CM) / (GOOD_CM - FAIR_CM) * 0.25
            )
        elif snowfall_after_freeze > 0:  # <1 inch = bad (but not zero)
            # Linear interpolation from 0.1 to 0.5
            amount_score = 0.1 + (snowfall_after_freeze / FAIR_CM) * 0.4
        else:
            # No snow since last ice event = icy base
            return 0.0

        # Temperature factor - is it currently warm enough to form ice?
        # Ice formation thresholds: 3h@+3°C, 6h@+2°C, 8h@+1°C
        if current_temp >= 3.0:
            # Currently at fast ice-forming temps - snow is degrading quickly
            temp_factor = max(0.3, 0.7 - (current_temp - 3.0) * 0.1)
        elif current_temp >= 2.0:
            # At moderate ice-forming temps
            temp_factor = 0.75
        elif current_temp >= 1.0:
            # At slow ice-forming temps
            temp_factor = 0.85
        elif current_temp >= 0:
            # Above freezing but below ice threshold - minimal degradation
            temp_factor = 0.9
        elif current_temp >= -5:
            # Good preservation temps
            temp_factor = 0.95
        else:
            # Cold - excellent preservation
            temp_factor = 1.0

        # Freshness factor - how long since last snowfall
        # Less critical since we're measuring from ice event
        if hours_since_snowfall is not None:
            if hours_since_snowfall <= 12:
                freshness = 1.0  # Recent snow
            elif hours_since_snowfall <= 24:
                freshness = 0.95
            elif hours_since_snowfall <= 48:
                freshness = 0.9
            elif hours_since_snowfall <= 72:
                freshness = 0.85
            else:
                # Snow is old but hasn't refrozen (no ice event since)
                freshness = 0.8
        else:
            freshness = 0.9  # Unknown, assume decent

        final_score = amount_score * temp_factor * freshness
        return max(0.0, min(1.0, final_score))

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
        """Convert numerical score to snow quality enum.

        Thresholds:
        - >= 0.8: EXCELLENT (3+ inches fresh powder)
        - >= 0.6: GOOD (2-3 inches)
        - >= 0.4: FAIR (1-2 inches)
        - >= 0.2: POOR (<1 inch)
        - >= 0.1: BAD (icy, no fresh snow)
        - < 0.1: HORRIBLE (not skiable, melting)
        """
        if score >= 0.8:
            return SnowQuality.EXCELLENT
        elif score >= 0.6:
            return SnowQuality.GOOD
        elif score >= 0.4:
            return SnowQuality.FAIR
        elif score >= 0.2:
            return SnowQuality.POOR
        elif score >= 0.1:
            return SnowQuality.BAD
        else:
            return SnowQuality.HORRIBLE

    def _estimate_fresh_snow_simple(self, weather: WeatherCondition) -> float:
        """Simple fresh snow estimate using available fields."""
        snowfall_after_freeze = getattr(weather, "snowfall_after_freeze_cm", 0.0) or 0.0
        snow_depth = getattr(weather, "snow_depth_cm", None)
        if snowfall_after_freeze > 0:
            # Apply temperature degradation
            currently_warming = getattr(weather, "currently_warming", False)
            if currently_warming and weather.current_temp_celsius > 3.0:
                degradation = min(0.4, (weather.current_temp_celsius - 3.0) * 0.1)
                fresh = max(0.0, snowfall_after_freeze * (1.0 - degradation))
            else:
                fresh = snowfall_after_freeze
            # Cap at snow depth (fresh snow can't exceed total depth on ground)
            if snow_depth and snow_depth > 0:
                fresh = min(fresh, snow_depth)
            return round(fresh, 1)
        return round(max(0.0, weather.snowfall_24h_cm or 0.0), 1)

    def _estimate_fresh_snow(
        self, weather: WeatherCondition, temp_score: float, time_score: float
    ) -> float:
        """Estimate amount of non-refrozen snow in cm.

        This is snow that fell AFTER the last ice formation event
        (4+ consecutive hours at >= 3°C). This snow hasn't had a chance
        to form ice or crust and represents skiable, non-icy coverage.
        """
        # Primary metric: snow that fell after the last ice formation event
        snowfall_after_freeze = getattr(weather, "snowfall_after_freeze_cm", 0.0) or 0.0
        currently_warming = getattr(weather, "currently_warming", False)
        snow_depth = getattr(weather, "snow_depth_cm", None)

        if snowfall_after_freeze > 0:
            fresh_snow = snowfall_after_freeze

            # If currently at ice-forming temps (>= 3°C), apply a degradation factor
            # but don't zero it out - snow doesn't instantly turn to ice
            if currently_warming:
                current_temp = weather.current_temp_celsius
                # Gradual degradation - 10% per degree above 3°C
                degradation = (
                    min(0.4, (current_temp - 3.0) * 0.1) if current_temp > 3.0 else 0.0
                )
                fresh_snow = fresh_snow * (1.0 - degradation)

            # Cap at snow depth (fresh snow can't exceed total depth on ground)
            if snow_depth and snow_depth > 0:
                fresh_snow = min(fresh_snow, snow_depth)

            return round(max(0.0, fresh_snow), 1)
        else:
            # Fallback to traditional estimation if new metric not available
            base_snow = weather.snowfall_24h_cm or 0.0
            snowfall_48h = weather.snowfall_48h_cm or 0.0

            # If there's been significant time above ice threshold, heavily penalize
            hours_above = weather.hours_above_ice_threshold or 0.0
            if hours_above >= 4:
                # Ice likely formed - reduce fresh snow estimate significantly
                ice_factor = max(0.1, 1.0 - (hours_above / 8.0))
            else:
                ice_factor = 1.0

            # Apply degradation based on temperature and time
            degradation_factor = temp_score * 0.6 + time_score * 0.4
            degradation_factor *= ice_factor

            # Estimate how much snow remains non-icy
            fresh_snow = base_snow * degradation_factor

            # Add some from 48h snowfall if conditions allow
            if snowfall_48h > base_snow and time_score > 0.3 and hours_above < 4:
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
            quality, fresh_snow, confidence, raw_score = self.assess_snow_quality(
                condition
            )
            if condition.elevation_level not in results:
                results[condition.elevation_level] = []
            results[condition.elevation_level].append((quality, fresh_snow, confidence))

        return results

    @staticmethod
    def calculate_overall_quality(conditions) -> "SnowQuality":
        """Calculate overall resort quality from per-elevation conditions.

        Uses the best of top/mid elevations (weighted 50/35/15) since base
        elevations in mountain resorts are often warm valley towns that
        nobody actually skis. A warm base shouldn't drag down a resort
        with excellent upper mountain conditions.
        """
        quality_scores = {
            SnowQuality.EXCELLENT: 6,
            SnowQuality.GOOD: 5,
            SnowQuality.FAIR: 4,
            SnowQuality.POOR: 3,
            SnowQuality.BAD: 2,
            SnowQuality.HORRIBLE: 1,
            SnowQuality.UNKNOWN: 0,
        }

        if not conditions:
            return SnowQuality.UNKNOWN

        # Separate by elevation
        scores_by_elevation = {}
        for c in conditions:
            quality = c.snow_quality
            if isinstance(quality, str):
                quality = SnowQuality(quality)
            scores_by_elevation[c.elevation_level] = quality_scores.get(quality, 0)

        if not scores_by_elevation:
            return SnowQuality.UNKNOWN

        # Weighted average: top 50%, mid 35%, base 15%
        weights = {"top": 0.50, "mid": 0.35, "base": 0.15}
        total_weight = 0
        weighted_score = 0
        for level, score in scores_by_elevation.items():
            w = weights.get(level, 0.15)
            weighted_score += score * w
            total_weight += w

        avg_score = weighted_score / total_weight if total_weight > 0 else 0

        if avg_score >= 5.5:
            return SnowQuality.EXCELLENT
        elif avg_score >= 4.5:
            return SnowQuality.GOOD
        elif avg_score >= 3.5:
            return SnowQuality.FAIR
        elif avg_score >= 2.5:
            return SnowQuality.POOR
        elif avg_score >= 1.5:
            return SnowQuality.BAD
        else:
            return SnowQuality.HORRIBLE
