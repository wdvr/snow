#!/usr/bin/env python3
"""
Command-line script for seeding initial resort data.

Usage:
    python scripts/seed_resorts.py [--validate] [--export] [--summary]

Options:
    --validate    Validate existing resort data integrity
    --export      Export current resort data to JSON file
    --summary     Show summary of current resort data
    --dry-run     Show what would be created without actually creating
"""

import argparse
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.resort_service import ResortService
from src.utils.resort_seeder import ResortSeeder

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_services():
    """Setup AWS services and resort seeder."""
    try:
        # Initialize DynamoDB resource
        dynamodb = boto3.resource("dynamodb")

        # Get table name from environment or use default
        table_name = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
        logger.info(f"Using DynamoDB table: {table_name}")

        # Initialize services
        table = dynamodb.Table(table_name)
        resort_service = ResortService(table)
        seeder = ResortSeeder(resort_service)

        return seeder, resort_service

    except ClientError as e:
        logger.error(f"AWS error: {e.response['Error']['Message']}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to setup services: {str(e)}")
        sys.exit(1)


def seed_resorts(
    seeder: ResortSeeder, dry_run: bool = False, update_existing: bool = False
):
    """Seed the initial resort data."""
    if dry_run:
        logger.info("DRY RUN: Would create the following resorts:")
        initial_resorts = seeder._get_initial_resort_data()
        for resort in initial_resorts:
            print(f"  - {resort.name} ({resort.resort_id})")
            print(f"    Country: {resort.country}, Region: {resort.region}")
            print(
                f"    Elevation: {min(p.elevation_meters for p in resort.elevation_points)}m - "
                f"{max(p.elevation_meters for p in resort.elevation_points)}m"
            )
            print()
        return

    try:
        logger.info("Starting resort data seeding...")
        results = seeder.seed_initial_resorts(update_existing=update_existing)

        print("\n" + "=" * 50)
        print("RESORT SEEDING RESULTS")
        print("=" * 50)
        print(f"Resorts created: {results['resorts_created']}")
        print(f"Resorts updated: {results.get('resorts_updated', 0)}")
        print(f"Resorts skipped: {results['resorts_skipped']}")
        print(f"Errors: {len(results['errors'])}")

        if results["created_resorts"]:
            print("\nCreated resorts:")
            for resort_id in results["created_resorts"]:
                print(f"  ✅ {resort_id}")

        if results.get("updated_resorts"):
            print("\nUpdated resorts:")
            for resort_id in results["updated_resorts"]:
                print(f"  🔄 {resort_id}")

        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  ❌ {error}")

        print("\n" + "=" * 50)

    except Exception as e:
        logger.error(f"Failed to seed resorts: {str(e)}")
        sys.exit(1)


def validate_resorts(seeder: ResortSeeder):
    """Validate resort data integrity."""
    try:
        logger.info("Validating resort data...")
        results = seeder.validate_resort_data()

        print("\n" + "=" * 50)
        print("RESORT DATA VALIDATION")
        print("=" * 50)
        print(f"Total resorts: {results['total_resorts']}")
        print(f"Valid resorts: {results['valid_resorts']}")
        print(f"Resorts with issues: {len(results['issues'])}")
        print(f"Warnings: {len(results['warnings'])}")

        if results["issues"]:
            print("\nIssues found:")
            for issue in results["issues"]:
                print(f"\n  🔴 {issue['resort_name']} ({issue['resort_id']}):")
                for problem in issue["issues"]:
                    print(f"     - {problem}")

        if results["warnings"]:
            print("\nWarnings:")
            for warning in results["warnings"]:
                print(f"  ⚠️  {warning}")

        if not results["issues"] and not results["warnings"]:
            print("\n✅ All resort data is valid!")

        print("\n" + "=" * 50)

    except Exception as e:
        logger.error(f"Failed to validate resorts: {str(e)}")
        sys.exit(1)


def show_summary(seeder: ResortSeeder):
    """Show summary of current resort data."""
    try:
        logger.info("Generating resort summary...")
        summary = seeder.get_resort_summary()

        print("\n" + "=" * 50)
        print("RESORT DATA SUMMARY")
        print("=" * 50)
        print(f"Total resorts: {summary['total_resorts']}")

        if summary["resorts_by_country"]:
            print("\nBy Country:")
            for country, count in summary["resorts_by_country"].items():
                country_name = (
                    "Canada"
                    if country == "CA"
                    else "United States"
                    if country == "US"
                    else country
                )
                print(f"  {country_name}: {count} resort{'s' if count != 1 else ''}")

        if summary["resorts_by_region"]:
            print("\nBy Region:")
            for region, count in summary["resorts_by_region"].items():
                print(f"  {region}: {count} resort{'s' if count != 1 else ''}")

        if summary["elevation_ranges"]:
            print("\nElevation Ranges:")
            for _resort_id, data in summary["elevation_ranges"].items():
                print(f"  {data['name']}:")
                print(
                    f"    Range: {data['min_elevation_m']}m - {data['max_elevation_m']}m"
                )
                print(f"    Vertical Drop: {data['vertical_drop_m']}m")
                print(f"    Elevation Points: {data['elevation_points']}")

        print("\n" + "=" * 50)

    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}")
        sys.exit(1)


def export_resorts(seeder: ResortSeeder):
    """Export resort data to JSON file."""
    try:
        logger.info("Exporting resort data...")
        file_path = seeder.export_resort_data()

        print("\n" + "=" * 50)
        print("RESORT DATA EXPORT")
        print("=" * 50)
        print(f"✅ Resort data exported to: {file_path}")
        print("\n" + "=" * 50)

    except Exception as e:
        logger.error(f"Failed to export resort data: {str(e)}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Seed initial resort data into Snow Quality Tracker database"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing resort data integrity",
    )
    parser.add_argument(
        "--export", action="store_true", help="Export current resort data to JSON file"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Show summary of current resort data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without actually creating",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing resorts instead of skipping them",
    )

    args = parser.parse_args()

    # Setup services
    seeder, resort_service = setup_services()

    # Execute requested operations
    if args.validate:
        validate_resorts(seeder)
    elif args.export:
        export_resorts(seeder)
    elif args.summary:
        show_summary(seeder)
    else:
        # Default action is to seed resorts
        seed_resorts(seeder, dry_run=args.dry_run, update_existing=args.update)


if __name__ == "__main__":
    main()
