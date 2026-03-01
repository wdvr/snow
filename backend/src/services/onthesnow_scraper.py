"""OnTheSnow.com scraper for accurate resort snowfall data.

OnTheSnow provides accurate, resort-reported snowfall data that is often
more reliable than weather API forecasts since it comes from actual
resort measurements.

Data is extracted from the structured JSON embedded in the __NEXT_DATA__
script tag (Next.js pattern). Falls back to regex-based HTML parsing if
JSON extraction fails.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

from models.weather import ConfidenceLevel

logger = logging.getLogger(__name__)

# Centimeters-to-inches conversion factor
_CM_TO_INCHES = 1.0 / 2.54

# Mapping of resort IDs to OnTheSnow URL slugs.
# URL pattern: https://www.onthesnow.com/{slug}/skireport
# NA resorts use {state-or-province}/{resort-name}.
# European resorts use {region}/{resort-name} and may redirect to .co.uk.
# None = resort not available on OnTheSnow (uses Snow-Forecast instead).
RESORT_URL_MAPPING: dict[str, str | None] = {
    # ── North America - West Coast ──────────────────────────────────
    "alyeska-resort": "alaska/alyeska-resort",
    "big-white": "british-columbia/big-white",
    "crystal-mountain-wa": "washington/crystal-mountain-wa",
    "fernie": "british-columbia/fernie-alpine",
    "heavenly": "california/heavenly-mountain-resort",
    "homewood-mountain-resort": "california/homewood-mountain-resort",
    "june-mountain": "california/june-mountain",
    "kicking-horse-golden": "british-columbia/kicking-horse",
    "kirkwood": "california/kirkwood",
    "mammoth-mountain": "california/mammoth-mountain-ski-area",
    "mt-bachelor": "oregon/mt-bachelor",
    "mt-baker": "washington/mt-baker",
    "mt-hood-meadows": "oregon/mt-hood-meadows",
    "northstar": "california/northstar-california",
    "palisades-tahoe": "california/palisades-tahoe",
    "panorama": "british-columbia/panorama-mountain-resort",
    "revelstoke": "british-columbia/revelstoke-mountain",
    "sierra-at-tahoe": "california/sierra-at-tahoe",
    "silver-star": "british-columbia/silver-star",
    "snoqualmie-pass": "washington/the-summit-at-snoqualmie",
    "stevens-pass": "washington/stevens-pass-resort",
    "sugar-bowl": "california/sugar-bowl-resort",
    "sun-peaks": "british-columbia/sun-peaks",
    "timberline": "oregon/timberline-ski-area",
    "whistler-blackcomb": "british-columbia/whistler-blackcomb",
    # ── North America - Rockies ─────────────────────────────────────
    "alta": "utah/alta-ski-area",
    "arapahoe-basin": "colorado/arapahoe-basin-ski-area",
    "aspen-snowmass": "colorado/aspen-snowmass",
    "aspen": "colorado/aspen-mountain",
    "aspen-highlands": "colorado/aspen-highlands",
    "banff-sunshine": "alberta/sunshine-village",
    "beaver-creek": "colorado/beaver-creek",
    "big-sky-resort": "montana/big-sky-resort",
    "breckenridge": "colorado/breckenridge",
    "brighton": "utah/brighton-resort",
    "castle-mountain": "alberta/castle-mountain",
    "copper-mountain": "colorado/copper-mountain-resort",
    "crested-butte": "colorado/crested-butte-mountain-resort",
    "deer-valley": "utah/deer-valley-resort",
    "grand-targhee": "wyoming/grand-targhee-resort",
    "jackson-hole": "wyoming/jackson-hole",
    "keystone": "colorado/keystone",
    "lake-louise": "alberta/lake-louise",
    "marmot-basin-jasper": "alberta/marmot-basin",
    "nakiska": "alberta/nakiska-ski-area",
    "park-city": "utah/park-city-mountain-resort",
    "purgatory-durango": "colorado/purgatory-at-durango-mountain-resort",
    "snowbasin": "utah/snowbasin",
    "snowbird": "utah/snowbird",
    "solitude": "utah/solitude-mountain-resort",
    "steamboat": "colorado/steamboat",
    "sunshine-village": "alberta/sunshine-village",
    "taos": "new-mexico/taos-ski-valley",
    "telluride": "colorado/telluride",
    "vail": "colorado/vail",
    "whitefish-mountain-resort": "montana/whitefish-mountain-resort",
    "winter-park-resort": "colorado/winter-park-resort",
    "wolf-creek": "colorado/wolf-creek-ski-area",
    # ── North America - East ────────────────────────────────────────
    "bretton-woods": "new-hampshire/bretton-woods",
    "jay-peak": "vermont/jay-peak",
    "killington": "vermont/killington-resort",
    "le-massif-de-charlevoix": "quebec/le-massif",
    "loon-mountain": "new-hampshire/loon-mountain",
    "stowe": "vermont/stowe-mountain-resort",
    "stratton": "vermont/stratton",
    "sugarbush": "vermont/sugarbush",
    "sugarloaf": "maine/sugarloaf",
    "sunday-river": "maine/sunday-river",
    "tremblant": "quebec/tremblant",
    "whiteface-lake-placid": "new-york/whiteface-lake-placid",
    # ── Alps ────────────────────────────────────────────────────────
    # European resorts use region-based slugs (not country).
    # The .com domain redirects to .co.uk for these; requests follows 301s.
    "chamonix": "northern-alps/chamonix-mont-blanc",
    "zermatt": "valais/zermatt",
    "st-anton": "tyrol/st-anton-am-arlberg",
    "verbier": "valais/verbier",
    "val-disere": "northern-alps/val-disere",
    "courchevel": "northern-alps/courchevel",
    "kitzbuehel": "tyrol/kitzbuehel",
    "cortina": "veneto/cortina-dampezzo",
    "alpe-dhuez": "northern-alps/alpe-dhuez",
    "les-arcs": "northern-alps/les-arcs-bourg-st-maurice",
    "meribel": "northern-alps/meribel",
    "la-plagne": "northern-alps/la-plagne",
    "val-thorens": "northern-alps/val-thorens",
    "tignes": "northern-alps/tignes",
    "davos-klosters": "graubuenden/davos-klosters",
    "st-moritz": "graubuenden/st-moritz",
    "lech-zuers": "vorarlberg/lech",
    "ischgl": "tyrol/ischgl",
    "saalbach-hinterglemm": "salzburg/saalbach-hinterglemm-leogang-fieberbrunn",
    "selva-val-gardena": "trentino-alto-adige/selva-di-val-gardena-wolkenstein-groeden",
    # ── Scandinavia (selected major resorts) ────────────────────────
    "are": "sweden/are",
    "hemsedal": "norway/hemsedal",
    "trysil": "norway/trysil",
    "levi": "finland/levi",
    "geilo": "norway/geilo",
    # ── Japan ───────────────────────────────────────────────────────
    "niseko": None,
    "hakuba": None,
    "furano": None,
    # ── Oceania ─────────────────────────────────────────────────────
    "queenstown-remarkables": None,
    "coronet-peak": None,
    "thredbo": None,
    "perisher": None,
    # ── South America ───────────────────────────────────────────────
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
    mid_depth_inches: float | None = None
    open_flag: bool | None = None

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
    """Scraper for OnTheSnow.com snow reports.

    Extracts structured JSON data from the __NEXT_DATA__ script tag
    embedded in OnTheSnow resort pages (Next.js pattern). Falls back
    to regex-based HTML text parsing if JSON extraction fails.
    """

    BASE_URL = "https://www.onthesnow.com"

    def __init__(self):
        """Initialize the scraper."""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; PowderChaser/1.0; +https://github.com/snowtracker)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

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

    # ── JSON extraction (primary) ───────────────────────────────────

    def _parse_snow_report(
        self, html: str, resort_id: str, source_url: str
    ) -> ScrapedSnowData | None:
        """Parse snow report HTML, preferring JSON extraction over regex."""
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON extraction first (reliable, structured)
        result = self._parse_from_json(soup, resort_id, source_url)
        if result is not None:
            return result

        # Fall back to regex-based parsing (fragile but covers edge cases)
        logger.info(
            f"JSON extraction failed for {resort_id}, falling back to regex parsing"
        )
        return self._parse_from_regex(soup, resort_id, source_url)

    def _parse_from_json(
        self, soup: BeautifulSoup, resort_id: str, source_url: str
    ) -> ScrapedSnowData | None:
        """Extract snow data from __NEXT_DATA__ JSON embedded in the page.

        OnTheSnow (Next.js) embeds all page data in a script tag:
            <script id="__NEXT_DATA__" type="application/json">{...}</script>

        Key paths (all numeric values in centimeters):
            props.pageProps.fullResort.snow.last24    - 24h snowfall (cm)
            props.pageProps.fullResort.snow.last48    - 48h snowfall (cm)
            props.pageProps.fullResort.snow.last72    - 72h snowfall (cm)
            props.pageProps.fullResort.depths.base    - base depth (cm)
            props.pageProps.fullResort.depths.middle  - mid depth (cm)
            props.pageProps.fullResort.depths.summit  - summit depth (cm)
            props.pageProps.fullResort.lifts.open     - lifts open
            props.pageProps.fullResort.lifts.total    - lifts total
            props.pageProps.fullResort.runs.open      - runs open
            props.pageProps.fullResort.runs.total     - runs total
            props.pageProps.fullResort.status.openFlag - 1=open, 0=closed
            props.pageProps.fullResort.updatedAt      - ISO 8601 timestamp
        """
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            return None

        try:
            next_data = json.loads(script_tag.string)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse __NEXT_DATA__ JSON for {resort_id}")
            return None

        # Navigate to fullResort data
        page_props = next_data.get("props", {}).get("pageProps", {})
        full_resort = page_props.get("fullResort")
        if not full_resort:
            # Try the simpler "resort" key as fallback
            full_resort = page_props.get("resort")
        if not full_resort:
            return None

        snow = full_resort.get("snow", {}) or {}
        depths = full_resort.get("depths", {}) or {}
        lifts = full_resort.get("lifts", {}) or {}
        runs = full_resort.get("runs", {}) or {}
        status = full_resort.get("status", {}) or {}

        # Extract snowfall values (cm -> inches for backward compatibility)
        # Verified Feb 2026: Vail last48=5.08 displays as "2 inches" on the
        # page (5.08 cm / 2.54 = 2.0 inches). All snow values are in cm.
        snowfall_24h = self._cm_to_inches(snow.get("last24"))
        snowfall_48h = self._cm_to_inches(snow.get("last48"))
        snowfall_72h = self._cm_to_inches(snow.get("last72"))

        # Extract depth values (cm -> inches for backward compatibility)
        base_depth = self._cm_to_inches(depths.get("base"))
        mid_depth = self._cm_to_inches(depths.get("middle"))
        summit_depth = self._cm_to_inches(depths.get("summit"))

        # If depths dict is empty, check snow object for base
        if base_depth is None:
            base_depth = self._cm_to_inches(snow.get("base"))

        # Lifts and runs
        lifts_open = self._safe_int(lifts.get("open"))
        lifts_total = self._safe_int(lifts.get("total"))
        runs_open = self._safe_int(runs.get("open"))
        runs_total = self._safe_int(runs.get("total"))

        # Open status flag (1 = open, 0 = closed)
        open_flag_raw = status.get("openFlag")
        open_flag = None
        if open_flag_raw is not None:
            try:
                open_flag = int(open_flag_raw) == 1
            except (ValueError, TypeError):
                pass

        # Last updated timestamp
        updated_at = full_resort.get("updatedAt")

        return ScrapedSnowData(
            resort_id=resort_id,
            snowfall_24h_inches=snowfall_24h,
            snowfall_48h_inches=snowfall_48h,
            snowfall_72h_inches=snowfall_72h,
            base_depth_inches=base_depth,
            summit_depth_inches=summit_depth,
            mid_depth_inches=mid_depth,
            surface_conditions=None,  # Not in structured JSON
            lifts_open=lifts_open,
            lifts_total=lifts_total,
            runs_open=runs_open,
            runs_total=runs_total,
            last_updated=updated_at,
            source_url=source_url,
            open_flag=open_flag,
        )

    # ── Regex fallback (legacy) ─────────────────────────────────────

    def _parse_from_regex(
        self, soup: BeautifulSoup, resort_id: str, source_url: str
    ) -> ScrapedSnowData | None:
        """Legacy regex-based parsing as fallback when JSON is unavailable."""
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
            r'(?:Base\s+(\d+\.?\d*)\s*"|(\d+\.?\d*)\s*"\s*base)',
            text,
            re.IGNORECASE,
        )
        if match_base:
            val = float(match_base.group(1) or match_base.group(2))
            if val <= 300:  # Sanity check: no resort has >300" base
                data.base_depth_inches = val

        # Try to extract summit depth
        match_summit = re.search(
            r'Summit\s+(\d+\.?\d*)\s*"',
            text,
            re.IGNORECASE,
        )
        if match_summit:
            val = float(match_summit.group(1))
            if val <= 500:  # Sanity check: no resort has >500" summit depth
                data.summit_depth_inches = val

        # Try to extract surface conditions
        conditions_match = re.search(
            r"(?:surface|conditions?)[:\s]*([A-Za-z\s,]+?)(?:\n|<|$)",
            text,
            re.IGNORECASE,
        )
        if conditions_match:
            data.surface_conditions = conditions_match.group(1).strip()

        # Try to extract lifts open
        lifts_match = re.search(
            r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:lifts?)", text, re.IGNORECASE
        )
        if lifts_match:
            data.lifts_open = int(lifts_match.group(1))
            data.lifts_total = int(lifts_match.group(2))

        # Try to extract runs open
        runs_match = re.search(
            r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:runs?|trails?)", text, re.IGNORECASE
        )
        if runs_match:
            data.runs_open = int(runs_match.group(1))
            data.runs_total = int(runs_match.group(2))

        return data

    # ── Merge logic ─────────────────────────────────────────────────

    def merge_with_weather_data(
        self,
        weather_data: dict[str, Any],
        scraped_data: ScrapedSnowData,
        elevation_level: str = "mid",
    ) -> dict[str, Any]:
        """
        Merge scraped data with weather API data, preferring scraped values.

        Scraped data from resort reports is generally more accurate than
        weather API forecasts for snowfall measurements.

        Args:
            weather_data: Weather data from Open-Meteo API
            scraped_data: Scraped data from OnTheSnow
            elevation_level: "base", "mid", or "top" - determines which
                scraped depth value to use
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

        # Override snow_depth with scraped data if available.
        # Resort-reported base/summit depth is far more accurate than
        # Open-Meteo's grid-level model estimate (~10-25km resolution).
        scraped_depth = self._get_scraped_depth_for_level(scraped_data, elevation_level)
        if scraped_depth is not None:
            merged["snow_depth_cm"] = scraped_depth

        # Upgrade confidence level since we have resort-reported data
        merged["source_confidence"] = ConfidenceLevel.HIGH
        merged["data_source"] = "open-meteo.com + onthesnow.com"

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

    @staticmethod
    def _get_scraped_depth_for_level(
        scraped_data: ScrapedSnowData, elevation_level: str
    ) -> float | None:
        """Get the appropriate scraped depth for an elevation level.

        Args:
            scraped_data: Scraped data with base_depth_cm and summit_depth_cm
            elevation_level: "base", "mid", or "top"

        Returns:
            Depth in cm, or None if not available for this level
        """
        base = scraped_data.base_depth_cm
        summit = scraped_data.summit_depth_cm

        if elevation_level == "base":
            return base
        elif elevation_level == "top":
            # Prefer summit depth, fall back to base if summit not available
            return summit if summit is not None else base
        else:  # mid
            # Average of base and summit if both available
            if base is not None and summit is not None:
                return (base + summit) / 2.0
            return summit if summit is not None else base

    def is_resort_supported(self, resort_id: str) -> bool:
        """Check if a resort is supported by this scraper."""
        return RESORT_URL_MAPPING.get(resort_id) is not None

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Safely convert a value to float, returning None for invalid/null/negative."""
        if value is None:
            return None
        try:
            v = float(value)
            return v if v >= 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _cm_to_inches(value: Any) -> float | None:
        """Convert a centimeter value to inches, returning None for invalid/null."""
        if value is None:
            return None
        try:
            cm = float(value)
            if cm < 0:
                return None
            return round(cm * _CM_TO_INCHES, 2)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """Safely convert a value to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
