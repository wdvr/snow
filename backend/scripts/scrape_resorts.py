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
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
USER_AGENT = "Mozilla/5.0 (compatible; SnowTrackerBot/1.0; +https://github.com/snowtracker)"
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
    "CA": "na_west",     # Default, will be refined by province
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
    website: Optional[str] = None
    features: list[str] = field(default_factory=list)
    annual_snowfall_cm: Optional[int] = None
    resort_id: str = ""
    source: str = ""
    source_url: str = ""

    def __post_init__(self):
        if not self.resort_id:
            self.resort_id = self._generate_id()

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
        }


class BaseScraper:
    """Base class for ski resort scrapers."""

    def __init__(self, session: Optional[requests.Session] = None):
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
                logger.warning(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    def _get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch URL and return BeautifulSoup object."""
        response = self._get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")

    def get_region(self, country: str, state_province: str = "") -> str:
        """Determine the region based on country and state/province."""
        # Check US-specific mapping
        if country == "US" and state_province in US_STATE_REGIONS:
            return US_STATE_REGIONS[state_province]

        # Check Canada-specific mapping
        if country == "CA" and state_province in CA_PROVINCE_REGIONS:
            return CA_PROVINCE_REGIONS[state_province]

        # Fall back to country mapping
        return REGION_MAPPINGS.get(country, "other")

    def get_timezone(self, country: str, state_province: str = "") -> str:
        """Get timezone for a resort based on country and state/province."""
        # Try specific state/province first
        if state_province:
            tz = TIMEZONE_MAPPINGS.get((country, state_province))
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
        countries: Optional[list[str]] = None,
        min_vertical: int = 300,
        session: Optional[requests.Session] = None
    ):
        super().__init__(session)
        self.countries = countries or list(self.COUNTRY_URLS.keys())
        self.min_vertical = min_vertical  # Minimum vertical drop in meters

    def scrape(self) -> list[ScrapedResort]:
        """Scrape resorts from all configured countries."""
        all_resorts = []

        for country in self.countries:
            if country not in self.COUNTRY_URLS:
                logger.warning(f"No URL configured for country: {country}")
                continue

            try:
                resorts = self._scrape_country(country)
                all_resorts.extend(resorts)
                logger.info(f"Scraped {len(resorts)} resorts from {country}")
            except Exception as e:
                logger.error(f"Failed to scrape {country}: {e}")

        return all_resorts

    def _scrape_country(self, country: str) -> list[ScrapedResort]:
        """Scrape all resorts from a specific country."""
        url = urljoin(self.BASE_URL, self.COUNTRY_URLS[country])
        resorts = []
        page = 1

        while True:
            page_url = f"{url}/page/{page}" if page > 1 else url
            logger.info(f"Scraping {page_url}")

            try:
                soup = self._get_soup(page_url)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    break  # No more pages
                raise

            # Find resort listings
            resort_cards = soup.select(".resort-list-item, .resort-item, [data-resort-id]")

            if not resort_cards:
                # Try alternative selectors
                resort_cards = soup.select(".panel-body a[href*='/ski-resort/']")

            if not resort_cards:
                break

            for card in resort_cards:
                try:
                    resort = self._parse_resort_card(card, country)
                    if resort and (resort.elevation_top_m - resort.elevation_base_m) >= self.min_vertical:
                        resorts.append(resort)
                except Exception as e:
                    logger.warning(f"Failed to parse resort card: {e}")

            # Check for next page
            next_link = soup.select_one(".pagination .next, a[rel='next']")
            if not next_link:
                break

            page += 1

            # Safety limit
            if page > 20:
                logger.warning(f"Reached page limit for {country}")
                break

        return resorts

    def _parse_resort_card(self, card, country: str) -> Optional[ScrapedResort]:
        """Parse a resort card/listing element."""
        # Get resort detail URL
        link = card.select_one("a[href*='/ski-resort/']") or card.find_parent("a")
        if not link:
            return None

        detail_url = urljoin(self.BASE_URL, link.get("href", ""))
        if not detail_url:
            return None

        # Scrape the detail page for full information
        return self._scrape_resort_detail(detail_url, country)

    def _scrape_resort_detail(self, url: str, country: str) -> Optional[ScrapedResort]:
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

        # Extract elevation data
        elevation_base = None
        elevation_top = None

        # Look for elevation information
        elevation_section = soup.select_one(".elevation, .altitude, [class*='elevation']")
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
                elem = soup.find(text=re.compile(label, re.I))
                if elem:
                    parent = elem.parent
                    if parent:
                        match = re.search(r"(\d+)\s*m", parent.get_text())
                        if match:
                            elevation_base = int(match.group(1))
                            break

            for label in ["Top", "Summit", "Peak"]:
                elem = soup.find(text=re.compile(label, re.I))
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

        # Extract location/region within country
        state_province = ""
        location_elem = soup.select_one(".region, .location, [class*='region']")
        if location_elem:
            state_province = location_elem.get_text(strip=True)

        # Extract coordinates
        latitude = None
        longitude = None

        # Look for coordinates in various places
        map_elem = soup.select_one("[data-lat], [data-latitude]")
        if map_elem:
            latitude = float(map_elem.get("data-lat") or map_elem.get("data-latitude"))
            longitude = float(map_elem.get("data-lng") or map_elem.get("data-lon") or map_elem.get("data-longitude"))

        # Try finding in scripts
        if not latitude:
            for script in soup.find_all("script"):
                if script.string:
                    lat_match = re.search(r"lat[itude]*[\"':\s]+(-?\d+\.?\d*)", script.string)
                    lng_match = re.search(r"(?:lng|lon)[gitude]*[\"':\s]+(-?\d+\.?\d*)", script.string)
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
        website_link = soup.select_one("a[href*='http'][target='_blank'], .official-website a")
        if website_link:
            href = website_link.get("href", "")
            if not "skiresort.info" in href:
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
        snow_elem = soup.find(text=re.compile(r"snowfall|snow.*average", re.I))
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
        countries: Optional[list[str]] = None,
        session: Optional[requests.Session] = None
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
                logger.info(f"Scraped {len(resorts)} resorts from Wikipedia for {country}")
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
                detail_url = urljoin(self.BASE_URL, link.get("href", "")) if link else None

                # Try to get more details from the resort's Wikipedia page
                resort = self._scrape_resort_detail(
                    name, country, detail_url
                )
                if resort:
                    resorts.append(resort)

        return resorts

    def _scrape_resort_detail(
        self,
        name: str,
        country: str,
        detail_url: Optional[str]
    ) -> Optional[ScrapedResort]:
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


class OpenMeteoGeocodingScraper(BaseScraper):
    """Use Open-Meteo's geocoding API to enrich resort data with coordinates."""

    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def geocode(self, resort_name: str, country: str) -> Optional[tuple[float, float]]:
        """Get coordinates for a resort by name."""
        params = {
            "name": resort_name,
            "count": 5,
            "language": "en",
            "format": "json",
        }

        try:
            response = self._get(self.GEOCODING_URL, params=params)
            data = response.json()

            results = data.get("results", [])

            # Find best match for the country
            for result in results:
                if result.get("country_code", "").upper() == country:
                    return (result["latitude"], result["longitude"])

            # Fall back to first result
            if results:
                return (results[0]["latitude"], results[0]["longitude"])

        except Exception as e:
            logger.warning(f"Geocoding failed for {resort_name}: {e}")

        return None

    def enrich_resorts(self, resorts: list[ScrapedResort]) -> list[ScrapedResort]:
        """Add coordinates to resorts that don't have them."""
        for resort in resorts:
            if resort.latitude == 0.0 and resort.longitude == 0.0:
                coords = self.geocode(resort.name, resort.country)
                if coords:
                    resort.latitude, resort.longitude = coords
                    logger.info(f"Geocoded {resort.name}: {coords}")

        return resorts


class ResortScraper:
    """Main scraper that combines multiple data sources."""

    def __init__(
        self,
        countries: Optional[list[str]] = None,
        min_vertical: int = 300,
    ):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.scrapers = [
            SkiResortInfoScraper(countries=countries, min_vertical=min_vertical, session=self.session),
            WikipediaScraper(countries=countries, session=self.session),
        ]
        self.geocoder = OpenMeteoGeocodingScraper(session=self.session)

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

    with open(path, "r") as f:
        return json.load(f)


def merge_resorts(
    existing: list[dict],
    new_resorts: list[ScrapedResort]
) -> list[dict]:
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
    existing_data: Optional[dict] = None,
    merge: bool = False,
) -> None:
    """Export resorts to JSON file."""

    if merge and existing_data:
        # Merge with existing
        all_resorts = merge_resorts(
            existing_data.get("resorts", []),
            resorts
        )
        regions = existing_data.get("regions", {})
    else:
        all_resorts = [r.to_dict() for r in resorts]
        # Create default regions
        regions = {
            "na_west": {"name": "North America - West", "display_name": "NA West Coast", "countries": ["CA", "US"]},
            "na_rockies": {"name": "North America - Rockies", "display_name": "Rockies", "countries": ["CA", "US"]},
            "na_east": {"name": "North America - East", "display_name": "NA East Coast", "countries": ["CA", "US"]},
            "na_midwest": {"name": "North America - Midwest", "display_name": "NA Midwest", "countries": ["CA", "US"]},
            "alps": {"name": "European Alps", "display_name": "Alps", "countries": ["FR", "CH", "AT", "IT", "DE", "SI"]},
            "scandinavia": {"name": "Scandinavia", "display_name": "Scandinavia", "countries": ["NO", "SE", "FI"]},
            "europe_east": {"name": "Eastern Europe", "display_name": "Eastern Europe", "countries": ["PL", "CZ", "SK", "RO", "BG"]},
            "japan": {"name": "Japan", "display_name": "Japan", "countries": ["JP"]},
            "asia": {"name": "Asia", "display_name": "Asia", "countries": ["KR", "CN", "IN"]},
            "oceania": {"name": "Australia & New Zealand", "display_name": "Oceania", "countries": ["AU", "NZ"]},
            "south_america": {"name": "South America", "display_name": "South America", "countries": ["CL", "AR"]},
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
        "--output", "-o",
        type=Path,
        default=Path("resorts_scraped.json"),
        help="Output file path (default: resorts_scraped.json)",
    )

    parser.add_argument(
        "--countries", "-c",
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
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load existing data if merging
    existing_data = None
    if args.merge_existing:
        existing_data = load_existing_resorts(args.existing_file)
        logger.info(f"Loaded {len(existing_data.get('resorts', []))} existing resorts")

    # Create scraper and run
    scraper = ResortScraper(
        countries=args.countries,
        min_vertical=args.min_vertical,
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
