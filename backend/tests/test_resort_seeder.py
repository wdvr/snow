"""Tests for the resort data seeder."""

from unittest.mock import Mock, patch

import pytest

from models.resort import ElevationLevel, ElevationPoint, Resort
from services.resort_service import ResortService
from utils.resort_seeder import ResortSeeder


class TestResortSeeder:
    """Test cases for ResortSeeder."""

    @pytest.fixture
    def mock_resort_service(self):
        """Create a mock resort service."""
        return Mock(spec=ResortService)

    @pytest.fixture
    def seeder(self, mock_resort_service):
        """Create a resort seeder instance."""
        return ResortSeeder(mock_resort_service)

    def test_get_initial_resort_data(self, seeder):
        """Test that initial resort data is correctly structured."""
        resorts = seeder._get_initial_resort_data()

        assert len(resorts) == 14  # Updated to reflect expanded resort list
        resort_ids = [r.resort_id for r in resorts]
        # Check core Canadian resorts
        assert "big-white" in resort_ids
        assert "lake-louise" in resort_ids
        assert "silver-star" in resort_ids
        # Check expanded resorts
        assert "vail" in resort_ids
        assert "chamonix" in resort_ids
        assert "niseko" in resort_ids

        # Check Big White data
        big_white = next(r for r in resorts if r.resort_id == "big-white")
        assert big_white.name == "Big White Ski Resort"
        assert big_white.country == "CA"
        assert big_white.region == "BC"
        assert len(big_white.elevation_points) == 3
        assert big_white.timezone == "America/Vancouver"
        assert "bigwhite.com" in big_white.official_website

        # Validate elevation points
        levels = [p.level for p in big_white.elevation_points]
        assert ElevationLevel.BASE in levels
        assert ElevationLevel.MID in levels
        assert ElevationLevel.TOP in levels

        # Check coordinates are reasonable (should be in BC)
        for point in big_white.elevation_points:
            assert 49 <= point.latitude <= 50  # BC latitude range
            assert -120 <= point.longitude <= -118  # BC longitude range

    def test_get_initial_resort_data_elevation_progression(self, seeder):
        """Test that elevation points are properly ordered."""
        resorts = seeder._get_initial_resort_data()

        for resort in resorts:
            base_point = next(
                p for p in resort.elevation_points if p.level == ElevationLevel.BASE
            )
            top_point = next(
                p for p in resort.elevation_points if p.level == ElevationLevel.TOP
            )

            # Top should be higher than base
            assert top_point.elevation_meters > base_point.elevation_meters
            assert top_point.elevation_feet > base_point.elevation_feet

    def test_get_initial_resort_data_coordinates_validation(self, seeder):
        """Test that all coordinates are valid."""
        resorts = seeder._get_initial_resort_data()

        for resort in resorts:
            for point in resort.elevation_points:
                # Valid latitude range (worldwide)
                assert -90 <= point.latitude <= 90
                # Valid longitude range (worldwide)
                assert -180 <= point.longitude <= 180

                # All resorts should be in northern hemisphere ski areas
                assert (
                    30 <= point.latitude <= 70
                )  # Northern hemisphere ski latitude range

    def test_seed_initial_resorts_success(self, seeder, mock_resort_service):
        """Test successful seeding of all resorts."""
        # Mock that no resorts exist yet
        mock_resort_service.get_resort.return_value = None

        # Mock successful creation
        def mock_create_resort(resort):
            return resort

        mock_resort_service.create_resort.side_effect = mock_create_resort

        results = seeder.seed_initial_resorts()

        assert results["resorts_created"] == 14
        assert results["resorts_skipped"] == 0
        assert len(results["errors"]) == 0
        assert len(results["created_resorts"]) == 14

        # Verify resort service was called correctly
        assert mock_resort_service.get_resort.call_count == 14
        assert mock_resort_service.create_resort.call_count == 14

    def test_seed_initial_resorts_some_exist(self, seeder, mock_resort_service):
        """Test seeding when some resorts already exist."""

        # Mock that Big White already exists
        def mock_get_resort(resort_id):
            if resort_id == "big-white":
                return Mock(resort_id=resort_id)
            return None

        mock_resort_service.get_resort.side_effect = mock_get_resort

        def mock_create_resort(resort):
            return resort

        mock_resort_service.create_resort.side_effect = mock_create_resort

        results = seeder.seed_initial_resorts()

        assert results["resorts_created"] == 13  # All except Big White
        assert results["resorts_skipped"] == 1  # Big White
        assert len(results["errors"]) == 0

        # Should create only 13 resorts
        assert mock_resort_service.create_resort.call_count == 13

    def test_seed_initial_resorts_with_errors(self, seeder, mock_resort_service):
        """Test seeding with some creation errors."""
        # Mock that no resorts exist
        mock_resort_service.get_resort.return_value = None

        # Mock creation with some failures
        def mock_create_resort(resort):
            if resort.resort_id == "lake-louise":
                raise Exception("Database connection failed")
            return resort

        mock_resort_service.create_resort.side_effect = mock_create_resort

        results = seeder.seed_initial_resorts()

        assert results["resorts_created"] == 13  # All except Lake Louise
        assert results["resorts_skipped"] == 0
        assert len(results["errors"]) == 1
        assert "lake-louise" in results["errors"][0]

    def test_get_resort_summary(self, seeder, mock_resort_service):
        """Test resort summary generation."""
        # Mock some resorts
        mock_resorts = [
            Mock(
                resort_id="big-white",
                name="Big White",
                country="CA",
                region="BC",
                elevation_points=[
                    Mock(elevation_meters=1500),
                    Mock(elevation_meters=2000),
                    Mock(elevation_meters=2300),
                ],
            ),
            Mock(
                resort_id="vail",
                name="Vail",
                country="US",
                region="CO",
                elevation_points=[
                    Mock(elevation_meters=2500),
                    Mock(elevation_meters=3500),
                ],
            ),
        ]

        mock_resort_service.get_all_resorts.return_value = mock_resorts

        summary = seeder.get_resort_summary()

        assert summary["total_resorts"] == 2
        assert summary["resorts_by_country"]["CA"] == 1
        assert summary["resorts_by_country"]["US"] == 1
        assert summary["resorts_by_region"]["BC, CA"] == 1
        assert summary["resorts_by_region"]["CO, US"] == 1

        # Check elevation ranges
        assert "big-white" in summary["elevation_ranges"]
        assert "vail" in summary["elevation_ranges"]

        big_white_elevation = summary["elevation_ranges"]["big-white"]
        assert big_white_elevation["min_elevation_m"] == 1500
        assert big_white_elevation["max_elevation_m"] == 2300
        assert big_white_elevation["vertical_drop_m"] == 800
        assert big_white_elevation["elevation_points"] == 3

    def test_validate_resort_data_valid_resorts(self, seeder, mock_resort_service):
        """Test validation of valid resort data."""
        valid_resorts = [
            Resort(
                resort_id="test-resort",
                name="Test Resort",
                country="CA",
                region="BC",
                timezone="America/Vancouver",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1000,
                        elevation_feet=3280,
                        latitude=49.0,
                        longitude=-120.0,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=2000,
                        elevation_feet=6562,
                        latitude=49.1,
                        longitude=-119.9,
                    ),
                ],
            )
        ]

        mock_resort_service.get_all_resorts.return_value = valid_resorts

        results = seeder.validate_resort_data()

        assert results["total_resorts"] == 1
        assert results["valid_resorts"] == 1
        assert len(results["issues"]) == 0

    def test_validate_resort_data_with_issues(self, seeder, mock_resort_service):
        """Test validation of resort data with issues."""
        # Create a mock resort with invalid attributes
        # Using spec=Resort ensures the Mock has the same attributes
        bad_resort = Mock()
        bad_resort.resort_id = "bad-resort"
        bad_resort.name = "X"  # Invalid name (too short)
        bad_resort.country = "XX"  # Invalid country
        bad_resort.region = "BC"
        bad_resort.timezone = ""  # Missing timezone

        # Create elevation point with invalid coordinates
        bad_point = Mock()
        bad_point.level = ElevationLevel.BASE
        bad_point.elevation_meters = 1000
        bad_point.latitude = 200.0  # Invalid latitude
        bad_point.longitude = -120.0

        bad_resort.elevation_points = [bad_point]

        mock_resort_service.get_all_resorts.return_value = [bad_resort]

        results = seeder.validate_resort_data()

        assert results["total_resorts"] == 1
        assert results["valid_resorts"] == 0
        assert len(results["issues"]) == 1

        issues = results["issues"][0]
        assert issues["resort_id"] == "bad-resort"
        assert any("name" in issue.lower() for issue in issues["issues"])
        assert any("country" in issue.lower() for issue in issues["issues"])
        assert any("timezone" in issue.lower() for issue in issues["issues"])
        assert any("latitude" in issue.lower() for issue in issues["issues"])

    @patch("builtins.open")
    @patch("json.dump")
    def test_export_resort_data(
        self, mock_json_dump, mock_open, seeder, mock_resort_service
    ):
        """Test resort data export functionality."""
        mock_resorts = [
            Mock(
                resort_id="test-resort",
                name="Test Resort",
                dict=lambda: {"resort_id": "test-resort", "name": "Test Resort"},
            )
        ]

        mock_resort_service.get_all_resorts.return_value = mock_resorts

        # Test export with default file name
        file_path = seeder.export_resort_data()

        assert file_path.startswith("resort_data_export_")
        assert file_path.endswith(".json")
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()

        # Check the exported data structure
        export_data = mock_json_dump.call_args[0][0]
        assert "export_timestamp" in export_data
        assert export_data["total_resorts"] == 1
        assert len(export_data["resorts"]) == 1

    def test_export_resort_data_custom_path(self, seeder, mock_resort_service):
        """Test resort data export with custom file path."""
        mock_resort_service.get_all_resorts.return_value = []

        with patch("builtins.open"), patch("json.dump"):
            file_path = seeder.export_resort_data("custom_export.json")
            assert file_path == "custom_export.json"

    def test_service_error_handling(self, seeder, mock_resort_service):
        """Test error handling when resort service fails."""
        mock_resort_service.get_all_resorts.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            seeder.get_resort_summary()

        with pytest.raises(Exception, match="Database error"):
            seeder.validate_resort_data()

        with pytest.raises(Exception, match="Database error"):
            seeder.export_resort_data()

    def test_specific_resort_data_accuracy(self, seeder):
        """Test specific accuracy of resort data for known values."""
        resorts = seeder._get_initial_resort_data()

        # Test Lake Louise specific data
        lake_louise = next(r for r in resorts if r.resort_id == "lake-louise")
        assert lake_louise.name == "Lake Louise Ski Resort"
        assert lake_louise.country == "CA"
        assert lake_louise.region == "AB"
        assert lake_louise.timezone == "America/Edmonton"

        # Check elevation data matches researched values
        summit_point = next(
            p for p in lake_louise.elevation_points if p.level == ElevationLevel.TOP
        )
        assert summit_point.elevation_meters == 2637
        assert summit_point.elevation_feet == 8652

        # Test Silver Star specific data
        silver_star = next(r for r in resorts if r.resort_id == "silver-star")
        assert silver_star.name == "SilverStar Mountain Resort"

        # Check coordinates are in reasonable ranges for Silver Star (near Vernon, BC)
        for point in silver_star.elevation_points:
            assert 50.35 <= point.latitude <= 50.37  # Near Vernon
            assert -119.07 <= point.longitude <= -119.06
