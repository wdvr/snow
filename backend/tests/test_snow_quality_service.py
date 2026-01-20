"""Tests for the snow quality assessment service."""

import pytest
from datetime import datetime, timezone, timedelta

from src.services.snow_quality_service import SnowQualityService
from src.models.weather import WeatherCondition, SnowQuality, ConfidenceLevel, SnowQualityAlgorithm


class TestSnowQualityService:
    """Test cases for SnowQualityService."""

    def test_assess_excellent_conditions(self, sample_weather_condition, snow_quality_algorithm):
        """Test assessment of excellent snow conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        quality, fresh_snow, confidence = service.assess_snow_quality(sample_weather_condition)

        assert quality == SnowQuality.EXCELLENT
        assert fresh_snow > 10.0  # Should have significant fresh snow
        assert confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]

    def test_assess_poor_conditions(self, poor_weather_condition, snow_quality_algorithm):
        """Test assessment of poor snow conditions."""
        service = SnowQualityService(snow_quality_algorithm)

        quality, fresh_snow, confidence = service.assess_snow_quality(poor_weather_condition)

        assert quality in [SnowQuality.POOR, SnowQuality.BAD]
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
        now = datetime.now(timezone.utc)
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
        assert 0.3 <= medium_score <= 0.8

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

    def test_fresh_snow_estimation(self, sample_weather_condition, snow_quality_algorithm):
        """Test fresh snow amount estimation."""
        service = SnowQualityService(snow_quality_algorithm)

        # Good conditions should preserve most snow
        quality, fresh_snow, confidence = service.assess_snow_quality(sample_weather_condition)
        assert fresh_snow >= sample_weather_condition.snowfall_24h_cm * 0.7

        # Poor conditions should reduce fresh snow significantly
        poor_condition = sample_weather_condition.model_copy()
        poor_condition.current_temp_celsius = 5.0
        poor_condition.hours_above_ice_threshold = 8.0

        quality, degraded_fresh_snow, confidence = service.assess_snow_quality(poor_condition)
        assert degraded_fresh_snow < fresh_snow

    def test_confidence_level_adjustment(self, sample_weather_condition, snow_quality_algorithm):
        """Test confidence level adjustments based on data quality."""
        service = SnowQualityService(snow_quality_algorithm)

        # Complete data with high source confidence should maintain/upgrade confidence
        complete_condition = sample_weather_condition.model_copy()
        complete_condition.source_confidence = ConfidenceLevel.VERY_HIGH

        quality, fresh_snow, confidence = service.assess_snow_quality(complete_condition)
        assert confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]

        # Incomplete data should downgrade confidence
        incomplete_condition = sample_weather_condition.model_copy()
        incomplete_condition.humidity_percent = None
        incomplete_condition.wind_speed_kmh = None
        incomplete_condition.snowfall_48h_cm = None
        incomplete_condition.source_confidence = ConfidenceLevel.LOW

        quality, fresh_snow, low_confidence = service.assess_snow_quality(incomplete_condition)
        assert low_confidence in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]

    def test_data_completeness_assessment(self, sample_weather_condition, snow_quality_algorithm):
        """Test data completeness scoring."""
        service = SnowQualityService(snow_quality_algorithm)

        # Complete data should score high
        complete_score = service._assess_data_completeness(sample_weather_condition)
        assert complete_score >= 0.8

        # Missing optional data should still score reasonably
        partial_condition = sample_weather_condition.model_copy()
        partial_condition.humidity_percent = None
        partial_condition.wind_speed_kmh = None

        partial_score = service._assess_data_completeness(partial_condition)
        assert 0.6 <= partial_score < 0.8

        # Missing required data should score low
        incomplete_condition = sample_weather_condition.model_copy()
        incomplete_condition.current_temp_celsius = None
        incomplete_condition.snowfall_24h_cm = None

        incomplete_score = service._assess_data_completeness(incomplete_condition)
        assert incomplete_score < 0.6

    def test_score_to_quality_mapping(self, snow_quality_algorithm):
        """Test the mapping from numerical scores to quality enums."""
        service = SnowQualityService(snow_quality_algorithm)

        assert service._score_to_quality(0.9) == SnowQuality.EXCELLENT
        assert service._score_to_quality(0.7) == SnowQuality.GOOD
        assert service._score_to_quality(0.5) == SnowQuality.FAIR
        assert service._score_to_quality(0.3) == SnowQuality.POOR
        assert service._score_to_quality(0.1) == SnowQuality.BAD

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
                source_confidence=ConfidenceLevel.MEDIUM
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
                source_confidence=ConfidenceLevel.HIGH
            )
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
            source_confidence=ConfidenceLevel.LOW
        )

        # Should not crash and should return reasonable values
        quality, fresh_snow, confidence = service.assess_snow_quality(invalid_timestamp_condition)
        assert quality in SnowQuality
        assert fresh_snow >= 0.0
        assert confidence in ConfidenceLevel