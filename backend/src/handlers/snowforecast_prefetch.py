"""Lambda handler for prefetching Snow-Forecast data for all resorts.

Scrapes Snow-Forecast.com for all supported resorts and writes the results
to a static JSON cache file in S3. This avoids scraping on-the-fly during
weather processing, which would be too slow and risk rate limiting.

Lambda config: 512MB memory, 900s timeout.
Runs on a schedule (e.g., every 6 hours).
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from services.resort_service import ResortService
from services.snowforecast_scraper import SnowForecastScraper

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", f"snow-tracker-resorts-{ENVIRONMENT}")
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", f"snow-tracker-website-{ENVIRONMENT}")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-west-2")
CACHE_S3_KEY = "data/snowforecast-cache.json"

# Delay between requests to avoid rate limiting
REQUEST_DELAY_SECONDS = 1.0

# Minimum time buffer before Lambda timeout (60 seconds)
MIN_TIME_BUFFER_MS = 60000

# Initialize AWS clients
_boto_config = BotoConfig(max_pool_connections=10, retries={"max_attempts": 3})
s3_client = boto3.client("s3", region_name=AWS_REGION, config=_boto_config)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION, config=_boto_config)


def get_remaining_time_ms(context) -> int:
    """Get remaining Lambda execution time in milliseconds."""
    if context and hasattr(context, "get_remaining_time_in_millis"):
        return context.get_remaining_time_in_millis()
    return 600000  # Default 10 minutes if no context


def snowforecast_prefetch_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler that scrapes Snow-Forecast for all resorts.

    Writes results to S3 as a JSON cache file that the weather processor
    can read instead of scraping on-the-fly.

    Args:
        event: Lambda event (scheduled CloudWatch event or manual invocation)
        context: Lambda context object

    Returns:
        Dict with processing results and statistics
    """
    start_time = datetime.now(UTC)
    logger.info(f"Starting Snow-Forecast prefetch at {start_time.isoformat()}")

    stats = {
        "resorts_total": 0,
        "resorts_scraped": 0,
        "hits": 0,
        "misses": 0,
        "errors": 0,
        "timeout_graceful": False,
        "start_time": start_time.isoformat(),
    }

    try:
        # Get all resorts from DynamoDB
        resort_service = ResortService(dynamodb.Table(RESORTS_TABLE))
        resorts = resort_service.get_all_resorts()
        stats["resorts_total"] = len(resorts)
        logger.info(f"Found {len(resorts)} resorts to scrape")

        if not resorts:
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {"message": "No resorts to process", "stats": stats}
                ),
            }

        # Scrape each resort sequentially with delay
        scraper = SnowForecastScraper()
        cache: dict[str, dict[str, Any]] = {}

        for resort in resorts:
            # Check remaining time before each request
            remaining_ms = get_remaining_time_ms(context)
            if remaining_ms < MIN_TIME_BUFFER_MS:
                logger.warning(
                    f"Approaching timeout ({remaining_ms}ms remaining), "
                    f"stopping after {stats['resorts_scraped']} resorts"
                )
                stats["timeout_graceful"] = True
                break

            resort_id = resort.resort_id

            try:
                data = scraper.get_snow_report(resort_id)

                if data:
                    cache[resort_id] = {
                        "snowfall_24h_cm": data.snowfall_24h_cm,
                        "snowfall_48h_cm": data.snowfall_48h_cm,
                        "snowfall_72h_cm": data.snowfall_72h_cm,
                        "upper_depth_cm": data.upper_depth_cm,
                        "lower_depth_cm": data.lower_depth_cm,
                        "surface_conditions": data.surface_conditions,
                        "source_url": data.source_url,
                    }
                    stats["hits"] += 1
                else:
                    stats["misses"] += 1

            except Exception as e:
                logger.warning(f"Error scraping Snow-Forecast for {resort_id}: {e}")
                stats["errors"] += 1

            stats["resorts_scraped"] += 1

            # Rate limit: delay between requests
            time.sleep(REQUEST_DELAY_SECONDS)

        # Write cache to S3
        cache_data = {
            "generated_at": datetime.now(UTC).isoformat(),
            "resort_count": len(cache),
            "resorts": cache,
        }

        s3_client.put_object(
            Bucket=WEBSITE_BUCKET,
            Key=CACHE_S3_KEY,
            Body=json.dumps(cache_data),
            ContentType="application/json",
        )

        logger.info(
            f"Wrote {len(cache)} resort records to s3://{WEBSITE_BUCKET}/{CACHE_S3_KEY}"
        )

        # Finalize stats
        end_time = datetime.now(UTC)
        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()

        message = (
            "Snow-Forecast prefetch stopped gracefully (timeout)"
            if stats["timeout_graceful"]
            else "Snow-Forecast prefetch completed successfully"
        )

        logger.info(f"{message}. Stats: {stats}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": message, "stats": stats}),
        }

    except Exception as e:
        logger.error(f"Fatal error in Snow-Forecast prefetch: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Snow-Forecast prefetch failed",
                    "error": str(e),
                    "stats": stats,
                }
            ),
        }
