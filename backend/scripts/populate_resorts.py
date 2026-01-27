#!/usr/bin/env python3
"""
Database Population Script for Ski Resorts

This script loads resort data from JSON files (either scraped or manually curated)
into the DynamoDB database.

Usage:
    # Load from scraped data
    python populate_resorts.py --source scraped_resorts.json

    # Load from the main resorts.json
    python populate_resorts.py --source ../data/resorts.json

    # Dry run to preview changes
    python populate_resorts.py --source data.json --dry-run

    # Update existing resorts (instead of skip)
    python populate_resorts.py --source data.json --update-existing
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.resort import ElevationLevel, ElevationPoint, Resort
from src.services.resort_service import ResortService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ResortValidator:
    """Validates resort data before database insertion."""

    # Valid country codes
    VALID_COUNTRIES = {
        "CA",
        "US",  # North America
        "FR",
        "CH",
        "AT",
        "IT",
        "DE",
        "SI",
        "ES",
        "AD",  # Alps/Europe
        "NO",
        "SE",
        "FI",  # Scandinavia
        "PL",
        "CZ",
        "SK",
        "RO",
        "BG",
        "UA",
        "RU",  # Eastern Europe
        "JP",
        "KR",
        "CN",
        "IN",
        "IR",  # Asia
        "AU",
        "NZ",  # Oceania
        "CL",
        "AR",  # South America
    }

    # Valid regions
    VALID_REGIONS = {
        "na_west",
        "na_rockies",
        "na_east",
        "na_midwest",
        "alps",
        "scandinavia",
        "europe_east",
        "japan",
        "asia",
        "oceania",
        "south_america",
        "other",
    }

    @classmethod
    def validate(cls, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate resort data.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Required fields
        required_fields = [
            "resort_id",
            "name",
            "country",
            "elevation_base_m",
            "elevation_top_m",
            "latitude",
            "longitude",
            "timezone",
        ]

        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate resort_id format
        resort_id = data.get("resort_id", "")
        if not resort_id or not resort_id.replace("-", "").replace("_", "").isalnum():
            errors.append(f"Invalid resort_id format: {resort_id}")

        # Validate name
        name = data.get("name", "")
        if not name or len(name.strip()) < 2:
            errors.append(f"Invalid name: {name}")

        # Validate country
        country = data.get("country", "")
        if country not in cls.VALID_COUNTRIES:
            errors.append(f"Invalid country code: {country}")

        # Validate region if present
        region = data.get("region", "")
        if region and region not in cls.VALID_REGIONS:
            # Not an error, just a warning - region might be state/province
            pass

        # Validate elevations
        base = data.get("elevation_base_m", 0)
        top = data.get("elevation_top_m", 0)

        if not isinstance(base, int | float) or base < 0 or base > 5000:
            errors.append(f"Invalid base elevation: {base}")
        if not isinstance(top, int | float) or top < 0 or top > 6000:
            errors.append(f"Invalid top elevation: {top}")
        if base >= top:
            errors.append(f"Base elevation ({base}m) must be less than top ({top}m)")

        # Validate coordinates
        lat = data.get("latitude", 0)
        lon = data.get("longitude", 0)

        if not isinstance(lat, int | float) or not (-90 <= lat <= 90):
            errors.append(f"Invalid latitude: {lat}")
        if not isinstance(lon, int | float) or not (-180 <= lon <= 180):
            errors.append(f"Invalid longitude: {lon}")

        # Check for placeholder coordinates
        if lat == 0 and lon == 0:
            errors.append("Coordinates are placeholder (0, 0)")

        # Validate timezone
        timezone = data.get("timezone", "")
        if not timezone or not isinstance(timezone, str):
            errors.append(f"Invalid timezone: {timezone}")

        return len(errors) == 0, errors


class ResortPopulator:
    """Populates the database with resort data."""

    def __init__(
        self,
        resort_service: ResortService,
        dry_run: bool = False,
        update_existing: bool = False,
    ):
        self.resort_service = resort_service
        self.dry_run = dry_run
        self.update_existing = update_existing

    def transform_to_resort(self, data: dict[str, Any]) -> Resort:
        """Transform raw JSON data to Resort model."""
        now = datetime.now(UTC).isoformat()

        base_elev_m = int(data.get("elevation_base_m", 0))
        top_elev_m = int(data.get("elevation_top_m", 0))
        mid_elev_m = (base_elev_m + top_elev_m) // 2

        lat = float(data.get("latitude", 0.0))
        lon = float(data.get("longitude", 0.0))

        # Estimate mid and top coordinates
        lat_diff = 0.005 if lat > 0 else -0.005
        lon_diff = 0.005

        elevation_points = [
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=base_elev_m,
                elevation_feet=int(base_elev_m * 3.28084),
                latitude=lat,
                longitude=lon,
                weather_station_id=None,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=mid_elev_m,
                elevation_feet=int(mid_elev_m * 3.28084),
                latitude=lat + lat_diff,
                longitude=lon + lon_diff,
                weather_station_id=None,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=top_elev_m,
                elevation_feet=int(top_elev_m * 3.28084),
                latitude=lat + lat_diff * 2,
                longitude=lon + lon_diff * 2,
                weather_station_id=None,
            ),
        ]

        # Determine region for Resort model (use state_province if available)
        region = data.get("state_province", data.get("region", ""))

        return Resort(
            resort_id=data["resort_id"],
            name=data["name"],
            country=data["country"],
            region=region,
            elevation_points=elevation_points,
            timezone=data.get("timezone", "UTC"),
            official_website=data.get("website"),
            weather_sources=["weatherapi"],
            created_at=now,
            updated_at=now,
        )

    def populate(self, resorts_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Populate the database with resort data.

        Returns:
            Dictionary with results and statistics.
        """
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "created_ids": [],
            "updated_ids": [],
            "skipped_ids": [],
            "errors": [],
        }

        for data in resorts_data:
            results["total_processed"] += 1
            resort_id = data.get("resort_id", "unknown")

            try:
                # Validate data
                is_valid, errors = ResortValidator.validate(data)
                if not is_valid:
                    results["failed"] += 1
                    results["errors"].append(
                        {
                            "resort_id": resort_id,
                            "errors": errors,
                        }
                    )
                    logger.warning(f"Validation failed for {resort_id}: {errors}")
                    continue

                # Check if resort exists
                existing = None
                if not self.dry_run:
                    existing = self.resort_service.get_resort(resort_id)

                if existing:
                    if self.update_existing:
                        # Update existing resort
                        resort = self.transform_to_resort(data)
                        resort.created_at = (
                            existing.created_at
                        )  # Preserve original creation time

                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would update: {resort.name}")
                        else:
                            self.resort_service.update_resort(resort)
                            logger.info(f"Updated: {resort.name}")

                        results["updated"] += 1
                        results["updated_ids"].append(resort_id)
                    else:
                        # Skip existing
                        results["skipped"] += 1
                        results["skipped_ids"].append(resort_id)
                        logger.debug(f"Skipped existing: {resort_id}")
                else:
                    # Create new resort
                    resort = self.transform_to_resort(data)

                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would create: {resort.name}")
                    else:
                        self.resort_service.create_resort(resort)
                        logger.info(f"Created: {resort.name}")

                    results["created"] += 1
                    results["created_ids"].append(resort_id)

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "resort_id": resort_id,
                        "errors": [str(e)],
                    }
                )
                logger.error(f"Failed to process {resort_id}: {e}")

        return results


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def setup_services(table_name: str | None = None) -> ResortService:
    """Setup AWS services."""
    try:
        dynamodb = boto3.resource("dynamodb")

        if not table_name:
            table_name = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")

        logger.info(f"Using DynamoDB table: {table_name}")

        table = dynamodb.Table(table_name)
        return ResortService(table)

    except ClientError as e:
        logger.error(f"AWS error: {e.response['Error']['Message']}")
        sys.exit(1)


def print_results(results: dict[str, Any]) -> None:
    """Print population results."""
    print("\n" + "=" * 60)
    print("RESORT POPULATION RESULTS")
    print("=" * 60)
    print(f"Total processed: {results['total_processed']}")
    print(f"Created:         {results['created']}")
    print(f"Updated:         {results['updated']}")
    print(f"Skipped:         {results['skipped']}")
    print(f"Failed:          {results['failed']}")

    if results["created_ids"]:
        print(f"\nCreated resorts ({len(results['created_ids'])}):")
        for resort_id in results["created_ids"][:20]:  # Show first 20
            print(f"  + {resort_id}")
        if len(results["created_ids"]) > 20:
            print(f"  ... and {len(results['created_ids']) - 20} more")

    if results["updated_ids"]:
        print(f"\nUpdated resorts ({len(results['updated_ids'])}):")
        for resort_id in results["updated_ids"][:20]:
            print(f"  ~ {resort_id}")
        if len(results["updated_ids"]) > 20:
            print(f"  ... and {len(results['updated_ids']) - 20} more")

    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results["errors"][:10]:
            print(f"  ✗ {error['resort_id']}: {', '.join(error['errors'])}")
        if len(results["errors"]) > 10:
            print(f"  ... and {len(results['errors']) - 10} more errors")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Populate DynamoDB with resort data from JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--source",
        "-s",
        type=Path,
        required=True,
        help="Path to JSON file containing resort data",
    )

    parser.add_argument(
        "--table",
        type=str,
        help="DynamoDB table name (default: from RESORTS_TABLE env or snow-tracker-resorts-dev)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually modifying the database",
    )

    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing resorts instead of skipping them",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of resorts to process",
    )

    parser.add_argument(
        "--country",
        type=str,
        help="Only process resorts from this country (e.g., US, CA, FR)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")

    # Load JSON data
    logger.info(f"Loading data from {args.source}")
    data = load_json_file(args.source)

    # Extract resorts list
    if "resorts" in data:
        resorts = data["resorts"]
    elif isinstance(data, list):
        resorts = data
    else:
        logger.error("Invalid JSON format: expected 'resorts' key or a list")
        sys.exit(1)

    logger.info(f"Loaded {len(resorts)} resorts from file")

    # Filter by country if specified
    if args.country:
        resorts = [r for r in resorts if r.get("country") == args.country.upper()]
        logger.info(
            f"Filtered to {len(resorts)} resorts for country {args.country.upper()}"
        )

    # Apply limit if specified
    if args.limit:
        resorts = resorts[: args.limit]
        logger.info(f"Limited to {len(resorts)} resorts")

    if not resorts:
        logger.warning("No resorts to process")
        return

    # Setup services (skip for dry run if we want to avoid AWS setup)
    if args.dry_run:
        # For dry run, we can still validate the data without AWS
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "created_ids": [],
            "updated_ids": [],
            "skipped_ids": [],
            "errors": [],
        }

        for data_item in resorts:
            results["total_processed"] += 1
            resort_id = data_item.get("resort_id", "unknown")

            is_valid, errors = ResortValidator.validate(data_item)
            if not is_valid:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "resort_id": resort_id,
                        "errors": errors,
                    }
                )
                logger.warning(f"[DRY RUN] Validation failed for {resort_id}: {errors}")
            else:
                results["created"] += 1
                results["created_ids"].append(resort_id)
                logger.info(
                    f"[DRY RUN] Would create: {data_item.get('name', resort_id)}"
                )

        print_results(results)
        return

    # Setup AWS services
    resort_service = setup_services(args.table)

    # Create populator and run
    populator = ResortPopulator(
        resort_service=resort_service,
        dry_run=args.dry_run,
        update_existing=args.update_existing,
    )

    results = populator.populate(resorts)
    print_results(results)


if __name__ == "__main__":
    main()
