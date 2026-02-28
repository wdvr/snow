"""Snow-Forecast.com scraper for resort snowfall and depth data.

Snow-Forecast provides snowfall forecasts and snow depth data for resorts
worldwide, including many European, Japanese, and Southern Hemisphere resorts
not covered by OnTheSnow.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from models.weather import ConfidenceLevel

logger = logging.getLogger(__name__)

# Path to override slugs file
SLUGS_FILE = Path(__file__).parent.parent.parent / "data" / "snowforecast_slugs.json"


@dataclass
class SnowForecastData:
    """Scraped snow report data from Snow-Forecast.com."""

    resort_id: str
    snowfall_24h_cm: float | None
    snowfall_48h_cm: float | None
    snowfall_72h_cm: float | None
    upper_depth_cm: float | None
    lower_depth_cm: float | None
    surface_conditions: str | None
    source_url: str


class SnowForecastScraper:
    """Scraper for Snow-Forecast.com snow reports."""

    BASE_URL = "https://www.snow-forecast.com"

    def __init__(self):
        """Initialize the scraper."""
        self._slug_overrides: dict[str, str] = {}
        self._load_slug_overrides()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; PowderChaser/1.0; +https://github.com/snowtracker)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    def _load_slug_overrides(self) -> None:
        """Load slug overrides from JSON file if it exists."""
        try:
            if SLUGS_FILE.exists():
                with open(SLUGS_FILE) as f:
                    self._slug_overrides = json.load(f)
                logger.debug(
                    f"Loaded {len(self._slug_overrides)} Snow-Forecast slug overrides"
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load Snow-Forecast slug overrides: {e}")
            self._slug_overrides = {}

    def _get_slug(self, resort_id: str) -> str:
        """Get Snow-Forecast URL slug for a resort.

        First checks override mappings, then auto-generates by capitalizing
        each segment: "big-white" -> "Big-White".
        """
        if resort_id in self._slug_overrides:
            return self._slug_overrides[resort_id]

        # Auto-generate: capitalize each dash-separated segment
        return "-".join(segment.capitalize() for segment in resort_id.split("-"))

    def get_snow_report(self, resort_id: str) -> SnowForecastData | None:
        """
        Fetch snow report data for a resort.

        Args:
            resort_id: Internal resort ID (e.g., 'big-white')

        Returns:
            SnowForecastData if successful, None if error
        """
        slug = self._get_slug(resort_id)
        url = f"{self.BASE_URL}/resorts/{slug}/6day/mid"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            return self._parse_snow_report(response.text, resort_id, url)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch Snow-Forecast data for {resort_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Snow-Forecast data for {resort_id}: {e}")
            return None

    def _parse_snow_report(
        self, html: str, resort_id: str, source_url: str
    ) -> SnowForecastData | None:
        """Parse Snow-Forecast HTML to extract snow data."""
        soup = BeautifulSoup(html, "html.parser")

        data = SnowForecastData(
            resort_id=resort_id,
            snowfall_24h_cm=None,
            snowfall_48h_cm=None,
            snowfall_72h_cm=None,
            upper_depth_cm=None,
            lower_depth_cm=None,
            surface_conditions=None,
            source_url=source_url,
        )

        text = soup.get_text()

        # Extract snowfall amounts (Snow-Forecast uses cm natively)
        # Patterns like "24hr: 15cm", "New snow 24h: 15 cm"
        match_24h = re.search(
            r"(?:24\s*(?:hr|hour|h)|new\s+snow\s*(?:in\s+)?24)[:\s]*(\d+\.?\d*)\s*cm",
            text,
            re.IGNORECASE,
        )
        if match_24h:
            data.snowfall_24h_cm = float(match_24h.group(1))

        match_48h = re.search(
            r"(?:48\s*(?:hr|hour|h)|new\s+snow\s*(?:in\s+)?48)[:\s]*(\d+\.?\d*)\s*cm",
            text,
            re.IGNORECASE,
        )
        if match_48h:
            data.snowfall_48h_cm = float(match_48h.group(1))

        match_72h = re.search(
            r"(?:72\s*(?:hr|hour|h)|new\s+snow\s*(?:in\s+)?72)[:\s]*(\d+\.?\d*)\s*cm",
            text,
            re.IGNORECASE,
        )
        if match_72h:
            data.snowfall_72h_cm = float(match_72h.group(1))

        # Extract snow depth
        # Snow-Forecast shows "Upper depth: 250cm" and "Lower depth: 120cm"
        match_upper = re.search(
            r"(?:upper|top|summit)\s*(?:snow\s*)?depth[:\s]*(\d+\.?\d*)\s*cm",
            text,
            re.IGNORECASE,
        )
        if match_upper:
            val = float(match_upper.group(1))
            if val <= 1500:  # Sanity check
                data.upper_depth_cm = val

        match_lower = re.search(
            r"(?:lower|base|bottom)\s*(?:snow\s*)?depth[:\s]*(\d+\.?\d*)\s*cm",
            text,
            re.IGNORECASE,
        )
        if match_lower:
            val = float(match_lower.group(1))
            if val <= 1500:  # Sanity check
                data.lower_depth_cm = val

        # Extract surface conditions
        conditions_match = re.search(
            r"(?:surface|snow)\s*(?:conditions?|type)[:\s]*([A-Za-z\s,/]+?)(?:\n|<|$|\d)",
            text,
            re.IGNORECASE,
        )
        if conditions_match:
            cond = conditions_match.group(1).strip()
            if len(cond) >= 3:  # Avoid capturing noise
                data.surface_conditions = cond

        return data

    def is_resort_supported(self, resort_id: str) -> bool:
        """Check if a resort is potentially supported by Snow-Forecast.

        Snow-Forecast has broad coverage, so we assume all resorts are
        potentially supported. The actual check happens when we try to
        fetch the page (404 = not supported).
        """
        return True
