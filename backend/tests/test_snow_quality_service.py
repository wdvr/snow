"""Tests for the snow quality assessment service."""

from datetime import UTC, datetime, timedelta, timezone

from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.snow_quality_service import SnowQualityService


class TestSnowQualityService:
    """Test cases for SnowQualityService."""

    def test_assess_excellent_conditions(
        self, sample_weather_condition, snow_quality_algorithm
    ):
        """Test assessment of excellent snow conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        quality, fresh_snow, confidence = service.assess_snow_quality(
            sample_weather_condition
        )

        assert quality == SnowQuality.EXCELLENT
        assert fresh_snow >= 10.0  # Should have significant fresh snow
        assert confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]

    def test_assess_poor_conditions(
        self, poor_weather_condition, snow_quality_algorithm
    ):
        """Test assessment of poor snow conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        quality, fresh_snow, confidence = service.assess_snow_quality(
            poor_weather_condition
        )

        # With no snow since freeze and currently warming, expect BAD or HORRIBLE
        assert quality in [SnowQuality.POOR, SnowQuality.BAD, SnowQuality.HORRIBLE]
        assert fresh_snow < 3.0  # Should have minimal fresh snow
        assert confidence == ConfidenceLevel.LOW

    def test_temperature_score_calculation(self, snow_quality_algorithm):
        """Test temperature score calculation logic."""
        service = SnowQualityService(snow_quality_algorithm)

        # Optimal temperature should score high
        optimal_score = service._calculate_temperature_score(-5.0, -3.0, 0.0)
        assert optimal_score >= 0.9

        # Warm temperature should score low
        warm_score = service._calculate_temperature_score(5.0, 8.0, 6.0)
        assert warm_score <= 0.2

        # Ice formation hours should reduce score
        ice_affected_score = service._calculate_temperature_score(-2.0, 1.0, 5.0)
        no_ice_score = service._calculate_temperature_score(-2.0, 1.0, 0.0)
        assert ice_affected_score < no_ice_score

    def test_time_degradation_score(self, snow_quality_algorithm):
        """Test time-based degradation scoring."""
        service = SnowQualityService(snow_quality_algorithm)

        # Recent timestamp should score high
        now = datetime.now(UTC)
        recent_timestamp = now.isoformat()
        recent_score = service._calculate_time_degradation_score(recent_timestamp)
        assert recent_score >= 0.9

        # Old timestamp should score low
        old_timestamp = (now - timedelta(hours=50)).isoformat()
        old_score = service._calculate_time_degradation_score(old_timestamp)
        assert old_score <= 0.2

        # Medium age should score moderately
        medium_timestamp = (now - timedelta(hours=12)).isoformat()
        medium_score = service._calculate_time_degradation_score(medium_timestamp)
        assert 0.3 <= medium_score <= 0.9

    def test_snowfall_score_calculation(self, snow_quality_algorithm):
        """Test snowfall amount scoring."""
        service = SnowQualityService(snow_quality_algorithm)

        # Heavy snowfall should score high
        heavy_score = service._calculate_snowfall_score(25.0, 30.0, 35.0)
        assert heavy_score >= 0.9

        # No snowfall should score zero
        no_snow_score = service._calculate_snowfall_score(0.0, 0.0, 0.0)
        assert no_snow_score == 0.0

        # Moderate snowfall should score moderately
        moderate_score = service._calculate_snowfall_score(8.0, 12.0, 15.0)
        assert 0.4 <= moderate_score <= 0.8

    def test_fresh_snow_estimation(
        self, sample_weather_condition, snow_quality_algorithm
    ):
        """Test fresh snow amount estimation."""
        service = SnowQualityService(snow_quality_algorithm)

        # Good conditions should preserve snow since last freeze-thaw
        quality, fresh_snow, confidence = service.assess_snow_quality(
            sample_weather_condition
        )
        # Fresh snow is based on snowfall_after_freeze_cm (non-refrozen snow)
        assert fresh_snow >= sample_weather_condition.snowfall_after_freeze_cm * 0.9

        # Poor conditions (warm temps, high ice formation hours) should reduce fresh snow
        poor_condition = sample_weather_condition.model_copy()
        poor_condition.current_temp_celsius = 5.0
        poor_condition.hours_above_ice_threshold = 8.0
        poor_condition.currently_warming = True

        quality, degraded_fresh_snow, confidence = service.assess_snow_quality(
            poor_condition
        )
        assert degraded_fresh_snow < fresh_snow

    def test_confidence_level_adjustment(
        self, sample_weather_condition, snow_quality_algorithm
    ):
        """Test confidence level adjustments based on data quality."""
        service = SnowQualityService(snow_quality_algorithm)

        # Complete data with high source confidence should maintain/upgrade confidence
        complete_condition = sample_weather_condition.model_copy()
        complete_condition.source_confidence = ConfidenceLevel.VERY_HIGH

        quality, fresh_snow, confidence = service.assess_snow_quality(
            complete_condition
        )
        assert confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]

        # Incomplete data should downgrade confidence
        incomplete_condition = sample_weather_condition.model_copy()
        incomplete_condition.humidity_percent = None
        incomplete_condition.wind_speed_kmh = None
        incomplete_condition.snowfall_48h_cm = None
        incomplete_condition.source_confidence = ConfidenceLevel.LOW

        quality, fresh_snow, low_confidence = service.assess_snow_quality(
            incomplete_condition
        )
        assert low_confidence in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]

    def test_data_completeness_assessment(
        self, sample_weather_condition, snow_quality_algorithm
    ):
        """Test data completeness scoring."""
        service = SnowQualityService(snow_quality_algorithm)

        # Complete data should score high
        complete_score = service._assess_data_completeness(sample_weather_condition)
        assert complete_score >= 0.8

        # Missing optional data should still score reasonably
        # With all required fields (80% weight) and 2/4 optional fields (50% * 20% = 10%)
        # Expected score: 0.8 + 0.1 = 0.9
        partial_condition = sample_weather_condition.model_copy()
        partial_condition.humidity_percent = None
        partial_condition.wind_speed_kmh = None

        partial_score = service._assess_data_completeness(partial_condition)
        assert 0.85 <= partial_score <= 0.95

        # Missing required data should score lower
        # With 3/5 required fields (60%) and 4/4 optional fields (100%)
        # Expected score: 0.6 * 0.8 + 1.0 * 0.2 = 0.68
        incomplete_condition = sample_weather_condition.model_copy()
        incomplete_condition.current_temp_celsius = None
        incomplete_condition.snowfall_24h_cm = None

        incomplete_score = service._assess_data_completeness(incomplete_condition)
        assert incomplete_score < 0.7

    def test_score_to_quality_mapping(self, snow_quality_algorithm):
        """Test the mapping from numerical scores to quality enums."""
        service = SnowQualityService(snow_quality_algorithm)

        assert service._score_to_quality(0.9) == SnowQuality.EXCELLENT
        assert service._score_to_quality(0.7) == SnowQuality.GOOD
        assert service._score_to_quality(0.5) == SnowQuality.FAIR
        assert service._score_to_quality(0.3) == SnowQuality.POOR
        assert service._score_to_quality(0.15) == SnowQuality.BAD
        assert service._score_to_quality(0.05) == SnowQuality.HORRIBLE

    def test_bulk_assessment(self, snow_quality_algorithm):
        """Test bulk assessment of multiple conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        conditions = [
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="base",
                timestamp="2026-01-20T10:00:00Z",
                current_temp_celsius=-3.0,
                min_temp_celsius=-5.0,
                max_temp_celsius=-1.0,
                snowfall_24h_cm=10.0,
                hours_above_ice_threshold=1.0,
                snow_quality=SnowQuality.GOOD,
                confidence_level=ConfidenceLevel.MEDIUM,
                fresh_snow_cm=8.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.MEDIUM,
            ),
            WeatherCondition(
                resort_id="test-resort",
                elevation_level="top",
                timestamp="2026-01-20T10:00:00Z",
                current_temp_celsius=-8.0,
                min_temp_celsius=-10.0,
                max_temp_celsius=-6.0,
                snowfall_24h_cm=20.0,
                hours_above_ice_threshold=0.0,
                snow_quality=SnowQuality.EXCELLENT,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=18.0,
                data_source="test-api",
                source_confidence=ConfidenceLevel.HIGH,
            ),
        ]

        results = service.bulk_assess_resort_conditions(conditions)

        assert "base" in results
        assert "top" in results
        assert len(results["base"]) == 1
        assert len(results["top"]) == 1

        # Top elevation should have better conditions
        base_quality, base_fresh, base_conf = results["base"][0]
        top_quality, top_fresh, top_conf = results["top"][0]

        # Top should have more fresh snow due to colder temperatures
        assert top_fresh >= base_fresh

    def test_edge_cases(self, snow_quality_algorithm):
        """Test edge cases and error conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        # Invalid timestamp
        invalid_timestamp_condition = WeatherCondition(
            resort_id="test",
            elevation_level="base",
            timestamp="invalid-timestamp",
            current_temp_celsius=0.0,
            min_temp_celsius=-2.0,
            max_temp_celsius=2.0,
            snowfall_24h_cm=5.0,
            hours_above_ice_threshold=2.0,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.LOW,
            fresh_snow_cm=3.0,
            data_source="test",
            source_confidence=ConfidenceLevel.LOW,
        )

        # Should not crash and should return reasonable values
        quality, fresh_snow, confidence = service.assess_snow_quality(
            invalid_timestamp_condition
        )
        # Quality might be enum or string (due to use_enum_values)
        quality_values = [q.value for q in SnowQuality]
        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value in quality_values
        assert fresh_snow >= 0.0
        # Confidence might be enum or string (due to use_enum_values)
        confidence_values = [c.value for c in ConfidenceLevel]
        confidence_value = (
            confidence.value if hasattr(confidence, "value") else confidence
        )
        assert confidence_value in confidence_values


class TestQualityCappingLogic:
    """Test cases for quality capping based on fresh powder since freeze-thaw."""

    def test_no_fresh_snow_caps_at_poor(self, snow_quality_algorithm):
        """Test that no fresh snow since freeze = Poor/Bad regardless of cold temps."""
        service = SnowQualityService(snow_quality_algorithm)

        # Cold temperatures but NO snow since last freeze-thaw
        cold_but_icy = WeatherCondition(
            resort_id="test",
            elevation_level="top",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-10.0,  # Very cold - normally excellent
            min_temp_celsius=-15.0,
            max_temp_celsius=-8.0,
            snowfall_24h_cm=0.0,  # No recent snowfall
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=0.0,  # No snow since freeze = icy
            last_freeze_thaw_hours_ago=48.0,
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(cold_but_icy)

        # Should be capped at Bad despite cold temps (no fresh snow = icy)
        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value == SnowQuality.BAD.value

    def test_less_than_one_inch_caps_at_fair(self, snow_quality_algorithm):
        """Test that <1 inch (2.54cm) since freeze caps quality at Fair."""
        service = SnowQualityService(snow_quality_algorithm)

        # Cold temps, some recent snow but less than 1 inch since freeze
        thin_cover = WeatherCondition(
            resort_id="test",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-8.0,
            min_temp_celsius=-12.0,
            max_temp_celsius=-5.0,
            snowfall_24h_cm=2.0,  # Some recent snow
            snowfall_48h_cm=3.0,
            snowfall_72h_cm=5.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=2.0,  # Less than 1 inch (2.54cm)
            last_freeze_thaw_hours_ago=36.0,
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=2.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(thin_cover)

        # Should be capped at Fair or below
        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value in [
            SnowQuality.FAIR.value,
            SnowQuality.POOR.value,
            SnowQuality.BAD.value,
        ]

    def test_two_inches_allows_good(self, snow_quality_algorithm):
        """Test that 2+ inches (5.08cm) since freeze allows Good rating."""
        service = SnowQualityService(snow_quality_algorithm)

        # Good conditions: ~2 inches of fresh powder
        good_cover = WeatherCondition(
            resort_id="test",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-5.0,
            min_temp_celsius=-8.0,
            max_temp_celsius=-3.0,
            snowfall_24h_cm=6.0,
            snowfall_48h_cm=8.0,
            snowfall_72h_cm=10.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=5.5,  # ~2.2 inches - should allow Good
            last_freeze_thaw_hours_ago=48.0,
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=6.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(good_cover)

        # Should be Good or better
        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value in [
            SnowQuality.EXCELLENT.value,
            SnowQuality.GOOD.value,
        ]

    def test_three_inches_allows_excellent(self, snow_quality_algorithm):
        """Test that 3+ inches (7.62cm) since freeze allows Excellent rating."""
        service = SnowQualityService(snow_quality_algorithm)

        # Excellent conditions: 3+ inches of fresh powder
        deep_powder = WeatherCondition(
            resort_id="test",
            elevation_level="top",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-8.0,
            min_temp_celsius=-12.0,
            max_temp_celsius=-5.0,
            snowfall_24h_cm=12.0,
            snowfall_48h_cm=20.0,
            snowfall_72h_cm=25.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=10.0,  # ~4 inches - should allow Excellent
            last_freeze_thaw_hours_ago=72.0,
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=12.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(deep_powder)

        # Should be Excellent
        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value == SnowQuality.EXCELLENT.value

    def test_currently_warming_downgrades_quality(self, snow_quality_algorithm):
        """Test that currently warming conditions reduce quality."""
        service = SnowQualityService(snow_quality_algorithm)

        # Good snow but warming up
        warming_conditions = WeatherCondition(
            resort_id="test",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=2.0,  # Warming up
            min_temp_celsius=-3.0,
            max_temp_celsius=3.0,
            snowfall_24h_cm=8.0,
            snowfall_48h_cm=12.0,
            snowfall_72h_cm=15.0,
            hours_above_ice_threshold=2.0,
            max_consecutive_warm_hours=2.0,
            snowfall_after_freeze_cm=8.0,  # Good amount
            last_freeze_thaw_hours_ago=24.0,
            currently_warming=True,  # Currently warming
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=6.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(
            warming_conditions
        )

        # Should be downgraded from what it would otherwise be
        quality_value = quality.value if hasattr(quality, "value") else quality
        # With warming, even 3+ inches shouldn't be Excellent
        assert quality_value in [
            SnowQuality.GOOD.value,
            SnowQuality.FAIR.value,
            SnowQuality.POOR.value,
        ]
