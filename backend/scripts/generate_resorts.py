#!/usr/bin/env python3
"""
Resort Data Generator

This script manages the resort database JSON file.
It can:
- Validate existing resort data
- Add new resorts interactively or from prompts
- Export resorts for seeding

Usage:
    python scripts/generate_resorts.py validate
    python scripts/generate_resorts.py list [--region REGION]
    python scripts/generate_resorts.py add --name "Resort Name" --country US --region na_west
    python scripts/generate_resorts.py stats
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Path to resort data
DATA_FILE = Path(__file__).parent.parent / "data" / "resorts.json"

# Valid regions
VALID_REGIONS = [
    "na_west",
    "na_rockies",
    "na_east",
    "alps",
    "scandinavia",
    "japan",
    "oceania",
    "south_america",
]

# Country codes
COUNTRY_CODES = {
    "CA": "Canada",
    "US": "United States",
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
    "FI": "Finland",
}


def load_data() -> dict[str, Any]:
    """Load resort data from JSON file."""
    if not DATA_FILE.exists():
        print(f"Error: Data file not found at {DATA_FILE}")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict[str, Any]) -> None:
    """Save resort data to JSON file."""
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(data['resorts'])} resorts to {DATA_FILE}")


def validate_resort(resort: dict[str, Any]) -> list[str]:
    """Validate a single resort entry. Returns list of errors."""
    errors = []

    required_fields = [
        "resort_id", "name", "country", "region", "state_province",
        "elevation_base_m", "elevation_top_m", "latitude", "longitude",
        "timezone", "website"
    ]

    for field in required_fields:
        if field not in resort:
            errors.append(f"Missing required field: {field}")

    if resort.get("region") not in VALID_REGIONS:
        errors.append(f"Invalid region: {resort.get('region')}. Must be one of {VALID_REGIONS}")

    if resort.get("country") not in COUNTRY_CODES:
        errors.append(f"Unknown country code: {resort.get('country')}")

    lat = resort.get("latitude", 0)
    lon = resort.get("longitude", 0)

    if not (-90 <= lat <= 90):
        errors.append(f"Invalid latitude: {lat}")
    if not (-180 <= lon <= 180):
        errors.append(f"Invalid longitude: {lon}")

    base_elev = resort.get("elevation_base_m", 0)
    top_elev = resort.get("elevation_top_m", 0)

    if base_elev >= top_elev:
        errors.append(f"Base elevation ({base_elev}m) must be less than top ({top_elev}m)")

    return errors


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all resort data."""
    data = load_data()
    resorts = data.get("resorts", [])

    print(f"Validating {len(resorts)} resorts...\n")

    all_valid = True
    resort_ids = set()

    for resort in resorts:
        resort_id = resort.get("resort_id", "unknown")

        # Check for duplicate IDs
        if resort_id in resort_ids:
            print(f"❌ {resort_id}: Duplicate resort ID")
            all_valid = False
        resort_ids.add(resort_id)

        errors = validate_resort(resort)
        if errors:
            all_valid = False
            print(f"❌ {resort_id}:")
            for error in errors:
                print(f"   - {error}")
        elif args.verbose:
            print(f"✓ {resort_id}")

    print()
    if all_valid:
        print("✓ All resorts are valid!")
    else:
        print("❌ Validation failed. Please fix the errors above.")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List resorts, optionally filtered by region."""
    data = load_data()
    resorts = data.get("resorts", [])
    regions = data.get("regions", {})

    if args.region:
        if args.region not in VALID_REGIONS:
            print(f"Invalid region: {args.region}")
            print(f"Valid regions: {', '.join(VALID_REGIONS)}")
            sys.exit(1)

        resorts = [r for r in resorts if r.get("region") == args.region]
        region_info = regions.get(args.region, {})
        print(f"\n{region_info.get('display_name', args.region)} ({len(resorts)} resorts):\n")
    else:
        print(f"\nAll Resorts ({len(resorts)}):\n")

    # Group by region if not filtered
    if not args.region:
        by_region = {}
        for resort in resorts:
            region = resort.get("region", "unknown")
            if region not in by_region:
                by_region[region] = []
            by_region[region].append(resort)

        for region_id in VALID_REGIONS:
            if region_id in by_region:
                region_info = regions.get(region_id, {})
                region_resorts = by_region[region_id]
                print(f"## {region_info.get('display_name', region_id)} ({len(region_resorts)})")
                for resort in sorted(region_resorts, key=lambda r: r["name"]):
                    country = resort.get("country", "??")
                    print(f"   - {resort['name']} ({country})")
                print()
    else:
        for resort in sorted(resorts, key=lambda r: r["name"]):
            vertical = resort.get("elevation_top_m", 0) - resort.get("elevation_base_m", 0)
            snowfall = resort.get("annual_snowfall_cm", "?")
            print(f"  {resort['name']}")
            print(f"    Elevation: {resort.get('elevation_base_m')}m - {resort.get('elevation_top_m')}m ({vertical}m vertical)")
            print(f"    Annual snowfall: {snowfall}cm")
            print(f"    Location: {resort.get('state_province')}, {COUNTRY_CODES.get(resort.get('country'), resort.get('country'))}")
            print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Show statistics about the resort database."""
    data = load_data()
    resorts = data.get("resorts", [])
    regions = data.get("regions", {})

    print("\n📊 Resort Database Statistics\n")
    print(f"Total resorts: {len(resorts)}")
    print(f"Last updated: {data.get('last_updated', 'unknown')}")
    print()

    # By region
    print("By Region:")
    by_region = {}
    for resort in resorts:
        region = resort.get("region", "unknown")
        by_region[region] = by_region.get(region, 0) + 1

    for region_id, count in sorted(by_region.items(), key=lambda x: -x[1]):
        region_info = regions.get(region_id, {})
        name = region_info.get("display_name", region_id)
        print(f"  {name}: {count}")
    print()

    # By country
    print("By Country:")
    by_country = {}
    for resort in resorts:
        country = resort.get("country", "??")
        by_country[country] = by_country.get(country, 0) + 1

    for country, count in sorted(by_country.items(), key=lambda x: -x[1]):
        name = COUNTRY_CODES.get(country, country)
        print(f"  {name}: {count}")
    print()

    # Elevation stats
    if resorts:
        elevations = [(r.get("elevation_top_m", 0) - r.get("elevation_base_m", 0)) for r in resorts]
        top_elevs = [r.get("elevation_top_m", 0) for r in resorts]
        snowfalls = [r.get("annual_snowfall_cm", 0) for r in resorts if r.get("annual_snowfall_cm")]

        print("Elevation Stats:")
        print(f"  Highest peak: {max(top_elevs)}m")
        print(f"  Biggest vertical: {max(elevations)}m")
        print(f"  Average vertical: {sum(elevations) // len(elevations)}m")

        if snowfalls:
            print(f"\nSnowfall Stats:")
            print(f"  Most snow: {max(snowfalls)}cm/year")
            print(f"  Average: {sum(snowfalls) // len(snowfalls)}cm/year")


def cmd_add(args: argparse.Namespace) -> None:
    """Add a new resort to the database."""
    data = load_data()
    resorts = data.get("resorts", [])

    # Check for duplicate
    resort_id = args.id or args.name.lower().replace(" ", "-").replace("'", "")
    existing = [r for r in resorts if r.get("resort_id") == resort_id]
    if existing:
        print(f"Error: Resort with ID '{resort_id}' already exists")
        sys.exit(1)

    # Create new resort
    new_resort = {
        "resort_id": resort_id,
        "name": args.name,
        "country": args.country.upper(),
        "region": args.region,
        "state_province": args.state or "",
        "elevation_base_m": args.base_elevation or 0,
        "elevation_top_m": args.top_elevation or 0,
        "latitude": args.latitude or 0.0,
        "longitude": args.longitude or 0.0,
        "timezone": args.timezone or "",
        "website": args.website or "",
        "features": args.features.split(",") if args.features else [],
        "annual_snowfall_cm": args.snowfall or 0,
    }

    # Validate
    errors = validate_resort(new_resort)
    if errors and not args.force:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nUse --force to add anyway, or fix the errors.")
        sys.exit(1)

    resorts.append(new_resort)
    data["resorts"] = resorts
    save_data(data)

    print(f"✓ Added resort: {args.name} ({resort_id})")


def cmd_export(args: argparse.Namespace) -> None:
    """Export resorts for use with resort_seeder.py."""
    data = load_data()
    resorts = data.get("resorts", [])

    if args.region:
        resorts = [r for r in resorts if r.get("region") == args.region]

    print(f"# Exporting {len(resorts)} resorts for resort_seeder.py\n")

    for resort in resorts:
        mid_elevation = (resort.get("elevation_base_m", 0) + resort.get("elevation_top_m", 0)) // 2

        # Estimate mid-mountain coordinates (simple interpolation)
        lat_diff = 0.01 if resort.get("latitude", 0) > 0 else -0.01
        lon_diff = 0.01

        print(f"""Resort(
    resort_id="{resort['resort_id']}",
    name="{resort['name']}",
    country="{resort['country']}",
    region="{resort.get('state_province', '')}",
    elevation_points=[
        ElevationPoint(
            level=ElevationLevel.BASE,
            elevation_meters={resort.get('elevation_base_m', 0)},
            elevation_feet={int(resort.get('elevation_base_m', 0) * 3.28084)},
            latitude={resort.get('latitude', 0)},
            longitude={resort.get('longitude', 0)},
            weather_station_id=None,
        ),
        ElevationPoint(
            level=ElevationLevel.MID,
            elevation_meters={mid_elevation},
            elevation_feet={int(mid_elevation * 3.28084)},
            latitude={resort.get('latitude', 0) + lat_diff},
            longitude={resort.get('longitude', 0) + lon_diff},
            weather_station_id=None,
        ),
        ElevationPoint(
            level=ElevationLevel.TOP,
            elevation_meters={resort.get('elevation_top_m', 0)},
            elevation_feet={int(resort.get('elevation_top_m', 0) * 3.28084)},
            latitude={resort.get('latitude', 0) + lat_diff * 2},
            longitude={resort.get('longitude', 0) + lon_diff * 2},
            weather_station_id=None,
        ),
    ],
    timezone="{resort.get('timezone', '')}",
    official_website="{resort.get('website', '')}",
    weather_sources=["weatherapi"],
    created_at=now,
    updated_at=now,
),""")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Snow Tracker resort database"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate resort data")
    validate_parser.add_argument("-v", "--verbose", action="store_true", help="Show all resorts")

    # List command
    list_parser = subparsers.add_parser("list", help="List resorts")
    list_parser.add_argument("--region", choices=VALID_REGIONS, help="Filter by region")

    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new resort")
    add_parser.add_argument("--name", required=True, help="Resort name")
    add_parser.add_argument("--country", required=True, help="Country code (CA, US, etc.)")
    add_parser.add_argument("--region", required=True, choices=VALID_REGIONS, help="Region")
    add_parser.add_argument("--id", help="Resort ID (auto-generated if not provided)")
    add_parser.add_argument("--state", help="State/Province")
    add_parser.add_argument("--base-elevation", type=int, help="Base elevation in meters")
    add_parser.add_argument("--top-elevation", type=int, help="Top elevation in meters")
    add_parser.add_argument("--latitude", type=float, help="Latitude")
    add_parser.add_argument("--longitude", type=float, help="Longitude")
    add_parser.add_argument("--timezone", help="Timezone")
    add_parser.add_argument("--website", help="Website URL")
    add_parser.add_argument("--features", help="Features (comma-separated)")
    add_parser.add_argument("--snowfall", type=int, help="Annual snowfall in cm")
    add_parser.add_argument("--force", action="store_true", help="Add even with validation errors")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export for resort_seeder.py")
    export_parser.add_argument("--region", choices=VALID_REGIONS, help="Filter by region")

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
