"""OnTheSnow.com scraper for accurate resort snowfall data.

OnTheSnow provides accurate, resort-reported snowfall data that is often
more reliable than weather API forecasts since it comes from actual
resort measurements.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

from models.weather import ConfidenceLevel

logger = logging.getLogger(__name__)

# Mapping of resort IDs to OnTheSnow URL slugs
RESORT_URL_MAPPING = {
    # North America - West
    "big-white": "british-columbia/big-white",
    "whistler-blackcomb": "british-columbia/whistler-blackcomb",
    "revelstoke": "british-columbia/revelstoke-mountain-resort",
    "silver-star": "british-columbia/silver-star",
    "sun-peaks": "british-columbia/sun-peaks-resort",
    "palisades-tahoe": "california/palisades-tahoe",
    "mammoth-mountain": "california/mammoth-mountain",
    # North America - Rockies
    "lake-louise": "alberta/lake-louise",
    "sunshine-village": "alberta/sunshine-village",
    "vail": "colorado/vail",
    "breckenridge": "colorado/breckenridge",
    "telluride": "colorado/telluride",
    "steamboat": "colorado/steamboat",
    "aspen-snowmass": "colorado/aspen-snowmass",
    "park-city": "utah/park-city-mountain-resort",
    "jackson-hole": "wyoming/jackson-hole",
    # Alps
    "chamonix": None,  # Not on OnTheSnow or different URL structure
    "zermatt": None,
    "st-anton": None,
    "verbier": None,
    "val-disere": None,
    "courchevel": None,
    "kitzbuehel": None,
    "cortina": None,
    # Japan
    "niseko": None,
    "hakuba": None,
    "furano": None,
    # Oceania
    "queenstown-remarkables": None,
    "coronet-peak": None,
    "thredbo": None,
    "perisher": None,
    # South America
    "portillo": None,
    "valle-nevado": None,
    "las-lenas": None,
}


@dataclass
class ScrapedSnowData:
    """Scraped snow report data from OnTheSnow."""

    resort_id: str
    snowfall_24h_inches: float | None
    snowfall_48h_inches: float | None
    snowfall_72h_inches: float | None
    base_depth_inches: float | None
    summit_depth_inches: float | None
    surface_conditions: str | None
    lifts_open: int | None
    lifts_total: int | None
    runs_open: int | None
    runs_total: int | None
    last_updated: str | None
    source_url: str

    @property
    def snowfall_24h_cm(self) -> float | None:
        """Convert 24h snowfall to cm."""
        return self.snowfall_24h_inches * 2.54 if self.snowfall_24h_inches else None

    @property
    def snowfall_48h_cm(self) -> float | None:
        """Convert 48h snowfall to cm."""
        return self.snowfall_48h_inches * 2.54 if self.snowfall_48h_inches else None

    @property
    def snowfall_72h_cm(self) -> float | None:
        """Convert 72h snowfall to cm."""
        return self.snowfall_72h_inches * 2.54 if self.snowfall_72h_inches else None

    @property
    def base_depth_cm(self) -> float | None:
        """Convert base depth to cm."""
        return self.base_depth_inches * 2.54 if self.base_depth_inches else None

    @property
    def summit_depth_cm(self) -> float | None:
        """Convert summit depth to cm."""
        return self.summit_depth_inches * 2.54 if self.summit_depth_inches else None


class OnTheSnowScraper:
    """Scraper for OnTheSnow.com snow reports."""

    BASE_URL = "https://www.onthesnow.com"

    def __init__(self):
        """Initialize the scraper."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; SnowTracker/1.0; +https://github.com/snowtracker)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def get_snow_report(self, resort_id: str) -> ScrapedSnowData | None:
        """
        Fetch snow report data for a resort.

        Args:
            resort_id: Internal resort ID (e.g., 'silver-star')

        Returns:
            ScrapedSnowData if successful, None if resort not supported or error
        """
        url_slug = RESORT_URL_MAPPING.get(resort_id)
        if not url_slug:
            logger.debug(f"Resort {resort_id} not mapped to OnTheSnow URL")
            return None

        url = f"{self.BASE_URL}/{url_slug}/skireport"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            return self._parse_snow_report(response.text, resort_id, url)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch OnTheSnow data for {resort_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing OnTheSnow data for {resort_id}: {e}")
            return None

    def _parse_snow_report(
        self, html: str, resort_id: str, source_url: str
    ) -> ScrapedSnowData | None:
        """Parse snow report HTML to extract data."""
        soup = BeautifulSoup(html, "html.parser")

        data = ScrapedSnowData(
            resort_id=resort_id,
            snowfall_24h_inches=None,
            snowfall_48h_inches=None,
            snowfall_72h_inches=None,
            base_depth_inches=None,
            summit_depth_inches=None,
            surface_conditions=None,
            lifts_open=None,
            lifts_total=None,
            runs_open=None,
            runs_total=None,
            last_updated=None,
            source_url=source_url,
        )

        # Try to find snowfall data
        # OnTheSnow typically shows "24 Hr", "48 Hr", "72 Hr" or "Last 24 Hours" etc.
        snowfall_pattern = re.compile(r"(\d+\.?\d*)[\"\s]*(in|inches)?", re.IGNORECASE)

        # Look for snowfall sections
        text = soup.get_text()

        # Try to extract 24h snowfall
        match_24h = re.search(
            r"(?:24\s*(?:hr|hour|h)|last\s+24)[^0-9]*(\d+\.?\d*)\s*(?:\"|in|inches)?",
            text,
            re.IGNORECASE,
        )
        if match_24h:
            data.snowfall_24h_inches = float(match_24h.group(1))

        # Try to extract 48h snowfall
        match_48h = re.search(
            r"(?:48\s*(?:hr|hour|h)|last\s+48)[^0-9]*(\d+\.?\d*)\s*(?:\"|in|inches)?",
            text,
            re.IGNORECASE,
        )
        if match_48h:
            data.snowfall_48h_inches = float(match_48h.group(1))

        # Try to extract 72h snowfall
        match_72h = re.search(
            r"(?:72\s*(?:hr|hour|h)|last\s+72)[^0-9]*(\d+\.?\d*)\s*(?:\"|in|inches)?",
            text,
            re.IGNORECASE,
        )
        if match_72h:
            data.snowfall_72h_inches = float(match_72h.group(1))

        # Try to extract base depth
        match_base = re.search(
            r"(?:base|bottom)[^0-9]*(\d+\.?\d*)\s*(?:\"|in|inches)?",
            text,
            re.IGNORECASE,
        )
        if match_base:
            data.base_depth_inches = float(match_base.group(1))

        # Try to extract summit depth
        match_summit = re.search(
            r"(?:summit|top|peak)[^0-9]*(\d+\.?\d*)\s*(?:\"|in|inches)?",
            text,
            re.IGNORECASE,
        )
        if match_summit:
            data.summit_depth_inches = float(match_summit.group(1))

        # Try to extract surface conditions
        conditions_match = re.search(
            r"(?:surface|conditions?)[:\s]*([A-Za-z\s,]+?)(?:\n|<|$)",
            text,
            re.IGNORECASE,
        )
        if conditions_match:
            data.surface_conditions = conditions_match.group(1).strip()

        # Try to extract lifts open
        lifts_match = re.search(r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:lifts?)", text, re.IGNORECASE)
        if lifts_match:
            data.lifts_open = int(lifts_match.group(1))
            data.lifts_total = int(lifts_match.group(2))

        # Try to extract runs open
        runs_match = re.search(r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:runs?|trails?)", text, re.IGNORECASE)
        if runs_match:
            data.runs_open = int(runs_match.group(1))
            data.runs_total = int(runs_match.group(2))

        return data

    def merge_with_weather_data(
        self, weather_data: dict[str, Any], scraped_data: ScrapedSnowData
    ) -> dict[str, Any]:
        """
        Merge scraped data with weather API data, preferring scraped values.

        Scraped data from resort reports is generally more accurate than
        weather API forecasts for snowfall measurements.
        """
        merged = weather_data.copy()

        # Override snowfall with scraped data if available (resort data is more accurate)
        if scraped_data.snowfall_24h_cm is not None:
            # Weight scraped data heavily but average with API for smoothing
            api_24h = merged.get("snowfall_24h_cm", 0.0)
            merged["snowfall_24h_cm"] = (
                scraped_data.snowfall_24h_cm * 0.7 + api_24h * 0.3
            )

        if scraped_data.snowfall_48h_cm is not None:
            api_48h = merged.get("snowfall_48h_cm", 0.0)
            merged["snowfall_48h_cm"] = (
                scraped_data.snowfall_48h_cm * 0.7 + api_48h * 0.3
            )

        if scraped_data.snowfall_72h_cm is not None:
            api_72h = merged.get("snowfall_72h_cm", 0.0)
            merged["snowfall_72h_cm"] = (
                scraped_data.snowfall_72h_cm * 0.7 + api_72h * 0.3
            )

        # Upgrade confidence level since we have resort-reported data
        merged["source_confidence"] = ConfidenceLevel.HIGH
        merged["data_source"] = f"open-meteo.com + onthesnow.com"

        # Store scraped data in raw_data for debugging
        if "raw_data" not in merged:
            merged["raw_data"] = {}
        merged["raw_data"]["scraped_onthesnow"] = {
            "snowfall_24h_inches": scraped_data.snowfall_24h_inches,
            "snowfall_48h_inches": scraped_data.snowfall_48h_inches,
            "snowfall_72h_inches": scraped_data.snowfall_72h_inches,
            "base_depth_inches": scraped_data.base_depth_inches,
            "summit_depth_inches": scraped_data.summit_depth_inches,
            "surface_conditions": scraped_data.surface_conditions,
            "source_url": scraped_data.source_url,
        }

        return merged

    def is_resort_supported(self, resort_id: str) -> bool:
        """Check if a resort is supported by this scraper."""
        return RESORT_URL_MAPPING.get(resort_id) is not None
