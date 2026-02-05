"""Static JSON API Generator.

Generates pre-computed static JSON files for fast edge-cached responses.
These files are uploaded to S3 and served via CloudFront for optimal performance.

Files generated:
- /data/resorts.json - All resort metadata
- /data/snow-quality.json - All resort snow quality summaries
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from models.resort import Resort
from models.weather import SnowQuality
from services.resort_service import ResortService
from services.weather_service import WeatherService

logger = logging.getLogger(__name__)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", f"snow-tracker-website-{ENVIRONMENT}")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-west-2")

# Initialize AWS clients
s3_client = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


class StaticJsonGenerator:
    """Generates and uploads static JSON files to S3."""

    def __init__(
        self,
        resorts_table_name: str | None = None,
        weather_conditions_table_name: str | None = None,
        website_bucket: str | None = None,
    ):
        """Initialize the generator with table and bucket names."""
        self.resorts_table_name = resorts_table_name or os.environ.get(
            "RESORTS_TABLE", f"snow-tracker-resorts-{ENVIRONMENT}"
        )
        self.weather_conditions_table_name = (
            weather_conditions_table_name
            or os.environ.get(
                "WEATHER_CONDITIONS_TABLE",
                f"snow-tracker-weather-conditions-{ENVIRONMENT}",
            )
        )
        self.website_bucket = website_bucket or WEBSITE_BUCKET

        # Initialize services
        self.resorts_table = dynamodb.Table(self.resorts_table_name)
        self.weather_table = dynamodb.Table(self.weather_conditions_table_name)
        self.resort_service = ResortService(self.resorts_table)
        # WeatherService needs api_key (not used for reading) and conditions_table
        self.weather_service = WeatherService(
            api_key="",  # Not needed for reading from DynamoDB
            conditions_table=self.weather_table,
        )

    def generate_all(self) -> dict[str, Any]:
        """Generate and upload all static JSON files.

        Returns:
            Dict with generation statistics and results
        """
        logger.info("Starting static JSON generation")
        start_time = datetime.now(UTC)
        results = {
            "generated_at": start_time.isoformat(),
            "files": [],
            "errors": [],
        }

        try:
            # Generate resorts.json
            resorts_result = self._generate_resorts_json()
            results["files"].append(resorts_result)
        except Exception as e:
            logger.error(f"Failed to generate resorts.json: {e}")
            results["errors"].append({"file": "resorts.json", "error": str(e)})

        try:
            # Generate snow-quality.json
            quality_result = self._generate_snow_quality_json()
            results["files"].append(quality_result)
        except Exception as e:
            logger.error(f"Failed to generate snow-quality.json: {e}")
            results["errors"].append({"file": "snow-quality.json", "error": str(e)})

        end_time = datetime.now(UTC)
        results["duration_seconds"] = (end_time - start_time).total_seconds()
        results["success"] = len(results["errors"]) == 0

        logger.info(
            f"Static JSON generation complete: {len(results['files'])} files, "
            f"{len(results['errors'])} errors, {results['duration_seconds']:.2f}s"
        )

        return results

    def _generate_resorts_json(self) -> dict[str, Any]:
        """Generate resorts.json with all resort metadata.

        Returns:
            Dict with file generation stats
        """
        logger.info("Generating resorts.json")

        # Get all resorts
        resorts = self.resort_service.get_all_resorts()
        logger.info(f"Found {len(resorts)} resorts")

        # Convert to JSON-serializable format
        resorts_data = []
        for resort in resorts:
            resort_dict = resort.model_dump()
            resorts_data.append(resort_dict)

        # Build the JSON structure
        output = {
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(resorts_data),
            "resorts": resorts_data,
        }

        # Upload to S3
        json_content = json.dumps(output, indent=None, separators=(",", ":"))
        s3_key = "data/resorts.json"

        self._upload_to_s3(s3_key, json_content)

        return {
            "file": s3_key,
            "resort_count": len(resorts_data),
            "size_bytes": len(json_content),
        }

    def _generate_snow_quality_json(self) -> dict[str, Any]:
        """Generate snow-quality.json with all resort snow quality summaries.

        Returns:
            Dict with file generation stats
        """
        logger.info("Generating snow-quality.json")

        # Get all resorts
        resorts = self.resort_service.get_all_resorts()

        # Build snow quality summaries for each resort
        quality_summaries = {}
        processed = 0
        errors = 0

        for resort in resorts:
            try:
                summary = self._get_snow_quality_for_resort(resort)
                if summary:
                    quality_summaries[resort.resort_id] = summary
                    processed += 1
            except Exception as e:
                logger.warning(
                    f"Failed to get snow quality for {resort.resort_id}: {e}"
                )
                errors += 1

        logger.info(f"Generated snow quality for {processed} resorts, {errors} errors")

        # Build the JSON structure
        output = {
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(quality_summaries),
            "results": quality_summaries,
        }

        # Upload to S3
        json_content = json.dumps(output, indent=None, separators=(",", ":"))
        s3_key = "data/snow-quality.json"

        self._upload_to_s3(s3_key, json_content)

        return {
            "file": s3_key,
            "resort_count": len(quality_summaries),
            "size_bytes": len(json_content),
            "errors": errors,
        }

    def _get_snow_quality_for_resort(self, resort: Resort) -> dict | None:
        """Get snow quality summary for a single resort.

        This mirrors the API's _get_snow_quality_for_resort function logic.
        """
        conditions = []

        # Get latest conditions for each elevation level
        for elevation_point in resort.elevation_points:
            level = (
                elevation_point.level.value
                if hasattr(elevation_point.level, "value")
                else elevation_point.level
            )
            try:
                condition = self.weather_service.get_latest_condition(
                    resort.resort_id, level
                )
                if condition:
                    conditions.append(condition)
            except Exception:
                pass

        if not conditions:
            return {
                "resort_id": resort.resort_id,
                "overall_quality": SnowQuality.UNKNOWN.value,
                "last_updated": None,
                "temperature_c": None,
                "snowfall_fresh_cm": None,
                "snowfall_24h_cm": None,
            }

        # Calculate overall quality (same logic as API)
        quality_scores = {
            SnowQuality.EXCELLENT: 6,
            SnowQuality.GOOD: 5,
            SnowQuality.FAIR: 4,
            SnowQuality.POOR: 3,
            SnowQuality.BAD: 2,
            SnowQuality.HORRIBLE: 1,
            SnowQuality.UNKNOWN: 0,
        }

        # If ANY elevation is HORRIBLE, the resort is not skiable
        has_horrible = any(
            c.snow_quality == SnowQuality.HORRIBLE or c.snow_quality == "horrible"
            for c in conditions
        )
        if has_horrible:
            overall_quality = SnowQuality.HORRIBLE
        else:
            total_score = 0
            count = 0
            for c in conditions:
                quality = c.snow_quality
                if isinstance(quality, str):
                    quality = SnowQuality(quality)
                total_score += quality_scores.get(quality, 0)
                count += 1

            if count > 0:
                avg_score = total_score / count
                if avg_score >= 5.5:
                    overall_quality = SnowQuality.EXCELLENT
                elif avg_score >= 4.5:
                    overall_quality = SnowQuality.GOOD
                elif avg_score >= 3.5:
                    overall_quality = SnowQuality.FAIR
                elif avg_score >= 2.5:
                    overall_quality = SnowQuality.POOR
                elif avg_score >= 1.5:
                    overall_quality = SnowQuality.BAD
                else:
                    overall_quality = SnowQuality.HORRIBLE
            else:
                overall_quality = SnowQuality.UNKNOWN

        # Get representative condition (prefer mid elevation)
        representative = None
        for c in conditions:
            level = c.elevation_level
            if level == "mid":
                representative = c
                break
        if not representative:
            for c in conditions:
                level = c.elevation_level
                if level == "base":
                    representative = c
                    break
        if not representative and conditions:
            representative = conditions[0]

        return {
            "resort_id": resort.resort_id,
            "overall_quality": (
                overall_quality.value
                if hasattr(overall_quality, "value")
                else overall_quality
            ),
            "last_updated": max(c.timestamp for c in conditions)
            if conditions
            else None,
            "temperature_c": (
                representative.current_temp_celsius if representative else None
            ),
            "snowfall_fresh_cm": (
                representative.snowfall_after_freeze_cm if representative else None
            ),
            "snowfall_24h_cm": (
                representative.snowfall_24h_cm if representative else None
            ),
        }

    def _upload_to_s3(self, key: str, content: str) -> None:
        """Upload content to S3 with appropriate headers.

        Args:
            key: S3 object key
            content: JSON content to upload
        """
        try:
            s3_client.put_object(
                Bucket=self.website_bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="application/json",
                CacheControl="public, max-age=3600",  # 1 hour cache
            )
            logger.info(f"Uploaded {key} to s3://{self.website_bucket}/{key}")
        except ClientError as e:
            logger.error(f"Failed to upload {key} to S3: {e}")
            raise


def generate_static_json_api() -> dict[str, Any]:
    """Main function to generate all static JSON files.

    This is the entry point called by the weather processor after
    weather data processing completes.

    Returns:
        Dict with generation results
    """
    generator = StaticJsonGenerator()
    return generator.generate_all()
