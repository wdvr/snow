"""Tests for the Snow-Forecast.com scraper."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from services.snowforecast_scraper import (
    SLUGS_FILE,
    SnowForecastData,
    SnowForecastScraper,
)


class TestSlugGeneration:
    """Tests for resort ID to Snow-Forecast slug conversion."""

    def test_simple_slug_auto_generation(self):
        """Auto-generated slugs capitalize each segment."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("big-white") == "Big-White"

    def test_single_word_slug(self):
        """Single-word resort IDs get capitalized."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("vail") == "Vail"

    def test_three_word_slug(self):
        """Multi-word resort IDs get each segment capitalized."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("big-sky-resort") == "Big-Sky-Resort"

    def test_override_slug_takes_precedence(self):
        """Override slugs from JSON file take precedence over auto-generation."""
        scraper = SnowForecastScraper()
        # These should come from the overrides file
        assert scraper._get_slug("st-anton") == "St-Anton-am-Arlberg"
        assert scraper._get_slug("queenstown-remarkables") == "The-Remarkables"
        assert scraper._get_slug("cortina") == "Cortina-d-Ampezzo"

    def test_val_disere_override(self):
        """Val d'Isere has a special slug."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("val-disere") == "Val-d-Isere"

    def test_kitzbuehel_override(self):
        """Kitzbuhel maps correctly (umlaut removed in resort_id)."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("kitzbuehel") == "Kitzbuhel"

    def test_unknown_resort_gets_auto_slug(self):
        """Resorts not in overrides get auto-generated slugs."""
        scraper = SnowForecastScraper()
        assert scraper._get_slug("some-new-resort") == "Some-New-Resort"


class TestSlugOverridesLoading:
    """Tests for loading slug overrides from file."""

    def test_loads_overrides_from_file(self):
        """Slug overrides file should be loaded on init."""
        scraper = SnowForecastScraper()
        # The file exists in our repo, should have been loaded
        assert len(scraper._slug_overrides) > 0

    @patch("services.snowforecast_scraper.SLUGS_FILE")
    def test_handles_missing_file(self, mock_path):
        """Missing overrides file should result in empty overrides."""
        mock_path.exists.return_value = False
        scraper = SnowForecastScraper()
        assert scraper._slug_overrides == {}

    @patch("services.snowforecast_scraper.SLUGS_FILE")
    def test_handles_invalid_json(self, mock_path):
        """Invalid JSON in overrides file should result in empty overrides."""
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda s: "/fake/path.json"
        with patch("builtins.open", side_effect=json.JSONDecodeError("", "", 0)):
            scraper = SnowForecastScraper()
            assert scraper._slug_overrides == {}


class TestHTMLParsing:
    """Tests for parsing Snow-Forecast HTML pages."""

    def test_parse_snowfall_24h(self):
        """Extract 24h snowfall from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>New snow in 24h: 15cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.snowfall_24h_cm == 15.0

    def test_parse_snowfall_48h(self):
        """Extract 48h snowfall from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>48hr: 30cm of fresh snow</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.snowfall_48h_cm == 30.0

    def test_parse_snowfall_72h(self):
        """Extract 72h snowfall from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>72h: 45.5cm accumulated</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.snowfall_72h_cm == 45.5

    def test_parse_upper_depth(self):
        """Extract upper snow depth from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>Upper snow depth: 250cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.upper_depth_cm == 250.0

    def test_parse_lower_depth(self):
        """Extract lower snow depth from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>Lower depth: 120cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.lower_depth_cm == 120.0

    def test_parse_top_depth_alias(self):
        """'Top depth' should be parsed as upper depth."""
        scraper = SnowForecastScraper()
        html = "<div>Top depth: 300cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.upper_depth_cm == 300.0

    def test_parse_base_depth_alias(self):
        """'Base depth' should be parsed as lower depth."""
        scraper = SnowForecastScraper()
        html = "<div>Base depth: 80cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.lower_depth_cm == 80.0

    def test_parse_surface_conditions(self):
        """Extract surface conditions from HTML."""
        scraper = SnowForecastScraper()
        html = "<div>Surface conditions: Packed Powder\n</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.surface_conditions == "Packed Powder"

    def test_parse_snow_type_conditions(self):
        """Extract 'snow type' as surface conditions."""
        scraper = SnowForecastScraper()
        html = "<div>Snow type: Fresh Powder\n</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.surface_conditions == "Fresh Powder"

    def test_parse_combined_report(self):
        """Parse a page with all data fields present."""
        scraper = SnowForecastScraper()
        html = """
        <div class="snow-report">
            <p>New snow in 24h: 12cm</p>
            <p>48hr: 25cm</p>
            <p>72h: 40cm</p>
            <p>Upper snow depth: 280cm</p>
            <p>Lower depth: 150cm</p>
            <p>Surface conditions: Machine Groomed</p>
        </div>
        """
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.snowfall_24h_cm == 12.0
        assert result.snowfall_48h_cm == 25.0
        assert result.snowfall_72h_cm == 40.0
        assert result.upper_depth_cm == 280.0
        assert result.lower_depth_cm == 150.0
        assert result.surface_conditions == "Machine Groomed"

    def test_parse_empty_html_returns_none_fields(self):
        """Empty HTML should produce data with all None fields."""
        scraper = SnowForecastScraper()
        html = "<html><body><p>No snow data here</p></body></html>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.resort_id == "test-resort"
        assert result.snowfall_24h_cm is None
        assert result.snowfall_48h_cm is None
        assert result.snowfall_72h_cm is None
        assert result.upper_depth_cm is None
        assert result.lower_depth_cm is None
        assert result.surface_conditions is None

    def test_sanity_check_rejects_huge_depth(self):
        """Depth values over 1500cm should be rejected."""
        scraper = SnowForecastScraper()
        html = "<div>Upper depth: 9999cm Lower depth: 9999cm</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.upper_depth_cm is None
        assert result.lower_depth_cm is None

    def test_parse_preserves_resort_id_and_url(self):
        """Parsed data should carry the resort_id and source_url."""
        scraper = SnowForecastScraper()
        html = "<div>nothing useful</div>"
        result = scraper._parse_snow_report(
            html, "chamonix", "https://snow-forecast.com/resorts/Chamonix/6day/mid"
        )
        assert result.resort_id == "chamonix"
        assert (
            result.source_url == "https://snow-forecast.com/resorts/Chamonix/6day/mid"
        )

    def test_short_surface_condition_ignored(self):
        """Very short condition strings (< 3 chars) should be ignored as noise."""
        scraper = SnowForecastScraper()
        html = "<div>Surface conditions: OK\n</div>"
        result = scraper._parse_snow_report(html, "test-resort", "https://test.com")
        assert result.surface_conditions is None


class TestGetSnowReport:
    """Tests for the get_snow_report method with mocked HTTP."""

    def test_successful_fetch(self):
        """Successful HTTP fetch returns parsed data."""
        scraper = SnowForecastScraper()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<div>24hr: 10cm Upper depth: 200cm</div>"
        mock_response.raise_for_status = Mock()

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.get_snow_report("big-white")

        assert result is not None
        assert result.resort_id == "big-white"
        assert result.snowfall_24h_cm == 10.0
        assert result.upper_depth_cm == 200.0
        assert "Big-White" in result.source_url

    def test_uses_correct_url(self):
        """get_snow_report uses the correct URL with slug."""
        scraper = SnowForecastScraper()
        mock_response = Mock()
        mock_response.text = "<div></div>"
        mock_response.raise_for_status = Mock()

        with patch.object(
            scraper.session, "get", return_value=mock_response
        ) as mock_get:
            scraper.get_snow_report("st-anton")
            mock_get.assert_called_once_with(
                "https://www.snow-forecast.com/resorts/St-Anton-am-Arlberg/6day/mid",
                timeout=15,
            )

    def test_network_error_returns_none(self):
        """Network errors should return None gracefully."""
        scraper = SnowForecastScraper()
        with patch.object(
            scraper.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = scraper.get_snow_report("big-white")
            assert result is None

    def test_timeout_returns_none(self):
        """Timeouts should return None gracefully."""
        scraper = SnowForecastScraper()
        with patch.object(
            scraper.session,
            "get",
            side_effect=requests.exceptions.Timeout("Timed out"),
        ):
            result = scraper.get_snow_report("big-white")
            assert result is None

    def test_http_404_returns_none(self):
        """404 responses should return None gracefully."""
        scraper = SnowForecastScraper()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.get_snow_report("nonexistent-resort")
            assert result is None

    def test_http_500_returns_none(self):
        """Server errors should return None gracefully."""
        scraper = SnowForecastScraper()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.get_snow_report("big-white")
            assert result is None

    def test_malformed_html_returns_empty_data(self):
        """Malformed HTML should return data object with None fields, not crash."""
        scraper = SnowForecastScraper()
        mock_response = Mock()
        mock_response.text = "<html><not closed properly<div>garbage"
        mock_response.raise_for_status = Mock()

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.get_snow_report("big-white")
            assert result is not None
            assert result.resort_id == "big-white"
            assert result.snowfall_24h_cm is None


class TestIsResortSupported:
    """Tests for the is_resort_supported method."""

    def test_all_resorts_supported(self):
        """Snow-Forecast has broad coverage, all resorts return True."""
        scraper = SnowForecastScraper()
        assert scraper.is_resort_supported("big-white") is True
        assert scraper.is_resort_supported("chamonix") is True
        assert scraper.is_resort_supported("niseko") is True
        assert scraper.is_resort_supported("unknown-resort") is True


class TestDataclass:
    """Tests for the SnowForecastData dataclass."""

    def test_create_full_data(self):
        """Create a SnowForecastData with all fields."""
        data = SnowForecastData(
            resort_id="chamonix",
            snowfall_24h_cm=15.0,
            snowfall_48h_cm=30.0,
            snowfall_72h_cm=45.0,
            upper_depth_cm=280.0,
            lower_depth_cm=120.0,
            surface_conditions="Fresh Powder",
            source_url="https://www.snow-forecast.com/resorts/Chamonix/6day/mid",
        )
        assert data.resort_id == "chamonix"
        assert data.snowfall_24h_cm == 15.0
        assert data.upper_depth_cm == 280.0

    def test_create_empty_data(self):
        """Create a SnowForecastData with all None optional fields."""
        data = SnowForecastData(
            resort_id="test",
            snowfall_24h_cm=None,
            snowfall_48h_cm=None,
            snowfall_72h_cm=None,
            upper_depth_cm=None,
            lower_depth_cm=None,
            surface_conditions=None,
            source_url="https://test.com",
        )
        assert data.resort_id == "test"
        assert data.snowfall_24h_cm is None
        assert data.upper_depth_cm is None
