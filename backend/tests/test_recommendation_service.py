"""Tests for RecommendationService."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from models.resort import ElevationLevel, ElevationPoint, Resort
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.recommendation_service import RecommendationService, ResortRecommendation


class TestRecommendationService:
    """Test cases for RecommendationService."""

    @pytest.fixture
    def mock_resort_service(self):
        """Create a mock ResortService."""
        service = Mock()
        return service

    @pytest.fixture
    def mock_weather_service(self):
        """Create a mock WeatherService."""
        service = Mock()
        return service

    @pytest.fixture
    def recommendation_service(self, mock_resort_service, mock_weather_service):
        """Create a RecommendationService with mocked dependencies."""
        return RecommendationService(
            resort_service=mock_resort_service,
            weather_service=mock_weather_service,
        )

    @pytest.fixture
    def sample_resorts(self):
        """Create sample resorts at different distances."""
        return [
            Resort(
                resort_id="nearby-resort",
                name="Nearby Resort",
                country="CA",
                region="BC",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=1500,
                        elevation_feet=4921,
                        latitude=49.3,  # Close to test location
                        longitude=-123.0,
                    ),
                ],
                timezone="America/Vancouver",
            ),
            Resort(
                resort_id="medium-resort",
                name="Medium Distance Resort",
                country="CA",
                region="BC",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=1800,
                        elevation_feet=5905,
                        latitude=50.0,  # ~80km away
                        longitude=-122.5,
                    ),
                ],
                timezone="America/Vancouver",
            ),
            Resort(
                resort_id="far-resort",
                name="Far Away Resort",
                country="CA",
                region="AB",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2000,
                        elevation_feet=6562,
                        latitude=51.5,  # ~300km away
                        longitude=-116.0,
                    ),
                ],
                timezone="America/Edmonton",
            ),
        ]

    @pytest.fixture
    def excellent_conditions(self):
        """Create excellent snow conditions."""
        return [
            WeatherCondition(
                resort_id="test",
                elevation_level="mid",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-8.0,
                min_temp_celsius=-12.0,
                max_temp_celsius=-4.0,
                snowfall_24h_cm=20.0,
                snowfall_48h_cm=35.0,
                snowfall_72h_cm=45.0,
                predicted_snow_24h_cm=10.0,
                predicted_snow_48h_cm=15.0,
                predicted_snow_72h_cm=25.0,
                hours_above_ice_threshold=0.0,
                max_consecutive_warm_hours=0.0,
                snowfall_after_freeze_cm=15.0,
                snow_quality=SnowQuality.EXCELLENT,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=20.0,
                data_source="test",
                source_confidence=ConfidenceLevel.HIGH,
            )
        ]

    @pytest.fixture
    def poor_conditions(self):
        """Create poor snow conditions."""
        return [
            WeatherCondition(
                resort_id="test",
                elevation_level="mid",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=3.0,
                min_temp_celsius=0.0,
                max_temp_celsius=5.0,
                snowfall_24h_cm=0.0,
                snowfall_48h_cm=2.0,
                snowfall_72h_cm=5.0,
                predicted_snow_24h_cm=0.0,
                predicted_snow_48h_cm=0.0,
                predicted_snow_72h_cm=2.0,
                hours_above_ice_threshold=6.0,
                max_consecutive_warm_hours=4.0,
                snowfall_after_freeze_cm=0.0,
                snow_quality=SnowQuality.BAD,
                confidence_level=ConfidenceLevel.LOW,
                fresh_snow_cm=0.0,
                data_source="test",
                source_confidence=ConfidenceLevel.LOW,
            )
        ]

    def test_get_recommendations_basic(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
    ):
        """Test basic recommendation generation."""
        # Setup mocks
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 10.0),  # 10km
            (sample_resorts[1], 80.0),  # 80km
        ]
        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": excellent_conditions,
            "medium-resort": excellent_conditions,
        }

        # Get recommendations
        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
            radius_km=200,
            limit=10,
        )

        assert len(recommendations) == 2
        assert all(isinstance(r, ResortRecommendation) for r in recommendations)
        mock_resort_service.get_nearby_resorts.assert_called_once()

    def test_get_recommendations_sorted_by_score(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
        poor_conditions,
    ):
        """Test that recommendations are sorted by combined score."""
        # Setup: nearby resort has poor conditions, far resort has excellent
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 10.0),  # Close but poor conditions
            (sample_resorts[2], 300.0),  # Far but excellent conditions
        ]

        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": poor_conditions,
            "far-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
            radius_km=500,
            limit=10,
        )

        # Should be sorted by combined score (far resort with excellent snow first)
        assert len(recommendations) == 2
        assert recommendations[0].resort.resort_id == "far-resort"
        assert recommendations[0].snow_quality == SnowQuality.EXCELLENT

    def test_get_recommendations_with_quality_filter(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
        poor_conditions,
    ):
        """Test quality filter excludes low-quality resorts."""
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 10.0),
            (sample_resorts[1], 80.0),
        ]

        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": poor_conditions,
            "medium-resort": excellent_conditions,
        }

        # Filter for GOOD or better
        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
            radius_km=200,
            limit=10,
            min_quality=SnowQuality.GOOD,
        )

        # Should only return the resort with excellent conditions
        assert len(recommendations) == 1
        assert recommendations[0].resort.resort_id == "medium-resort"

    def test_get_recommendations_respects_limit(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
    ):
        """Test that limit parameter works correctly."""
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 10.0),
            (sample_resorts[1], 80.0),
            (sample_resorts[2], 300.0),
        ]
        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": excellent_conditions,
            "medium-resort": excellent_conditions,
            "far-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
            radius_km=500,
            limit=2,
        )

        assert len(recommendations) == 2

    def test_get_recommendations_empty_when_no_resorts(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
    ):
        """Test empty result when no resorts nearby."""
        mock_resort_service.get_nearby_resorts.return_value = []
        mock_weather_service.get_all_latest_conditions.return_value = {}

        recommendations = recommendation_service.get_recommendations(
            latitude=0.0,
            longitude=0.0,
            radius_km=100,
        )

        assert len(recommendations) == 0

    def test_get_recommendations_skips_resorts_without_conditions(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
    ):
        """Test that resorts without condition data are skipped."""
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 10.0),
            (sample_resorts[1], 80.0),
        ]

        # Service uses batch query now - nearby resort has no conditions
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": [],  # No conditions
            "medium-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
            radius_km=200,
        )

        # Should only include resort with conditions
        assert len(recommendations) == 1
        assert recommendations[0].resort.resort_id == "medium-resort"

    def test_get_best_conditions_globally(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
        poor_conditions,
    ):
        """Test getting best conditions globally (no location bias)."""
        mock_resort_service.get_all_resorts.return_value = sample_resorts

        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": poor_conditions,
            "medium-resort": poor_conditions,
            "far-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_best_conditions_globally(limit=10)

        # Far resort should be first (best quality)
        assert len(recommendations) == 3
        assert recommendations[0].resort.resort_id == "far-resort"
        assert recommendations[0].snow_quality == SnowQuality.EXCELLENT

    def test_recommendation_to_dict(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
    ):
        """Test that recommendations convert to dict correctly."""
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 50.0),
        ]
        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
        )

        assert len(recommendations) == 1
        rec_dict = recommendations[0].to_dict()

        # Check required fields
        assert "resort" in rec_dict
        assert "distance_km" in rec_dict
        assert "distance_miles" in rec_dict
        assert "snow_quality" in rec_dict
        assert "quality_score" in rec_dict
        assert "combined_score" in rec_dict
        assert "fresh_snow_cm" in rec_dict
        assert "reason" in rec_dict

    def test_distance_score_calculation(self, recommendation_service):
        """Test distance score calculation."""
        # Very close = high score
        close_score = recommendation_service._calculate_distance_score(10.0)
        assert close_score > 0.9

        # At ideal distance
        ideal_score = recommendation_service._calculate_distance_score(50.0)
        assert ideal_score == 1.0

        # Far away = lower score
        far_score = recommendation_service._calculate_distance_score(400.0)
        assert far_score < 0.7

        # Very far = very low score
        very_far_score = recommendation_service._calculate_distance_score(1000.0)
        assert very_far_score < 0.3

    def test_quality_score_calculation(self, recommendation_service):
        """Test quality score mapping."""
        assert (
            recommendation_service._calculate_quality_score(SnowQuality.EXCELLENT)
            == 1.0
        )
        assert recommendation_service._calculate_quality_score(SnowQuality.GOOD) == 0.8
        assert recommendation_service._calculate_quality_score(SnowQuality.FAIR) == 0.6
        assert recommendation_service._calculate_quality_score(SnowQuality.POOR) == 0.4
        assert recommendation_service._calculate_quality_score(SnowQuality.BAD) == 0.2
        assert (
            recommendation_service._calculate_quality_score(SnowQuality.HORRIBLE) == 0.0
        )

    def test_fresh_snow_score_calculation(self, recommendation_service):
        """Test fresh/predicted snow score calculation."""
        # No snow = 0
        assert recommendation_service._calculate_fresh_snow_score(0.0, 0.0) == 0.0

        # Some fresh snow
        score = recommendation_service._calculate_fresh_snow_score(10.0, 0.0)
        assert 0.4 < score < 0.6

        # Lots of fresh + predicted
        score = recommendation_service._calculate_fresh_snow_score(15.0, 20.0)
        assert score == 1.0

    def test_recommendation_reason_generation(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
        excellent_conditions,
    ):
        """Test that recommendation reasons are generated."""
        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 50.0),
        ]
        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": excellent_conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
        )

        assert len(recommendations) == 1
        assert recommendations[0].reason is not None
        assert len(recommendations[0].reason) > 10  # Should have meaningful content

    def test_elevation_conditions_summary(
        self,
        recommendation_service,
        mock_resort_service,
        mock_weather_service,
        sample_resorts,
    ):
        """Test elevation conditions summary is built correctly."""
        # Create conditions for multiple elevations
        conditions = [
            WeatherCondition(
                resort_id="nearby-resort",
                elevation_level="base",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-2.0,
                min_temp_celsius=-5.0,
                max_temp_celsius=0.0,
                snowfall_24h_cm=5.0,
                snowfall_48h_cm=10.0,
                snowfall_72h_cm=15.0,
                snowfall_after_freeze_cm=5.0,
                snow_quality=SnowQuality.FAIR,
                confidence_level=ConfidenceLevel.MEDIUM,
                fresh_snow_cm=5.0,
                data_source="test",
                source_confidence=ConfidenceLevel.MEDIUM,
            ),
            WeatherCondition(
                resort_id="nearby-resort",
                elevation_level="top",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-10.0,
                min_temp_celsius=-15.0,
                max_temp_celsius=-5.0,
                snowfall_24h_cm=15.0,
                snowfall_48h_cm=25.0,
                snowfall_72h_cm=35.0,
                snowfall_after_freeze_cm=15.0,
                snow_quality=SnowQuality.EXCELLENT,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=15.0,
                data_source="test",
                source_confidence=ConfidenceLevel.HIGH,
            ),
        ]

        mock_resort_service.get_nearby_resorts.return_value = [
            (sample_resorts[0], 50.0),
        ]
        # Service uses batch query now
        mock_weather_service.get_all_latest_conditions.return_value = {
            "nearby-resort": conditions,
        }

        recommendations = recommendation_service.get_recommendations(
            latitude=49.28,
            longitude=-123.12,
        )

        assert len(recommendations) == 1
        elevation_summary = recommendations[0].elevation_conditions

        assert "base" in elevation_summary
        assert "top" in elevation_summary
        assert elevation_summary["base"]["quality"] == "fair"
        assert elevation_summary["top"]["quality"] == "excellent"
