#!/usr/bin/env python3
"""
Resort Data Enrichment Script

Enriches resorts.json with:
1. Pass affiliations (Epic, Ikon, Mountain Collective, Indy Pass)
2. Resort labels (family_friendly, expert_terrain, large_resort, ski_in_out)
3. Web-scraped data (trail %, snowmaking, ticket prices) from skiresort.info
4. Annual snowfall estimates

Usage:
    python enrich_resorts.py                              # Enrich all, only fill missing
    python enrich_resorts.py --input data/resorts.json    # Custom input
    python enrich_resorts.py --only-missing               # Only fill null/missing fields
    python enrich_resorts.py --skip-scrape                # Only apply static data (passes, labels)
    python enrich_resorts.py --workers 20                 # Parallel scraping workers
"""

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Currency conversion rates to USD
USD_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "CHF": 1.12,
    "CAD": 0.74,
    "NOK": 0.095,
    "SEK": 0.096,
    "JPY": 0.0067,
    "AUD": 0.65,
    "NZD": 0.61,
    "CLP": 0.0011,
    "ARS": 0.0011,
    "GBP": 1.27,
    "PLN": 0.25,
    "CZK": 0.043,
    "RON": 0.22,
    "BGN": 0.55,
    "KRW": 0.00075,
    "CNY": 0.14,
    "INR": 0.012,
}

COUNTRY_CURRENCY = {
    "US": "USD",
    "CA": "CAD",
    "FR": "EUR",
    "CH": "CHF",
    "AT": "EUR",
    "IT": "EUR",
    "DE": "EUR",
    "SI": "EUR",
    "ES": "EUR",
    "AD": "EUR",
    "NO": "NOK",
    "SE": "SEK",
    "FI": "EUR",
    "PL": "PLN",
    "CZ": "CZK",
    "SK": "EUR",
    "RO": "RON",
    "BG": "BGN",
    "JP": "JPY",
    "KR": "KRW",
    "CN": "CNY",
    "IN": "INR",
    "AU": "AUD",
    "NZ": "NZD",
    "CL": "CLP",
    "AR": "ARS",
}

# ============================================================
# PASS AFFILIATION LOOKUP TABLES (2024-25 season)
# ============================================================

EPIC_PASS_RESORTS = {
    # Unlimited access
    "vail": "Unlimited",
    "beaver-creek": "Unlimited",
    "breckenridge": "Unlimited",
    "keystone": "Unlimited",
    "crested-butte": "Unlimited",
    "park-city": "Unlimited",
    "whistler-blackcomb": "Unlimited",
    "stowe": "Unlimited",
    "okemo": "Unlimited",
    "mount-sunapee": "Unlimited",
    "stevens-pass": "Unlimited",
    "heavenly": "Unlimited",
    "northstar": "Unlimited",
    "kirkwood": "Unlimited",
    "afton-alps": "Unlimited",
    "mt-brighton": "Unlimited",
    "wilmot-mountain": "Unlimited",
    "attitash": "Unlimited",
    "wildcat-mountain": "Unlimited",
    "crotched-mountain": "Unlimited",
    "mount-snow": "Unlimited",
    "hunter-mountain": "Unlimited",
    "jack-frost": "Unlimited",
    "big-boulder": "Unlimited",
    "liberty-mountain": "Unlimited",
    "roundtop-mountain": "Unlimited",
    "whitetail-resort": "Unlimited",
    "seven-springs": "Unlimited",
    "hidden-valley": "Unlimited",
    "laurel-mountain": "Unlimited",
    "alpine-valley": "Unlimited",
    "boston-mills": "Unlimited",
    "brandywine": "Unlimited",
    "mad-river-mountain": "Unlimited",
    "snow-creek": "Unlimited",
    "paoli-peaks": "Unlimited",
    # Limited days
    "telluride": "7 days",
    "sun-valley": "7 days",
    "snowbasin": "7 days",
    "hakuba-valley": "5 days",
    "rusutsu": "5 days",
    "niseko-united": "5 days",
    "perisher": "5 days",
    "falls-creek": "5 days",
    "hotham": "5 days",
    "fernie": "5 days",
    "kicking-horse": "5 days",
    "kimberley": "5 days",
    "nakiska": "5 days",
    "mont-sainte-anne": "5 days",
    "stoneham": "5 days",
    "mont-tremblant": "5 days",
    "les-3-vallees": "5 days",
    "paradiski": "5 days",
    "tignes": "5 days",
    "val-disere": "5 days",
    "4-vallees": "5 days",
    "verbier": "5 days",
    "skirama-dolomiti": "5 days",
    "dolomiti-superski": "5 days",
    "skicircus-saalbach": "5 days",
    "arlberg": "5 days",
    "st-anton": "5 days",
    "lech-zuers": "5 days",
    "andermatt-sedrun": "5 days",
    "zermatt": "5 days",
    "cervinia": "5 days",
    "courmayeur": "5 days",
    "big-white": "7 days",
    "silver-star": "7 days",
    "revelstoke": "7 days",
    "sun-peaks": "7 days",
    "panorama": "7 days",
}

IKON_PASS_RESORTS = {
    # Unlimited access
    "aspen-snowmass": "Unlimited",
    "aspen-mountain": "Unlimited",
    "aspen-highlands": "Unlimited",
    "snowmass": "Unlimited",
    "buttermilk": "Unlimited",
    "steamboat": "Unlimited",
    "winter-park": "Unlimited",
    "copper-mountain": "Unlimited",
    "eldora": "Unlimited",
    "arapahoe-basin": "Unlimited",
    "mammoth-mountain": "Unlimited",
    "june-mountain": "Unlimited",
    "big-bear": "Unlimited",
    "brighton": "Unlimited",
    "solitude": "Unlimited",
    "deer-valley": "Unlimited",
    "alta": "Unlimited",
    "snowbird": "Unlimited",
    "jackson-hole": "Unlimited",
    "big-sky": "Unlimited",
    "crystal-mountain": "Unlimited",
    "boyne-highlands": "Unlimited",
    "boyne-mountain": "Unlimited",
    "the-summit-at-snoqualmie": "Unlimited",
    "loon-mountain": "Unlimited",
    "sunday-river": "Unlimited",
    "sugarloaf": "Unlimited",
    "tremblant": "Unlimited",
    "mont-tremblant": "Unlimited",
    "blue-mountain": "Unlimited",
    "stratton": "Unlimited",
    "sugarbush": "Unlimited",
    "killington": "Unlimited",
    "pico-mountain": "Unlimited",
    "windham-mountain": "Unlimited",
    # Limited days
    "chamonix": "7 days",
    "lake-louise": "7 days",
    "sunshine-village": "7 days",
    "banff-sunshine": "7 days",
    "revelstoke": "5 days",
    "cypress-mountain": "5 days",
    "red-mountain": "5 days",
    "panorama": "5 days",
    "niseko-united": "5 days",
    "thredbo": "5 days",
    "coronet-peak": "5 days",
    "the-remarkables": "5 days",
    "mt-hutt": "5 days",
    "zermatt": "7 days",
    "st-anton": "5 days",
    "kitzbuhel": "5 days",
    "lech-zuers": "5 days",
    "dolomiti-superski": "5 days",
    "val-gardena": "5 days",
    "alta-badia": "5 days",
    "cortina-dampezzo": "5 days",
    "val-di-fassa": "5 days",
    "grandvalira": "7 days",
    "jay-peak": "5 days",
    "grand-targhee": "5 days",
    "taos": "7 days",
}

MOUNTAIN_COLLECTIVE_RESORTS = {
    "aspen-snowmass": "2 days",
    "alta": "2 days",
    "banff-sunshine": "2 days",
    "lake-louise": "2 days",
    "big-sky": "2 days",
    "coronet-peak": "2 days",
    "the-remarkables": "2 days",
    "jackson-hole": "2 days",
    "mammoth-mountain": "2 days",
    "panorama": "2 days",
    "revelstoke": "2 days",
    "snowbird": "2 days",
    "sun-valley": "2 days",
    "sugarbush": "2 days",
    "taos": "2 days",
    "thredbo": "2 days",
    "palisades-tahoe": "2 days",
    "niseko-united": "2 days",
    "chamonix": "2 days",
    "zermatt": "2 days",
}

INDY_PASS_RESORTS = {
    # This is a large list of ~200 smaller/independent resorts
    # Including key ones - expand as needed
    "red-mountain": "2 days",
    "apex-mountain": "2 days",
    "castle-mountain": "2 days",
    "manning-park": "2 days",
    "sasquatch-mountain": "2 days",
    "red-lodge": "2 days",
    "brundage": "2 days",
    "bogus-basin": "2 days",
    "monarch-mountain": "2 days",
    "powderhorn": "2 days",
    "ski-cooper": "2 days",
    "sunlight": "2 days",
    "magic-mountain": "2 days",
    "bolton-valley": "2 days",
    "cannon-mountain": "2 days",
    "black-mountain": "2 days",
    "suicide-six": "2 days",
    "berkshire-east": "2 days",
    "catamount": "2 days",
    "powder-mountain": "2 days",
    "brian-head": "2 days",
    "mission-ridge": "2 days",
    "mt-baker": "2 days",
    "hurricane-ridge": "2 days",
    "mt-hood-meadows": "2 days",
    "mt-bachelor": "2 days",
    "timberline-lodge": "2 days",
    "schweitzer": "2 days",
    "lookout-pass": "2 days",
    "lost-trail": "2 days",
    "discovery": "2 days",
    "bridger-bowl": "2 days",
    "showdown": "2 days",
    "terry-peak": "2 days",
    "searchmont": "2 days",
    "mount-pakenham": "2 days",
    "nozawa-onsen": "2 days",
    "myoko-kogen": "2 days",
    "madarao": "2 days",
    "shiga-kogen": "2 days",
    "lotte-arai": "2 days",
}

# ============================================================
# SKI-IN/SKI-OUT KNOWN RESORTS
# ============================================================

SKI_IN_OUT_RESORTS = {
    "whistler-blackcomb",
    "big-white",
    "silver-star",
    "sun-peaks",
    "lake-louise",
    "banff-sunshine",
    "fernie",
    "panorama",
    "vail",
    "breckenridge",
    "beaver-creek",
    "keystone",
    "steamboat",
    "aspen-snowmass",
    "snowmass",
    "deer-valley",
    "park-city",
    "snowbird",
    "alta",
    "solitude",
    "brighton",
    "big-sky",
    "jackson-hole",
    "stowe",
    "killington",
    "stratton",
    "okemo",
    "sugarbush",
    "mont-tremblant",
    "tremblant",
    "chamonix",
    "val-disere",
    "tignes",
    "courchevel",
    "meribel",
    "les-arcs",
    "la-plagne",
    "les-deux-alpes",
    "alpe-dhuez",
    "zermatt",
    "verbier",
    "st-moritz",
    "davos",
    "laax",
    "st-anton",
    "lech-zuers",
    "kitzbuhel",
    "ischgl",
    "solden",
    "cervinia",
    "courmayeur",
    "madonna-di-campiglio",
    "cortina-dampezzo",
    "val-gardena",
    "niseko-united",
    "rusutsu",
    "furano",
}


class ResortEnricher:
    """Enriches resort data from multiple sources."""

    BASE_URL = "https://www.skiresort.info"
    USER_AGENT = "Mozilla/5.0 (compatible; PowderChaserBot/1.0)"
    REQUEST_DELAY = 1.5

    def __init__(
        self, workers: int = 10, only_missing: bool = True, skip_scrape: bool = False
    ):
        self.workers = workers
        self.only_missing = only_missing
        self.skip_scrape = skip_scrape
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        self._last_request_time = 0
        self._lock = Lock()
        self._stats = {"enriched": 0, "scraped": 0, "errors": 0, "skipped": 0}

    def _rate_limit(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.REQUEST_DELAY:
                time.sleep(self.REQUEST_DELAY - elapsed)
            self._last_request_time = time.time()

    def _get_soup(self, url: str) -> BeautifulSoup | None:
        self._rate_limit()
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                if attempt < 2:
                    time.sleep(2**attempt)
                else:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    return None
        return None

    def _set_if_missing(self, resort: dict, key: str, value):
        """Set a field only if it's missing/None and value is not None."""
        if value is None:
            return
        if self.only_missing and resort.get(key) is not None:
            return
        resort[key] = value

    def enrich_passes(self, resort: dict) -> None:
        """Apply pass affiliation lookup."""
        rid = resort.get("resort_id", "")

        self._set_if_missing(resort, "epic_pass", EPIC_PASS_RESORTS.get(rid))
        self._set_if_missing(resort, "ikon_pass", IKON_PASS_RESORTS.get(rid))
        self._set_if_missing(
            resort, "mountain_collective", MOUNTAIN_COLLECTIVE_RESORTS.get(rid)
        )
        self._set_if_missing(resort, "indy_pass", INDY_PASS_RESORTS.get(rid))

    def enrich_labels(self, resort: dict) -> None:
        """Apply rule-based label classification."""
        rid = resort.get("resort_id", "")
        green = resort.get("green_runs_pct") or 0
        black = resort.get("black_runs_pct") or 0
        double_black = resort.get("double_black_runs_pct") or 0

        base_m = resort.get("elevation_base_m", 0) or 0
        top_m = resort.get("elevation_top_m", 0) or 0
        vertical = top_m - base_m

        # Family friendly: green >= 25%
        if green > 0:
            self._set_if_missing(resort, "family_friendly", green >= 25)

        # Expert terrain: (black + double_black) >= 35%
        if black > 0 or double_black > 0:
            self._set_if_missing(resort, "expert_terrain", (black + double_black) >= 35)

        # Large resort: vertical drop >= 1000m
        if vertical > 0:
            self._set_if_missing(resort, "large_resort", vertical >= 1000)

        # Ski-in/ski-out: hardcoded set
        if rid in SKI_IN_OUT_RESORTS:
            self._set_if_missing(resort, "ski_in_out", True)

    def _find_skiresort_url(self, resort: dict) -> str | None:
        """Find matching skiresort.info URL for a resort."""
        rid = resort.get("resort_id", "")
        name = resort.get("name", "")

        # Try direct URL pattern
        url = f"{self.BASE_URL}/ski-resort/{rid}/"
        try:
            self._rate_limit()
            resp = self.session.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return resp.url if resp.url != url else url
        except Exception:
            pass

        # Try search
        search_url = f"{self.BASE_URL}/ski-resort-search/{name.replace(' ', '+')}"
        soup = self._get_soup(search_url)
        if soup:
            link = soup.select_one("a[href*='/ski-resort/']")
            if link:
                from urllib.parse import urljoin

                return urljoin(self.BASE_URL, link.get("href", ""))

        return None

    def scrape_resort_data(self, resort: dict) -> dict:
        """Scrape additional data from skiresort.info."""
        result = {}

        url = self._find_skiresort_url(resort)
        if not url:
            return result

        soup = self._get_soup(url)
        if not soup:
            return result

        page_text = soup.get_text().lower()

        # --- Trail percentages ---
        slope_data = {}
        for label_pattern, key in [
            (r"(?:easy|green|beginner)", "green"),
            (r"(?:intermediate|blue|medium)", "blue"),
            (r"(?:difficult|black|advanced|expert)", "black"),
            (r"(?:freeride|extreme|double.?black)", "double_black"),
        ]:
            for elem in soup.find_all(string=re.compile(label_pattern, re.I)):
                parent = elem.parent
                if parent:
                    nearby_text = parent.get_text()
                    for sibling in [parent.next_sibling, parent.previous_sibling]:
                        if sibling:
                            nearby_text += " " + (
                                sibling.get_text()
                                if hasattr(sibling, "get_text")
                                else str(sibling)
                            )
                    km_match = re.search(r"(\d+(?:\.\d+)?)\s*km", nearby_text)
                    if km_match and key not in slope_data:
                        slope_data[key] = float(km_match.group(1))
                        break

        total_km = sum(slope_data.values())
        if total_km > 0:
            if "green" in slope_data:
                result["green_runs_pct"] = round(slope_data["green"] / total_km * 100)
            if "blue" in slope_data:
                result["blue_runs_pct"] = round(slope_data["blue"] / total_km * 100)
            if "black" in slope_data:
                result["black_runs_pct"] = round(slope_data["black"] / total_km * 100)
            if "double_black" in slope_data:
                result["double_black_runs_pct"] = round(
                    slope_data["double_black"] / total_km * 100
                )

        # --- Snowmaking ---
        if any(
            term in page_text
            for term in [
                "snow-making",
                "snowmaking",
                "snow cannon",
                "snow gun",
                "artificial snow",
            ]
        ):
            result["has_snowmaking"] = True

        # --- Ticket price range ---
        country = resort.get("country", "US")
        currency = COUNTRY_CURRENCY.get(country, "USD")
        rate = USD_RATES.get(currency, 1.0)
        currencies_pattern = r"(?:USD|EUR|CHF|CAD|NOK|SEK|AUD|NZD|JPY|GBP|PLN|CZK)"

        # Collect all price values from ticket-related sections
        usd_prices = []
        ticket_section = ""
        for kw in ["ticket", "lift pass", "day pass", "ski pass", "adult"]:
            idx = page_text.lower().find(kw)
            if idx >= 0:
                ticket_section += page_text[max(0, idx - 200) : idx + 500] + " "

        if ticket_section:
            section_prices = re.findall(
                r"[\$\u20ac\u00a3\u00a5]?\s*(\d+(?:[.,]\d+)?)", ticket_section
            )
            for p in section_prices:
                try:
                    val = float(str(p).replace(",", "."))
                    usd_val = round(val * rate)
                    if 10 <= usd_val <= 500:
                        usd_prices.append(usd_val)
                except (ValueError, TypeError):
                    continue

        if usd_prices:
            min_price = min(usd_prices)
            max_price = max(usd_prices)
            # If range is too wide (>3x), likely noise — use median
            if max_price > min_price * 3:
                median = sorted(usd_prices)[len(usd_prices) // 2]
                min_price = median
                max_price = median
            result["day_ticket_price_min_usd"] = min_price
            result["day_ticket_price_max_usd"] = max_price

        # --- Annual snowfall ---
        snow_match = re.search(
            r"(\d+)\s*cm\s*(?:annual|average|yearly|season)", page_text
        )
        if not snow_match:
            snow_match = re.search(
                r"(?:annual|average|yearly|season)\s*(?:snowfall|snow)\s*:?\s*(\d+)\s*cm",
                page_text,
            )
        if snow_match:
            result["annual_snowfall_cm"] = int(snow_match.group(1))

        # --- Trail map URL ---
        # The trail map is on a separate /trail-map/ subpage of the resort
        trail_map_url = self._scrape_trail_map(url)
        if trail_map_url:
            result["trail_map_url"] = trail_map_url

        # --- Webcam URL ---
        # skiresort.info has webcam pages at /ski-resort/{slug}/webcams/
        webcam_url = url.rstrip("/") + "/webcams/"
        try:
            self._rate_limit()
            resp = self.session.head(webcam_url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                result["webcam_url"] = webcam_url
        except Exception:
            pass

        return result

    def _scrape_trail_map(self, resort_url: str) -> str | None:
        """Scrape trail map image URL from skiresort.info trail-map subpage."""
        trail_map_page = resort_url.rstrip("/") + "/trail-map/"
        try:
            self._rate_limit()
            resp = self.session.get(trail_map_page, timeout=15, allow_redirects=False)
            if resp.status_code in (301, 302):
                location = resp.headers.get("Location", "")
                if location.rstrip("/") == "https://www.skiresort.info":
                    return None
                resp = self.session.get(location, timeout=15)
            if resp.status_code != 200:
                return None
            # Find trailmap IDs in the page JavaScript
            trailmap_ids = re.findall(r"init_trailmap_(\d+)", resp.text)
            if not trailmap_ids:
                return None
            primary_id = trailmap_ids[0]
            # Use level 8 for a usable thumbnail (~200px for typical maps)
            # Level 0 = 1x1 pixel (useless)
            return (
                f"https://www.skiresort.info/uploads/tx_mgskiresort/"
                f"trailmapsV2/trailmap_{primary_id}_files/8/0_0.jpg"
            )
        except Exception:
            return None

    def enrich_resort(self, resort: dict) -> dict:
        """Enrich a single resort with all available data."""
        resort = deepcopy(resort)
        rid = resort.get("resort_id", "")

        # 1. Static data: pass affiliations
        self.enrich_passes(resort)

        # 2. Web-scraped data
        if not self.skip_scrape:
            needs_scrape = any(
                resort.get(f) is None
                for f in [
                    "green_runs_pct",
                    "blue_runs_pct",
                    "black_runs_pct",
                    "has_snowmaking",
                    "day_ticket_price_min_usd",
                    "day_ticket_price_max_usd",
                    "annual_snowfall_cm",
                    "trail_map_url",
                    "webcam_url",
                ]
            )
            if needs_scrape:
                try:
                    scraped = self.scrape_resort_data(resort)
                    for key, value in scraped.items():
                        self._set_if_missing(resort, key, value)
                    if scraped:
                        self._stats["scraped"] += 1
                except Exception as e:
                    logger.warning(f"Scrape failed for {rid}: {e}")
                    self._stats["errors"] += 1
            else:
                self._stats["skipped"] += 1

        # 3. Rule-based labels (after trail % may have been filled)
        self.enrich_labels(resort)

        self._stats["enriched"] += 1
        return resort

    def enrich_all(self, resorts: list[dict]) -> list[dict]:
        """Enrich all resorts, optionally in parallel."""
        total = len(resorts)
        logger.info(
            f"Enriching {total} resorts (workers={self.workers}, only_missing={self.only_missing}, skip_scrape={self.skip_scrape})"
        )

        if self.skip_scrape or self.workers <= 1:
            # Sequential for static-only or single worker
            enriched = []
            for i, resort in enumerate(resorts):
                enriched.append(self.enrich_resort(resort))
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i + 1}/{total}")
            return enriched

        # Parallel scraping
        enriched = [None] * total
        completed = 0

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_idx = {
                executor.submit(self.enrich_resort, resort): i
                for i, resort in enumerate(resorts)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                completed += 1
                try:
                    enriched[idx] = future.result()
                    if completed % 25 == 0:
                        logger.info(f"Progress: {completed}/{total}")
                except Exception as e:
                    logger.error(f"Failed to enrich resort at index {idx}: {e}")
                    enriched[idx] = resorts[idx]  # Keep original on failure

        return enriched

    def validate(self, resorts: list[dict]) -> list[str]:
        """Validate enriched data quality."""
        warnings = []
        for resort in resorts:
            rid = resort.get("resort_id", "unknown")
            green = resort.get("green_runs_pct")
            blue = resort.get("blue_runs_pct")
            black = resort.get("black_runs_pct")
            double_black = resort.get("double_black_runs_pct", 0) or 0

            if green is not None and blue is not None and black is not None:
                total = green + blue + black + double_black
                if total < 90 or total > 110:
                    warnings.append(f"{rid}: trail % total = {total} (expected ~100)")

            price_min = resort.get("day_ticket_price_min_usd")
            price_max = resort.get("day_ticket_price_max_usd")
            for label, price in [("min", price_min), ("max", price_max)]:
                if price is not None and (price < 10 or price > 500):
                    warnings.append(
                        f"{rid}: ticket price {label} ${price} seems unreasonable"
                    )
            if (
                price_min is not None
                and price_max is not None
                and price_min > price_max
            ):
                warnings.append(
                    f"{rid}: ticket price min (${price_min}) > max (${price_max})"
                )

            base = resort.get("elevation_base_m", 0) or 0
            top = resort.get("elevation_top_m", 0) or 0
            if top > 0 and base >= top:
                warnings.append(f"{rid}: base ({base}m) >= top ({top}m)")

        return warnings


def main():
    parser = argparse.ArgumentParser(description="Enrich resort data")
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "resorts.json",
        help="Input resorts.json path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output path (default: overwrite input)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        default=True,
        help="Only fill null/missing fields (default)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing values"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip web scraping, only apply static data",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=10, help="Number of parallel workers"
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_path = args.output or args.input

    # Load data
    logger.info(f"Loading resorts from {args.input}")
    with open(args.input) as f:
        data = json.load(f)

    resorts = data.get("resorts", [])
    logger.info(f"Loaded {len(resorts)} resorts")

    # Enrich
    enricher = ResortEnricher(
        workers=args.workers,
        only_missing=not args.overwrite,
        skip_scrape=args.skip_scrape,
    )
    enriched_resorts = enricher.enrich_all(resorts)

    # Validate
    warnings = enricher.validate(enriched_resorts)
    if warnings:
        logger.warning(f"Validation warnings ({len(warnings)}):")
        for w in warnings[:20]:
            logger.warning(f"  {w}")

    # Save
    data["resorts"] = enriched_resorts
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Print stats
    stats = enricher._stats
    print(f"\n{'=' * 50}")
    print("ENRICHMENT RESULTS")
    print(f"{'=' * 50}")
    print(f"Total resorts:  {len(enriched_resorts)}")
    print(f"Enriched:       {stats['enriched']}")
    print(f"Scraped:        {stats['scraped']}")
    print(f"Skipped:        {stats['skipped']}")
    print(f"Errors:         {stats['errors']}")
    print(f"Warnings:       {len(warnings)}")
    print(f"Output:         {output_path}")

    # Coverage report
    fields = [
        "green_runs_pct",
        "blue_runs_pct",
        "black_runs_pct",
        "epic_pass",
        "ikon_pass",
        "mountain_collective",
        "indy_pass",
        "has_snowmaking",
        "day_ticket_price_min_usd",
        "day_ticket_price_max_usd",
        "annual_snowfall_cm",
        "family_friendly",
        "expert_terrain",
        "large_resort",
        "ski_in_out",
    ]
    print("\nField coverage:")
    for field in fields:
        count = sum(1 for r in enriched_resorts if r.get(field) is not None)
        pct = round(count / len(enriched_resorts) * 100, 1) if enriched_resorts else 0
        print(f"  {field:30s}: {count:4d}/{len(enriched_resorts)} ({pct}%)")

    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
