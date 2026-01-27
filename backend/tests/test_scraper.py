"""Tests for the ski resort scraper and population scripts."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from populate_resorts import ResortPopulator, ResortValidator
from scrape_resorts import (
    CA_PROVINCE_REGIONS,
    REGION_MAPPINGS,
    TIMEZONE_MAPPINGS,
    US_STATE_REGIONS,
    BaseScraper,
    ScrapedResort,
)


class TestScrapedResort:
    """Tests for the ScrapedResort dataclass."""

    def test_resort_id_generation(self):
        """Test automatic resort ID generation from name."""
        resort = ScrapedResort(
            name="Whistler Blackcomb",
            country="CA",
            region="na_west",
            state_province="BC",
            elevation_base_m=675,
            elevation_top_m=2284,
            latitude=50.1159,
            longitude=-122.9546,
            timezone="America/Vancouver",
        )
        assert resort.resort_id == "whistler-blackcomb"

    def test_resort_id_special_characters(self):
        """Test resort ID handles special characters."""
        resort = ScrapedResort(
            name="Val d'Isère",
            country="FR",
            region="alps",
            state_province="Savoie",
            elevation_base_m=1850,
            elevation_top_m=3456,
            latitude=45.4478,
            longitude=6.9803,
            timezone="Europe/Paris",
        )
        # Apostrophes are removed, resulting in "val disere" -> "val-disere"
        assert resort.resort_id == "val-disere"

    def test_resort_id_umlauts(self):
        """Test resort ID handles umlauts and accents."""
        resort = ScrapedResort(
            name="Kitzbühel",
            country="AT",
            region="alps",
            state_province="Tyrol",
            elevation_base_m=800,
            elevation_top_m=2000,
            latitude=47.4492,
            longitude=12.3917,
            timezone="Europe/Vienna",
        )
        assert resort.resort_id == "kitzbuhel"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        resort = ScrapedResort(
            name="Vail Mountain Resort",
            country="US",
            region="na_rockies",
            state_province="CO",
            elevation_base_m=2475,
            elevation_top_m=3527,
            latitude=39.6403,
            longitude=-106.3742,
            timezone="America/Denver",
            website="https://www.vail.com",
            features=["terrain_park", "night_skiing"],
            annual_snowfall_cm=889,
        )

        result = resort.to_dict()

        assert result["resort_id"] == "vail-mountain-resort"
        assert result["name"] == "Vail Mountain Resort"
        assert result["country"] == "US"
        assert result["region"] == "na_rockies"
        assert result["state_province"] == "CO"
        assert result["elevation_base_m"] == 2475
        assert result["elevation_top_m"] == 3527
        assert result["latitude"] == 39.6403
        assert result["longitude"] == -106.3742
        assert result["timezone"] == "America/Denver"
        assert result["website"] == "https://www.vail.com"
        assert "terrain_park" in result["features"]
        assert result["annual_snowfall_cm"] == 889


class TestBaseScraper:
    """Tests for the BaseScraper class."""

    def test_get_region_us_rockies(self):
        """Test region determination for US Rocky Mountain states."""
        scraper = BaseScraper()

        assert scraper.get_region("US", "CO") == "na_rockies"
        assert scraper.get_region("US", "UT") == "na_rockies"
        assert scraper.get_region("US", "WY") == "na_rockies"
        assert scraper.get_region("US", "MT") == "na_rockies"

    def test_get_region_us_west(self):
        """Test region determination for US West Coast states."""
        scraper = BaseScraper()

        assert scraper.get_region("US", "CA") == "na_west"
        assert scraper.get_region("US", "OR") == "na_west"
        assert scraper.get_region("US", "WA") == "na_west"

    def test_get_region_us_east(self):
        """Test region determination for US East Coast states."""
        scraper = BaseScraper()

        assert scraper.get_region("US", "VT") == "na_east"
        assert scraper.get_region("US", "NH") == "na_east"
        assert scraper.get_region("US", "ME") == "na_east"
        assert scraper.get_region("US", "NY") == "na_east"

    def test_get_region_canada(self):
        """Test region determination for Canadian provinces."""
        scraper = BaseScraper()

        assert scraper.get_region("CA", "BC") == "na_west"
        assert scraper.get_region("CA", "AB") == "na_rockies"
        assert scraper.get_region("CA", "QC") == "na_east"
        assert scraper.get_region("CA", "ON") == "na_east"

    def test_get_region_europe(self):
        """Test region determination for European countries."""
        scraper = BaseScraper()

        assert scraper.get_region("FR", "") == "alps"
        assert scraper.get_region("CH", "") == "alps"
        assert scraper.get_region("AT", "") == "alps"
        assert scraper.get_region("IT", "") == "alps"
        assert scraper.get_region("NO", "") == "scandinavia"
        assert scraper.get_region("SE", "") == "scandinavia"

    def test_get_region_other(self):
        """Test region determination for other countries."""
        scraper = BaseScraper()

        assert scraper.get_region("JP", "") == "japan"
        assert scraper.get_region("AU", "") == "oceania"
        assert scraper.get_region("NZ", "") == "oceania"
        assert scraper.get_region("CL", "") == "south_america"
        assert scraper.get_region("AR", "") == "south_america"

    def test_get_timezone_us(self):
        """Test timezone determination for US states."""
        scraper = BaseScraper()

        assert scraper.get_timezone("US", "CA") == "America/Los_Angeles"
        assert scraper.get_timezone("US", "CO") == "America/Denver"
        assert scraper.get_timezone("US", "VT") == "America/New_York"

    def test_get_timezone_canada(self):
        """Test timezone determination for Canadian provinces."""
        scraper = BaseScraper()

        assert scraper.get_timezone("CA", "BC") == "America/Vancouver"
        assert scraper.get_timezone("CA", "AB") == "America/Edmonton"
        assert scraper.get_timezone("CA", "ON") == "America/Toronto"

    def test_get_timezone_europe(self):
        """Test timezone determination for European countries."""
        scraper = BaseScraper()

        assert scraper.get_timezone("FR", "") == "Europe/Paris"
        assert scraper.get_timezone("CH", "") == "Europe/Zurich"
        assert scraper.get_timezone("AT", "") == "Europe/Vienna"

    def test_get_timezone_fallback(self):
        """Test timezone fallback to UTC."""
        scraper = BaseScraper()

        assert scraper.get_timezone("XX", "") == "UTC"


class TestResortValidator:
    """Tests for the ResortValidator class."""

    def test_valid_resort(self):
        """Test validation of a valid resort."""
        data = {
            "resort_id": "big-white",
            "name": "Big White Ski Resort",
            "country": "CA",
            "region": "na_west",
            "state_province": "BC",
            "elevation_base_m": 1508,
            "elevation_top_m": 2319,
            "latitude": 49.7196,
            "longitude": -118.9296,
            "timezone": "America/Vancouver",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is True
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Test validation catches missing required fields."""
        data = {
            "resort_id": "test-resort",
            "name": "Test Resort",
            # Missing country, elevation, coordinates, timezone
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("country" in e.lower() for e in errors)

    def test_invalid_country_code(self):
        """Test validation catches invalid country codes."""
        data = {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "XX",  # Invalid
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": 45.0,
            "longitude": -120.0,
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("country" in e.lower() for e in errors)

    def test_invalid_elevation_order(self):
        """Test validation catches base elevation greater than top."""
        data = {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "US",
            "elevation_base_m": 3000,  # Higher than top
            "elevation_top_m": 2000,
            "latitude": 45.0,
            "longitude": -120.0,
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("elevation" in e.lower() for e in errors)

    def test_invalid_coordinates(self):
        """Test validation catches invalid coordinates."""
        data = {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "US",
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": 100.0,  # Invalid latitude
            "longitude": -120.0,
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("latitude" in e.lower() for e in errors)

    def test_placeholder_coordinates(self):
        """Test validation catches placeholder (0, 0) coordinates."""
        data = {
            "resort_id": "test-resort",
            "name": "Test Resort",
            "country": "US",
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": 0.0,  # Placeholder
            "longitude": 0.0,  # Placeholder
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("placeholder" in e.lower() or "(0, 0)" in e for e in errors)

    def test_invalid_resort_id(self):
        """Test validation catches invalid resort ID format."""
        data = {
            "resort_id": "test resort!!!",  # Invalid characters
            "name": "Test Resort",
            "country": "US",
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": 45.0,
            "longitude": -120.0,
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("resort_id" in e.lower() for e in errors)

    def test_invalid_name(self):
        """Test validation catches invalid names."""
        data = {
            "resort_id": "test-resort",
            "name": "X",  # Too short
            "country": "US",
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": 45.0,
            "longitude": -120.0,
            "timezone": "UTC",
        }

        is_valid, errors = ResortValidator.validate(data)

        assert is_valid is False
        assert any("name" in e.lower() for e in errors)


class TestResortPopulator:
    """Tests for the ResortPopulator class."""

    def test_transform_to_resort(self):
        """Test transformation of JSON data to Resort model."""
        mock_service = Mock()
        populator = ResortPopulator(mock_service)

        data = {
            "resort_id": "big-white",
            "name": "Big White Ski Resort",
            "country": "CA",
            "region": "na_west",
            "state_province": "BC",
            "elevation_base_m": 1508,
            "elevation_top_m": 2319,
            "latitude": 49.7196,
            "longitude": -118.9296,
            "timezone": "America/Vancouver",
            "website": "https://www.bigwhite.com",
        }

        resort = populator.transform_to_resort(data)

        assert resort.resort_id == "big-white"
        assert resort.name == "Big White Ski Resort"
        assert resort.country == "CA"
        assert resort.region == "BC"  # Uses state_province
        assert resort.timezone == "America/Vancouver"
        assert resort.official_website == "https://www.bigwhite.com"
        assert len(resort.elevation_points) == 3

        # Check elevation points
        base = resort.elevation_points[0]
        assert base.level.value == "base"
        assert base.elevation_meters == 1508
        assert base.latitude == 49.7196
        assert base.longitude == -118.9296

        mid = resort.elevation_points[1]
        assert mid.level.value == "mid"
        assert mid.elevation_meters == (1508 + 2319) // 2

        top = resort.elevation_points[2]
        assert top.level.value == "top"
        assert top.elevation_meters == 2319

    def test_populate_creates_new_resort(self):
        """Test populating a new resort."""
        mock_service = Mock()
        mock_service.get_resort.return_value = None
        mock_service.create_resort.return_value = Mock()

        populator = ResortPopulator(mock_service)

        data = [
            {
                "resort_id": "new-resort",
                "name": "New Resort",
                "country": "US",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": -120.0,
                "timezone": "America/Los_Angeles",
            }
        ]

        results = populator.populate(data)

        assert results["created"] == 1
        assert results["skipped"] == 0
        assert results["failed"] == 0
        assert "new-resort" in results["created_ids"]
        mock_service.create_resort.assert_called_once()

    def test_populate_skips_existing_resort(self):
        """Test that existing resorts are skipped by default."""
        mock_service = Mock()
        mock_service.get_resort.return_value = Mock()  # Resort exists

        populator = ResortPopulator(mock_service)

        data = [
            {
                "resort_id": "existing-resort",
                "name": "Existing Resort",
                "country": "US",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": -120.0,
                "timezone": "America/Los_Angeles",
            }
        ]

        results = populator.populate(data)

        assert results["created"] == 0
        assert results["skipped"] == 1
        assert "existing-resort" in results["skipped_ids"]
        mock_service.create_resort.assert_not_called()

    def test_populate_updates_existing_when_flag_set(self):
        """Test that existing resorts are updated when flag is set."""
        mock_service = Mock()
        existing = Mock()
        existing.created_at = "2026-01-01T00:00:00Z"
        mock_service.get_resort.return_value = existing
        mock_service.update_resort.return_value = Mock()

        populator = ResortPopulator(mock_service, update_existing=True)

        data = [
            {
                "resort_id": "existing-resort",
                "name": "Existing Resort",
                "country": "US",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": -120.0,
                "timezone": "America/Los_Angeles",
            }
        ]

        results = populator.populate(data)

        assert results["updated"] == 1
        assert "existing-resort" in results["updated_ids"]
        mock_service.update_resort.assert_called_once()

    def test_populate_handles_validation_failure(self):
        """Test that validation failures are handled gracefully."""
        mock_service = Mock()
        populator = ResortPopulator(mock_service)

        data = [
            {
                "resort_id": "invalid-resort",
                "name": "X",  # Too short
                "country": "XX",  # Invalid
                # Missing other required fields
            }
        ]

        results = populator.populate(data)

        assert results["failed"] == 1
        assert len(results["errors"]) == 1
        mock_service.create_resort.assert_not_called()

    def test_populate_dry_run(self):
        """Test that dry run doesn't modify database."""
        mock_service = Mock()
        populator = ResortPopulator(mock_service, dry_run=True)

        data = [
            {
                "resort_id": "new-resort",
                "name": "New Resort",
                "country": "US",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": -120.0,
                "timezone": "America/Los_Angeles",
            }
        ]

        results = populator.populate(data)

        # In dry run mode, we don't call the service
        assert results["created"] == 1
        mock_service.create_resort.assert_not_called()


class TestRegionMappings:
    """Tests for the region and timezone mapping constants."""

    def test_all_regions_have_countries(self):
        """Test that region mappings cover major skiing countries."""
        skiing_countries = [
            "US",
            "CA",
            "FR",
            "CH",
            "AT",
            "IT",
            "JP",
            "AU",
            "NZ",
            "CL",
            "AR",
        ]

        for country in skiing_countries:
            assert country in REGION_MAPPINGS, f"Missing region mapping for {country}"

    def test_us_states_have_regions(self):
        """Test that major US skiing states have region mappings."""
        skiing_states = ["CO", "UT", "CA", "WY", "MT", "VT", "NH"]

        for state in skiing_states:
            assert state in US_STATE_REGIONS, f"Missing US state mapping for {state}"

    def test_canadian_provinces_have_regions(self):
        """Test that major Canadian provinces have region mappings."""
        skiing_provinces = ["BC", "AB", "QC", "ON"]

        for province in skiing_provinces:
            assert province in CA_PROVINCE_REGIONS, (
                f"Missing CA province mapping for {province}"
            )

    def test_timezone_coverage(self):
        """Test that major skiing locations have timezone mappings."""
        # Test US timezones
        assert ("US", "CO") in TIMEZONE_MAPPINGS
        assert ("US", "CA") in TIMEZONE_MAPPINGS

        # Test Canadian timezones
        assert ("CA", "BC") in TIMEZONE_MAPPINGS
        assert ("CA", "AB") in TIMEZONE_MAPPINGS

        # Test European timezones
        assert ("FR", None) in TIMEZONE_MAPPINGS
        assert ("CH", None) in TIMEZONE_MAPPINGS
        assert ("AT", None) in TIMEZONE_MAPPINGS

        # Test other regions
        assert ("JP", None) in TIMEZONE_MAPPINGS
        assert ("NZ", None) in TIMEZONE_MAPPINGS
