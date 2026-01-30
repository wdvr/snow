#!/usr/bin/env python3
"""
Ski Resort Scraper

Scrapes ski resorts from multiple sources worldwide and outputs data
compatible with the Snow Tracker application.

Data Sources:
1. Skiresort.info - Comprehensive database with ratings and details
2. Wikipedia - Lists of ski resorts by country
3. OpenStreetMap - Coordinate data

Usage:
    python scrape_resorts.py --output resorts_scraped.json
    python scrape_resorts.py --region alps --limit 50
    python scrape_resorts.py --merge-existing
"""

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

# Thread-safe logging lock
_log_lock = Lock()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
USER_AGENT = (
    "Mozilla/5.0 (compatible; SnowTrackerBot/1.0; +https://github.com/snowtracker)"
)
REQUEST_DELAY = 1.5  # Seconds between requests to be respectful
MAX_RETRIES = 3

# Region mappings
REGION_MAPPINGS = {
    # Europe
    "FR": "alps",
    "CH": "alps",
    "AT": "alps",
    "IT": "alps",
    "DE": "alps",  # German Alps
    "SI": "alps",  # Slovenia
    "AD": "alps",  # Andorra (Pyrenees, but grouped with Alps)
    "ES": "alps",  # Spain (Pyrenees)
    # Scandinavia
    "NO": "scandinavia",
    "SE": "scandinavia",
    "FI": "scandinavia",
    # North America
    "US": "na_rockies",  # Default, will be refined by state
    "CA": "na_west",  # Default, will be refined by province
    # Japan
    "JP": "japan",
    # Oceania
    "AU": "oceania",
    "NZ": "oceania",
    # South America
    "CL": "south_america",
    "AR": "south_america",
    # Eastern Europe
    "PL": "europe_east",
    "CZ": "europe_east",
    "SK": "europe_east",
    "RO": "europe_east",
    "BG": "europe_east",
    "UA": "europe_east",
    "RU": "europe_east",
    # Asia (non-Japan)
    "KR": "asia",
    "CN": "asia",
    "IN": "asia",
    "IR": "asia",
}

# US state to region mapping
US_STATE_REGIONS = {
    # West Coast
    "CA": "na_west",
    "OR": "na_west",
    "WA": "na_west",
    # Rockies
    "CO": "na_rockies",
    "UT": "na_rockies",
    "WY": "na_rockies",
    "MT": "na_rockies",
    "ID": "na_rockies",
    "NM": "na_rockies",
    "AZ": "na_rockies",
    "NV": "na_rockies",
    # East
    "VT": "na_east",
    "NH": "na_east",
    "ME": "na_east",
    "NY": "na_east",
    "PA": "na_east",
    "MA": "na_east",
    "CT": "na_east",
    "NJ": "na_east",
    "WV": "na_east",
    "VA": "na_east",
    "NC": "na_east",
    "MD": "na_east",
    # Midwest
    "MI": "na_midwest",
    "WI": "na_midwest",
    "MN": "na_midwest",
    "OH": "na_midwest",
    "IA": "na_midwest",
    "SD": "na_midwest",
    "ND": "na_midwest",
}

# Canadian province to region mapping
CA_PROVINCE_REGIONS = {
    "BC": "na_west",
    "AB": "na_rockies",
    "ON": "na_east",
    "QC": "na_east",
    "NS": "na_east",
    "NB": "na_east",
    "NL": "na_east",
    "SK": "na_midwest",
    "MB": "na_midwest",
    "YT": "na_west",
    "NT": "na_west",
}

# Full name to abbreviation mappings for US states
US_STATE_ABBREV = {
    "california": "CA",
    "oregon": "OR",
    "washington": "WA",
    "colorado": "CO",
    "utah": "UT",
    "wyoming": "WY",
    "montana": "MT",
    "idaho": "ID",
    "new mexico": "NM",
    "arizona": "AZ",
    "nevada": "NV",
    "vermont": "VT",
    "new hampshire": "NH",
    "maine": "ME",
    "new york": "NY",
    "pennsylvania": "PA",
    "massachusetts": "MA",
    "connecticut": "CT",
    "new jersey": "NJ",
    "west virginia": "WV",
    "virginia": "VA",
    "north carolina": "NC",
    "maryland": "MD",
    "michigan": "MI",
    "wisconsin": "WI",
    "minnesota": "MN",
    "ohio": "OH",
    "iowa": "IA",
    "south dakota": "SD",
    "north dakota": "ND",
    "alaska": "AK",
}

# Full name to abbreviation mappings for Canadian provinces
CA_PROVINCE_ABBREV = {
    "british columbia": "BC",
    "alberta": "AB",
    "ontario": "ON",
    "quebec": "QC",
    "nova scotia": "NS",
    "new brunswick": "NB",
    "newfoundland": "NL",
    "newfoundland and labrador": "NL",
    "saskatchewan": "SK",
    "manitoba": "MB",
    "yukon": "YT",
    "northwest territories": "NT",
    "nunavut": "NU",
}

# Timezone mappings by country and region
TIMEZONE_MAPPINGS = {
    # North America
    ("US", "CA"): "America/Los_Angeles",
    ("US", "OR"): "America/Los_Angeles",
    ("US", "WA"): "America/Los_Angeles",
    ("US", "NV"): "America/Los_Angeles",
    ("US", "CO"): "America/Denver",
    ("US", "UT"): "America/Denver",
    ("US", "WY"): "America/Denver",
    ("US", "MT"): "America/Denver",
    ("US", "ID"): "America/Denver",
    ("US", "NM"): "America/Denver",
    ("US", "AZ"): "America/Phoenix",
    ("US", "VT"): "America/New_York",
    ("US", "NH"): "America/New_York",
    ("US", "ME"): "America/New_York",
    ("US", "NY"): "America/New_York",
    ("US", "PA"): "America/New_York",
    ("US", "MI"): "America/Detroit",
    ("US", "WI"): "America/Chicago",
    ("US", "MN"): "America/Chicago",
    ("CA", "BC"): "America/Vancouver",
    ("CA", "AB"): "America/Edmonton",
    ("CA", "ON"): "America/Toronto",
    ("CA", "QC"): "America/Montreal",
    # Europe
    ("FR", None): "Europe/Paris",
    ("CH", None): "Europe/Zurich",
    ("AT", None): "Europe/Vienna",
    ("IT", None): "Europe/Rome",
    ("DE", None): "Europe/Berlin",
    ("ES", None): "Europe/Madrid",
    ("AD", None): "Europe/Andorra",
    ("NO", None): "Europe/Oslo",
    ("SE", None): "Europe/Stockholm",
    ("FI", None): "Europe/Helsinki",
    ("SI", None): "Europe/Ljubljana",
    ("PL", None): "Europe/Warsaw",
    ("CZ", None): "Europe/Prague",
    ("SK", None): "Europe/Bratislava",
    ("RO", None): "Europe/Bucharest",
    ("BG", None): "Europe/Sofia",
    # Japan
    ("JP", None): "Asia/Tokyo",
    # Oceania
    ("AU", "NSW"): "Australia/Sydney",
    ("AU", "VIC"): "Australia/Melbourne",
    ("AU", "TAS"): "Australia/Hobart",
    ("NZ", None): "Pacific/Auckland",
    # South America
    ("CL", None): "America/Santiago",
    ("AR", None): "America/Argentina/Buenos_Aires",
    # Asia
    ("KR", None): "Asia/Seoul",
    ("CN", None): "Asia/Shanghai",
    ("IN", None): "Asia/Kolkata",
}


@dataclass
class ScrapedResort:
    """Represents a scraped ski resort."""

    name: str
    country: str
    region: str
    state_province: str
    elevation_base_m: int
    elevation_top_m: int
    latitude: float
    longitude: float
    timezone: str
    website: str | None = None
    features: list[str] = field(default_factory=list)
    annual_snowfall_cm: int | None = None
    resort_id: str = ""
    source: str = ""
    source_url: str = ""
    scraped_at: str = ""  # ISO timestamp when this resort was scraped

    def __post_init__(self):
        # Clean up name (remove common prefixes)
        self.name = self._clean_name(self.name)
        if not self.resort_id:
            self.resort_id = self._generate_id()
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()

    def _clean_name(self, name: str) -> str:
        """Remove common prefixes and clean up resort name."""
        # Remove "Ski resort " prefix from skiresort.info
        if name.lower().startswith("ski resort "):
            name = name[11:]  # len("Ski resort ")
        # Remove other common prefixes
        name = re.sub(r"^(?:Ski Area |Ski Resort )", "", name, flags=re.IGNORECASE)
        return name.strip()

    def _generate_id(self) -> str:
        """Generate a URL-friendly resort ID from the name."""
        # Remove special characters, convert to lowercase
        resort_id = self.name.lower()
        # Handle common name patterns
        resort_id = re.sub(r"[''`]", "", resort_id)
        resort_id = re.sub(r"[àáâãäå]", "a", resort_id)
        resort_id = re.sub(r"[èéêë]", "e", resort_id)
        resort_id = re.sub(r"[ìíîï]", "i", resort_id)
        resort_id = re.sub(r"[òóôõö]", "o", resort_id)
        resort_id = re.sub(r"[ùúûü]", "u", resort_id)
        resort_id = re.sub(r"[ñ]", "n", resort_id)
        resort_id = re.sub(r"[ç]", "c", resort_id)
        resort_id = re.sub(r"[ß]", "ss", resort_id)
        # Replace spaces and special chars with hyphens
        resort_id = re.sub(r"[^a-z0-9]+", "-", resort_id)
        # Remove leading/trailing hyphens
        resort_id = resort_id.strip("-")
        # Collapse multiple hyphens
        resort_id = re.sub(r"-+", "-", resort_id)
        return resort_id

    def to_dict(self) -> dict:
        """Convert to dictionary matching our JSON schema."""
        return {
            "resort_id": self.resort_id,
            "name": self.name,
            "country": self.country,
            "region": self.region,
            "state_province": self.state_province,
            "elevation_base_m": self.elevation_base_m,
            "elevation_top_m": self.elevation_top_m,
            "latitude": round(self.latitude, 4),
            "longitude": round(self.longitude, 4),
            "timezone": self.timezone,
            "website": self.website,
            "features": self.features,
            "annual_snowfall_cm": self.annual_snowfall_cm,
            "source": self.source,
            "scraped_at": self.scraped_at,
        }


class BaseScraper:
    """Base class for ski resort scrapers."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited GET request with retries."""
        self._rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    raise

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    def _get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch URL and return BeautifulSoup object."""
        response = self._get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")

    def normalize_state_province(self, country: str, state_province: str) -> str:
        """Convert full state/province name to abbreviation."""
        if not state_province:
            return ""

        # Already an abbreviation?
        if len(state_province) <= 3 and state_province.isupper():
            return state_province

        normalized = state_province.lower().strip()

        if country == "US":
            return US_STATE_ABBREV.get(normalized, state_province)
        elif country == "CA":
            return CA_PROVINCE_ABBREV.get(normalized, state_province)

        return state_province

    def get_region(self, country: str, state_province: str = "") -> str:
        """Determine the region based on country and state/province."""
        # Normalize state/province to abbreviation
        abbrev = self.normalize_state_province(country, state_province)

        # Check US-specific mapping
        if country == "US" and abbrev in US_STATE_REGIONS:
            return US_STATE_REGIONS[abbrev]

        # Check Canada-specific mapping
        if country == "CA" and abbrev in CA_PROVINCE_REGIONS:
            return CA_PROVINCE_REGIONS[abbrev]

        # Fall back to country mapping
        return REGION_MAPPINGS.get(country, "other")

    def get_timezone(self, country: str, state_province: str = "") -> str:
        """Get timezone for a resort based on country and state/province."""
        # Normalize state/province to abbreviation
        abbrev = self.normalize_state_province(country, state_province)

        # Try specific state/province first
        if abbrev:
            tz = TIMEZONE_MAPPINGS.get((country, abbrev))
            if tz:
                return tz

        # Fall back to country-level
        tz = TIMEZONE_MAPPINGS.get((country, None))
        if tz:
            return tz

        # Default fallback
        return "UTC"

    def scrape(self) -> list[ScrapedResort]:
        """Scrape resorts. Override in subclass."""
        raise NotImplementedError


class SkiResortInfoScraper(BaseScraper):
    """Scraper for skiresort.info - comprehensive ski resort database."""

    BASE_URL = "https://www.skiresort.info"

    # Country code mapping for skiresort.info URLs
    COUNTRY_URLS = {
        # North America
        "US": "/ski-resorts/usa",
        "CA": "/ski-resorts/canada",
        # Europe - Alps
        "AT": "/ski-resorts/austria",
        "CH": "/ski-resorts/switzerland",
        "FR": "/ski-resorts/france",
        "IT": "/ski-resorts/italy",
        "DE": "/ski-resorts/germany",
        "SI": "/ski-resorts/slovenia",
        # Scandinavia
        "NO": "/ski-resorts/norway",
        "SE": "/ski-resorts/sweden",
        "FI": "/ski-resorts/finland",
        # Japan
        "JP": "/ski-resorts/japan",
        # Oceania
        "AU": "/ski-resorts/australia",
        "NZ": "/ski-resorts/new-zealand",
        # South America
        "CL": "/ski-resorts/chile",
        "AR": "/ski-resorts/argentina",
        # Eastern Europe
        "PL": "/ski-resorts/poland",
        "CZ": "/ski-resorts/czech-republic",
        "SK": "/ski-resorts/slovakia",
        "RO": "/ski-resorts/romania",
        "BG": "/ski-resorts/bulgaria",
        # Spain (Pyrenees)
        "ES": "/ski-resorts/spain",
        "AD": "/ski-resorts/andorra",
        # Asia
        "KR": "/ski-resorts/south-korea",
        "CN": "/ski-resorts/china",
    }

    def __init__(
        self,
        countries: list[str] | None = None,
        min_vertical: int = 300,
        session: requests.Session | None = None,
        max_workers: int = 10,
        existing_ids: set[str] | None = None,
    ):
        super().__init__(session)
        self.countries = countries or list(self.COUNTRY_URLS.keys())
        self.min_vertical = min_vertical  # Minimum vertical drop in meters
        self.max_workers = max_workers
        self.existing_ids = existing_ids or set()  # For delta mode

    def scrape(self) -> list[ScrapedResort]:
        """Scrape resorts from all configured countries using parallel requests."""
        # Phase 1: Collect all resort URLs (fast, sequential)
        logger.info("Phase 1: Collecting resort URLs from all countries...")
        resort_urls = []  # List of (url, country) tuples

        for country in self.countries:
            if country not in self.COUNTRY_URLS:
                logger.warning(f"No URL configured for country: {country}")
                continue

            try:
                urls = self._collect_resort_urls(country)
                # Filter out existing resorts in delta mode
                if self.existing_ids:
                    before = len(urls)
                    urls = [
                        (u, c)
                        for u, c in urls
                        if self._url_to_id(u) not in self.existing_ids
                    ]
                    skipped = before - len(urls)
                    if skipped > 0:
                        logger.info(
                            f"  Skipped {skipped} existing resorts in {country}"
                        )
                resort_urls.extend(urls)
                logger.info(f"  Found {len(urls)} resort URLs in {country}")
            except Exception as e:
                logger.error(f"Failed to collect URLs from {country}: {e}")

        logger.info(f"Total: {len(resort_urls)} resorts to scrape")

        if not resort_urls:
            return []

        # Phase 2: Scrape all resort detail pages in parallel
        logger.info(
            f"Phase 2: Scraping {len(resort_urls)} resort details with {self.max_workers} workers..."
        )
        all_resorts = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self._scrape_resort_detail, url, country): (
                    url,
                    country,
                )
                for url, country in resort_urls
            }

            # Process completed tasks
            for future in as_completed(future_to_url):
                url, country = future_to_url[future]
                completed += 1

                try:
                    resort = future.result()
                    if (
                        resort
                        and (resort.elevation_top_m - resort.elevation_base_m)
                        >= self.min_vertical
                    ):
                        all_resorts.append(resort)
                        with _log_lock:
                            logger.info(
                                f"[{completed}/{len(resort_urls)}] ✓ {resort.name}"
                            )
                    else:
                        with _log_lock:
                            logger.debug(
                                f"[{completed}/{len(resort_urls)}] Skipped (low vertical)"
                            )
                except Exception as e:
                    with _log_lock:
                        logger.warning(f"[{completed}/{len(resort_urls)}] ✗ {url}: {e}")

        logger.info(f"Scraped {len(all_resorts)} resorts total")
        return all_resorts

    def _url_to_id(self, url: str) -> str:
        """Convert URL to resort ID."""
        match = re.search(r"/ski-resort/([^/]+)/?", url)
        return match.group(1) if match else url

    def _collect_resort_urls(self, country: str) -> list[tuple[str, str]]:
        """Collect all resort URLs from a country's listing pages."""
        url = urljoin(self.BASE_URL, self.COUNTRY_URLS[country])
        resort_urls = []
        page = 1

        while True:
            page_url = f"{url}/page/{page}" if page > 1 else url

            try:
                soup = self._get_soup(page_url)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    break
                raise

            # Find resort links (exclude non-resort subpages)
            links = soup.select("a[href*='/ski-resort/']")
            seen = set()
            skip_patterns = [
                "/snow-report",
                "/test-report",
                "/test-result",
                "/reviews",
                "/photos",
                "/events",
                "/webcams",
                "/trail-map",
                "/video",
                "/ski-lifts",
                "/ski-schools",
                "/apres-ski",
                "/accommodation",
            ]
            for link in links:
                href = link.get("href", "")
                # Skip non-resort pages (subpages of resort detail pages)
                if any(pattern in href for pattern in skip_patterns):
                    continue
                full_url = urljoin(self.BASE_URL, href)
                if "/ski-resort/" in full_url and full_url not in seen:
                    seen.add(full_url)
                    resort_urls.append((full_url, country))

            # Check for next page
            next_link = soup.select_one(".pagination .next, a[rel='next']")
            if not next_link or page >= 20:
                break
            page += 1

        return resort_urls

    def _scrape_resort_detail(self, url: str, country: str) -> ScrapedResort | None:
        """Scrape detailed resort information from its page."""
        try:
            soup = self._get_soup(url)
        except Exception as e:
            logger.warning(f"Failed to fetch resort detail {url}: {e}")
            return None

        # Extract name
        name_elem = soup.select_one("h1, .resort-name, .title")
        if not name_elem:
            return None
        name = name_elem.get_text(strip=True)

        # Remove common suffixes
        name = re.sub(r"\s*[-–]\s*Ski Resort.*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*Ski Area.*$", "", name, flags=re.IGNORECASE)

        # Skip non-resort pages based on name
        skip_prefixes = [
            "Snow report",
            "Test report",
            "Trail map",
            "Events",
            "Webcams",
            "Ski lifts",
            "Slope offering",
            "Mountain restaurants",
            "Advanced skiers",
            "Beginners",
            "Experts",
            "Families",
            "Snow reliability",
        ]
        if any(name.lower().startswith(prefix.lower()) for prefix in skip_prefixes):
            logger.debug(f"Skipping non-resort page: {name}")
            return None

        # Extract elevation data
        elevation_base = None
        elevation_top = None

        # Look for elevation information
        elevation_section = soup.select_one(
            ".elevation, .altitude, [class*='elevation']"
        )
        if elevation_section:
            text = elevation_section.get_text()
            # Try to extract numbers
            numbers = re.findall(r"(\d+)\s*m", text)
            if len(numbers) >= 2:
                elevation_base = int(min(numbers))
                elevation_top = int(max(numbers))

        # Alternative: look for specific labeled values
        if not elevation_base or not elevation_top:
            for label in ["Base", "Valley", "Bottom"]:
                elem = soup.find(string=re.compile(label, re.I))
                if elem:
                    parent = elem.parent
                    if parent:
                        match = re.search(r"(\d+)\s*m", parent.get_text())
                        if match:
                            elevation_base = int(match.group(1))
                            break

            for label in ["Top", "Summit", "Peak"]:
                elem = soup.find(string=re.compile(label, re.I))
                if elem:
                    parent = elem.parent
                    if parent:
                        match = re.search(r"(\d+)\s*m", parent.get_text())
                        if match:
                            elevation_top = int(match.group(1))
                            break

        # If we still don't have elevation, try finding it in the general text
        if not elevation_base or not elevation_top:
            all_elevations = re.findall(r"(\d{3,4})\s*m", soup.get_text())
            all_elevations = [int(e) for e in all_elevations if 100 < int(e) < 5000]
            if len(all_elevations) >= 2:
                elevation_base = min(all_elevations)
                elevation_top = max(all_elevations)

        if not elevation_base or not elevation_top:
            logger.warning(f"Could not extract elevation for {name}")
            return None

        # Extract location/region within country (state/province)
        state_province = self._extract_state_province(soup, country)

        # Extract coordinates
        latitude = None
        longitude = None

        # Look for coordinates in various places
        map_elem = soup.select_one("[data-lat], [data-latitude]")
        if map_elem:
            latitude = float(map_elem.get("data-lat") or map_elem.get("data-latitude"))
            longitude = float(
                map_elem.get("data-lng")
                or map_elem.get("data-lon")
                or map_elem.get("data-longitude")
            )

        # Try finding in scripts
        if not latitude:
            for script in soup.find_all("script"):
                if script.string:
                    lat_match = re.search(
                        r"lat[itude]*[\"':\s]+(-?\d+\.?\d*)", script.string
                    )
                    lng_match = re.search(
                        r"(?:lng|lon)[gitude]*[\"':\s]+(-?\d+\.?\d*)", script.string
                    )
                    if lat_match and lng_match:
                        latitude = float(lat_match.group(1))
                        longitude = float(lng_match.group(1))
                        break

        # Try meta tags
        if not latitude:
            lat_meta = soup.find("meta", {"property": "place:location:latitude"})
            lng_meta = soup.find("meta", {"property": "place:location:longitude"})
            if lat_meta and lng_meta:
                latitude = float(lat_meta.get("content"))
                longitude = float(lng_meta.get("content"))

        if not latitude or not longitude:
            logger.warning(f"Could not extract coordinates for {name}")
            # Use placeholder - will need to be filled in later
            latitude = 0.0
            longitude = 0.0

        # Extract website
        website = None
        website_link = soup.select_one(
            "a[href*='http'][target='_blank'], .official-website a"
        )
        if website_link:
            href = website_link.get("href", "")
            if "skiresort.info" not in href:
                website = href

        # Extract features
        features = []
        features_section = soup.select_one(".facilities, .features, [class*='feature']")
        if features_section:
            feature_items = features_section.select("li, .feature-item, span")
            for item in feature_items:
                feature_text = item.get_text(strip=True).lower()
                if "terrain park" in feature_text or "snowpark" in feature_text:
                    features.append("terrain_park")
                if "night" in feature_text:
                    features.append("night_skiing")
                if "glacier" in feature_text:
                    features.append("glacier")
                if "cross country" in feature_text or "nordic" in feature_text:
                    features.append("cross_country")

        # Extract snowfall
        annual_snowfall_cm = None
        snow_elem = soup.find(string=re.compile(r"snowfall|snow.*average", re.I))
        if snow_elem:
            parent = snow_elem.parent
            if parent:
                match = re.search(r"(\d+)\s*cm", parent.get_text())
                if match:
                    annual_snowfall_cm = int(match.group(1))

        # Determine region and timezone
        region = self.get_region(country, state_province)
        timezone = self.get_timezone(country, state_province)

        return ScrapedResort(
            name=name,
            country=country,
            region=region,
            state_province=state_province,
            elevation_base_m=elevation_base,
            elevation_top_m=elevation_top,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            website=website,
            features=list(set(features)),
            annual_snowfall_cm=annual_snowfall_cm,
            source="skiresort.info",
            source_url=url,
        )

    def _extract_state_province(self, soup: BeautifulSoup, country: str) -> str:
        """Extract state/province from the page's region selector."""
        # Method 1: Parse the mobile header which has the full path
        # Format: "VailWorldwideNorth AmericaUSAColoradoVail"
        # or "Whistler BlackcombWorldwideNorth AmericaCanadaBritish ColumbiaWhistler"
        mobile_header = soup.select_one(".mobile-header-regionselector")
        if mobile_header:
            text = mobile_header.get_text()

            # For USA - look for pattern USAStateName
            match = re.search(
                r"USA([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)(?=[A-Z][a-z]|$)", text
            )
            if match:
                state = match.group(1).strip()
                if state and state not in ["Worldwide", "North", "Search", "Tips"]:
                    return state

            # For Canada - look for pattern CanadaProvinceName
            match = re.search(
                r"Canada([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)(?=[A-Z][a-z]|$)", text
            )
            if match:
                province = match.group(1).strip()
                if province and province not in [
                    "Worldwide",
                    "North",
                    "Search",
                    "Tips",
                ]:
                    return province

        # Method 2: Look for state/province in region-select text
        region_select = soup.select_one(".region-select")
        if region_select:
            text = region_select.get_text()
            for pattern in [
                r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)States",
                r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)Provinces",
            ]:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip()

        # Method 3: Check links for state/province pages
        province_map = {
            "british-columbia": "British Columbia",
            "alberta": "Alberta",
            "ontario": "Ontario",
            "quebec": "Quebec",
            "colorado": "Colorado",
            "california": "California",
            "utah": "Utah",
            "vermont": "Vermont",
            "wyoming": "Wyoming",
            "montana": "Montana",
            "idaho": "Idaho",
            "washington": "Washington",
            "oregon": "Oregon",
            "new-york": "New York",
            "new-hampshire": "New Hampshire",
            "maine": "Maine",
            "new-mexico": "New Mexico",
            "nevada": "Nevada",
            "arizona": "Arizona",
            "alaska": "Alaska",
        }
        for a in soup.select('a[href*="/ski-resorts/"]'):
            href = a.get("href", "")
            for slug, name in province_map.items():
                if f"/{slug}/" in href:
                    return name

        return ""


class WikipediaScraper(BaseScraper):
    """Scraper for Wikipedia ski resort lists."""

    BASE_URL = "https://en.wikipedia.org"

    # Wikipedia list pages by country
    LIST_PAGES = {
        "US": "/wiki/List_of_ski_areas_and_resorts_in_the_United_States",
        "CA": "/wiki/List_of_ski_areas_and_resorts_in_Canada",
        "AT": "/wiki/List_of_ski_resorts_in_Austria",
        "CH": "/wiki/List_of_ski_resorts_in_Switzerland",
        "FR": "/wiki/List_of_ski_resorts_in_France",
        "IT": "/wiki/List_of_ski_resorts_in_Italy",
        "JP": "/wiki/List_of_ski_areas_and_resorts_in_Japan",
        "AU": "/wiki/List_of_ski_areas_and_resorts_in_Australia",
        "NZ": "/wiki/List_of_ski_areas_and_resorts_in_New_Zealand",
    }

    def __init__(
        self,
        countries: list[str] | None = None,
        session: requests.Session | None = None,
    ):
        super().__init__(session)
        self.countries = countries or list(self.LIST_PAGES.keys())

    def scrape(self) -> list[ScrapedResort]:
        """Scrape resort lists from Wikipedia."""
        all_resorts = []

        for country in self.countries:
            if country not in self.LIST_PAGES:
                continue

            try:
                resorts = self._scrape_country_list(country)
                all_resorts.extend(resorts)
                logger.info(
                    f"Scraped {len(resorts)} resorts from Wikipedia for {country}"
                )
            except Exception as e:
                logger.error(f"Failed to scrape Wikipedia for {country}: {e}")

        return all_resorts

    def _scrape_country_list(self, country: str) -> list[ScrapedResort]:
        """Scrape the list page for a country."""
        url = urljoin(self.BASE_URL, self.LIST_PAGES[country])
        soup = self._get_soup(url)

        resorts = []

        # Look for tables with resort data
        tables = soup.find_all("table", class_="wikitable")

        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

            # Check if this table has relevant columns
            name_col = None
            elev_col = None

            for i, header in enumerate(headers):
                if "name" in header or "resort" in header or "area" in header:
                    name_col = i
                if "elevation" in header or "vertical" in header or "summit" in header:
                    elev_col = i

            if name_col is None:
                continue

            # Parse rows
            for row in table.find_all("tr")[1:]:  # Skip header
                cells = row.find_all(["td", "th"])
                if len(cells) <= name_col:
                    continue

                name_cell = cells[name_col]
                name = name_cell.get_text(strip=True)

                # Skip empty or invalid names
                if not name or len(name) < 3:
                    continue

                # Get link for more details
                link = name_cell.find("a")
                detail_url = (
                    urljoin(self.BASE_URL, link.get("href", "")) if link else None
                )

                # Try to get more details from the resort's Wikipedia page
                resort = self._scrape_resort_detail(name, country, detail_url)
                if resort:
                    resorts.append(resort)

        return resorts

    def _scrape_resort_detail(
        self, name: str, country: str, detail_url: str | None
    ) -> ScrapedResort | None:
        """Scrape details from a resort's Wikipedia page."""
        if not detail_url:
            return None

        try:
            soup = self._get_soup(detail_url)
        except Exception:
            return None

        # Extract from infobox
        infobox = soup.select_one(".infobox, .vcard")
        if not infobox:
            return None

        elevation_base = None
        elevation_top = None
        latitude = None
        longitude = None
        state_province = ""
        website = None

        # Parse infobox rows
        for row in infobox.find_all("tr"):
            header = row.find("th")
            data = row.find("td")

            if not header or not data:
                continue

            header_text = header.get_text(strip=True).lower()
            data_text = data.get_text(strip=True)

            if "base" in header_text or "bottom" in header_text:
                match = re.search(r"(\d+(?:,\d+)?)\s*(?:m|metres)", data_text)
                if match:
                    elevation_base = int(match.group(1).replace(",", ""))

            if "top" in header_text or "summit" in header_text:
                match = re.search(r"(\d+(?:,\d+)?)\s*(?:m|metres)", data_text)
                if match:
                    elevation_top = int(match.group(1).replace(",", ""))

            if "location" in header_text:
                state_province = data_text.split(",")[0].strip()

            if "website" in header_text:
                link = data.find("a")
                if link:
                    website = link.get("href")

        # Extract coordinates from geo tags
        geo = soup.select_one(".geo, .geo-dec, .latitude")
        if geo:
            coords_text = geo.get_text()
            lat_match = re.search(r"(-?\d+\.?\d*)", coords_text)
            if lat_match:
                latitude = float(lat_match.group(1))

            geo_lon = soup.select_one(".longitude")
            if geo_lon:
                lon_match = re.search(r"(-?\d+\.?\d*)", geo_lon.get_text())
                if lon_match:
                    longitude = float(lon_match.group(1))

        if not elevation_base or not elevation_top:
            return None

        if not latitude or not longitude:
            latitude = 0.0
            longitude = 0.0

        region = self.get_region(country, state_province)
        timezone = self.get_timezone(country, state_province)

        return ScrapedResort(
            name=name,
            country=country,
            region=region,
            state_province=state_province,
            elevation_base_m=elevation_base,
            elevation_top_m=elevation_top,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            website=website,
            features=[],
            annual_snowfall_cm=None,
            source="wikipedia",
            source_url=detail_url,
        )


class MultiSourceGeocoder(BaseScraper):
    """
    Robust geocoding using multiple sources in priority order:
    1. Known ski resorts database (hardcoded major resorts)
    2. Nominatim/OpenStreetMap (has ski resort POIs)
    3. Wikipedia API (many resorts have wiki pages with coordinates)
    4. Open-Meteo (city/town names as fallback)
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
    OPEN_METEO_URL = "https://geocoding-api.open-meteo.com/v1/search"

    # Country code to bounding box (approximate) for filtering
    COUNTRY_BOUNDS = {
        "US": {"min_lat": 24, "max_lat": 72, "min_lon": -180, "max_lon": -66},
        "CA": {"min_lat": 41, "max_lat": 84, "min_lon": -141, "max_lon": -52},
        "FR": {"min_lat": 41, "max_lat": 51, "min_lon": -5, "max_lon": 10},
        "CH": {"min_lat": 45.8, "max_lat": 47.8, "min_lon": 5.9, "max_lon": 10.5},
        "AT": {"min_lat": 46.4, "max_lat": 49.0, "min_lon": 9.5, "max_lon": 17.2},
        "IT": {"min_lat": 35.5, "max_lat": 47.1, "min_lon": 6.6, "max_lon": 18.5},
        "DE": {"min_lat": 47.3, "max_lat": 55.1, "min_lon": 5.9, "max_lon": 15.0},
        "JP": {"min_lat": 24, "max_lat": 46, "min_lon": 122, "max_lon": 154},
        "NZ": {"min_lat": -47, "max_lat": -34, "min_lon": 166, "max_lon": 179},
        "AU": {"min_lat": -44, "max_lat": -10, "min_lon": 112, "max_lon": 154},
        "CL": {"min_lat": -56, "max_lat": -17, "min_lon": -76, "max_lon": -66},
        "AR": {"min_lat": -55, "max_lat": -21, "min_lon": -74, "max_lon": -53},
        "NO": {"min_lat": 57, "max_lat": 71, "min_lon": 4, "max_lon": 31},
        "SE": {"min_lat": 55, "max_lat": 69, "min_lon": 11, "max_lon": 24},
    }

    # Hardcoded coordinates for well-known resorts that geocoding often misses
    KNOWN_RESORTS = {
        # North America - West
        "whistler blackcomb": (50.1163, -122.9574),
        "whistler": (50.1163, -122.9574),
        "big white": (49.7236, -118.929),
        "sun peaks": (50.8833, -119.9),
        "silver star": (50.3617, -119.0608),
        "revelstoke": (51.0, -118.2),
        "revelstoke mountain resort": (51.0, -118.2),
        "red mountain": (49.1047, -117.8464),
        "apex mountain": (49.3903, -119.9017),
        "cypress mountain": (49.3967, -123.2046),
        "grouse mountain": (49.3807, -123.0815),
        "mammoth mountain": (37.6308, -119.0326),
        "palisades tahoe": (39.1969, -120.2358),
        "squaw valley": (39.1969, -120.2358),
        "heavenly": (38.9353, -119.9400),
        "northstar": (39.2746, -120.1210),
        "kirkwood": (38.6850, -120.0653),
        "mt bachelor": (43.9792, -121.6889),
        "mt hood meadows": (45.3314, -121.6650),
        "crystal mountain": (46.9281, -121.5044),
        "stevens pass": (47.7453, -121.0889),
        # North America - Rockies
        "vail": (39.6403, -106.3742),
        "breckenridge": (39.4817, -106.0384),
        "keystone": (39.6069, -105.9497),
        "copper mountain": (39.5022, -106.1497),
        "winter park": (39.8841, -105.7627),
        "arapahoe basin": (39.6425, -105.8719),
        "aspen": (39.1911, -106.8175),
        "aspen mountain": (39.1875, -106.8186),
        "aspen highlands": (39.1822, -106.8556),
        "snowmass": (39.2130, -106.9378),
        "buttermilk": (39.2030, -106.8600),
        "steamboat": (40.4572, -106.8045),
        "telluride": (37.9375, -107.8123),
        "crested butte": (38.8986, -106.9650),
        "park city": (40.6514, -111.5080),
        "deer valley": (40.6375, -111.4783),
        "snowbird": (40.5830, -111.6508),
        "alta": (40.5884, -111.6386),
        "brighton": (40.5980, -111.5833),
        "solitude": (40.6197, -111.5919),
        "snowbasin": (41.2161, -111.8569),
        "jackson hole": (43.5875, -110.8278),
        "grand targhee": (43.7892, -110.9583),
        "big sky": (45.2858, -111.4019),
        "lake louise": (51.4254, -116.1773),
        "sunshine village": (51.0783, -115.7711),
        "banff sunshine": (51.0783, -115.7711),
        "kicking horse": (51.2975, -117.0478),
        "fernie": (49.4628, -115.0869),
        "panorama": (50.4603, -116.2389),
        "marmot basin": (52.7978, -118.0825),
        "nakiska": (50.9425, -115.1500),
        "castle mountain": (49.3167, -114.4000),
        # North America - East
        "killington": (43.6045, -72.8201),
        "stowe": (44.5303, -72.7814),
        "sugarbush": (44.1358, -72.9033),
        "jay peak": (44.9267, -72.5053),
        "stratton": (43.1136, -72.9083),
        "okemo": (43.4019, -72.7172),
        "sunday river": (44.4736, -70.8567),
        "sugarloaf": (45.0314, -70.3131),
        "mont tremblant": (46.2119, -74.5850),
        "tremblant": (46.2119, -74.5850),
        "mont sainte anne": (47.0750, -70.9069),
        "le massif": (47.2833, -70.6000),
        "bromont": (45.3167, -72.6500),
        "whiteface": (44.3656, -73.9028),
        "gore mountain": (43.6728, -74.0056),
        "hunter mountain": (42.2003, -74.2258),
        # Europe - Alps
        "chamonix": (45.9237, 6.8694),
        "val disere": (45.4481, 6.9800),
        "val d'isere": (45.4481, 6.9800),
        "tignes": (45.4683, 6.9056),
        "courchevel": (45.4153, 6.6347),
        "meribel": (45.3967, 6.5656),
        "les arcs": (45.5703, 6.8278),
        "la plagne": (45.5053, 6.6778),
        "les deux alpes": (45.0167, 6.1222),
        "alpe d'huez": (45.0908, 6.0681),
        "zermatt": (46.0207, 7.7491),
        "verbier": (46.0967, 7.2286),
        "st moritz": (46.4908, 9.8353),
        "davos": (46.8003, 9.8367),
        "laax": (46.8075, 9.2586),
        "st anton": (47.1297, 10.2686),
        "lech": (47.2069, 10.1419),
        "kitzbuhel": (47.4492, 12.3925),
        "ischgl": (46.9697, 10.2933),
        "solden": (46.9650, 10.8750),
        "cortina": (46.5369, 12.1358),
        "cervinia": (45.9333, 7.6333),
        "courmayeur": (45.7967, 6.9689),
        "madonna di campiglio": (46.2294, 10.8264),
        "garmisch partenkirchen": (47.5000, 11.0833),
        # Japan
        "niseko": (42.8048, 140.6874),
        "hakuba": (36.6983, 137.8617),
        "nozawa onsen": (36.9219, 138.4406),
        "myoko kogen": (36.8894, 138.1856),
        "shiga kogen": (36.7000, 138.5167),
        "furano": (43.3406, 142.3828),
        "rusutsu": (42.7500, 140.8833),
        # Oceania
        "thredbo": (-36.5042, 148.3069),
        "perisher": (-36.4000, 148.4167),
        "falls creek": (-36.8667, 147.2833),
        "mt buller": (-37.1456, 146.4386),
        "coronet peak": (-45.0833, 168.7167),
        "the remarkables": (-45.0333, 168.8167),
        "treble cone": (-44.6167, 168.9000),
        "cardrona": (-44.8667, 169.0333),
        "mt hutt": (-43.4833, 171.5333),
        # South America
        "portillo": (-32.8333, -70.1333),
        "valle nevado": (-33.3667, -70.2500),
        "el colorado": (-33.3500, -70.2833),
        "la parva": (-33.3333, -70.2833),
        "cerro catedral": (-41.1667, -71.4500),
        "las lenas": (-35.0667, -70.0667),
        "chapelco": (-40.1333, -71.2500),
    }

    def _clean_name(self, name: str) -> str:
        """Clean resort name for searching."""
        clean = name.lower()
        clean = clean.replace("ski resort ", "").replace("ski area ", "")
        clean = re.sub(r"\s*–\s*", " ", clean)  # Em dash to space
        clean = re.sub(r"\s*-\s*", " ", clean)  # Hyphen to space
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _in_country_bounds(self, lat: float, lon: float, country: str) -> bool:
        """Check if coordinates are within country bounds."""
        bounds = self.COUNTRY_BOUNDS.get(country)
        if not bounds:
            return True  # No bounds defined, accept
        return (
            bounds["min_lat"] <= lat <= bounds["max_lat"]
            and bounds["min_lon"] <= lon <= bounds["max_lon"]
        )

    def _geocode_known(self, name: str, country: str) -> tuple[float, float] | None:
        """Check hardcoded known resorts."""
        clean = self._clean_name(name)
        for known_name, coords in self.KNOWN_RESORTS.items():
            if known_name in clean or clean in known_name:
                lat, lon = coords
                if self._in_country_bounds(lat, lon, country):
                    logger.debug(f"Found in known resorts: {name} -> {coords}")
                    return coords
        return None

    def _geocode_nominatim(
        self, name: str, country: str, state_province: str = ""
    ) -> tuple[float, float] | None:
        """Search OpenStreetMap/Nominatim for ski resort POIs."""
        clean = self._clean_name(name)

        # Try multiple search queries
        queries = [
            f"{clean} ski resort",
            f"{clean} ski area",
            clean,
        ]

        if state_province:
            queries.insert(0, f"{clean} {state_province}")

        for query in queries:
            try:
                params = {
                    "q": query,
                    "format": "json",
                    "limit": 10,
                    "addressdetails": 1,
                }
                # Add country filter
                country_map = {
                    "US": "United States",
                    "CA": "Canada",
                    "FR": "France",
                    "CH": "Switzerland",
                    "AT": "Austria",
                    "IT": "Italy",
                    "DE": "Germany",
                    "JP": "Japan",
                    "NZ": "New Zealand",
                    "AU": "Australia",
                    "CL": "Chile",
                    "AR": "Argentina",
                    "NO": "Norway",
                    "SE": "Sweden",
                }
                if country in country_map:
                    params["countrycodes"] = country.lower()

                response = self._get(self.NOMINATIM_URL, params=params)
                results = response.json()

                for result in results:
                    lat = float(result.get("lat", 0))
                    lon = float(result.get("lon", 0))

                    # Verify country matches
                    addr = result.get("address", {})
                    result_country = addr.get("country_code", "").upper()

                    if result_country == country or self._in_country_bounds(
                        lat, lon, country
                    ):
                        # Check if it's likely a ski resort
                        result_type = result.get("type", "")
                        result_class = result.get("class", "")
                        display = result.get("display_name", "").lower()

                        is_ski = (
                            "ski" in display
                            or "mountain" in display
                            or "resort" in display
                            or result_type in ["ski", "winter_sports"]
                            or result_class in ["leisure", "tourism", "natural"]
                        )

                        if is_ski or clean in display:
                            logger.debug(f"Nominatim found {name}: {lat}, {lon}")
                            return (lat, lon)

                time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

            except Exception as e:
                logger.debug(f"Nominatim error for {name}: {e}")

        return None

    def _geocode_wikipedia(self, name: str, country: str) -> tuple[float, float] | None:
        """Search Wikipedia for resort page and extract coordinates."""
        clean = self._clean_name(name)

        # Try different search terms
        search_terms = [
            f"{clean} ski resort",
            f"{clean} ski area",
            clean,
        ]

        for search_term in search_terms:
            try:
                # Search Wikipedia
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": search_term,
                    "format": "json",
                    "srlimit": 5,
                }
                response = self._get(self.WIKIPEDIA_API, params=params)
                data = response.json()

                search_results = data.get("query", {}).get("search", [])

                for result in search_results:
                    page_title = result.get("title", "")

                    # Get coordinates for this page
                    coord_params = {
                        "action": "query",
                        "titles": page_title,
                        "prop": "coordinates",
                        "format": "json",
                    }
                    coord_response = self._get(self.WIKIPEDIA_API, params=coord_params)
                    coord_data = coord_response.json()

                    pages = coord_data.get("query", {}).get("pages", {})
                    for _page_id, page_info in pages.items():
                        coords = page_info.get("coordinates", [])
                        if coords:
                            lat = coords[0].get("lat")
                            lon = coords[0].get("lon")
                            if (
                                lat
                                and lon
                                and self._in_country_bounds(lat, lon, country)
                            ):
                                logger.debug(f"Wikipedia found {name}: {lat}, {lon}")
                                return (lat, lon)

                time.sleep(0.5)  # Be nice to Wikipedia

            except Exception as e:
                logger.debug(f"Wikipedia error for {name}: {e}")

        return None

    def _geocode_openmeteo(
        self, name: str, country: str, state_province: str = ""
    ) -> tuple[float, float] | None:
        """Fallback to Open-Meteo geocoding (city names)."""
        clean = self._clean_name(name)
        # Also try just the first part of the name
        simple_name = clean.split()[0] if clean else clean

        for search_name in [clean, simple_name]:
            try:
                params = {
                    "name": search_name,
                    "count": 20,
                    "language": "en",
                    "format": "json",
                }
                response = self._get(self.OPEN_METEO_URL, params=params)
                data = response.json()

                results = data.get("results", [])
                country_matches = [
                    r for r in results if r.get("country_code", "").upper() == country
                ]

                if not country_matches:
                    continue

                # Filter by state if available
                if state_province and len(country_matches) > 1:
                    state_matches = [
                        r
                        for r in country_matches
                        if state_province.lower() in (r.get("admin1", "") or "").lower()
                    ]
                    if state_matches:
                        country_matches = state_matches

                best = country_matches[0]
                lat, lon = best["latitude"], best["longitude"]
                logger.debug(f"Open-Meteo found {name}: {lat}, {lon}")
                return (lat, lon)

            except Exception as e:
                logger.debug(f"Open-Meteo error for {name}: {e}")

        return None

    def geocode(
        self, resort_name: str, country: str, state_province: str = ""
    ) -> tuple[float, float] | None:
        """
        Try multiple geocoding sources in priority order.
        Returns coordinates or None if all sources fail.
        """
        # 1. Check known resorts first (instant, most reliable)
        coords = self._geocode_known(resort_name, country)
        if coords:
            return coords

        # 2. Try Nominatim/OpenStreetMap (has ski resort POIs)
        coords = self._geocode_nominatim(resort_name, country, state_province)
        if coords:
            return coords

        # 3. Try Wikipedia (many resorts have wiki pages)
        coords = self._geocode_wikipedia(resort_name, country)
        if coords:
            return coords

        # 4. Fallback to Open-Meteo (city names)
        coords = self._geocode_openmeteo(resort_name, country, state_province)
        if coords:
            return coords

        logger.warning(f"All geocoding sources failed for: {resort_name}")
        return None

    def enrich_resorts(self, resorts: list[ScrapedResort]) -> list[ScrapedResort]:
        """Add coordinates to resorts that don't have them."""
        total = len([r for r in resorts if r.latitude == 0.0])
        geocoded = 0

        logger.info(f"Geocoding {total} resorts without coordinates...")

        for resort in resorts:
            if resort.latitude == 0.0 and resort.longitude == 0.0:
                coords = self.geocode(
                    resort.name, resort.country, resort.state_province
                )
                if coords:
                    resort.latitude, resort.longitude = coords
                    geocoded += 1
                    logger.info(
                        f"[{geocoded}/{total}] Geocoded {resort.name}: {coords}"
                    )

        logger.info(f"Geocoding complete: {geocoded}/{total} successful")
        return resorts


class ResortScraper:
    """Main scraper that combines multiple data sources."""

    def __init__(
        self,
        countries: list[str] | None = None,
        min_vertical: int = 300,
        max_workers: int = 10,
        existing_ids: set[str] | None = None,
    ):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        # Increase connection pool for parallel requests
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers + 5,
            pool_maxsize=max_workers + 5,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.scrapers = [
            SkiResortInfoScraper(
                countries=countries,
                min_vertical=min_vertical,
                session=self.session,
                max_workers=max_workers,
                existing_ids=existing_ids,
            ),
            WikipediaScraper(countries=countries, session=self.session),
        ]
        self.geocoder = MultiSourceGeocoder(session=self.session)

    def scrape(self) -> list[ScrapedResort]:
        """Scrape from all sources and deduplicate."""
        all_resorts = []
        seen_ids = set()

        for scraper in self.scrapers:
            try:
                resorts = scraper.scrape()
                for resort in resorts:
                    if resort.resort_id not in seen_ids:
                        all_resorts.append(resort)
                        seen_ids.add(resort.resort_id)
            except Exception as e:
                logger.error(f"Scraper {scraper.__class__.__name__} failed: {e}")

        # Enrich with coordinates
        all_resorts = self.geocoder.enrich_resorts(all_resorts)

        # Sort by country, then name
        all_resorts.sort(key=lambda r: (r.country, r.name))

        return all_resorts


def load_existing_resorts(path: Path) -> dict:
    """Load existing resorts.json file."""
    if not path.exists():
        return {"version": "1.0.0", "regions": {}, "resorts": []}

    with open(path) as f:
        return json.load(f)


def merge_resorts(existing: list[dict], new_resorts: list[ScrapedResort]) -> list[dict]:
    """Merge new resorts with existing, preferring existing data."""
    existing_ids = {r["resort_id"] for r in existing}

    merged = list(existing)

    for resort in new_resorts:
        if resort.resort_id not in existing_ids:
            merged.append(resort.to_dict())

    return merged


def export_resorts(
    resorts: list[ScrapedResort],
    output_path: Path,
    existing_data: dict | None = None,
    merge: bool = False,
) -> None:
    """Export resorts to JSON file."""

    if merge and existing_data:
        # Merge with existing
        all_resorts = merge_resorts(existing_data.get("resorts", []), resorts)
        regions = existing_data.get("regions", {})
    else:
        all_resorts = [r.to_dict() for r in resorts]
        # Create default regions
        regions = {
            "na_west": {
                "name": "North America - West",
                "display_name": "NA West Coast",
                "countries": ["CA", "US"],
            },
            "na_rockies": {
                "name": "North America - Rockies",
                "display_name": "Rockies",
                "countries": ["CA", "US"],
            },
            "na_east": {
                "name": "North America - East",
                "display_name": "NA East Coast",
                "countries": ["CA", "US"],
            },
            "na_midwest": {
                "name": "North America - Midwest",
                "display_name": "NA Midwest",
                "countries": ["CA", "US"],
            },
            "alps": {
                "name": "European Alps",
                "display_name": "Alps",
                "countries": ["FR", "CH", "AT", "IT", "DE", "SI"],
            },
            "scandinavia": {
                "name": "Scandinavia",
                "display_name": "Scandinavia",
                "countries": ["NO", "SE", "FI"],
            },
            "europe_east": {
                "name": "Eastern Europe",
                "display_name": "Eastern Europe",
                "countries": ["PL", "CZ", "SK", "RO", "BG"],
            },
            "japan": {"name": "Japan", "display_name": "Japan", "countries": ["JP"]},
            "asia": {
                "name": "Asia",
                "display_name": "Asia",
                "countries": ["KR", "CN", "IN"],
            },
            "oceania": {
                "name": "Australia & New Zealand",
                "display_name": "Oceania",
                "countries": ["AU", "NZ"],
            },
            "south_america": {
                "name": "South America",
                "display_name": "South America",
                "countries": ["CL", "AR"],
            },
        }

    output = {
        "version": "1.0.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "regions": regions,
        "resorts": all_resorts,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(all_resorts)} resorts to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape ski resorts from multiple sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("resorts_scraped.json"),
        help="Output file path (default: resorts_scraped.json)",
    )

    parser.add_argument(
        "--countries",
        "-c",
        type=str,
        nargs="+",
        help="Country codes to scrape (e.g., US CA FR CH). Defaults to all.",
    )

    parser.add_argument(
        "--min-vertical",
        type=int,
        default=300,
        help="Minimum vertical drop in meters (default: 300)",
    )

    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Merge with existing resorts.json instead of replacing",
    )

    parser.add_argument(
        "--existing-file",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "resorts.json",
        help="Path to existing resorts.json file",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Full scrape (default is delta mode which skips existing resorts)",
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load existing data for delta mode or merging
    existing_data = None
    existing_ids = set()

    if args.merge_existing or not args.full:
        existing_data = load_existing_resorts(args.existing_file)
        if existing_data:
            existing_ids = {
                r.get("resort_id") for r in existing_data.get("resorts", [])
            }
            logger.info(f"Loaded {len(existing_ids)} existing resorts")
            if not args.full:
                logger.info("Delta mode: will skip existing resorts")
        else:
            logger.info("No existing data found, doing full scrape")

    # Create scraper and run
    scraper = ResortScraper(
        countries=args.countries,
        min_vertical=args.min_vertical,
        max_workers=args.workers,
        existing_ids=existing_ids if not args.full else None,
    )

    resorts = scraper.scrape()
    logger.info(f"Scraped {len(resorts)} total resorts")

    # Export results
    export_resorts(
        resorts,
        args.output,
        existing_data=existing_data,
        merge=args.merge_existing,
    )

    # Print summary
    countries = {}
    for resort in resorts:
        countries[resort.country] = countries.get(resort.country, 0) + 1

    print("\n=== Scraping Summary ===")
    print(f"Total resorts: {len(resorts)}")
    print("\nBy country:")
    for country, count in sorted(countries.items(), key=lambda x: -x[1]):
        print(f"  {country}: {count}")


if __name__ == "__main__":
    main()
