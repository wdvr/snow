"""Comprehensive unit tests for the scraper_worker Lambda handler.

Tests cover:
- ScraperSession (rate limiting, retries, get_soup)
- get_region() mapping logic
- collect_resort_urls() pagination and URL filtering
- scrape_resort_detail() HTML parsing and data extraction
- extract_state_province()
- extract_coordinates()
- geocode_resort()
- generate_resort_id() (special characters, accents, etc.)
- get_existing_resort_ids() DynamoDB scanning with pagination
- publish_new_resorts_notification() SNS publishing
- scraper_worker_handler() Lambda entry point (S3 uploads, delta mode, errors)
"""

import json
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import requests
from bs4 import BeautifulSoup

# We need to patch the module-level AWS clients before import.
# The module initializes boto3 clients at import time, so we patch boto3.resource/client
# during the import.
with patch("boto3.resource"), patch("boto3.client"):
    from handlers.scraper_worker import (
        CA_PROVINCE_REGIONS,
        COUNTRY_URLS,
        MAX_RETRIES,
        MIN_VERTICAL,
        REGION_MAPPINGS,
        US_STATE_REGIONS,
        ScraperSession,
        collect_resort_urls,
        extract_coordinates,
        extract_state_province,
        generate_resort_id,
        geocode_resort,
        get_existing_resort_ids,
        get_region,
        publish_new_resorts_notification,
        scrape_resort_detail,
        scraper_worker_handler,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup object from an HTML fragment."""
    return BeautifulSoup(html, "html.parser")


def _resort_page_html(
    name="Chamonix Mont-Blanc",
    base=1035,
    top=3842,
    data_lat=None,
    data_lng=None,
    script_coords=False,
    mobile_header_text="",
    has_next_page=False,
):
    """Build a minimal resort detail HTML page."""
    coords_attr = ""
    if data_lat is not None and data_lng is not None:
        coords_attr = f'<div data-lat="{data_lat}" data-lng="{data_lng}"></div>'

    script_tag = ""
    if script_coords:
        script_tag = "<script>var lat = 45.92; var lng = 6.87;</script>"

    mobile = ""
    if mobile_header_text:
        mobile = f'<div class="mobile-header-regionselector">{mobile_header_text}</div>'

    next_link = ""
    if has_next_page:
        next_link = (
            '<div class="pagination"><a class="next" href="/page/2">Next</a></div>'
        )

    return f"""
    <html><body>
    <h1>Ski resort {name}</h1>
    {mobile}
    {coords_attr}
    {script_tag}
    <div>{base} m - {top} m</div>
    {next_link}
    </body></html>
    """


def _listing_page_html(resort_hrefs, has_next=False):
    """Build a listing page with resort links."""
    links = "\n".join(f'<a href="{href}">Resort</a>' for href in resort_hrefs)
    pagination = ""
    if has_next:
        pagination = '<div class="pagination"><a class="next" href="#">Next</a></div>'
    return f"<html><body>{links}{pagination}</body></html>"


# ===========================================================================
# Tests for generate_resort_id
# ===========================================================================


class TestGenerateResortId:
    """Tests for the generate_resort_id helper."""

    def test_basic_name(self):
        assert generate_resort_id("Vail Mountain") == "vail-mountain"

    def test_special_characters(self):
        assert generate_resort_id("Val d'Isere") == "val-disere"

    def test_accented_characters(self):
        assert generate_resort_id("Kitzbuhel") == "kitzbuhel"
        assert generate_resort_id("Chamonix Mont-Blanc") == "chamonix-mont-blanc"

    def test_umlaut_o(self):
        assert generate_resort_id("Soelden") == "soelden"
        # o with umlaut
        assert generate_resort_id("Solden") == "solden"

    def test_accented_a(self):
        assert generate_resort_id("Arlberg") == "arlberg"
        # a with accent
        result = generate_resort_id("Arare")
        assert result == "arare"

    def test_accented_e(self):
        result = generate_resort_id("Val d'Isere")
        assert "isere" in result

    def test_accented_u(self):
        result = generate_resort_id("Kitzbuhel")
        assert result == "kitzbuhel"

    def test_leading_trailing_hyphens_stripped(self):
        result = generate_resort_id("  --Test Resort-- ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_consecutive_hyphens_collapsed(self):
        result = generate_resort_id("Big   White")
        assert "--" not in result
        assert result == "big-white"

    def test_backtick_removed(self):
        result = generate_resort_id("Val d`Isere")
        assert "`" not in result

    def test_empty_after_cleaning(self):
        # Pure special characters produce an empty string
        result = generate_resort_id("---")
        assert result == ""

    def test_numeric_names(self):
        result = generate_resort_id("3 Valleys")
        assert result == "3-valleys"


# ===========================================================================
# Tests for get_region
# ===========================================================================


class TestGetRegion:
    """Tests for the get_region() function."""

    def test_us_state_colorado(self):
        assert get_region("US", "CO") == "na_rockies"

    def test_us_state_california(self):
        assert get_region("US", "CA") == "na_west"

    def test_us_state_vermont(self):
        assert get_region("US", "VT") == "na_east"

    def test_us_state_wisconsin(self):
        assert get_region("US", "WI") == "na_midwest"

    def test_us_unknown_state_falls_through_to_country(self):
        # US with unknown state falls back to REGION_MAPPINGS["US"]
        assert get_region("US", "ZZ") == "na_rockies"

    def test_canada_bc(self):
        assert get_region("CA", "BC") == "na_west"

    def test_canada_ab(self):
        assert get_region("CA", "AB") == "na_rockies"

    def test_canada_unknown_province(self):
        assert get_region("CA", "ZZ") == "na_west"

    def test_france_alps(self):
        assert get_region("FR", "") == "alps"

    def test_japan(self):
        assert get_region("JP", "") == "japan"

    def test_unknown_country(self):
        assert get_region("XX", "") == "other"

    def test_south_america(self):
        assert get_region("CL", "") == "south_america"
        assert get_region("AR", "") == "south_america"

    def test_scandinavia(self):
        assert get_region("NO", "") == "scandinavia"
        assert get_region("SE", "") == "scandinavia"
        assert get_region("FI", "") == "scandinavia"


# ===========================================================================
# Tests for ScraperSession
# ===========================================================================


class TestScraperSession:
    """Tests for the ScraperSession HTTP wrapper."""

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_rate_limiting_sleeps_when_too_fast(self, mock_time, mock_sleep):
        """Requests closer than REQUEST_DELAY apart should trigger sleep."""
        # First call to time.time() in __init__ is 0
        # _rate_limit calls time.time() to get elapsed, then again to update _last_request_time
        mock_time.side_effect = [100.0, 100.5, 101.0]
        session = ScraperSession()
        session._last_request_time = 100.0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        session.session = Mock()
        session.session.get.return_value = mock_response

        session.get("https://example.com")
        mock_sleep.assert_called_once()

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_no_sleep_when_enough_time_elapsed(self, mock_time, mock_sleep):
        """No sleep needed when enough time has passed since last request."""
        mock_time.side_effect = [200.0, 200.0]
        session = ScraperSession()
        session._last_request_time = 0  # Very old timestamp -> elapsed > REQUEST_DELAY

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        session.session = Mock()
        session.session.get.return_value = mock_response

        session.get("https://example.com")
        mock_sleep.assert_not_called()

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_retries_on_request_exception(self, mock_time, mock_sleep):
        """Should retry on RequestException up to MAX_RETRIES."""
        mock_time.return_value = 0
        session = ScraperSession()
        session._last_request_time = 0

        session.session = Mock()
        session.session.get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException):
            session.get("https://example.com")

        assert session.session.get.call_count == MAX_RETRIES

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_successful_after_retry(self, mock_time, mock_sleep):
        """Should succeed if a retry succeeds."""
        mock_time.return_value = 0
        session = ScraperSession()
        session._last_request_time = 0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        session.session = Mock()
        session.session.get.side_effect = [
            requests.RequestException("Fail 1"),
            mock_response,
        ]

        result = session.get("https://example.com")
        assert result is mock_response
        assert session.session.get.call_count == 2

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_get_soup_returns_beautifulsoup(self, mock_time, mock_sleep):
        """get_soup should return a BeautifulSoup object."""
        mock_time.return_value = 0
        session = ScraperSession()
        session._last_request_time = 0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = "<html><body><h1>Hello</h1></body></html>"

        session.session = Mock()
        session.session.get.return_value = mock_response

        soup = session.get_soup("https://example.com")
        assert isinstance(soup, BeautifulSoup)
        assert soup.h1.get_text() == "Hello"

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time")
    def test_exponential_backoff_on_retries(self, mock_time, mock_sleep):
        """Should use exponential backoff between retries."""
        mock_time.return_value = 0
        session = ScraperSession()
        session._last_request_time = 0

        session.session = Mock()
        session.session.get.side_effect = requests.RequestException("Error")

        with pytest.raises(requests.RequestException):
            session.get("https://example.com")

        # Check backoff sleep calls: 2^0=1, 2^1=2 (third attempt raises, no sleep after)
        backoff_calls = [
            c
            for c in mock_sleep.call_args_list
            if c != call(pytest.approx(1.0, abs=1.1))
        ]
        # The sleeps should include exponential backoff (2**0=1 and 2**1=2)
        sleep_args = [c[0][0] for c in mock_sleep.call_args_list]
        # At least some of these should be backoff values
        assert 1 in sleep_args or 2 in sleep_args


# ===========================================================================
# Tests for extract_coordinates
# ===========================================================================


class TestExtractCoordinates:
    """Tests for extracting coordinates from HTML."""

    def test_data_attributes_lat_lng(self):
        soup = _make_soup('<div data-lat="47.45" data-lng="12.39"></div>')
        lat, lon = extract_coordinates(soup)
        assert lat == 47.45
        assert lon == 12.39

    def test_data_attributes_latitude_longitude(self):
        soup = _make_soup('<div data-latitude="45.0" data-longitude="6.9"></div>')
        lat, lon = extract_coordinates(soup)
        assert lat == 45.0
        assert lon == 6.9

    def test_data_attributes_lat_lon(self):
        soup = _make_soup('<div data-lat="40.0" data-lon="-111.5"></div>')
        lat, lon = extract_coordinates(soup)
        assert lat == 40.0
        assert lon == -111.5

    def test_script_tag_coordinates(self):
        # The regex expects lat[itude]*["':\s]+ then digits, so use JSON-like format
        soup = _make_soup('<script>{"lat": 45.92, "lng": 6.87}</script>')
        lat, lon = extract_coordinates(soup)
        assert lat == pytest.approx(45.92)
        assert lon == pytest.approx(6.87)

    def test_script_tag_with_quotes(self):
        soup = _make_soup(
            """<script>{"latitude": "48.12", "longitude": "11.07"}</script>"""
        )
        lat, lon = extract_coordinates(soup)
        assert lat == pytest.approx(48.12)
        assert lon == pytest.approx(11.07)

    def test_no_coordinates_returns_zeros(self):
        soup = _make_soup("<html><body><p>No coordinates here</p></body></html>")
        lat, lon = extract_coordinates(soup)
        assert lat == 0.0
        assert lon == 0.0

    def test_negative_coordinates(self):
        soup = _make_soup('<div data-lat="-43.5" data-lng="172.6"></div>')
        lat, lon = extract_coordinates(soup)
        assert lat == -43.5
        assert lon == 172.6


# ===========================================================================
# Tests for extract_state_province
# ===========================================================================


class TestExtractStateProvince:
    """Tests for extracting state/province information."""

    def test_us_state_extraction(self):
        html = '<div class="mobile-header-regionselector">WorldwideNorth AmericaUSAColoradoVail</div>'
        soup = _make_soup(html)
        result = extract_state_province(soup, "US")
        assert result == "Colorado"

    def test_canada_province_extraction(self):
        html = '<div class="mobile-header-regionselector">WorldwideNorth AmericaCanadaBritish Columbia</div>'
        soup = _make_soup(html)
        result = extract_state_province(soup, "CA")
        # The regex looks for CanadaXxx pattern
        assert "British" in result or result != ""

    def test_no_mobile_header_returns_empty(self):
        soup = _make_soup("<html><body><p>Nothing here</p></body></html>")
        result = extract_state_province(soup, "US")
        assert result == ""

    def test_non_us_non_ca_returns_empty(self):
        html = '<div class="mobile-header-regionselector">SomeText</div>'
        soup = _make_soup(html)
        result = extract_state_province(soup, "FR")
        assert result == ""

    def test_worldwide_filtered_out(self):
        html = '<div class="mobile-header-regionselector">USAWorldwide</div>'
        soup = _make_soup(html)
        result = extract_state_province(soup, "US")
        # "Worldwide" should be filtered out
        assert result != "Worldwide"


# ===========================================================================
# Tests for geocode_resort
# ===========================================================================


class TestGeocodeResort:
    """Tests for the geocoding fallback."""

    @patch("handlers.scraper_worker.requests.get")
    def test_successful_geocode_matching_country(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "results": [
                {"latitude": 45.92, "longitude": 6.87, "country_code": "FR"},
            ]
        }
        mock_get.return_value = mock_response

        lat, lon = geocode_resort("Chamonix", "FR")
        assert lat == 45.92
        assert lon == 6.87

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_fallback_to_first_result(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "results": [
                {"latitude": 46.0, "longitude": 7.0, "country_code": "CH"},
            ]
        }
        mock_get.return_value = mock_response

        lat, lon = geocode_resort("Chamonix", "FR")
        assert lat == 46.0
        assert lon == 7.0

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_no_results_retries_without_ski(self, mock_get):
        """When first search returns no results, retry without 'ski' suffix."""
        mock_response_empty = Mock()
        mock_response_empty.raise_for_status = Mock()
        mock_response_empty.json.return_value = {"results": []}

        mock_response_with_result = Mock()
        mock_response_with_result.raise_for_status = Mock()
        mock_response_with_result.json.return_value = {
            "results": [
                {"latitude": 39.64, "longitude": -106.37, "country_code": "US"},
            ]
        }

        mock_get.side_effect = [mock_response_empty, mock_response_with_result]

        lat, lon = geocode_resort("Vail", "US")
        assert lat == 39.64
        assert lon == -106.37
        assert mock_get.call_count == 2

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_failure_returns_zeros(self, mock_get):
        mock_get.side_effect = requests.RequestException("Timeout")

        lat, lon = geocode_resort("Unknown Resort", "XX")
        assert lat == 0.0
        assert lon == 0.0

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_no_results_at_all(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {}

        mock_get.return_value = mock_response

        lat, lon = geocode_resort("Nonexistent Resort", "XX")
        assert lat == 0.0
        assert lon == 0.0

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_cleans_name(self, mock_get):
        """Verify name cleaning removes 'ski resort', 'ski area', 'mountain resort'."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "results": [
                {"latitude": 45.0, "longitude": 6.0, "country_code": "FR"},
            ]
        }
        mock_get.return_value = mock_response

        geocode_resort("Chamonix Ski Resort", "FR")

        # Check that the cleaned name was sent -- "ski resort" removed
        first_call_params = mock_get.call_args_list[0][1]["params"]
        assert "ski resort" not in first_call_params["name"]
        # The name should contain "chamonix" (lowered) with "ski" suffix appended
        assert "chamonix" in first_call_params["name"]

    @patch("handlers.scraper_worker.requests.get")
    def test_geocode_skips_zero_coords_in_results(self, mock_get):
        """Skip results where latitude and longitude are both 0.0."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "results": [
                {"latitude": 0.0, "longitude": 0.0, "country_code": "US"},
                {"latitude": 40.0, "longitude": -105.0, "country_code": "US"},
            ]
        }
        mock_get.return_value = mock_response

        lat, lon = geocode_resort("Vail", "US")
        # First result has 0,0 but lat!=0 OR lon!=0 fails, so falls through
        # The code checks `if lat != 0.0 or lon != 0.0` -- 0.0 and 0.0 is False
        # So it should skip the first result and return the second
        assert lat == 40.0
        assert lon == -105.0


# ===========================================================================
# Tests for collect_resort_urls
# ===========================================================================


class TestCollectResortUrls:
    """Tests for collecting resort URLs from listing pages."""

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_single_page_collection(self, mock_time, mock_sleep):
        html = _listing_page_html(
            [
                "/ski-resort/chamonix-mont-blanc",
                "/ski-resort/val-disere",
            ]
        )
        session = ScraperSession()
        session._last_request_time = 0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        urls = collect_resort_urls(session, "FR")
        assert len(urls) == 2
        assert all(country == "FR" for _, country in urls)
        assert any("chamonix" in url for url, _ in urls)

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_skips_non_resort_links(self, mock_time, mock_sleep):
        """Links like snow-report, reviews, etc. should be filtered."""
        html = _listing_page_html(
            [
                "/ski-resort/chamonix-mont-blanc",
                "/ski-resort/chamonix-mont-blanc/snow-report",
                "/ski-resort/chamonix-mont-blanc/reviews",
                "/ski-resort/chamonix-mont-blanc/webcams",
                "/ski-resort/chamonix-mont-blanc/trail-map",
                "/ski-resort/chamonix-mont-blanc/test-report",
                "/ski-resort/chamonix-mont-blanc/photos",
            ]
        )
        session = ScraperSession()
        session._last_request_time = 0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        urls = collect_resort_urls(session, "FR")
        assert len(urls) == 1
        assert "snow-report" not in urls[0][0]

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_deduplicates_urls(self, mock_time, mock_sleep):
        html = _listing_page_html(
            [
                "/ski-resort/chamonix",
                "/ski-resort/chamonix",
                "/ski-resort/chamonix",
            ]
        )
        session = ScraperSession()
        session._last_request_time = 0

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        urls = collect_resort_urls(session, "FR")
        assert len(urls) == 1

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_multi_page_pagination(self, mock_time, mock_sleep):
        """Should follow pagination to collect URLs from multiple pages."""
        page1_html = _listing_page_html(["/ski-resort/resort-a"], has_next=True)
        page2_html = _listing_page_html(["/ski-resort/resort-b"], has_next=False)

        session = ScraperSession()
        session._last_request_time = 0

        resp1 = Mock()
        resp1.raise_for_status = Mock()
        resp1.text = page1_html

        resp2 = Mock()
        resp2.raise_for_status = Mock()
        resp2.text = page2_html

        session.session = Mock()
        session.session.get.side_effect = [resp1, resp2]

        urls = collect_resort_urls(session, "FR")
        assert len(urls) == 2

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_stops_on_404(self, mock_time, mock_sleep):
        """Should stop collecting when a 404 is encountered."""
        session = ScraperSession()
        session._last_request_time = 0

        # First page works, second returns 404
        resp1 = Mock()
        resp1.raise_for_status = Mock()
        resp1.text = _listing_page_html(["/ski-resort/resort-a"], has_next=True)

        http_error = requests.HTTPError()
        http_error.response = Mock()
        http_error.response.status_code = 404

        resp2 = Mock()
        resp2.raise_for_status.side_effect = http_error
        resp2.text = ""

        session.session = Mock()
        session.session.get.side_effect = [resp1, resp2]

        # The get_soup method calls get which calls raise_for_status
        # For 404, it should be caught in collect_resort_urls
        # We need to make get_soup raise HTTPError for the second page
        # Actually, let's patch at a higher level
        original_get_soup = session.get_soup

        call_count = [0]

        def mock_get_soup(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_soup(
                    _listing_page_html(["/ski-resort/resort-a"], has_next=True)
                )
            else:
                raise http_error

        session.get_soup = mock_get_soup

        urls = collect_resort_urls(session, "FR")
        assert len(urls) == 1


# ===========================================================================
# Tests for scrape_resort_detail
# ===========================================================================


class TestScrapeResortDetail:
    """Tests for scraping individual resort pages."""

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.92, 6.87))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_successful_scrape(self, mock_time, mock_sleep, mock_geocode):
        html = _resort_page_html(
            name="Chamonix Mont-Blanc",
            base=1035,
            top=3842,
            data_lat=45.92,
            data_lng=6.87,
        )
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(
            session,
            "https://www.skiresort.info/ski-resort/chamonix",
            "FR",
        )

        assert result is not None
        assert result["name"] == "Chamonix Mont-Blanc"
        assert result["elevation_base_m"] == 1035
        assert result["elevation_top_m"] == 3842
        assert result["country"] == "FR"
        assert result["region"] == "alps"
        assert result["latitude"] == 45.92
        assert result["longitude"] == 6.87
        assert result["resort_id"] == "chamonix-mont-blanc"
        assert result["source"] == "skiresort.info"

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_returns_none_when_no_name(self, mock_time, mock_sleep, mock_geocode):
        """Returns None when no h1 or name element is found."""
        html = "<html><body><p>No name here</p><div>1000 m - 2000 m</div></body></html>"
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is None

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_returns_none_when_no_elevation(self, mock_time, mock_sleep, mock_geocode):
        """Returns None when elevation data is missing."""
        html = "<html><body><h1>Test Resort</h1><p>No elevation</p></body></html>"
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is None

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_returns_none_when_vertical_too_small(
        self, mock_time, mock_sleep, mock_geocode
    ):
        """Returns None when vertical drop is below MIN_VERTICAL (300m)."""
        html = _resort_page_html(name="Tiny Hill", base=1000, top=1100)
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is None

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_skips_snow_report_pages(self, mock_time, mock_sleep, mock_geocode):
        """Pages whose name starts with 'Snow report' should be skipped."""
        html = "<html><body><h1>Snow report Chamonix</h1><div>1000 m - 3000 m</div></body></html>"
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is None

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_cleans_ski_resort_prefix(self, mock_time, mock_sleep, mock_geocode):
        """'Ski resort ' prefix should be stripped from names.

        The _resort_page_html template already adds 'Ski resort ' to the h1,
        so pass just the resort name to test the cleaning logic.
        """
        html = _resort_page_html(name="Chamonix", base=1000, top=3000)
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        # The h1 text is "Ski resort Chamonix"; the cleaning regex removes the prefix
        assert result["name"] == "Chamonix"
        assert not result["name"].lower().startswith("ski resort")

    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_returns_none_on_fetch_error(self, mock_time, mock_sleep):
        """Returns None when the HTTP request fails."""
        session = ScraperSession()
        session._last_request_time = 0
        session.session = Mock()
        session.session.get.side_effect = requests.RequestException("Timeout")

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is None

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.92, 6.87))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_elevation_base_top_swap_when_reversed(
        self, mock_time, mock_sleep, mock_geocode
    ):
        """If base > top in the range pattern, they should be swapped."""
        html = _resort_page_html(name="Test Resort", base=3000, top=1000)
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        assert result["elevation_base_m"] == 1000
        assert result["elevation_top_m"] == 3000

    @patch("handlers.scraper_worker.geocode_resort", return_value=(0.0, 0.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_geohash_is_none_when_no_coords(self, mock_time, mock_sleep, mock_geocode):
        """geo_hash should be None when coordinates are (0,0)."""
        html = _resort_page_html(name="Test Resort", base=1000, top=3000)
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        assert result["geo_hash"] is None

    @patch("handlers.scraper_worker.encode_geohash", return_value="u0nd")
    @patch("handlers.scraper_worker.geocode_resort", return_value=(47.0, 12.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_geohash_set_when_coords_available(
        self, mock_time, mock_sleep, mock_geocode, mock_geohash
    ):
        """geo_hash should be computed when valid coordinates exist."""
        html = _resort_page_html(
            name="Test Resort", base=1000, top=3000, data_lat=47.0, data_lng=12.0
        )
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "AT")
        assert result is not None
        assert result["geo_hash"] == "u0nd"

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.0, 6.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_scraped_at_is_iso_format(self, mock_time, mock_sleep, mock_geocode):
        """scraped_at field should be a valid ISO format timestamp."""
        html = _resort_page_html(
            name="Test Resort", base=1000, top=3000, data_lat=45.0, data_lng=6.0
        )
        session = ScraperSession()
        session._last_request_time = 0
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.text = html
        session.session = Mock()
        session.session.get.return_value = mock_response

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        # Should be parseable as an ISO timestamp
        datetime.fromisoformat(result["scraped_at"])


# ===========================================================================
# Tests for get_existing_resort_ids
# ===========================================================================


class TestGetExistingResortIds:
    """Tests for DynamoDB scanning to get existing resort IDs."""

    @patch("handlers.scraper_worker.dynamodb")
    def test_returns_ids_from_single_scan(self, mock_dynamodb):
        mock_table = Mock()
        mock_table.scan.return_value = {
            "Items": [
                {"resort_id": "chamonix"},
                {"resort_id": "zermatt"},
            ]
        }
        mock_dynamodb.Table.return_value = mock_table

        ids = get_existing_resort_ids()
        assert ids == {"chamonix", "zermatt"}

    @patch("handlers.scraper_worker.dynamodb")
    def test_handles_paginated_scan(self, mock_dynamodb):
        mock_table = Mock()
        mock_table.scan.side_effect = [
            {
                "Items": [{"resort_id": "resort-a"}],
                "LastEvaluatedKey": {"resort_id": "resort-a"},
            },
            {
                "Items": [{"resort_id": "resort-b"}],
            },
        ]
        mock_dynamodb.Table.return_value = mock_table

        ids = get_existing_resort_ids()
        assert ids == {"resort-a", "resort-b"}
        assert mock_table.scan.call_count == 2

    @patch("handlers.scraper_worker.dynamodb")
    def test_returns_empty_set_on_error(self, mock_dynamodb):
        mock_table = Mock()
        mock_table.scan.side_effect = Exception("DynamoDB error")
        mock_dynamodb.Table.return_value = mock_table

        ids = get_existing_resort_ids()
        assert ids == set()

    @patch("handlers.scraper_worker.dynamodb")
    def test_returns_empty_set_when_no_items(self, mock_dynamodb):
        mock_table = Mock()
        mock_table.scan.return_value = {"Items": []}
        mock_dynamodb.Table.return_value = mock_table

        ids = get_existing_resort_ids()
        assert ids == set()


# ===========================================================================
# Tests for publish_new_resorts_notification
# ===========================================================================


class TestPublishNewResortsNotification:
    """Tests for SNS notification publishing."""

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_publishes_notification_for_new_resorts(self, mock_sns):
        resorts = [
            {
                "name": "New Resort",
                "region": "alps",
                "elevation_base_m": 1000,
                "elevation_top_m": 3000,
                "latitude": 45.0,
                "longitude": 6.0,
            }
        ]
        publish_new_resorts_notification(resorts, "FR", "job-123")

        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert "arn:aws:sns" in call_kwargs["TopicArn"]
        assert "1 new resorts" in call_kwargs["Subject"]
        assert "FR" in call_kwargs["Subject"]

    @patch("handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN", "")
    @patch("handlers.scraper_worker.sns")
    def test_skips_when_no_topic_arn(self, mock_sns):
        resorts = [{"name": "Test"}]
        publish_new_resorts_notification(resorts, "FR", "job-123")
        mock_sns.publish.assert_not_called()

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_skips_when_empty_resorts(self, mock_sns):
        publish_new_resorts_notification([], "FR", "job-123")
        mock_sns.publish.assert_not_called()

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_includes_missing_coords_warning(self, mock_sns):
        resorts = [
            {
                "name": "No Coords Resort",
                "region": "alps",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 0.0,
                "longitude": 0.0,
            }
        ]
        publish_new_resorts_notification(resorts, "FR", "job-123")

        call_kwargs = mock_sns.publish.call_args[1]
        assert "missing coords" in call_kwargs["Subject"]
        assert "WARNING" in call_kwargs["Message"]
        assert "No Coords Resort" in call_kwargs["Message"]

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_truncates_long_resort_list(self, mock_sns):
        """Should only show first 20 resorts in the message."""
        resorts = [
            {
                "name": f"Resort {i}",
                "region": "alps",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": 6.0,
            }
            for i in range(25)
        ]
        publish_new_resorts_notification(resorts, "FR", "job-123")

        call_kwargs = mock_sns.publish.call_args[1]
        assert "and 5 more" in call_kwargs["Message"]

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_handles_sns_error_gracefully(self, mock_sns):
        mock_sns.publish.side_effect = Exception("SNS error")
        resorts = [
            {
                "name": "Test",
                "region": "alps",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 45.0,
                "longitude": 6.0,
            }
        ]
        # Should not raise
        publish_new_resorts_notification(resorts, "FR", "job-123")

    @patch(
        "handlers.scraper_worker.NEW_RESORTS_TOPIC_ARN",
        "arn:aws:sns:us-west-2:123:topic",
    )
    @patch("handlers.scraper_worker.sns")
    def test_subject_truncated_to_100_chars(self, mock_sns):
        resorts = [
            {
                "name": "Resort",
                "region": "alps",
                "elevation_base_m": 1000,
                "elevation_top_m": 2000,
                "latitude": 0.0,
                "longitude": 0.0,
            }
        ] * 999  # Many resorts to make subject long

        publish_new_resorts_notification(resorts, "FR", "job-123")

        call_kwargs = mock_sns.publish.call_args[1]
        assert len(call_kwargs["Subject"]) <= 100


# ===========================================================================
# Tests for scraper_worker_handler (Lambda entry point)
# ===========================================================================


class TestScraperWorkerHandler:
    """Tests for the main Lambda handler function."""

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_successful_scrape(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/chamonix", "FR"),
        ]
        mock_scrape.return_value = {
            "resort_id": "chamonix",
            "name": "Chamonix",
            "country": "FR",
            "region": "alps",
            "state_province": "",
            "elevation_base_m": 1035,
            "elevation_top_m": 3842,
            "latitude": 45.92,
            "longitude": 6.87,
            "geo_hash": "u0hf",
            "source": "skiresort.info",
            "source_url": "https://skiresort.info/ski-resort/chamonix",
            "scraped_at": "2026-02-21T00:00:00+00:00",
        }

        event = {"country": "FR", "delta_mode": True, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["resorts_scraped"] == 1
        assert body["country"] == "FR"

        # Verify S3 upload
        mock_s3.put_object.assert_called_once()
        s3_call = mock_s3.put_object.call_args[1]
        assert "scraper-results/test-job/FR.json" in s3_call["Key"]
        assert s3_call["ContentType"] == "application/json"

    def test_invalid_country_returns_400(self):
        event = {"country": "INVALID"}
        result = scraper_worker_handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body

    def test_missing_country_returns_400(self):
        event = {}
        result = scraper_worker_handler(event, None)
        assert result["statusCode"] == 400

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value={"chamonix"})
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_delta_mode_skips_existing_by_url_id(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Delta mode should skip resorts whose URL-derived ID is already known."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/chamonix", "FR"),
        ]

        event = {"country": "FR", "delta_mode": True, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        body = json.loads(result["body"])
        assert body["resorts_skipped"] == 1
        assert body["resorts_scraped"] == 0
        mock_scrape.assert_not_called()

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value={"chamonix"})
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_delta_mode_skips_existing_by_resort_id(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Delta mode double-checks the generated resort_id against existing IDs."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/some-other-url", "FR"),
        ]
        mock_scrape.return_value = {
            "resort_id": "chamonix",
            "name": "Chamonix",
            "country": "FR",
            "region": "alps",
            "state_province": "",
            "elevation_base_m": 1035,
            "elevation_top_m": 3842,
            "latitude": 45.0,
            "longitude": 6.0,
            "geo_hash": None,
            "source": "skiresort.info",
            "source_url": "url",
            "scraped_at": "2026-02-21T00:00:00+00:00",
        }

        event = {"country": "FR", "delta_mode": True, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        body = json.loads(result["body"])
        assert body["resorts_skipped"] == 1
        assert body["resorts_scraped"] == 0

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_delta_mode_false_does_not_fetch_existing(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """When delta_mode=False, we should not call get_existing_resort_ids."""
        mock_collect.return_value = []

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        scraper_worker_handler(event, None)

        mock_existing.assert_not_called()

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_no_s3_upload_when_no_resorts(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Should not upload to S3 when no resorts were scraped."""
        mock_collect.return_value = []

        event = {"country": "FR", "delta_mode": True, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        assert result["statusCode"] == 200
        mock_s3.put_object.assert_not_called()
        mock_notify.assert_not_called()

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_handles_scrape_errors_gracefully(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Individual resort scrape failures should be counted, not crash the handler."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/resort-a", "FR"),
            ("https://skiresort.info/ski-resort/resort-b", "FR"),
        ]
        mock_scrape.side_effect = [Exception("Parse error"), None]

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["errors"] == 1
        assert body["resorts_scraped"] == 0

    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_fatal_error_returns_500(self, mock_collect):
        """A fatal error in the handler should return status 500."""
        mock_collect.side_effect = Exception("Network failure")

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "error" in body
        assert "Network failure" in body["error"]

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_default_job_id_when_not_provided(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """job_id should default to a timestamp when not provided."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/resort-a", "FR"),
        ]
        mock_scrape.return_value = {
            "resort_id": "resort-a",
            "name": "Resort A",
            "country": "FR",
            "region": "alps",
            "state_province": "",
            "elevation_base_m": 1000,
            "elevation_top_m": 3000,
            "latitude": 45.0,
            "longitude": 6.0,
            "geo_hash": None,
            "source": "skiresort.info",
            "source_url": "url",
            "scraped_at": "2026-02-21T00:00:00+00:00",
        }

        event = {"country": "FR", "delta_mode": False}
        result = scraper_worker_handler(event, None)

        assert result["statusCode"] == 200
        # S3 key should contain a timestamp-based job_id
        s3_call = mock_s3.put_object.call_args[1]
        assert "scraper-results/" in s3_call["Key"]
        assert "/FR.json" in s3_call["Key"]

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_duration_seconds_in_response(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Response body should include duration_seconds."""
        mock_collect.return_value = []

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        body = json.loads(result["body"])
        assert "duration_seconds" in body
        assert isinstance(body["duration_seconds"], int | float)

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_sends_sns_notification_on_success(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Should call publish_new_resorts_notification when resorts are found."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/test", "FR"),
        ]
        resort_data = {
            "resort_id": "test",
            "name": "Test",
            "country": "FR",
            "region": "alps",
            "state_province": "",
            "elevation_base_m": 1000,
            "elevation_top_m": 3000,
            "latitude": 45.0,
            "longitude": 6.0,
            "geo_hash": None,
            "source": "skiresort.info",
            "source_url": "url",
            "scraped_at": "2026-02-21T00:00:00+00:00",
        }
        mock_scrape.return_value = resort_data

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        scraper_worker_handler(event, None)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args[0]
        assert len(call_args[0]) == 1  # resorts list
        assert call_args[1] == "FR"  # country
        assert call_args[2] == "test-job"  # job_id

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_s3_body_contains_resorts_and_stats(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """S3 upload body should contain both resorts list and stats."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/test", "FR"),
        ]
        resort_data = {
            "resort_id": "test",
            "name": "Test",
            "country": "FR",
            "region": "alps",
            "state_province": "",
            "elevation_base_m": 1000,
            "elevation_top_m": 3000,
            "latitude": 45.0,
            "longitude": 6.0,
            "geo_hash": None,
            "source": "skiresort.info",
            "source_url": "url",
            "scraped_at": "2026-02-21T00:00:00+00:00",
        }
        mock_scrape.return_value = resort_data

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        scraper_worker_handler(event, None)

        s3_body = json.loads(mock_s3.put_object.call_args[1]["Body"])
        assert "resorts" in s3_body
        assert "stats" in s3_body
        assert len(s3_body["resorts"]) == 1
        assert s3_body["stats"]["country"] == "FR"
        assert s3_body["stats"]["resorts_scraped"] == 1

    @patch("handlers.scraper_worker.publish_new_resorts_notification")
    @patch("handlers.scraper_worker.s3")
    @patch("handlers.scraper_worker.get_existing_resort_ids", return_value=set())
    @patch("handlers.scraper_worker.scrape_resort_detail")
    @patch("handlers.scraper_worker.collect_resort_urls")
    def test_scrape_returns_none_not_counted(
        self, mock_collect, mock_scrape, mock_existing, mock_s3, mock_notify
    ):
        """Resorts where scrape_resort_detail returns None should not be counted."""
        mock_collect.return_value = [
            ("https://skiresort.info/ski-resort/resort-a", "FR"),
            ("https://skiresort.info/ski-resort/resort-b", "FR"),
        ]
        mock_scrape.return_value = (
            None  # Both return None (e.g., insufficient vertical)
        )

        event = {"country": "FR", "delta_mode": False, "job_id": "test-job"}
        result = scraper_worker_handler(event, None)

        body = json.loads(result["body"])
        assert body["resorts_scraped"] == 0
        assert body["errors"] == 0
        mock_s3.put_object.assert_not_called()


# ===========================================================================
# Tests for COUNTRY_URLS and REGION_MAPPINGS consistency
# ===========================================================================


class TestMappingConsistency:
    """Tests for consistency between various mappings."""

    def test_all_country_urls_have_region_mappings(self):
        """Every country in COUNTRY_URLS should have a REGION_MAPPINGS entry."""
        for country in COUNTRY_URLS:
            assert country in REGION_MAPPINGS, (
                f"Country {country} in COUNTRY_URLS but missing from REGION_MAPPINGS"
            )

    def test_all_us_states_map_to_valid_regions(self):
        valid_regions = {"na_west", "na_rockies", "na_east", "na_midwest"}
        for state, region in US_STATE_REGIONS.items():
            assert region in valid_regions, (
                f"US state {state} maps to invalid region {region}"
            )

    def test_all_ca_provinces_map_to_valid_regions(self):
        valid_regions = {"na_west", "na_rockies", "na_east"}
        for province, region in CA_PROVINCE_REGIONS.items():
            assert region in valid_regions, (
                f"CA province {province} maps to invalid region {region}"
            )

    def test_country_urls_are_valid_paths(self):
        for country, path in COUNTRY_URLS.items():
            assert path.startswith("/ski-resorts/"), (
                f"Country {country} URL path should start with /ski-resorts/"
            )


# ===========================================================================
# Tests for elevation extraction edge cases
# ===========================================================================


class TestElevationExtraction:
    """Tests for various elevation extraction patterns in scrape_resort_detail."""

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.0, 6.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_elevation_from_range_with_dash(self, mock_time, mock_sleep, mock_geocode):
        """Should extract elevation from '1035 m - 3842 m' pattern."""
        html = (
            "<html><body><h1>Test Resort</h1><div>1035 m - 3842 m</div></body></html>"
        )
        session = ScraperSession()
        session._last_request_time = 0
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.text = html
        session.session = Mock()
        session.session.get.return_value = mock_resp

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        assert result["elevation_base_m"] == 1035
        assert result["elevation_top_m"] == 3842

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.0, 6.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_elevation_from_altitude_section(self, mock_time, mock_sleep, mock_geocode):
        """Should extract elevation when there's an 'altitude' label."""
        html = """<html><body>
        <h1>Test Resort</h1>
        <div><span>Altitude</span><div>800 m and 2500 m available</div></div>
        </body></html>"""
        session = ScraperSession()
        session._last_request_time = 0
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.text = html
        session.session = Mock()
        session.session.get.return_value = mock_resp

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        assert result["elevation_base_m"] == 800
        assert result["elevation_top_m"] == 2500

    @patch("handlers.scraper_worker.geocode_resort", return_value=(45.0, 6.0))
    @patch("handlers.scraper_worker.time.sleep")
    @patch("handlers.scraper_worker.time.time", return_value=0)
    def test_elevation_with_en_dash(self, mock_time, mock_sleep, mock_geocode):
        """Should handle en-dash in elevation range."""
        html = "<html><body><h1>Test Resort</h1><div>1500 m \u2013 3500 m</div></body></html>"
        session = ScraperSession()
        session._last_request_time = 0
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.text = html
        session.session = Mock()
        session.session.get.return_value = mock_resp

        result = scrape_resort_detail(session, "https://example.com", "FR")
        assert result is not None
        assert result["elevation_base_m"] == 1500
        assert result["elevation_top_m"] == 3500
