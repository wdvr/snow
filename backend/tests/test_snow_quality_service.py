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


class TestSnowDepthReliability:
    """Regression tests for snow_depth reliability checks.

    These tests cover the bug where Open-Meteo's forecast model snow_depth
    was wildly inaccurate for mountain terrain and hard-capped quality to
    BAD/Icy even when there was abundant fresh powder.

    Real-world example: Big White showed "Icy" with 28cm fresh snow because
    Open-Meteo reported snow_depth=11cm (actually 81-141cm at the resort).
    """

    def test_low_model_depth_does_not_override_fresh_powder_medium_confidence(
        self, snow_quality_algorithm
    ):
        """Test: Low model snow_depth with MEDIUM confidence should NOT cap quality.

        Regression for Big White bug: Open-Meteo reported 11cm depth (model
        artifact from 3-day forecast) when real depth was 81-141cm. This
        triggered the <20cm cap, overriding 28cm of fresh powder to "Icy".
        """
        service = SnowQualityService(snow_quality_algorithm)

        # Big White-like conditions: cold, lots of fresh snow, but model
        # reports low snow_depth (common Open-Meteo inaccuracy for mountains)
        big_white_like = WeatherCondition(
            resort_id="test-big-white",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-6.0,
            min_temp_celsius=-10.0,
            max_temp_celsius=-3.0,
            snowfall_24h_cm=1.3,
            snowfall_48h_cm=2.0,
            snowfall_72h_cm=2.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=27.5,  # 28cm fresh since last freeze
            hours_since_last_snowfall=24.0,
            last_freeze_thaw_hours_ago=336.0,  # 14 days ago
            currently_warming=False,
            snow_depth_cm=11.0,  # Model says 11cm - WRONG for a ski resort!
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.MEDIUM,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com",
            source_confidence=ConfidenceLevel.MEDIUM,  # Open-Meteo = MEDIUM
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(big_white_like)

        quality_value = quality.value if hasattr(quality, "value") else quality
        # Should NOT be BAD/Icy! With 27.5cm fresh powder at -6°C, should be GOOD+
        assert quality_value not in [
            SnowQuality.BAD.value,
            SnowQuality.HORRIBLE.value,
        ], (
            f"Quality should not be {quality_value} with 27.5cm fresh snow. "
            f"Low model snow_depth from MEDIUM confidence source should not override."
        )

    def test_low_model_depth_still_caps_with_high_confidence(
        self, snow_quality_algorithm
    ):
        """Test: Low snow_depth with HIGH confidence (resort report) SHOULD cap quality.

        If a resort actually reports only 11cm of snow, that's a real problem
        and the quality cap should apply.
        """
        service = SnowQualityService(snow_quality_algorithm)

        resort_reported_thin = WeatherCondition(
            resort_id="test-resort",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-5.0,
            min_temp_celsius=-8.0,
            max_temp_celsius=-3.0,
            snowfall_24h_cm=5.0,
            snowfall_48h_cm=8.0,
            snowfall_72h_cm=10.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=1.0,  # Only 1cm since freeze
            hours_since_last_snowfall=6.0,
            last_freeze_thaw_hours_ago=48.0,
            currently_warming=False,
            snow_depth_cm=11.0,  # Resort reports 11cm - this IS reliable
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="resort-report",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(
            resort_reported_thin
        )

        quality_value = quality.value if hasattr(quality, "value") else quality
        # With HIGH confidence and genuinely thin cover, should be capped
        assert quality_value in [
            SnowQuality.BAD.value,
            SnowQuality.POOR.value,
        ]

    def test_inconsistent_depth_vs_fresh_snow_ignored(self, snow_quality_algorithm):
        """Test: snow_depth < snowfall_after_freeze means model is wrong."""
        service = SnowQualityService(snow_quality_algorithm)

        # Even with HIGH confidence, if depth < accumulated fresh snow,
        # the depth data is clearly wrong
        inconsistent = WeatherCondition(
            resort_id="test-resort",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-8.0,
            min_temp_celsius=-12.0,
            max_temp_celsius=-5.0,
            snowfall_24h_cm=10.0,
            snowfall_48h_cm=20.0,
            snowfall_72h_cm=25.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=30.0,  # 30cm fresh since freeze
            hours_since_last_snowfall=4.0,
            last_freeze_thaw_hours_ago=72.0,
            currently_warming=False,
            snow_depth_cm=15.0,  # 15cm < 30cm fresh = impossible, model is wrong
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(inconsistent)

        quality_value = quality.value if hasattr(quality, "value") else quality
        # Should NOT be capped by the inconsistent snow_depth
        assert quality_value not in [
            SnowQuality.BAD.value,
            SnowQuality.HORRIBLE.value,
        ], (
            f"Quality {quality_value} should not be BAD/HORRIBLE when "
            f"snowfall_after_freeze (30cm) > snow_depth (15cm) - model is wrong"
        )

    def test_zero_depth_with_no_snow_still_horrible(self, snow_quality_algorithm):
        """Test: snow_depth=0 with no fresh snow and HIGH confidence = HORRIBLE."""
        service = SnowQualityService(snow_quality_algorithm)

        no_snow = WeatherCondition(
            resort_id="test-resort",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=15.0,
            min_temp_celsius=10.0,
            max_temp_celsius=20.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=24.0,
            max_consecutive_warm_hours=24.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=None,
            last_freeze_thaw_hours_ago=None,
            currently_warming=True,
            snow_depth_cm=0.0,  # Confirmed no snow
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="resort-report",
            source_confidence=ConfidenceLevel.HIGH,  # Reliable source
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(no_snow)

        quality_value = quality.value if hasattr(quality, "value") else quality
        assert quality_value == SnowQuality.HORRIBLE.value

    def test_zero_depth_but_fresh_snow_not_horrible(self, snow_quality_algorithm):
        """Test: snow_depth=0 but recent snowfall = model is wrong, not HORRIBLE."""
        service = SnowQualityService(snow_quality_algorithm)

        model_says_zero = WeatherCondition(
            resort_id="test-resort",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-5.0,
            min_temp_celsius=-8.0,
            max_temp_celsius=-2.0,
            snowfall_24h_cm=10.0,
            snowfall_48h_cm=15.0,
            snowfall_72h_cm=20.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=15.0,  # 15cm fresh snow
            hours_since_last_snowfall=3.0,
            last_freeze_thaw_hours_ago=72.0,
            currently_warming=False,
            snow_depth_cm=0.0,  # Model says 0 - but we have 15cm fresh!
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.MEDIUM,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com",
            source_confidence=ConfidenceLevel.MEDIUM,
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(model_says_zero)

        quality_value = quality.value if hasattr(quality, "value") else quality
        # Should NOT be HORRIBLE - model snow_depth=0 contradicts fresh snow data
        assert quality_value != SnowQuality.HORRIBLE.value, (
            "Quality should not be HORRIBLE when there's 15cm fresh snow. "
            "Model snow_depth=0 contradicts snowfall data."
        )

    def test_deep_base_boosts_only_with_reliable_data(self, snow_quality_algorithm):
        """Test: snow_depth >= 100cm boost only applies with reliable data."""
        service = SnowQualityService(snow_quality_algorithm)

        deep_base = WeatherCondition(
            resort_id="test-resort",
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
            snowfall_after_freeze_cm=10.0,
            hours_since_last_snowfall=2.0,
            last_freeze_thaw_hours_ago=72.0,
            currently_warming=False,
            snow_depth_cm=150.0,  # Deep base
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="resort-report",
            source_confidence=ConfidenceLevel.HIGH,  # Reliable source
        )

        quality, fresh_snow, confidence = service.assess_snow_quality(deep_base)

        quality_value = quality.value if hasattr(quality, "value") else quality
        # Deep base + lots of fresh = Excellent
        assert quality_value in [
            SnowQuality.EXCELLENT.value,
            SnowQuality.GOOD.value,
        ]


class TestFreezeThawAndQualityEdgeCases:
    """Regression tests for freeze-thaw detection and quality edge cases.

    Covers bugs found during multi-resort spot-checks (Feb 2026):
    - Big White top: 7h above 0°C missed by ICE_THRESHOLDS
    - Whistler mid: freeze detected at current hour, resetting accumulation
    - Vail base/mid: HORRIBLE rating from unreliable 0cm depth
    - Jackson Hole mid: quality flipping BAD↔POOR at 0°C boundary
    - Jackson Hole top: old unfrozen snow rated POOR despite no freeze in 14d
    """

    def test_zero_depth_unreliable_not_horrible_vail_scenario(
        self, snow_quality_algorithm
    ):
        """Regression: Vail base/mid - Open-Meteo reports 0cm but real depth ~94cm.

        With MEDIUM confidence (model data), snow_depth=0 should NOT trigger
        HORRIBLE. The model is simply wrong for this grid cell.
        """
        service = SnowQualityService(snow_quality_algorithm)

        vail_like = WeatherCondition(
            resort_id="test-vail",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=3.4,
            min_temp_celsius=-2.0,
            max_temp_celsius=5.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=3.0,
            max_consecutive_warm_hours=9.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=312.0,
            last_freeze_thaw_hours_ago=14.0,
            currently_warming=True,
            snow_depth_cm=0.0,  # Model says 0 - WRONG
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.MEDIUM,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com",
            source_confidence=ConfidenceLevel.MEDIUM,  # Unreliable
        )

        quality, _, _ = service.assess_snow_quality(vail_like)
        quality_value = quality.value if hasattr(quality, "value") else quality

        # Should NOT be HORRIBLE - depth data is unreliable
        assert quality_value != SnowQuality.HORRIBLE.value, (
            "Quality should not be HORRIBLE when snow_depth=0 from unreliable "
            "source. Open-Meteo grid model often reports 0cm at mountain resorts."
        )

    def test_old_unfrozen_snow_not_icy_jackson_top_scenario(
        self, snow_quality_algorithm
    ):
        """Regression: Jackson Hole top - 157cm at -4.2°C, no freeze in 14+ days.

        Snow that has NEVER been through a freeze-thaw cycle is aged packed
        powder, not icy. Should be FAIR, not BAD.
        """
        service = SnowQualityService(snow_quality_algorithm)

        jackson_top = WeatherCondition(
            resort_id="test-jackson",
            elevation_level="top",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-4.2,
            min_temp_celsius=-8.0,
            max_temp_celsius=-2.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=0.0,  # No fresh snow
            hours_since_last_snowfall=200.0,
            last_freeze_thaw_hours_ago=336.0,  # No freeze in 14+ days!
            currently_warming=False,
            snow_depth_cm=157.0,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com + onthesnow.com",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, _, _ = service.assess_snow_quality(jackson_top)
        quality_value = quality.value if hasattr(quality, "value") else quality

        # Should be FAIR (packed powder), not BAD (icy)
        assert quality_value in [
            SnowQuality.FAIR.value,
            SnowQuality.GOOD.value,
        ], (
            f"Quality {quality_value} is too low for -4.2°C with no freeze-thaw "
            f"in 14+ days. Old unfrozen snow is packed powder, not icy."
        )

    def test_old_unfrozen_snow_cold_is_fair(self, snow_quality_algorithm):
        """Test: Very cold old snow with no freeze in 14d = FAIR (dry packed)."""
        service = SnowQualityService(snow_quality_algorithm)

        cold_old = WeatherCondition(
            resort_id="test-resort",
            elevation_level="top",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-10.0,  # Very cold
            min_temp_celsius=-15.0,
            max_temp_celsius=-8.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=0.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=300.0,
            last_freeze_thaw_hours_ago=336.0,  # No freeze in 14+ days
            currently_warming=False,
            snow_depth_cm=200.0,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="open-meteo.com + onthesnow.com",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, _, _ = service.assess_snow_quality(cold_old)
        quality_value = quality.value if hasattr(quality, "value") else quality

        assert quality_value == SnowQuality.FAIR.value, (
            f"Quality {quality_value} should be FAIR for very cold (-10°C) old "
            f"snow with no freeze-thaw. This is dry packed powder."
        )

    def test_smooth_zero_degree_transition(self, snow_quality_algorithm):
        """Regression: Jackson Hole mid - quality shouldn't flip at exactly 0°C.

        At 0.5°C with recent freeze and no fresh snow, quality should be
        between BAD (0°C) and POOR (2°C), not jump to either extreme.
        """
        service = SnowQualityService(snow_quality_algorithm)

        at_half_degree = WeatherCondition(
            resort_id="test-resort",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=0.5,  # Just above 0
            min_temp_celsius=-3.0,
            max_temp_celsius=2.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=3.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=100.0,
            last_freeze_thaw_hours_ago=20.0,  # Recent freeze
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        at_minus_half = WeatherCondition(
            resort_id="test-resort",
            elevation_level="mid",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=-0.5,  # Just below 0
            min_temp_celsius=-3.0,
            max_temp_celsius=2.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=0.0,
            max_consecutive_warm_hours=3.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=100.0,
            last_freeze_thaw_hours_ago=20.0,  # Recent freeze
            currently_warming=False,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality_above, _, _ = service.assess_snow_quality(at_half_degree)
        quality_below, _, _ = service.assess_snow_quality(at_minus_half)

        q_above = (
            quality_above.value if hasattr(quality_above, "value") else quality_above
        )
        q_below = (
            quality_below.value if hasattr(quality_below, "value") else quality_below
        )

        # Both should be in the BAD-POOR range (transition zone)
        assert q_above in [SnowQuality.BAD.value, SnowQuality.POOR.value]
        assert q_below == SnowQuality.BAD.value

    def test_recent_freeze_no_snow_above_2c_is_poor(self, snow_quality_algorithm):
        """Test: Recent freeze + no fresh snow + clearly above freezing = POOR."""
        service = SnowQualityService(snow_quality_algorithm)

        warm_after_freeze = WeatherCondition(
            resort_id="test-resort",
            elevation_level="base",
            timestamp=datetime.now(UTC).isoformat(),
            current_temp_celsius=3.0,
            min_temp_celsius=-1.0,
            max_temp_celsius=5.0,
            snowfall_24h_cm=0.0,
            snowfall_48h_cm=0.0,
            snowfall_72h_cm=0.0,
            hours_above_ice_threshold=2.0,
            max_consecutive_warm_hours=5.0,
            snowfall_after_freeze_cm=0.0,
            hours_since_last_snowfall=100.0,
            last_freeze_thaw_hours_ago=12.0,  # Recent freeze
            currently_warming=True,
            snow_quality=SnowQuality.UNKNOWN,
            confidence_level=ConfidenceLevel.HIGH,
            fresh_snow_cm=0.0,
            data_source="test-api",
            source_confidence=ConfidenceLevel.HIGH,
        )

        quality, _, _ = service.assess_snow_quality(warm_after_freeze)
        quality_value = quality.value if hasattr(quality, "value") else quality

        assert quality_value == SnowQuality.POOR.value, (
            f"Quality {quality_value} should be POOR (Soft/Slushy) for "
            f"above-freezing conditions with recent freeze and no fresh snow."
        )


class TestSnowConditionMatrix:
    """Comprehensive tests mapping real-world ski conditions to quality ratings.

    Based on ski industry standards (OnTheSnow, OpenSnow, resort reporting).
    Labels: EXCELLENT=Powder, GOOD=Soft Surface, FAIR=Some Fresh/Packed,
            POOR=Soft/Slushy, BAD=Icy, HORRIBLE=Not Skiable
    """

    def _make_condition(self, **overrides):
        """Helper to create a WeatherCondition with sensible defaults."""
        defaults = {
            "resort_id": "test",
            "elevation_level": "mid",
            "timestamp": datetime.now(UTC).isoformat(),
            "current_temp_celsius": -5.0,
            "min_temp_celsius": -8.0,
            "max_temp_celsius": -3.0,
            "snowfall_24h_cm": 0.0,
            "snowfall_48h_cm": 0.0,
            "snowfall_72h_cm": 0.0,
            "hours_above_ice_threshold": 0.0,
            "max_consecutive_warm_hours": 0.0,
            "snowfall_after_freeze_cm": 0.0,
            "hours_since_last_snowfall": None,
            "last_freeze_thaw_hours_ago": 48.0,
            "currently_warming": False,
            "snow_depth_cm": 150.0,
            "snow_quality": SnowQuality.UNKNOWN,
            "confidence_level": ConfidenceLevel.HIGH,
            "fresh_snow_cm": 0.0,
            "data_source": "test",
            "source_confidence": ConfidenceLevel.HIGH,
        }
        defaults.update(overrides)
        return WeatherCondition(**defaults)

    def _assess(self, condition, algorithm):
        service = SnowQualityService(algorithm)
        quality, _, _ = service.assess_snow_quality(condition)
        return quality.value if hasattr(quality, "value") else quality

    # === POWDER / EXCELLENT scenarios ===

    def test_deep_powder_cold(self, snow_quality_algorithm):
        """15+ cm fresh at -10°C, no thaw → EXCELLENT (Deep Powder)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-10.0,
                snowfall_after_freeze_cm=20.0,
                snowfall_24h_cm=15.0,
                hours_since_last_snowfall=4.0,
                last_freeze_thaw_hours_ago=72.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.EXCELLENT.value

    def test_fresh_powder_moderate_cold(self, snow_quality_algorithm):
        """10cm fresh at -5°C → EXCELLENT or GOOD."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-5.0,
                snowfall_after_freeze_cm=10.0,
                snowfall_24h_cm=8.0,
                hours_since_last_snowfall=8.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.EXCELLENT.value, SnowQuality.GOOD.value]

    def test_heavy_damp_powder_near_freezing(self, snow_quality_algorithm):
        """10cm fresh at +1°C ("Sierra cement") → GOOD or FAIR."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=1.0,
                max_temp_celsius=2.0,
                snowfall_after_freeze_cm=12.0,
                snowfall_24h_cm=10.0,
                hours_since_last_snowfall=6.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.GOOD.value, SnowQuality.FAIR.value]

    def test_wet_snow_above_freezing(self, snow_quality_algorithm):
        """10cm fresh at +4°C → FAIR at best (heavy wet snow)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=4.0,
                max_temp_celsius=5.0,
                snowfall_after_freeze_cm=10.0,
                snowfall_24h_cm=8.0,
                hours_since_last_snowfall=6.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.FAIR.value, SnowQuality.POOR.value]

    # === ICY scenarios (freeze-thaw + cold + no/thin fresh) ===

    def test_icy_classic_freeze_thaw_cold(self, snow_quality_algorithm):
        """No fresh, -10°C, thaw 2 days ago → BAD (Icy)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-10.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.BAD.value, (
            f"Got {q}. -10°C with no fresh snow after freeze = Icy (BAD)"
        )

    def test_icy_recent_freeze_minus5(self, snow_quality_algorithm):
        """No fresh, -5°C, thaw yesterday → BAD (Icy).
        This is Big White top scenario: -5.4°C, 1.19cm, freeze 45h ago.
        """
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-5.4,
                snowfall_after_freeze_cm=1.19,  # < 2.54cm (1 inch)
                snowfall_24h_cm=1.07,
                hours_since_last_snowfall=5.0,
                last_freeze_thaw_hours_ago=45.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.BAD.value, (
            f"Got {q}. Big White top: -5.4°C with 1.19cm dust on refrozen "
            f"base should be Icy (BAD), not Soft (POOR)"
        )

    def test_icy_thin_dusting_cold(self, snow_quality_algorithm):
        """2cm fresh at -8°C, thaw 36h ago → BAD (dust on crust)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-8.0,
                snowfall_after_freeze_cm=2.0,  # < 2.54cm
                snowfall_24h_cm=2.0,
                hours_since_last_snowfall=6.0,
                last_freeze_thaw_hours_ago=36.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.BAD.value, (
            f"Got {q}. Thin dusting (<1 inch) over ice at -8°C = Icy (BAD)"
        )

    # === SOFT/SLUSHY scenarios (warm + no fresh) ===

    def test_soft_warm_after_freeze(self, snow_quality_algorithm):
        """No fresh, +3°C, thaw ongoing → POOR (Soft/Slushy)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=3.0,
                max_temp_celsius=5.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=6.0,
                currently_warming=True,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.POOR.value, (
            f"Got {q}. +3°C with no fresh after freeze = Soft (POOR)"
        )

    def test_soft_thin_dusting_warm(self, snow_quality_algorithm):
        """1.5cm fresh at +2°C, recent freeze → POOR (Soft)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=2.0,
                max_temp_celsius=3.0,
                snowfall_after_freeze_cm=1.5,
                snowfall_24h_cm=1.5,
                hours_since_last_snowfall=3.0,
                last_freeze_thaw_hours_ago=24.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.POOR.value, (
            f"Got {q}. Thin wet snow at +2°C = Soft (POOR)"
        )

    def test_slushy_hot(self, snow_quality_algorithm):
        """No fresh, +8°C → POOR (Slushy/Mashed Potatoes)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=8.0,
                max_temp_celsius=10.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=3.0,
                currently_warming=True,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.POOR.value, SnowQuality.BAD.value]

    # === PACKED POWDER / FAIR scenarios (old snow, never refrozen) ===

    def test_packed_powder_cold(self, snow_quality_algorithm):
        """No fresh, -10°C, NO freeze in 14+ days → FAIR (Packed Powder)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-10.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=336.0,  # 14+ days
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.FAIR.value, (
            f"Got {q}. Cold packed powder never refrozen = FAIR, not Icy"
        )

    def test_packed_powder_light_dusting(self, snow_quality_algorithm):
        """1.5cm fresh, -5°C, NO freeze in 14+ days → FAIR (nice dusting)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-5.0,
                snowfall_after_freeze_cm=1.5,
                snowfall_24h_cm=1.5,
                hours_since_last_snowfall=8.0,
                last_freeze_thaw_hours_ago=336.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.FAIR.value, (
            f"Got {q}. Light dusting on packed powder (no freeze) = FAIR"
        )

    # === SPRING CORN scenarios ===

    def test_spring_corn_warm(self, snow_quality_algorithm):
        """No fresh, +3°C, thaw 12h ago (overnight freeze) → POOR."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=3.0,
                max_temp_celsius=5.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=12.0,
                hours_above_ice_threshold=2.0,
                currently_warming=True,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.POOR.value

    # === NOT SKIABLE scenarios ===

    def test_not_skiable_summer(self, snow_quality_algorithm):
        """+20°C, no snow → HORRIBLE."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=20.0,
                max_temp_celsius=22.0,
                snow_depth_cm=0.0,
                snowfall_after_freeze_cm=0.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.HORRIBLE.value

    def test_not_skiable_warm_no_snow(self, snow_quality_algorithm):
        """+12°C, no fresh, melting out → POOR or worse."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=12.0,
                max_temp_celsius=15.0,
                snow_depth_cm=10.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=2.0,
                currently_warming=True,
            ),
            snow_quality_algorithm,
        )
        assert q in [
            SnowQuality.POOR.value,
            SnowQuality.BAD.value,
            SnowQuality.HORRIBLE.value,
        ]

    # === TRANSITION ZONE scenarios (near 0°C) ===

    def test_transition_at_zero_icy_side(self, snow_quality_algorithm):
        """No fresh, -0.5°C, recent freeze → BAD (still frozen = icy)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-0.5,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=24.0,
            ),
            snow_quality_algorithm,
        )
        assert q == SnowQuality.BAD.value

    def test_transition_at_one_degree(self, snow_quality_algorithm):
        """No fresh, +1°C, recent freeze → BAD or POOR (transitioning)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=1.0,
                snowfall_after_freeze_cm=0.0,
                last_freeze_thaw_hours_ago=24.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.BAD.value, SnowQuality.POOR.value]

    # === ENOUGH FRESH SNOW COVERS ICY BASE ===

    def test_3_inches_covers_ice(self, snow_quality_algorithm):
        """8cm fresh at -5°C, freeze 48h ago → GOOD+ (fresh covers ice)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-5.0,
                snowfall_after_freeze_cm=8.0,
                snowfall_24h_cm=6.0,
                hours_since_last_snowfall=6.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [SnowQuality.EXCELLENT.value, SnowQuality.GOOD.value], (
            f"Got {q}. 8cm (3+ inches) of fresh at -5°C should cover icy base"
        )

    def test_2_inches_partially_covers(self, snow_quality_algorithm):
        """5.5cm fresh at -5°C, freeze 48h ago → GOOD+ (good coverage)."""
        q = self._assess(
            self._make_condition(
                current_temp_celsius=-5.0,
                snowfall_after_freeze_cm=5.5,
                snowfall_24h_cm=4.0,
                hours_since_last_snowfall=12.0,
                last_freeze_thaw_hours_ago=48.0,
            ),
            snow_quality_algorithm,
        )
        assert q in [
            SnowQuality.EXCELLENT.value,
            SnowQuality.GOOD.value,
            SnowQuality.FAIR.value,
        ]
