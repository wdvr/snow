"""Lambda handler for consolidating scraper results into versioned resort database.

This consolidator Lambda aggregates results from all scraper workers and creates
a versioned snapshot of the resort database that can be reviewed and deployed.

S3 Structure:
- scraper-results/{job_id}/ - Raw scraper worker outputs
- resort-versions/data/v{job_id}/resorts.json - Consolidated resort data
- resort-versions/manifests/v{job_id}.json - Version manifest with stats and diff
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "snow-tracker-pulumi-state-us-west-2")
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
RESORT_UPDATES_TOPIC_ARN = os.environ.get("RESORT_UPDATES_TOPIC_ARN", "")


def get_latest_scraper_job_id() -> str | None:
    """Find the most recent scraper job ID from S3."""
    try:
        response = s3.list_objects_v2(
            Bucket=RESULTS_BUCKET,
            Prefix="scraper-results/",
            Delimiter="/",
        )
        prefixes = response.get("CommonPrefixes", [])
        if not prefixes:
            return None

        # Job IDs are timestamps like 20260203060000, so sorting works
        job_ids = [
            p["Prefix"].split("/")[1] for p in prefixes if p["Prefix"].split("/")[1]
        ]
        job_ids = [
            j for j in job_ids if j and not j.startswith("test-")
        ]  # Skip test jobs
        if not job_ids:
            return None

        return sorted(job_ids, reverse=True)[0]  # Most recent
    except Exception as e:
        logger.error(f"Error finding latest job ID: {e}")
        return None


def get_scraper_results(job_id: str) -> list[dict[str, Any]]:
    """Aggregate all scraper results from a job into a single list of resorts."""
    resorts = []
    stats_by_country = {}

    try:
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"scraper-results/{job_id}/"

        for page in paginator.paginate(Bucket=RESULTS_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip metadata files
                if key.endswith("_metadata.json") or key.endswith("job_metadata.json"):
                    continue
                if not key.endswith(".json"):
                    continue

                try:
                    response = s3.get_object(Bucket=RESULTS_BUCKET, Key=key)
                    data = json.loads(response["Body"].read().decode("utf-8"))
                    country_resorts = data.get("resorts", [])
                    country_stats = data.get("stats", {})

                    # Extract country from filename (e.g., "US.json")
                    country = key.split("/")[-1].replace(".json", "")

                    resorts.extend(country_resorts)
                    stats_by_country[country] = {
                        "count": len(country_resorts),
                        "scraped": country_stats.get("resorts_scraped", 0),
                        "skipped": country_stats.get("resorts_skipped", 0),
                        "errors": country_stats.get("errors", 0),
                    }

                    logger.info(f"Loaded {len(country_resorts)} resorts from {key}")

                except Exception as e:
                    logger.error(f"Error reading {key}: {e}")

    except Exception as e:
        logger.error(f"Error listing scraper results: {e}")

    return resorts, stats_by_country


def get_production_resorts() -> dict[str, dict[str, Any]]:
    """Get current production resort data from DynamoDB."""
    resorts = {}
    table = dynamodb.Table(RESORTS_TABLE)

    try:
        response = table.scan()
        for item in response.get("Items", []):
            resort_id = item.get("resort_id")
            if resort_id:
                resorts[resort_id] = item

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            for item in response.get("Items", []):
                resort_id = item.get("resort_id")
                if resort_id:
                    resorts[resort_id] = item

        logger.info(f"Loaded {len(resorts)} resorts from production DynamoDB")

    except Exception as e:
        logger.error(f"Error scanning DynamoDB: {e}")

    return resorts


def calculate_diff(
    new_resorts: list[dict[str, Any]], production_resorts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Calculate the difference between new scraped resorts and production."""
    new_resort_ids = {r["resort_id"] for r in new_resorts}
    production_ids = set(production_resorts.keys())

    added_ids = new_resort_ids - production_ids
    removed_ids = production_ids - new_resort_ids
    existing_ids = new_resort_ids & production_ids

    # Build lookup for new resorts
    new_resorts_by_id = {r["resort_id"]: r for r in new_resorts}

    # Find modified resorts (compare key fields)
    modified = []
    for resort_id in existing_ids:
        new_data = new_resorts_by_id[resort_id]
        prod_data = production_resorts[resort_id]

        # Compare key fields
        changes = []
        if new_data.get("name") != prod_data.get("name"):
            changes.append(f"name: {prod_data.get('name')} -> {new_data.get('name')}")
        if new_data.get("elevation_base_m") != prod_data.get("elevation_base_m"):
            # Handle nested elevation_points structure in production
            prod_base = prod_data.get("elevation_base_m")
            if prod_base is None and prod_data.get("elevation_points"):
                for ep in prod_data.get("elevation_points", []):
                    if ep.get("level") == "base":
                        prod_base = ep.get("elevation_meters")
                        break
            if new_data.get("elevation_base_m") != prod_base:
                changes.append(
                    f"base_elev: {prod_base} -> {new_data.get('elevation_base_m')}"
                )
        if new_data.get("elevation_top_m") != prod_data.get("elevation_top_m"):
            prod_top = prod_data.get("elevation_top_m")
            if prod_top is None and prod_data.get("elevation_points"):
                for ep in prod_data.get("elevation_points", []):
                    if ep.get("level") == "top":
                        prod_top = ep.get("elevation_meters")
                        break
            if new_data.get("elevation_top_m") != prod_top:
                changes.append(
                    f"top_elev: {prod_top} -> {new_data.get('elevation_top_m')}"
                )

        if changes:
            modified.append(
                {
                    "resort_id": resort_id,
                    "name": new_data.get("name"),
                    "changes": changes,
                }
            )

    return {
        "added": [
            {
                "resort_id": rid,
                "name": new_resorts_by_id[rid].get("name"),
                "country": new_resorts_by_id[rid].get("country"),
                "region": new_resorts_by_id[rid].get("region"),
            }
            for rid in sorted(added_ids)
        ],
        "removed": [
            {
                "resort_id": rid,
                "name": production_resorts[rid].get("name"),
                "country": production_resorts[rid].get("country"),
                "region": production_resorts[rid].get("region"),
            }
            for rid in sorted(removed_ids)
        ],
        "modified": modified,
        "unchanged_count": len(existing_ids) - len(modified),
    }


def generate_stats(
    resorts: list[dict[str, Any]], stats_by_country: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Generate statistics about the resort dataset."""
    # Count by country
    by_country = {}
    for resort in resorts:
        country = resort.get("country", "unknown")
        by_country[country] = by_country.get(country, 0) + 1

    # Count by region
    by_region = {}
    for resort in resorts:
        region = resort.get("region", "unknown")
        by_region[region] = by_region.get(region, 0) + 1

    # Count resorts with valid coordinates
    with_coords = sum(
        1 for r in resorts if r.get("latitude", 0) != 0 or r.get("longitude", 0) != 0
    )

    return {
        "total_resorts": len(resorts),
        "by_country": by_country,
        "by_region": by_region,
        "with_valid_coordinates": with_coords,
        "scraper_stats": stats_by_country,
    }


def store_version(
    job_id: str,
    resorts: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> tuple[str, str]:
    """Store consolidated resort data and manifest to S3."""
    version_id = f"v{job_id}"

    # Store consolidated resort data
    data_key = f"resort-versions/data/{version_id}/resorts.json"
    s3.put_object(
        Bucket=RESULTS_BUCKET,
        Key=data_key,
        Body=json.dumps({"resorts": resorts}, indent=2),
        ContentType="application/json",
    )
    logger.info(f"Stored resort data: s3://{RESULTS_BUCKET}/{data_key}")

    # Store manifest
    manifest_key = f"resort-versions/manifests/{version_id}.json"
    s3.put_object(
        Bucket=RESULTS_BUCKET,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2),
        ContentType="application/json",
    )
    logger.info(f"Stored manifest: s3://{RESULTS_BUCKET}/{manifest_key}")

    return data_key, manifest_key


def send_notification(
    version_id: str, stats: dict[str, Any], diff: dict[str, Any]
) -> None:
    """Send SNS notification about new version."""
    if not RESORT_UPDATES_TOPIC_ARN:
        logger.info("No SNS topic configured, skipping notification")
        return

    added_count = len(diff.get("added", []))
    removed_count = len(diff.get("removed", []))
    modified_count = len(diff.get("modified", []))

    subject = f"[{ENVIRONMENT}] Resort Version {version_id}: +{added_count}/-{removed_count} resorts"

    lines = [
        f"Resort Database Version: {version_id}",
        f"Environment: {ENVIRONMENT}",
        "=" * 50,
        "",
        "SUMMARY",
        "-" * 30,
        f"Total resorts: {stats.get('total_resorts', 0)}",
        f"Added: {added_count}",
        f"Removed: {removed_count}",
        f"Modified: {modified_count}",
        "",
    ]

    if diff.get("added"):
        lines.append(f"ADDED RESORTS ({added_count}):")
        lines.append("-" * 30)
        for resort in diff["added"][:20]:
            lines.append(f"  + {resort['name']} ({resort['country']})")
        if added_count > 20:
            lines.append(f"  ... and {added_count - 20} more")
        lines.append("")

    if diff.get("removed"):
        lines.append(f"REMOVED RESORTS ({removed_count}):")
        lines.append("-" * 30)
        for resort in diff["removed"][:20]:
            lines.append(f"  - {resort['name']} ({resort['country']})")
        if removed_count > 20:
            lines.append(f"  ... and {removed_count - 20} more")
        lines.append("")

    lines.extend(
        [
            "",
            "To deploy this version:",
            f"  gh workflow run manage-resort-versions.yml -f action=deploy -f version={version_id} -f environment=staging",
            "",
            f"Data: s3://{RESULTS_BUCKET}/resort-versions/data/{version_id}/resorts.json",
            f"Manifest: s3://{RESULTS_BUCKET}/resort-versions/manifests/{version_id}.json",
        ]
    )

    message = "\n".join(lines)

    try:
        sns.publish(
            TopicArn=RESORT_UPDATES_TOPIC_ARN,
            Subject=subject[:100],
            Message=message,
        )
        logger.info("Sent notification to SNS topic")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def version_consolidator_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for consolidating scraper results into a versioned database.

    Args:
        event: Contains:
            - job_id: Optional specific job ID to process
            - process_latest: If true (default), find and process the most recent job
        context: Lambda context object

    Returns:
        Dict with consolidation results
    """
    start_time = datetime.now(UTC)

    job_id = event.get("job_id")

    # If no job_id provided, find the latest
    if not job_id and event.get("process_latest", True):
        job_id = get_latest_scraper_job_id()
        logger.info(f"Found latest job ID: {job_id}")

    if not job_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No job_id provided and no jobs found"}),
        }

    logger.info(f"Consolidating scraper results for job {job_id}")

    # Get scraper results
    resorts, stats_by_country = get_scraper_results(job_id)

    if not resorts:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"No resorts found for job {job_id}"}),
        }

    logger.info(f"Loaded {len(resorts)} resorts from scraper results")

    # Get production data for comparison
    production_resorts = get_production_resorts()

    # Calculate diff
    diff = calculate_diff(resorts, production_resorts)

    # Generate stats
    stats = generate_stats(resorts, stats_by_country)

    # Create manifest
    version_id = f"v{job_id}"
    manifest = {
        "version_id": version_id,
        "job_id": job_id,
        "created_at": start_time.isoformat(),
        "environment": ENVIRONMENT,
        "stats": stats,
        "diff": diff,
        "status": "pending",  # pending, deployed_staging, deployed_prod
        "deployment_history": [],
    }

    # Store version
    data_key, manifest_key = store_version(job_id, resorts, manifest)

    # Send notification
    send_notification(version_id, stats, diff)

    duration = (datetime.now(UTC) - start_time).total_seconds()

    logger.info(
        f"Consolidation complete: {stats['total_resorts']} resorts, "
        f"+{len(diff['added'])}/-{len(diff['removed'])} changes, "
        f"duration={duration:.2f}s"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Created version {version_id}",
                "version_id": version_id,
                "total_resorts": stats["total_resorts"],
                "added": len(diff["added"]),
                "removed": len(diff["removed"]),
                "modified": len(diff["modified"]),
                "data_key": data_key,
                "manifest_key": manifest_key,
                "duration_seconds": duration,
            }
        ),
    }
