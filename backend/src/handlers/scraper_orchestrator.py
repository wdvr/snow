"""Lambda handler for orchestrating parallel resort scraping.

This orchestrator Lambda fans out to worker Lambdas, each processing
one country in parallel for faster scraping.
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
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")
s3 = boto3.client("s3")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SCRAPER_WORKER_LAMBDA = os.environ.get(
    "SCRAPER_WORKER_LAMBDA", f"snow-tracker-scraper-worker-{ENVIRONMENT}"
)
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "snow-tracker-pulumi-state-us-west-2")
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")

# Countries to scrape, grouped by priority/size
# Group 1: Major markets (process first)
PRIORITY_COUNTRIES = ["US", "CA", "AT", "CH", "FR", "IT", "JP"]
# Group 2: Secondary markets
SECONDARY_COUNTRIES = ["DE", "NO", "SE", "AU", "NZ", "CL", "AR"]
# Group 3: Other markets
OTHER_COUNTRIES = ["FI", "ES", "AD", "PL", "CZ", "SK", "SI", "KR", "CN"]

ALL_COUNTRIES = PRIORITY_COUNTRIES + SECONDARY_COUNTRIES + OTHER_COUNTRIES


def is_first_of_month() -> bool:
    """Check if today is the first day of the month."""
    return datetime.now(UTC).day == 1


def publish_orchestrator_metrics(stats: dict[str, Any]) -> None:
    """Publish orchestrator metrics to CloudWatch."""
    try:
        metrics = [
            {
                "MetricName": "ScraperWorkersInvoked",
                "Value": stats.get("workers_invoked", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ScraperWorkersFailed",
                "Value": stats.get("workers_failed", 0),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ScraperMode",
                "Value": 1.0 if stats.get("full_scrape") else 0.0,
                "Unit": "None",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
            {
                "MetricName": "ScraperOrchestrationDuration",
                "Value": stats.get("duration_seconds", 0),
                "Unit": "Seconds",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            },
        ]

        cloudwatch.put_metric_data(
            Namespace="SnowTracker/ScraperOrchestrator", MetricData=metrics
        )
        logger.info("Published orchestrator metrics")

    except Exception as e:
        logger.error(f"Failed to publish orchestrator metrics: {e}")


def scraper_orchestrator_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for orchestrating parallel resort scraping.

    Invokes worker Lambdas for each country in parallel.

    Args:
        event: Contains:
            - full_scrape: If true, scrape all resorts (ignore existing)
                          If false (default), only scrape new resorts
            - countries: Optional list of specific countries to scrape
        context: Lambda context object

    Returns:
        Dict with orchestration results
    """
    start_time = datetime.now(UTC)
    job_id = start_time.strftime("%Y%m%d%H%M%S")

    # Determine scrape mode
    # Full scrape on first of month or if explicitly requested
    full_scrape = event.get("full_scrape", False) or is_first_of_month()
    delta_mode = not full_scrape

    # Get countries to scrape
    countries = event.get("countries", ALL_COUNTRIES)

    logger.info(
        f"Starting scraper orchestration: job_id={job_id}, "
        f"full_scrape={full_scrape}, countries={len(countries)}"
    )

    stats = {
        "job_id": job_id,
        "full_scrape": full_scrape,
        "workers_invoked": 0,
        "workers_failed": 0,
        "countries": [],
        "start_time": start_time.isoformat(),
    }

    invocations = []

    # Invoke worker Lambda for each country
    for country in countries:
        try:
            payload = {
                "country": country,
                "delta_mode": delta_mode,
                "job_id": job_id,
            }

            logger.info(f"Invoking scraper worker for {country}")

            response = lambda_client.invoke(
                FunctionName=SCRAPER_WORKER_LAMBDA,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(payload),
            )

            success = response.get("StatusCode") == 202
            invocations.append(
                {
                    "country": country,
                    "status_code": response.get("StatusCode"),
                    "success": success,
                }
            )

            if success:
                stats["workers_invoked"] += 1
                stats["countries"].append(country)
            else:
                stats["workers_failed"] += 1

        except Exception as e:
            logger.error(f"Failed to invoke worker for {country}: {e}")
            invocations.append(
                {
                    "country": country,
                    "error": str(e),
                    "success": False,
                }
            )
            stats["workers_failed"] += 1

    stats["end_time"] = datetime.now(UTC).isoformat()
    stats["duration_seconds"] = (datetime.now(UTC) - start_time).total_seconds()

    # Store job metadata in S3
    try:
        job_metadata = {
            "job_id": job_id,
            "start_time": stats["start_time"],
            "full_scrape": full_scrape,
            "countries": countries,
            "invocations": invocations,
        }
        s3.put_object(
            Bucket=RESULTS_BUCKET,
            Key=f"scraper-results/{job_id}/job_metadata.json",
            Body=json.dumps(job_metadata),
            ContentType="application/json",
        )
        logger.info(
            f"Stored job metadata to s3://{RESULTS_BUCKET}/scraper-results/{job_id}/"
        )
    except Exception as e:
        logger.error(f"Failed to store job metadata: {e}")

    # Publish metrics
    publish_orchestrator_metrics(stats)

    logger.info(
        f"Orchestration complete: {stats['workers_invoked']} workers invoked, "
        f"{stats['workers_failed']} failed, duration={stats['duration_seconds']:.2f}s"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Dispatched {stats['workers_invoked']} scraper workers",
                "job_id": job_id,
                "mode": "full" if full_scrape else "delta",
                "workers_invoked": stats["workers_invoked"],
                "workers_failed": stats["workers_failed"],
                "countries": stats["countries"],
                "duration_seconds": stats["duration_seconds"],
            }
        ),
    }


def process_scraper_results_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for processing scraper results and populating DynamoDB.

    This should be triggered after all worker Lambdas complete (e.g., via Step Functions
    or a scheduled cleanup job).

    Args:
        event: Contains:
            - job_id: The scraper job ID to process
        context: Lambda context object

    Returns:
        Dict with processing results
    """
    job_id = event.get("job_id")
    if not job_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "job_id is required"}),
        }

    logger.info(f"Processing scraper results for job {job_id}")

    stats = {
        "job_id": job_id,
        "resorts_added": 0,
        "resorts_updated": 0,
        "errors": 0,
    }

    try:
        table = dynamodb.Table(RESORTS_TABLE)

        # List all result files for this job
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"scraper-results/{job_id}/"

        for page in paginator.paginate(Bucket=RESULTS_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("_metadata.json") or not key.endswith(".json"):
                    continue

                # Download and parse results
                try:
                    response = s3.get_object(Bucket=RESULTS_BUCKET, Key=key)
                    data = json.loads(response["Body"].read().decode("utf-8"))
                    resorts = data.get("resorts", [])

                    for resort_data in resorts:
                        try:
                            # Convert to DynamoDB format
                            item = convert_to_dynamodb_item(resort_data)
                            table.put_item(Item=item)
                            stats["resorts_added"] += 1
                        except Exception as e:
                            logger.error(
                                f"Error adding resort {resort_data.get('resort_id')}: {e}"
                            )
                            stats["errors"] += 1

                except Exception as e:
                    logger.error(f"Error processing {key}: {e}")
                    stats["errors"] += 1

        logger.info(
            f"Processed job {job_id}: "
            f"{stats['resorts_added']} added, {stats['errors']} errors"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Processed {stats['resorts_added']} resorts",
                    "stats": stats,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Fatal error processing results: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def convert_to_dynamodb_item(resort_data: dict) -> dict:
    """Convert scraped resort data to DynamoDB item format."""
    now = datetime.now(UTC).isoformat()

    # Calculate elevation points
    base_m = resort_data["elevation_base_m"]
    top_m = resort_data["elevation_top_m"]
    mid_m = (base_m + top_m) // 2

    lat = resort_data.get("latitude", 0.0)
    lon = resort_data.get("longitude", 0.0)

    elevation_points = [
        {
            "level": "base",
            "elevation_meters": base_m,
            "elevation_feet": int(base_m * 3.28084),
            "latitude": lat,
            "longitude": lon,
        },
        {
            "level": "mid",
            "elevation_meters": mid_m,
            "elevation_feet": int(mid_m * 3.28084),
            "latitude": lat + 0.002,
            "longitude": lon - 0.003,
        },
        {
            "level": "top",
            "elevation_meters": top_m,
            "elevation_feet": int(top_m * 3.28084),
            "latitude": lat + 0.004,
            "longitude": lon - 0.006,
        },
    ]

    return {
        "resort_id": resort_data["resort_id"],
        "name": resort_data["name"],
        "country": resort_data["country"],
        "region": resort_data.get("region", "other"),
        "elevation_points": elevation_points,
        "timezone": get_timezone(
            resort_data["country"], resort_data.get("state_province", "")
        ),
        "created_at": now,
        "updated_at": now,
        "source": resort_data.get("source"),
        "scraped_at": resort_data.get("scraped_at"),
    }


def get_timezone(country: str, state_province: str) -> str:
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
