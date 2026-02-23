#!/usr/bin/env python3
"""
Enrich resorts.json with annual snowfall data (annual_snowfall_cm).

Two-phase approach:
  Phase 1: Scrape skiresort.info resort detail pages for snow reliability data
  Phase 2: For resorts still missing data, use Open-Meteo Historical Weather API
           to compute average annual snowfall from the past 5 winter seasons

Usage:
    python3 backend/scripts/enrich_annual_snowfall.py
    python3 backend/scripts/enrich_annual_snowfall.py --dry-run
    python3 backend/scripts/enrich_annual_snowfall.py --limit 50
    python3 backend/scripts/enrich_annual_snowfall.py --skip-scrape
    python3 backend/scripts/enrich_annual_snowfall.py --only-meteo
"""

import argparse
import asyncio
import json
import math
import re
import time
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

# Configuration
SKIRESORT_MAX_CONCURRENT = 5
SKIRESORT_REQUEST_DELAY = 0.2  # ~5 req/sec
METEO_MAX_CONCURRENT = 3
METEO_REQUEST_DELAY = 0.5  # ~2 req/sec (avoid 429s)
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.skiresort.info"
RESORTS_JSON = Path(__file__).parent.parent / "data" / "resorts.json"

# Open-Meteo Historical API
# Query 5 full winter seasons (Oct-Apr for Northern Hemisphere, May-Oct for Southern)
# Northern: 2020-10 to 2025-04, Southern: 2020-05 to 2025-10
METEO_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Country listing pages on skiresort.info (reused from enrich_run_percentages.py)
COUNTRY_URLS = {
    "US": "/ski-resorts/usa",
    "CA": "/ski-resorts/canada",
    "AT": "/ski-resorts/austria",
    "CH": "/ski-resorts/switzerland",
    "FR": "/ski-resorts/france",
    "IT": "/ski-resorts/italy",
    "DE": "/ski-resorts/germany",
    "SI": "/ski-resorts/slovenia",
    "NO": "/ski-resorts/norway",
    "SE": "/ski-resorts/sweden",
    "FI": "/ski-resorts/finland",
    "JP": "/ski-resorts/japan",
    "AU": "/ski-resorts/australia",
    "NZ": "/ski-resorts/new-zealand",
    "CL": "/ski-resorts/chile",
    "AR": "/ski-resorts/argentina",
    "ES": "/ski-resorts/spain",
    "AD": "/ski-resorts/andorra",
    "PL": "/ski-resorts/poland",
    "CZ": "/ski-resorts/czech-republic",
    "SK": "/ski-resorts/slovakia",
    "RO": "/ski-resorts/romania",
    "BG": "/ski-resorts/bulgaria",
    "KR": "/ski-resorts/south-korea",
    "CN": "/ski-resorts/china",
    "IN": "/ski-resorts/india",
}

SKIP_PATTERNS = [
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

# Southern hemisphere countries (different winter season)
SOUTHERN_HEMISPHERE = {"AU", "NZ", "CL", "AR"}


def needs_enrichment(resort: dict) -> bool:
    """Check if a resort is missing annual snowfall data."""
    return resort.get("annual_snowfall_cm") is None


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"[''`]", "", slug)
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "à": "a",
        "á": "a",
        "â": "a",
        "ã": "a",
        "å": "aa",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ñ": "n",
        "ç": "c",
        "æ": "ae",
        "ø": "oe",
        "ð": "d",
        "þ": "th",
        "ý": "y",
    }
    for char, repl in replacements.items():
        slug = slug.replace(char, repl)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


def clean_name_for_matching(name: str) -> str:
    """Normalize a name for fuzzy matching."""
    name = name.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return slugify(name)


def find_slug_in_index(resort_name: str, slug_index: dict) -> str | None:
    """Find the best matching slug in the index for a resort name."""
    clean = clean_name_for_matching(resort_name)

    for suffix in [
        "-ski-resort",
        "-resort",
        "-mountain-resort",
        "-ski-area",
        "-mountain",
    ]:
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]

    if clean in slug_index:
        return slug_index[clean]

    words = [w for w in clean.split("-") if len(w) > 2]
    if not words:
        return None

    best_score = 0
    best_slug = None

    for idx_name, slug in slug_index.items():
        idx_words = set(idx_name.split("-"))
        matched = sum(1 for w in words if w in idx_words)
        if matched == 0:
            if len(words) == 1 and words[0] in idx_name:
                score = 0.7
            elif len(words) >= 2 and all(w in idx_name for w in words[:2]):
                score = 0.8
            else:
                continue
        else:
            score = matched / len(words)

        common = {"ski", "resort", "mountain", "big", "new", "les", "mount"}
        if matched > 0 and all(w in common for w in words if w in idx_words):
            score *= 0.3

        if score > best_score:
            best_score = score
            best_slug = slug

    return best_slug if best_score >= 0.7 else None


class RateLimiter:
    """Token bucket rate limiter for async requests."""

    def __init__(self, rate: float):
        self._rate = rate
        self._last_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._rate - (now - self._last_time)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_time = time.monotonic()


# ---------------------------------------------------------------------------
# Phase 1: skiresort.info scraping
# ---------------------------------------------------------------------------


def parse_annual_snowfall(html: str) -> int | None:
    """Parse annual snowfall data from a skiresort.info resort page.

    Looks for snow reliability data, average snowfall, or snow depth info
    that can be used to estimate annual snowfall in cm.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: Look for explicit annual/average snowfall mentions
    # Pattern: "Average snowfall: XXX cm" or "Annual snowfall: XXX cm/inches"
    page_text = soup.get_text(" ", strip=True)

    # Try various patterns for snowfall amounts
    snowfall_patterns = [
        # "average snowfall ... XXX cm"
        r"(?:average|annual|yearly)\s+snowfall[:\s]+.*?(\d[\d,.]+)\s*cm",
        # "XXX cm average snowfall"
        r"(\d[\d,.]+)\s*cm\s+(?:average|annual|yearly)\s+snowfall",
        # "snowfall: XXX cm"
        r"snowfall[:\s]+(\d[\d,.]+)\s*cm",
        # "XXX inches of snow per year" (convert to cm)
        r"(\d[\d,.]+)\s*(?:inches|in\.?)\s+(?:of\s+)?snow(?:fall)?\s+(?:per|a)\s+year",
        # "average annual snowfall of XXX inches"
        r"average\s+annual\s+snowfall\s+(?:of\s+)?(\d[\d,.]+)\s*(?:inches|in\.?)",
        # "XXXcm of snowfall"
        r"(\d[\d,.]+)\s*cm\s+of\s+snowfall",
    ]

    for pattern in snowfall_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(",", "")
            try:
                value = float(value_str)
            except ValueError:
                continue

            # If the pattern matched inches, convert to cm
            if "inch" in pattern or "in\\." in pattern:
                value = value * 2.54

            # Sanity check: annual snowfall should be between 50cm and 3000cm
            if 50 <= value <= 3000:
                return round(value)

    # Strategy 2: Look for snow depth data in structured elements
    # Some pages show "Snow reliability" with average snow depths
    for elem in soup.find_all(["div", "td", "span", "p"]):
        text = elem.get_text(strip=True)
        # "Snow reliability 4/5 stars" type data doesn't give us a number
        # but "XXX cm natural snow" might
        match = re.search(
            r"(\d[\d,.]+)\s*cm\s+(?:natural|fresh|new)\s+snow", text, re.IGNORECASE
        )
        if match:
            value = float(match.group(1).replace(",", ""))
            if 50 <= value <= 3000:
                return round(value)

    # Strategy 3: Look in meta tags or structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            if isinstance(ld, dict):
                # Check for snowfall in structured data
                snow = ld.get("snowfall") or ld.get("annualSnowfall")
                if snow:
                    value = float(str(snow).replace(",", ""))
                    if 50 <= value <= 3000:
                        return round(value)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None


def is_resort_page(html: str) -> bool:
    """Check if the HTML is a valid resort detail page."""
    if len(html) < 1000:
        return False
    if "run-table" in html or "resort-logo" in html or "selBeginner" in html:
        return True
    soup = BeautifulSoup(html[:5000], "html.parser")
    title = soup.find("title")
    if title:
        title_text = title.get_text(strip=True).lower()
        if "ski resort " in title_text:
            return True
    return False


def build_candidate_urls(resort: dict, slug_index: dict | None = None) -> list[str]:
    """Build a list of candidate skiresort.info URLs for a resort."""
    seen = set()
    urls = []

    def add(slug: str):
        url = f"{BASE_URL}/ski-resort/{slug}/"
        if url not in seen:
            seen.add(url)
            urls.append(url)

    resort_id = resort["resort_id"]
    name = resort.get("name", "")

    add(resort_id)

    if name:
        name_slug = slugify(name)
        add(name_slug)

        for suffix in [
            " ski resort",
            " resort",
            " mountain resort",
            " ski area",
            " mountain",
            " ski",
            " ski center",
            " ski centre",
        ]:
            if name.lower().endswith(suffix):
                short = slugify(name[: -len(suffix)])
                if short:
                    add(short)

        if " – " in name or " - " in name:
            parts = re.split(r"\s*[–-]\s*", name)
            for part in parts:
                part_slug = slugify(part.strip())
                if part_slug and len(part_slug) > 2:
                    add(part_slug)

        words = name.split()
        if len(words) > 1:
            first = slugify(words[0])
            if first and len(first) > 2 and first != name_slug:
                add(first)

    if slug_index and name:
        index_slug = find_slug_in_index(name, slug_index)
        if index_slug:
            add(index_slug)

    return urls


async def fetch_page_raw(
    session: aiohttp.ClientSession,
    url: str,
    rate_limiter: RateLimiter,
) -> str | None:
    """Fetch a page with rate limiting. Returns HTML or None."""
    await rate_limiter.acquire()

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=True,
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                elif resp.status == 404:
                    return None
                else:
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(1 + attempt)
        except (TimeoutError, aiohttp.ClientError):
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 + attempt)
    return None


async def build_slug_index(
    session: aiohttp.ClientSession,
    rate_limiter: RateLimiter,
    countries: set[str],
) -> dict[str, str]:
    """Build a mapping of cleaned resort names to skiresort.info slugs."""
    slug_index = {}
    relevant_countries = {c for c in countries if c in COUNTRY_URLS}
    print(f"  Building slug index for {len(relevant_countries)} countries...")

    for country in sorted(relevant_countries):
        path = COUNTRY_URLS[country]
        page = 1
        while page <= 20:
            url = f"{BASE_URL}{path}" + (f"/page/{page}" if page > 1 else "")
            html = await fetch_page_raw(session, url, rate_limiter)
            if html is None:
                break

            soup = BeautifulSoup(html, "html.parser")
            found = 0

            for link in soup.select('a[href*="/ski-resort/"]'):
                href = link.get("href", "")
                if any(p in href for p in SKIP_PATTERNS):
                    continue
                match = re.search(r"/ski-resort/([^/]+)/", href)
                if match:
                    slug = match.group(1)
                    name = link.get_text(strip=True)
                    if name and slug and len(name) > 2:
                        name = re.sub(
                            r"^ski resort\s+", "", name, flags=re.IGNORECASE
                        ).strip()
                        clean = clean_name_for_matching(name)
                        if clean and clean not in slug_index:
                            slug_index[clean] = slug
                            found += 1

            has_next = soup.select_one('.pagination .next, a[rel="next"]')
            if not has_next:
                break
            page += 1

    print(f"  Built index with {len(slug_index)} resort name-to-slug mappings")
    return slug_index


async def fetch_resort_page(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
) -> str | None:
    """Fetch a single URL, returning HTML if it's a valid resort page."""
    async with semaphore:
        await rate_limiter.acquire()

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    allow_redirects=True,
                ) as resp:
                    final_url = str(resp.url)
                    if (
                        final_url.rstrip("/") == BASE_URL
                        or "/ski-resort/" not in final_url
                    ):
                        return None
                    if resp.status == 200:
                        html = await resp.text()
                        return html if is_resort_page(html) else None
                    elif resp.status == 404:
                        return None
                    else:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(1 + attempt)
            except (TimeoutError, aiohttp.ClientError):
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1 + attempt)
                else:
                    return None
    return None


async def scrape_resort_snowfall(
    resort: dict,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
    slug_index: dict | None = None,
) -> int | None:
    """Try to scrape annual snowfall from skiresort.info for a single resort."""
    candidate_urls = build_candidate_urls(resort, slug_index)

    for url in candidate_urls:
        html = await fetch_resort_page(session, url, semaphore, rate_limiter)
        if html is None:
            continue

        snowfall = parse_annual_snowfall(html)
        if snowfall is not None:
            return snowfall

    return None


# ---------------------------------------------------------------------------
# Phase 2: Open-Meteo Historical Weather API
# ---------------------------------------------------------------------------


def get_winter_seasons(country: str) -> list[tuple[str, str]]:
    """Get date ranges for the last 5 winter seasons based on hemisphere.

    Northern hemisphere: Oct 1 - Apr 30 (main snow season)
    Southern hemisphere: May 1 - Oct 31 (main snow season)

    Returns list of (start_date, end_date) tuples as ISO date strings.
    """
    seasons = []

    if country in SOUTHERN_HEMISPHERE:
        # Southern hemisphere winters: May-October
        for year in range(2020, 2025):
            seasons.append((f"{year}-05-01", f"{year}-10-31"))
    else:
        # Northern hemisphere winters: October-April
        for start_year in range(2020, 2025):
            end_year = start_year + 1
            seasons.append((f"{start_year}-10-01", f"{end_year}-04-30"))

    return seasons


def compute_annual_snowfall(
    daily_data: dict, seasons: list[tuple[str, str]]
) -> int | None:
    """Compute average annual snowfall from Open-Meteo daily data.

    Args:
        daily_data: The "daily" section of the Open-Meteo response with
                    "time" and "snowfall_sum" arrays.
        seasons: List of (start_date, end_date) tuples for each season.

    Returns:
        Average annual snowfall in cm (rounded to nearest int), or None if
        insufficient data.
    """
    times = daily_data.get("time", [])
    snowfall_values = daily_data.get("snowfall_sum", [])

    if not times or not snowfall_values:
        return None

    # Build a date-to-snowfall lookup
    date_snowfall = {}
    for date_str, snow_val in zip(times, snowfall_values, strict=False):
        if snow_val is not None:
            date_snowfall[date_str] = snow_val

    season_totals = []
    for start_date, end_date in seasons:
        season_sum = 0.0
        day_count = 0
        # Iterate over dates in this season
        for date_str, snow_val in date_snowfall.items():
            if start_date <= date_str <= end_date:
                season_sum += snow_val
                day_count += 1

        # Only count seasons with at least 100 days of data (out of ~180-210)
        if day_count >= 100:
            season_totals.append(season_sum)

    if not season_totals:
        return None

    avg = sum(season_totals) / len(season_totals)

    # Sanity check: very low values might mean the location doesn't get snow
    # We still record it if > 0, but filter out implausible negatives
    if avg < 0:
        return None

    return round(avg)


async def fetch_meteo_snowfall(
    session: aiohttp.ClientSession,
    resort: dict,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
) -> int | None:
    """Fetch historical snowfall data from Open-Meteo and compute annual average.

    Uses the resort's mid-elevation coordinates. Queries the full 5-year period
    in a single request for efficiency.
    """
    lat = resort.get("latitude")
    lon = resort.get("longitude")

    if lat is None or lon is None:
        return None

    # Determine hemisphere and get full date range
    country = resort.get("country", "")
    seasons = get_winter_seasons(country)

    if not seasons:
        return None

    # Use the earliest start and latest end for a single API call
    start_date = seasons[0][0]
    end_date = seasons[-1][1]

    # Use mid-elevation if available for more representative snowfall
    elevation = (
        resort.get("elevation_mid_m")
        or resort.get("elevation_top_m")
        or resort.get("elevation_base_m")
    )

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "snowfall_sum",
        "timezone": "auto",
    }
    # Open-Meteo can use a custom elevation for temperature lapse rate adjustment
    if elevation:
        params["elevation"] = elevation

    async with semaphore:
        await rate_limiter.acquire()

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(
                    METEO_BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        daily = data.get("daily")
                        if daily:
                            return compute_annual_snowfall(daily, seasons)
                        return None
                    elif resp.status == 429:
                        # Rate limited, back off significantly
                        wait = 10 + attempt * 15
                        await asyncio.sleep(wait)
                    elif resp.status == 400:
                        # Bad request (e.g., invalid coordinates)
                        return None
                    else:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(1 + attempt)
            except (TimeoutError, aiohttp.ClientError):
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1 + attempt)

    return None


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def main_async(args):
    """Main async entry point."""
    print(f"Loading resorts from {RESORTS_JSON}...")
    with open(RESORTS_JSON) as f:
        data = json.load(f)

    resorts = data["resorts"]
    total_resorts = len(resorts)
    already_have = sum(1 for r in resorts if r.get("annual_snowfall_cm") is not None)
    print(f"Total resorts: {total_resorts}")
    print(f"Already have annual_snowfall_cm: {already_have}")

    # Identify resorts needing enrichment
    to_enrich = [(i, r) for i, r in enumerate(resorts) if needs_enrichment(r)]
    print(f"Resorts needing annual snowfall data: {len(to_enrich)}")

    if args.limit:
        to_enrich = to_enrich[: args.limit]
        print(f"Limited to first {args.limit} resorts")

    if not to_enrich:
        print("No resorts need enrichment. Done!")
        return

    # Tracking
    scraped_count = 0
    meteo_count = 0
    failed_count = 0
    failed_resorts = []
    start_time = time.time()

    # Phase 1: Try skiresort.info scraping
    still_need = list(to_enrich)

    if not args.only_meteo:
        print(f"\n{'=' * 60}")
        print("PHASE 1: Scraping skiresort.info for snowfall data")
        print(f"{'=' * 60}")

        skiresort_semaphore = asyncio.Semaphore(SKIRESORT_MAX_CONCURRENT)
        skiresort_limiter = RateLimiter(SKIRESORT_REQUEST_DELAY)
        connector = aiohttp.TCPConnector(
            limit=SKIRESORT_MAX_CONCURRENT + 5,
            limit_per_host=SKIRESORT_MAX_CONCURRENT,
        )
        headers = {"User-Agent": USER_AGENT}

        async with aiohttp.ClientSession(
            connector=connector, headers=headers
        ) as session:
            # Build slug index
            if not args.skip_index:
                countries_needed = {r["country"] for _, r in to_enrich}
                slug_index = await build_slug_index(
                    session, skiresort_limiter, countries_needed
                )
            else:
                slug_index = None
                print("  Skipping slug index build (--skip-index)")

            # Process in batches
            print(f"\n  Scraping {len(to_enrich)} resort pages...")
            batch_size = 50
            phase1_results = {}  # idx -> snowfall_cm

            for batch_start in range(0, len(to_enrich), batch_size):
                batch = to_enrich[batch_start : batch_start + batch_size]

                tasks = [
                    scrape_resort_snowfall(
                        resort,
                        session,
                        skiresort_semaphore,
                        skiresort_limiter,
                        slug_index,
                    )
                    for _, resort in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for (idx, _resort), result in zip(batch, results, strict=False):
                    if isinstance(result, Exception):
                        continue
                    if result is not None:
                        phase1_results[idx] = result
                        scraped_count += 1

                elapsed = time.time() - start_time
                total_done = min(batch_start + len(batch), len(to_enrich))
                print(
                    f"  [{total_done}/{len(to_enrich)}] "
                    f"Found: {scraped_count} ({elapsed:.0f}s elapsed)"
                )

            # Apply Phase 1 results
            if not args.dry_run:
                for idx, snowfall in phase1_results.items():
                    resorts[idx]["annual_snowfall_cm"] = snowfall

            # Filter out resorts that were enriched in Phase 1
            still_need = [(i, r) for i, r in to_enrich if i not in phase1_results]

        print(
            f"\n  Phase 1 results: {scraped_count} resorts enriched from skiresort.info"
        )
        print(f"  Remaining without data: {len(still_need)}")
    else:
        print("\n  Skipping Phase 1 (--only-meteo)")

    # Phase 2: Open-Meteo Historical Weather API
    if still_need:
        print(f"\n{'=' * 60}")
        print("PHASE 2: Computing from Open-Meteo Historical Weather API")
        print(f"{'=' * 60}")
        print(f"  Processing {len(still_need)} resorts...")

        meteo_semaphore = asyncio.Semaphore(METEO_MAX_CONCURRENT)
        meteo_limiter = RateLimiter(METEO_REQUEST_DELAY)
        connector = aiohttp.TCPConnector(limit=METEO_MAX_CONCURRENT + 5)

        async with aiohttp.ClientSession(connector=connector) as session:
            batch_size = 50
            phase2_start = time.time()

            for batch_start in range(0, len(still_need), batch_size):
                batch = still_need[batch_start : batch_start + batch_size]

                tasks = [
                    fetch_meteo_snowfall(
                        session, resort, meteo_semaphore, meteo_limiter
                    )
                    for _, resort in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for (idx, resort), result in zip(batch, results, strict=False):
                    if isinstance(result, Exception):
                        failed_count += 1
                        failed_resorts.append(resort["resort_id"])
                        continue
                    if result is not None and result > 0:
                        if not args.dry_run:
                            resorts[idx]["annual_snowfall_cm"] = result
                        meteo_count += 1
                    else:
                        failed_count += 1
                        failed_resorts.append(resort["resort_id"])

                elapsed = time.time() - phase2_start
                total_done = min(batch_start + len(batch), len(still_need))
                rate = total_done / elapsed if elapsed > 0 else 0
                remaining = (len(still_need) - total_done) / rate if rate > 0 else 0
                print(
                    f"  [{total_done}/{len(still_need)}] "
                    f"Found: {meteo_count}, Failed: {failed_count} "
                    f"({rate:.1f}/sec, ~{remaining:.0f}s left)"
                )

        print(f"\n  Phase 2 results: {meteo_count} resorts enriched from Open-Meteo")

    # Save results
    total_enriched = scraped_count + meteo_count
    if not args.dry_run and total_enriched > 0:
        print("\nSaving updated resorts.json...")
        with open(RESORTS_JSON, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved to {RESORTS_JSON}")
    elif args.dry_run:
        print("\nDry run - no changes saved.")

    # Print summary
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print("ENRICHMENT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total resorts:                {total_resorts}")
    print(f"Already had data:             {already_have}")
    print(f"Needed enrichment:            {len(to_enrich)}")
    print(f"Enriched from skiresort.info: {scraped_count}")
    print(f"Enriched from Open-Meteo:     {meteo_count}")
    print(f"Total enriched:               {total_enriched}")
    print(f"Failed (no data):             {failed_count}")
    print(
        f"Success rate:                 {total_enriched / len(to_enrich) * 100:.1f}%"
        if to_enrich
        else "N/A"
    )
    print(f"Time elapsed:                 {elapsed:.1f}s")
    print(f"{'=' * 60}")

    # Show data coverage
    if total_enriched > 0 and not args.dry_run:
        has_snowfall = sum(
            1 for r in resorts if r.get("annual_snowfall_cm") is not None
        )
        still_missing = sum(1 for r in resorts if needs_enrichment(r))
        print("\nData coverage after enrichment:")
        print(
            f"  annual_snowfall_cm: {has_snowfall}/{total_resorts} ({has_snowfall / total_resorts * 100:.1f}%)"
        )
        print(f"  Still missing:      {still_missing}/{total_resorts}")

    if failed_resorts:
        shown = failed_resorts[:80]
        print(
            f"\nFailed resort IDs ({len(failed_resorts)} total, showing {len(shown)}):"
        )
        for rid in shown:
            print(f"  - {rid}")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich resorts.json with annual snowfall data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save changes, just show what would be updated",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of resorts to process (for testing)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip building slug index from country listings",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Alias for --only-meteo",
    )
    parser.add_argument(
        "--only-meteo",
        action="store_true",
        help="Skip skiresort.info scraping, only use Open-Meteo historical data",
    )
    args = parser.parse_args()

    # --skip-scrape is an alias for --only-meteo
    if args.skip_scrape:
        args.only_meteo = True

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
