#!/usr/bin/env python3
"""
Cleanup script for scraped resort data.

This script applies fixes to existing scraped data:
1. Fixes resort names (removes "Ski resort " prefix)
2. Fixes regions based on state/province
3. Fixes timezones based on country/state
4. Applies known resort coordinates for (0,0) entries
5. Adds scraped_at timestamp

Usage:
    python cleanup_scraped_resorts.py --input resorts_scraped.json --output resorts_cleaned.json
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

# Import mappings from scraper
import sys
sys.path.insert(0, str(Path(__file__).parent))

from scrape_resorts import (
    US_STATE_ABBREV,
    CA_PROVINCE_ABBREV,
    US_STATE_REGIONS,
    CA_PROVINCE_REGIONS,
    REGION_MAPPINGS,
    TIMEZONE_MAPPINGS,
    MultiSourceGeocoder,
)


def normalize_state_province(country: str, state_province: str) -> str:
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


def get_region(country: str, state_province: str) -> str:
    """Determine the region based on country and state/province."""
    abbrev = normalize_state_province(country, state_province)

    if country == "US" and abbrev in US_STATE_REGIONS:
        return US_STATE_REGIONS[abbrev]

    if country == "CA" and abbrev in CA_PROVINCE_REGIONS:
        return CA_PROVINCE_REGIONS[abbrev]

    return REGION_MAPPINGS.get(country, "other")


def get_timezone(country: str, state_province: str) -> str:
    """Get timezone for a resort based on country and state/province."""
    abbrev = normalize_state_province(country, state_province)

    if abbrev:
        tz = TIMEZONE_MAPPINGS.get((country, abbrev))
        if tz:
            return tz

    tz = TIMEZONE_MAPPINGS.get((country, None))
    if tz:
        return tz

    return "UTC"


def clean_name(name: str) -> str:
    """Remove common prefixes and clean up resort name."""
    if name.lower().startswith("ski resort "):
        name = name[11:]
    name = re.sub(r"^(?:Ski Area |Ski Resort )", "", name, flags=re.IGNORECASE)
    return name.strip()


def generate_id(name: str) -> str:
    """Generate a URL-friendly resort ID from the name."""
    resort_id = name.lower()
    resort_id = re.sub(r"[''`]", "", resort_id)
    resort_id = re.sub(r"[àáâãäå]", "a", resort_id)
    resort_id = re.sub(r"[èéêë]", "e", resort_id)
    resort_id = re.sub(r"[ìíîï]", "i", resort_id)
    resort_id = re.sub(r"[òóôõö]", "o", resort_id)
    resort_id = re.sub(r"[ùúûü]", "u", resort_id)
    resort_id = re.sub(r"[ñ]", "n", resort_id)
    resort_id = re.sub(r"[ç]", "c", resort_id)
    resort_id = re.sub(r"[ß]", "ss", resort_id)
    resort_id = re.sub(r"[^a-z0-9]+", "-", resort_id)
    resort_id = resort_id.strip("-")
    resort_id = re.sub(r"-+", "-", resort_id)
    return resort_id


def cleanup_resort(resort: dict, geocoder: MultiSourceGeocoder) -> dict:
    """Apply all cleanup fixes to a resort."""
    # Clean name
    original_name = resort.get("name", "")
    clean = clean_name(original_name)

    country = resort.get("country", "")
    state_province = resort.get("state_province", "")

    # Fix region
    new_region = get_region(country, state_province)

    # Fix timezone
    new_timezone = get_timezone(country, state_province)

    # Fix coordinates if (0,0)
    lat = resort.get("latitude", 0)
    lon = resort.get("longitude", 0)

    if lat == 0 and lon == 0:
        # Try to geocode using known resorts
        coords = geocoder._geocode_known(clean, country)
        if coords:
            lat, lon = coords
            print(f"  Geocoded {clean}: ({lat}, {lon})")

    # Generate new ID from cleaned name
    new_id = generate_id(clean)

    return {
        "resort_id": new_id,
        "name": clean,
        "country": country,
        "region": new_region,
        "state_province": state_province,
        "elevation_base_m": resort.get("elevation_base_m", 0),
        "elevation_top_m": resort.get("elevation_top_m", 0),
        "latitude": lat,
        "longitude": lon,
        "timezone": new_timezone,
        "website": resort.get("website"),
        "features": resort.get("features", []),
        "annual_snowfall_cm": resort.get("annual_snowfall_cm"),
        "source": resort.get("source", "skiresort.info"),
        "scraped_at": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Clean up scraped resort data")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "resorts_scraped.json",
        help="Input file path",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "resorts_cleaned.json",
        help="Output file path",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    print(f"Loading data from {args.input}")
    with open(args.input) as f:
        data = json.load(f)

    resorts = data.get("resorts", [])
    print(f"Loaded {len(resorts)} resorts")

    # Create geocoder for coordinate lookup
    geocoder = MultiSourceGeocoder()

    # Process each resort
    cleaned = []
    stats = {
        "name_fixed": 0,
        "region_fixed": 0,
        "timezone_fixed": 0,
        "coords_fixed": 0,
        "total": len(resorts),
    }

    seen_ids = set()

    for resort in resorts:
        original_name = resort.get("name", "")
        original_region = resort.get("region", "")
        original_tz = resort.get("timezone", "")
        original_lat = resort.get("latitude", 0)
        original_lon = resort.get("longitude", 0)

        cleaned_resort = cleanup_resort(resort, geocoder)

        # Track changes
        if cleaned_resort["name"] != original_name:
            stats["name_fixed"] += 1
            if args.verbose:
                print(f"  Name: '{original_name}' -> '{cleaned_resort['name']}'")

        if cleaned_resort["region"] != original_region:
            stats["region_fixed"] += 1
            if args.verbose:
                print(f"  Region: '{original_region}' -> '{cleaned_resort['region']}'")

        if cleaned_resort["timezone"] != original_tz:
            stats["timezone_fixed"] += 1
            if args.verbose:
                print(f"  Timezone: '{original_tz}' -> '{cleaned_resort['timezone']}'")

        if (original_lat == 0 and original_lon == 0 and
            (cleaned_resort["latitude"] != 0 or cleaned_resort["longitude"] != 0)):
            stats["coords_fixed"] += 1

        # Deduplicate by ID
        if cleaned_resort["resort_id"] not in seen_ids:
            cleaned.append(cleaned_resort)
            seen_ids.add(cleaned_resort["resort_id"])
        else:
            print(f"  Skipping duplicate: {cleaned_resort['name']}")

    # Build output
    output = {
        "version": "1.0.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "regions": data.get("regions", {}),
        "resorts": cleaned,
    }

    # Write output
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n=== Cleanup Summary ===")
    print(f"Total resorts: {stats['total']}")
    print(f"Names fixed: {stats['name_fixed']}")
    print(f"Regions fixed: {stats['region_fixed']}")
    print(f"Timezones fixed: {stats['timezone_fixed']}")
    print(f"Coordinates fixed: {stats['coords_fixed']}")
    print(f"Output resorts: {len(cleaned)}")
    print(f"Output file: {args.output}")


if __name__ == "__main__":
    main()
