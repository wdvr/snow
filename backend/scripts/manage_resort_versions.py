#!/usr/bin/env python3
"""
Resort Version Management CLI

This script manages versioned resort database snapshots stored in S3.

Usage:
    # List all available versions
    python manage_resort_versions.py list

    # Show details of a specific version
    python manage_resort_versions.py show v20260203060000

    # Deploy a version to staging (dry run)
    python manage_resort_versions.py deploy v20260203060000 --env staging --dry-run

    # Deploy a version to production
    python manage_resort_versions.py deploy v20260203060000 --env prod

    # Compare two versions
    python manage_resort_versions.py compare v20260201060000 v20260203060000
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_BUCKET = "snow-tracker-pulumi-state-us-west-2"
VERSIONS_PREFIX = "resort-versions/manifests/"
DATA_PREFIX = "resort-versions/data/"


class ResortVersionManager:
    """Manages resort database versions in S3."""

    def __init__(self, bucket: str = DEFAULT_BUCKET):
        self.bucket = bucket
        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb")

    def list_versions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List all available versions with summary information."""
        versions = []

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=VERSIONS_PREFIX):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith(".json"):
                        continue

                    # Extract version ID from key
                    version_id = key.split("/")[-1].replace(".json", "")

                    try:
                        response = self.s3.get_object(Bucket=self.bucket, Key=key)
                        manifest = json.loads(response["Body"].read().decode("utf-8"))

                        versions.append(
                            {
                                "version_id": version_id,
                                "created_at": manifest.get("created_at", "unknown"),
                                "total_resorts": manifest.get("stats", {}).get(
                                    "total_resorts", 0
                                ),
                                "added": len(manifest.get("diff", {}).get("added", [])),
                                "removed": len(
                                    manifest.get("diff", {}).get("removed", [])
                                ),
                                "status": manifest.get("status", "unknown"),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Error reading manifest {key}: {e}")

        except Exception as e:
            logger.error(f"Error listing versions: {e}")

        # Sort by version_id (timestamp-based) descending
        versions.sort(key=lambda v: v["version_id"], reverse=True)

        return versions[:limit]

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        """Get full manifest for a specific version."""
        manifest_key = f"{VERSIONS_PREFIX}{version_id}.json"

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=manifest_key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.error(f"Version {version_id} not found")
                return None
            raise

    def get_version_data(self, version_id: str) -> list[dict[str, Any]] | None:
        """Get resort data for a specific version."""
        data_key = f"{DATA_PREFIX}{version_id}/resorts.json"

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=data_key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            return data.get("resorts", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.error(f"Version data {version_id} not found")
                return None
            raise

    def deploy_version(
        self,
        version_id: str,
        environment: str,
        dry_run: bool = False,
        update_existing: bool = False,
    ) -> dict[str, Any]:
        """Deploy a version to DynamoDB."""
        table_name = f"snow-tracker-resorts-{environment}"

        # Load version data
        resorts = self.get_version_data(version_id)
        if resorts is None:
            return {"success": False, "error": f"Version {version_id} not found"}

        manifest = self.get_version(version_id)
        if manifest is None:
            return {"success": False, "error": f"Manifest for {version_id} not found"}

        logger.info(f"Deploying {len(resorts)} resorts to {table_name}")

        if dry_run:
            logger.info("[DRY RUN] Would deploy the following:")
            diff = manifest.get("diff", {})
            print(f"\n  Total resorts: {len(resorts)}")
            print(f"  New resorts: {len(diff.get('added', []))}")
            print(f"  Removed resorts: {len(diff.get('removed', []))}")
            print(f"  Modified resorts: {len(diff.get('modified', []))}")

            if diff.get("added"):
                print("\n  Would add:")
                for r in diff["added"][:10]:
                    print(f"    + {r['name']} ({r['country']})")
                if len(diff["added"]) > 10:
                    print(f"    ... and {len(diff['added']) - 10} more")

            if diff.get("removed"):
                print("\n  Would remove:")
                for r in diff["removed"][:10]:
                    print(f"    - {r['name']} ({r['country']})")
                if len(diff["removed"]) > 10:
                    print(f"    ... and {len(diff['removed']) - 10} more")

            return {
                "success": True,
                "dry_run": True,
                "total_resorts": len(resorts),
                "added": len(diff.get("added", [])),
                "removed": len(diff.get("removed", [])),
            }

        # Actually deploy
        table = self.dynamodb.Table(table_name)
        now = datetime.now(UTC).isoformat()

        results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
        }

        # Get existing resort IDs for comparison
        existing_ids = set()
        try:
            scan_response = table.scan(ProjectionExpression="resort_id")
            existing_ids.update(
                item["resort_id"] for item in scan_response.get("Items", [])
            )
            while "LastEvaluatedKey" in scan_response:
                scan_response = table.scan(
                    ProjectionExpression="resort_id",
                    ExclusiveStartKey=scan_response["LastEvaluatedKey"],
                )
                existing_ids.update(
                    item["resort_id"] for item in scan_response.get("Items", [])
                )
        except Exception as e:
            logger.warning(f"Error scanning existing resorts: {e}")

        # Deploy each resort
        for resort_data in resorts:
            resort_id = resort_data.get("resort_id")
            if not resort_id:
                results["errors"] += 1
                continue

            try:
                item = self._convert_to_dynamodb_item(resort_data, now)

                if resort_id in existing_ids:
                    if update_existing:
                        # Preserve created_at for existing resorts
                        existing = table.get_item(Key={"resort_id": resort_id})
                        if existing.get("Item", {}).get("created_at"):
                            item["created_at"] = existing["Item"]["created_at"]
                        table.put_item(Item=item)
                        results["updated"] += 1
                    else:
                        results["skipped"] += 1
                else:
                    table.put_item(Item=item)
                    results["created"] += 1

            except Exception as e:
                logger.error(f"Error deploying {resort_id}: {e}")
                results["errors"] += 1
                results["error_details"].append(
                    {
                        "resort_id": resort_id,
                        "error": str(e),
                    }
                )

        # Update manifest with deployment info
        self._update_manifest_status(version_id, environment, results, now)

        logger.info(
            f"Deployment complete: {results['created']} created, "
            f"{results['updated']} updated, {results['skipped']} skipped, "
            f"{results['errors']} errors"
        )

        return {
            "success": results["errors"] == 0,
            "results": results,
        }

    def _convert_to_dynamodb_item(
        self, resort_data: dict[str, Any], timestamp: str
    ) -> dict[str, Any]:
        """Convert scraped resort data to DynamoDB item format."""
        base_m = resort_data.get("elevation_base_m", 0)
        top_m = resort_data.get("elevation_top_m", 0)
        mid_m = (base_m + top_m) // 2

        lat = resort_data.get("latitude", 0.0)
        lon = resort_data.get("longitude", 0.0)

        elevation_points = [
            {
                "level": "base",
                "elevation_meters": base_m,
                "elevation_feet": int(base_m * 3.28084),
                "latitude": Decimal(str(lat)),
                "longitude": Decimal(str(lon)),
            },
            {
                "level": "mid",
                "elevation_meters": mid_m,
                "elevation_feet": int(mid_m * 3.28084),
                "latitude": Decimal(str(lat + 0.002)),
                "longitude": Decimal(str(lon - 0.003)),
            },
            {
                "level": "top",
                "elevation_meters": top_m,
                "elevation_feet": int(top_m * 3.28084),
                "latitude": Decimal(str(lat + 0.004)),
                "longitude": Decimal(str(lon - 0.006)),
            },
        ]

        return {
            "resort_id": resort_data["resort_id"],
            "name": resort_data["name"],
            "country": resort_data["country"],
            "region": resort_data.get("region", "other"),
            "elevation_points": elevation_points,
            "timezone": self._get_timezone(
                resort_data["country"], resort_data.get("state_province", "")
            ),
            "created_at": timestamp,
            "updated_at": timestamp,
            "source": resort_data.get("source"),
            "scraped_at": resort_data.get("scraped_at"),
        }

    def _get_timezone(self, country: str, state_province: str) -> str:
        """Get timezone for a resort based on country and state/province."""
        timezone_map = {
            "US": {
                "CA": "America/Los_Angeles",
                "OR": "America/Los_Angeles",
                "WA": "America/Los_Angeles",
                "CO": "America/Denver",
                "UT": "America/Denver",
                "WY": "America/Denver",
                "MT": "America/Denver",
                "VT": "America/New_York",
                "NH": "America/New_York",
                "ME": "America/New_York",
                "NY": "America/New_York",
                "_default": "America/Denver",
            },
            "CA": {
                "BC": "America/Vancouver",
                "AB": "America/Edmonton",
                "ON": "America/Toronto",
                "QC": "America/Montreal",
                "_default": "America/Vancouver",
            },
            "FR": "Europe/Paris",
            "CH": "Europe/Zurich",
            "AT": "Europe/Vienna",
            "IT": "Europe/Rome",
            "DE": "Europe/Berlin",
            "JP": "Asia/Tokyo",
            "AU": "Australia/Sydney",
            "NZ": "Pacific/Auckland",
            "CL": "America/Santiago",
            "AR": "America/Argentina/Buenos_Aires",
            "NO": "Europe/Oslo",
            "SE": "Europe/Stockholm",
        }

        if country in timezone_map:
            tz = timezone_map[country]
            if isinstance(tz, dict):
                return tz.get(state_province, tz.get("_default", "UTC"))
            return tz

        return "UTC"

    def _update_manifest_status(
        self,
        version_id: str,
        environment: str,
        results: dict[str, Any],
        timestamp: str,
    ) -> None:
        """Update manifest with deployment status."""
        manifest = self.get_version(version_id)
        if not manifest:
            return

        # Update status based on environment
        if environment == "prod":
            manifest["status"] = "deployed_prod"
        elif environment == "staging":
            if manifest.get("status") != "deployed_prod":
                manifest["status"] = "deployed_staging"

        # Add to deployment history
        deployment_record = {
            "environment": environment,
            "timestamp": timestamp,
            "results": {
                "created": results["created"],
                "updated": results["updated"],
                "skipped": results["skipped"],
                "errors": results["errors"],
            },
        }
        manifest.setdefault("deployment_history", []).append(deployment_record)

        # Save updated manifest
        manifest_key = f"{VERSIONS_PREFIX}{version_id}.json"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2),
            ContentType="application/json",
        )

    def compare_versions(self, version_a: str, version_b: str) -> dict[str, Any]:
        """Compare two versions and show differences."""
        resorts_a = self.get_version_data(version_a)
        resorts_b = self.get_version_data(version_b)

        if resorts_a is None or resorts_b is None:
            return {"error": "One or both versions not found"}

        ids_a = {r["resort_id"] for r in resorts_a}
        ids_b = {r["resort_id"] for r in resorts_b}

        resorts_a_map = {r["resort_id"]: r for r in resorts_a}
        resorts_b_map = {r["resort_id"]: r for r in resorts_b}

        added = ids_b - ids_a
        removed = ids_a - ids_b

        return {
            "version_a": version_a,
            "version_b": version_b,
            "count_a": len(resorts_a),
            "count_b": len(resorts_b),
            "added": [
                {"resort_id": rid, "name": resorts_b_map[rid].get("name")}
                for rid in sorted(added)
            ],
            "removed": [
                {"resort_id": rid, "name": resorts_a_map[rid].get("name")}
                for rid in sorted(removed)
            ],
        }


def cmd_list(args):
    """Handle list command."""
    manager = ResortVersionManager(args.bucket)
    versions = manager.list_versions(args.limit)

    if not versions:
        print("No versions found")
        return

    print(
        f"\n{'Version ID':<20} {'Created':<25} {'Resorts':>8} {'Added':>7} {'Removed':>8} {'Status':<18}"
    )
    print("-" * 100)

    for v in versions:
        created = v["created_at"][:19] if len(v["created_at"]) > 19 else v["created_at"]
        print(
            f"{v['version_id']:<20} {created:<25} {v['total_resorts']:>8} "
            f"+{v['added']:>6} -{v['removed']:>6} {v['status']:<18}"
        )

    print(f"\nTotal: {len(versions)} version(s)")


def cmd_show(args):
    """Handle show command."""
    manager = ResortVersionManager(args.bucket)
    manifest = manager.get_version(args.version)

    if not manifest:
        print(f"Version {args.version} not found")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"VERSION: {manifest['version_id']}")
    print(f"{'=' * 60}")
    print(f"Created: {manifest.get('created_at', 'unknown')}")
    print(f"Status: {manifest.get('status', 'unknown')}")
    print(f"Environment: {manifest.get('environment', 'unknown')}")

    stats = manifest.get("stats", {})
    print("\nSTATISTICS:")
    print(f"  Total resorts: {stats.get('total_resorts', 0)}")
    print(f"  With coordinates: {stats.get('with_valid_coordinates', 0)}")

    if stats.get("by_country"):
        print("\n  By country:")
        for country, count in sorted(stats["by_country"].items(), key=lambda x: -x[1])[
            :10
        ]:
            print(f"    {country}: {count}")

    if stats.get("by_region"):
        print("\n  By region:")
        for region, count in sorted(stats["by_region"].items(), key=lambda x: -x[1]):
            print(f"    {region}: {count}")

    diff = manifest.get("diff", {})
    print("\nCHANGES (vs production at time of scrape):")
    print(f"  Added: {len(diff.get('added', []))}")
    print(f"  Removed: {len(diff.get('removed', []))}")
    print(f"  Modified: {len(diff.get('modified', []))}")
    print(f"  Unchanged: {diff.get('unchanged_count', 0)}")

    if args.verbose:
        if diff.get("added"):
            print("\n  Added resorts:")
            for r in diff["added"][:20]:
                print(f"    + {r['name']} ({r['country']})")
            if len(diff["added"]) > 20:
                print(f"    ... and {len(diff['added']) - 20} more")

        if diff.get("removed"):
            print("\n  Removed resorts:")
            for r in diff["removed"][:20]:
                print(f"    - {r['name']} ({r['country']})")
            if len(diff["removed"]) > 20:
                print(f"    ... and {len(diff['removed']) - 20} more")

    if manifest.get("deployment_history"):
        print("\nDEPLOYMENT HISTORY:")
        for d in manifest["deployment_history"]:
            results = d.get("results", {})
            print(
                f"  {d['timestamp'][:19]} -> {d['environment']}: "
                f"+{results.get('created', 0)} created, "
                f"~{results.get('updated', 0)} updated, "
                f"!{results.get('errors', 0)} errors"
            )

    print(f"\n{'=' * 60}")


def cmd_deploy(args):
    """Handle deploy command."""
    manager = ResortVersionManager(args.bucket)

    print(f"\nDeploying version {args.version} to {args.env}")
    if args.dry_run:
        print("[DRY RUN MODE]")

    result = manager.deploy_version(
        args.version,
        args.env,
        dry_run=args.dry_run,
        update_existing=args.update_existing,
    )

    if not result.get("success"):
        print(f"\nDeployment failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    if not args.dry_run:
        results = result.get("results", {})
        print("\nDeployment complete:")
        print(f"  Created: {results.get('created', 0)}")
        print(f"  Updated: {results.get('updated', 0)}")
        print(f"  Skipped: {results.get('skipped', 0)}")
        print(f"  Errors: {results.get('errors', 0)}")

        if results.get("error_details"):
            print("\n  Error details:")
            for err in results["error_details"][:10]:
                print(f"    {err['resort_id']}: {err['error']}")


def cmd_compare(args):
    """Handle compare command."""
    manager = ResortVersionManager(args.bucket)
    result = manager.compare_versions(args.version_a, args.version_b)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"\nComparing {args.version_a} vs {args.version_b}")
    print(f"  {args.version_a}: {result['count_a']} resorts")
    print(f"  {args.version_b}: {result['count_b']} resorts")

    added = result.get("added", [])
    removed = result.get("removed", [])

    print(f"\n  Added in {args.version_b}: {len(added)}")
    for r in added[:10]:
        print(f"    + {r['name']}")
    if len(added) > 10:
        print(f"    ... and {len(added) - 10} more")

    print(f"\n  Removed in {args.version_b}: {len(removed)}")
    for r in removed[:10]:
        print(f"    - {r['name']}")
    if len(removed) > 10:
        print(f"    ... and {len(removed) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        description="Manage resort database versions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket for version storage (default: {DEFAULT_BUCKET})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List available versions")
    list_parser.add_argument(
        "--limit", "-n", type=int, default=20, help="Number of versions to show"
    )
    list_parser.set_defaults(func=cmd_list)

    # Show command
    show_parser = subparsers.add_parser("show", help="Show version details")
    show_parser.add_argument("version", help="Version ID (e.g., v20260203060000)")
    show_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed change list"
    )
    show_parser.set_defaults(func=cmd_show)

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy version to DynamoDB")
    deploy_parser.add_argument("version", help="Version ID to deploy")
    deploy_parser.add_argument(
        "--env",
        required=True,
        choices=["staging", "prod"],
        help="Target environment",
    )
    deploy_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deployment without making changes",
    )
    deploy_parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing resorts (default: skip)",
    )
    deploy_parser.set_defaults(func=cmd_deploy)

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two versions")
    compare_parser.add_argument("version_a", help="First version ID")
    compare_parser.add_argument("version_b", help="Second version ID")
    compare_parser.set_defaults(func=cmd_compare)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
