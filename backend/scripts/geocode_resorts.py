#!/usr/bin/env python3
"""
Geocode ski resorts that have (0.0, 0.0) coordinates.

Uses Open-Meteo Geocoding API (primary) and Nominatim (fallback).
Updates resorts.json in-place with latitude, longitude, and timezone.
"""

import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import aiohttp
from timezonefinder import TimezoneFinder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RESORTS_FILE = Path(__file__).parent.parent / "data" / "resorts.json"

# Open-Meteo geocoding API (generous rate limits, 10 concurrent OK)
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Nominatim fallback (1 req/sec, needs User-Agent)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "PowderChaser/1.0 (ski resort geocoding)"

# Concurrency settings
OPEN_METEO_CONCURRENCY = 10
NOMINATIM_RATE_LIMIT = 1.1  # seconds between requests

# Country code to full name mapping for Nominatim queries
COUNTRY_NAMES = {
    "AD": "Andorra",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "BG": "Bulgaria",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "IN": "India",
    "IT": "Italy",
    "JP": "Japan",
    "KR": "South Korea",
    "NO": "Norway",
    "NZ": "New Zealand",
    "PL": "Poland",
    "RO": "Romania",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "US": "United States",
}

# Suffixes to strip for simplified search
STRIP_SUFFIXES = [
    r"\s*\(planned\)",
    r"\s*–\s*.*$",  # Everything after em-dash
    r"\s*/\s*.*$",  # Everything after slash (often multiple resort names)
    r"\s*-\s+.*$",  # Everything after spaced hyphen
    r"\s+Ski Resort$",
    r"\s+Ski Area$",
    r"\s+Ski Centre$",
    r"\s+Ski Center$",
    r"\s+Mountain Resort$",
    r"\s+Mountain$",
    r"\s+Alpine Resort$",
    r"\s+Snow Resort$",
    r"\s+Resort$",
]

tf = TimezoneFinder()


def simplify_name(name: str) -> str:
    """Remove common suffixes and secondary resort names to get core name."""
    # Replace unicode characters
    simplified = (
        name.replace("\u200b", "").replace("\u2013", "-").replace("\u2014", "-")
    )

    for pattern in STRIP_SUFFIXES:
        simplified = re.sub(pattern, "", simplified, flags=re.IGNORECASE).strip()

    return simplified


def extract_primary_name(name: str) -> str:
    """Extract just the first/primary name from compound resort names."""
    # Replace unicode chars
    clean = name.replace("\u200b", "").replace("\u2013", "-").replace("\u2014", "-")

    # Take first part before dash, slash, parenthesis
    for sep in [" - ", " – ", " / ", "/", " (", "(", " – "]:
        if sep in clean:
            clean = clean.split(sep)[0].strip()
            break

    return clean


def match_country(result: dict, country_code: str) -> bool:
    """Check if a geocoding result matches the expected country."""
    result_cc = result.get("country_code", "").upper()

    # Direct match
    if result_cc == country_code:
        return True

    # Some country code variations
    aliases = {
        "CZ": ["CZ", "CS"],
        "SK": ["SK"],
        "KR": ["KR"],
        "CN": ["CN"],
    }

    if country_code in aliases:
        return result_cc in aliases[country_code]

    return False


def is_plausible_ski_location(result: dict, resort: dict) -> bool:
    """Check if a geocoding result is plausible for a ski resort."""
    lat = result.get("latitude", 0)
    elevation = result.get("elevation", 0)
    country = resort.get("country", "")

    # Southern hemisphere ski resorts are OK at lower latitudes
    if country in ("AR", "CL", "NZ", "AU"):
        return True

    # For northern hemisphere, ski resorts are typically above certain latitudes
    # But be lenient - some exist at surprising places
    if country in ("CN", "IN", "KR", "JP", "ES"):
        return True  # Wide range of latitudes

    # For European/North American resorts, check they're not at sea level
    # (unless the resort data says so)
    if (
        elevation is not None
        and elevation < 50
        and resort.get("elevation_base_m", 0) > 300
    ):
        return False

    return True


async def geocode_open_meteo(
    session: aiohttp.ClientSession,
    resort: dict,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Try to geocode a resort using Open-Meteo Geocoding API."""
    name = resort["name"]
    country = resort["country"]

    # Try multiple name variants
    name_variants = [
        name,
        simplify_name(name),
        extract_primary_name(name),
    ]
    # Deduplicate while preserving order
    seen = set()
    unique_variants = []
    for v in name_variants:
        if v not in seen and v:
            seen.add(v)
            unique_variants.append(v)

    for variant in unique_variants:
        async with semaphore:
            try:
                params = {
                    "name": variant,
                    "count": 10,
                    "language": "en",
                    "format": "json",
                }
                async with session.get(
                    OPEN_METEO_GEOCODE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

                results = data.get("results", [])
                if not results:
                    continue

                # Filter by country
                country_matches = [r for r in results if match_country(r, country)]

                if not country_matches:
                    continue

                # Filter for plausible ski locations
                plausible = [
                    r for r in country_matches if is_plausible_ski_location(r, resort)
                ]
                if plausible:
                    best = plausible[0]
                else:
                    best = country_matches[0]

                return {
                    "latitude": round(best["latitude"], 4),
                    "longitude": round(best["longitude"], 4),
                    "elevation": best.get("elevation"),
                    "source": f"open-meteo:{variant}",
                }

            except (TimeoutError, aiohttp.ClientError, KeyError) as e:
                logger.debug(f"Open-Meteo error for {name} ({variant}): {e}")
                continue

    return None


async def geocode_nominatim(
    session: aiohttp.ClientSession,
    resort: dict,
    rate_limiter: asyncio.Lock,
    last_request_time: list,
) -> dict | None:
    """Try to geocode a resort using Nominatim (fallback, rate-limited)."""
    name = resort["name"]
    country = resort["country"]
    country_name = COUNTRY_NAMES.get(country, country)

    # Try multiple query formats
    queries = [
        f"{simplify_name(name)} ski {country_name}",
        f"{extract_primary_name(name)} ski resort {country_name}",
        f"{extract_primary_name(name)} {country_name}",
    ]
    # Deduplicate
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    for query in unique_queries:
        async with rate_limiter:
            # Enforce rate limit
            now = time.monotonic()
            elapsed = now - last_request_time[0]
            if elapsed < NOMINATIM_RATE_LIMIT:
                await asyncio.sleep(NOMINATIM_RATE_LIMIT - elapsed)
            last_request_time[0] = time.monotonic()

        try:
            params = {
                "q": query,
                "format": "json",
                "limit": 5,
                "countrycodes": country.lower(),
            }
            headers = {"User-Agent": NOMINATIM_USER_AGENT}

            async with session.get(
                NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    continue
                results = await resp.json()

            if not results:
                continue

            best = results[0]
            lat = float(best["lat"])
            lon = float(best["lon"])

            return {
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "elevation": None,  # Nominatim doesn't provide elevation
                "source": f"nominatim:{query}",
            }

        except (TimeoutError, aiohttp.ClientError, KeyError, ValueError) as e:
            logger.debug(f"Nominatim error for {name} ({query}): {e}")
            continue

    return None


async def geocode_resort(
    session: aiohttp.ClientSession,
    resort: dict,
    semaphore: asyncio.Semaphore,
    nominatim_lock: asyncio.Lock,
    nominatim_last_time: list,
    nominatim_queue: list,
) -> tuple[dict, dict | None]:
    """Geocode a single resort, trying Open-Meteo first, then queuing for Nominatim."""
    result = await geocode_open_meteo(session, resort, semaphore)

    if result is None:
        # Queue for Nominatim fallback (will be processed sequentially later)
        nominatim_queue.append(resort)

    return resort, result


async def process_nominatim_batch(
    session: aiohttp.ClientSession,
    resorts: list[dict],
    nominatim_lock: asyncio.Lock,
    nominatim_last_time: list,
) -> dict:
    """Process Nominatim fallback batch sequentially (rate limited)."""
    results = {}
    for i, resort in enumerate(resorts):
        logger.info(
            f"  Nominatim fallback {i + 1}/{len(resorts)}: {resort['name']} ({resort['country']})"
        )
        result = await geocode_nominatim(
            session, resort, nominatim_lock, nominatim_last_time
        )
        if result:
            results[resort["resort_id"]] = result
        else:
            logger.warning(f"  FAILED: {resort['name']} ({resort['country']})")
    return results


def update_timezone(lat: float, lon: float, current_tz: str | None) -> str:
    """Get timezone from coordinates. Falls back to current timezone if lookup fails."""
    try:
        tz = tf.timezone_at(lat=lat, lng=lon)
        if tz:
            return tz
    except Exception:
        pass
    return current_tz or "UTC"


async def main():
    """Main geocoding workflow."""
    logger.info(f"Loading resorts from {RESORTS_FILE}")

    with open(RESORTS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    resorts = data["resorts"]
    total = len(resorts)

    # Find resorts needing geocoding
    needs_geocoding = [
        r
        for r in resorts
        if r.get("latitude", 0) == 0.0 and r.get("longitude", 0) == 0.0
    ]

    logger.info(f"Total resorts: {total}")
    logger.info(f"Need geocoding: {len(needs_geocoding)}")
    logger.info(f"Already geocoded: {total - len(needs_geocoding)}")

    if not needs_geocoding:
        logger.info("All resorts already have coordinates. Nothing to do.")
        return

    # Phase 1: Open-Meteo (concurrent)
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Phase 1: Open-Meteo Geocoding API ({len(needs_geocoding)} resorts)")
    logger.info(f"{'=' * 60}")

    semaphore = asyncio.Semaphore(OPEN_METEO_CONCURRENCY)
    nominatim_lock = asyncio.Lock()
    nominatim_last_time = [0.0]
    nominatim_queue = []
    open_meteo_results = {}

    async with aiohttp.ClientSession() as session:
        tasks = [
            geocode_resort(
                session,
                resort,
                semaphore,
                nominatim_lock,
                nominatim_last_time,
                nominatim_queue,
            )
            for resort in needs_geocoding
        ]

        completed = 0
        for coro in asyncio.as_completed(tasks):
            resort, result = await coro
            completed += 1
            if result:
                open_meteo_results[resort["resort_id"]] = result
                if completed % 50 == 0 or completed == len(needs_geocoding):
                    logger.info(
                        f"  Progress: {completed}/{len(needs_geocoding)} processed, "
                        f"{len(open_meteo_results)} geocoded"
                    )
            elif completed % 50 == 0:
                logger.info(
                    f"  Progress: {completed}/{len(needs_geocoding)} processed, "
                    f"{len(open_meteo_results)} geocoded"
                )

    logger.info(f"Open-Meteo results: {len(open_meteo_results)} geocoded")
    logger.info(f"Nominatim fallback needed: {len(nominatim_queue)} resorts")

    # Phase 2: Nominatim fallback (sequential, rate-limited)
    nominatim_results = {}
    if nominatim_queue:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Phase 2: Nominatim Fallback ({len(nominatim_queue)} resorts)")
        logger.info(f"{'=' * 60}")
        logger.info(
            f"  Estimated time: ~{len(nominatim_queue) * 3 * NOMINATIM_RATE_LIMIT:.0f}s "
            f"(3 queries/resort, {NOMINATIM_RATE_LIMIT}s rate limit)"
        )

        async with aiohttp.ClientSession() as session:
            nominatim_results = await process_nominatim_batch(
                session, nominatim_queue, nominatim_lock, nominatim_last_time
            )

    logger.info(f"Nominatim results: {len(nominatim_results)} geocoded")

    # Merge results
    all_results = {**open_meteo_results, **nominatim_results}

    # Phase 3: Update resorts
    logger.info(f"\n{'=' * 60}")
    logger.info("Phase 3: Updating resorts.json")
    logger.info(f"{'=' * 60}")

    updated_count = 0
    failed_resorts = []

    for resort in resorts:
        resort_id = resort["resort_id"]
        if resort_id not in all_results:
            if resort.get("latitude", 0) == 0.0 and resort.get("longitude", 0) == 0.0:
                failed_resorts.append(resort)
            continue

        result = all_results[resort_id]
        lat = result["latitude"]
        lon = result["longitude"]

        resort["latitude"] = lat
        resort["longitude"] = lon

        # Update timezone based on new coordinates
        new_tz = update_timezone(lat, lon, resort.get("timezone"))
        if new_tz and new_tz != resort.get("timezone"):
            old_tz = resort.get("timezone", "N/A")
            resort["timezone"] = new_tz
            logger.debug(f"  {resort['name']}: timezone {old_tz} -> {new_tz}")

        updated_count += 1

    # Write updated data
    logger.info("Writing updated resorts.json...")
    with open(RESORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Final summary
    still_zero = sum(
        1
        for r in resorts
        if r.get("latitude", 0) == 0.0 and r.get("longitude", 0) == 0.0
    )

    logger.info(f"\n{'=' * 60}")
    logger.info("RESULTS SUMMARY")
    logger.info(f"{'=' * 60}")
    logger.info(f"Total resorts:           {total}")
    logger.info(f"Needed geocoding:        {len(needs_geocoding)}")
    logger.info(f"Successfully geocoded:   {updated_count}")
    logger.info(f"  - via Open-Meteo:      {len(open_meteo_results)}")
    logger.info(f"  - via Nominatim:       {len(nominatim_results)}")
    logger.info(f"Failed:                  {len(failed_resorts)}")
    logger.info(f"Still at (0,0):          {still_zero}")

    if failed_resorts:
        logger.info("\nFailed resorts:")
        for r in sorted(failed_resorts, key=lambda x: x["country"]):
            logger.info(f"  {r['country']}: {r['name']} (id={r['resort_id']})")

    # Return exit code based on success rate
    success_rate = updated_count / len(needs_geocoding) if needs_geocoding else 1.0
    logger.info(f"\nSuccess rate: {success_rate:.1%}")

    if success_rate < 0.5:
        logger.error("Less than 50% success rate!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
