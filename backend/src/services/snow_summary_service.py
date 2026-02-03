"""Snow summary service for persisting accumulated snow data.

This service manages the snow_summary table which stores:
- Last freeze date for each resort/elevation
- Accumulated snowfall since last freeze
- Total season snowfall
- Season start tracking

The snow summary table NEVER expires (no TTL), ensuring we maintain
accurate season-long accumulation data that survives the weather
conditions table TTL (60 days).
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SnowSummaryService:
    """Service for managing persistent snow accumulation summaries.

    The snow summary table stores long-term snow data that survives
    the weather conditions TTL. This allows for:
    - Unlimited accumulation tracking (full season if no freeze)
    - Accurate freeze date persistence across weather data expiration
    - Season-long statistics
    """

    def __init__(self, table):
        """Initialize the service with DynamoDB table.

        Args:
            table: boto3 DynamoDB Table resource
        """
        self.table = table

    def get_summary(self, resort_id: str, elevation_level: str) -> dict | None:
        """Get the current snow summary for a resort/elevation.

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)

        Returns:
            dict with summary data or None if no summary exists
        """
        try:
            response = self.table.get_item(
                Key={
                    "resort_id": resort_id,
                    "elevation_level": elevation_level,
                }
            )
            item = response.get("Item")
            if item:
                # Convert Decimals to floats for easier use
                return self._convert_decimals(item)
            return None
        except ClientError as e:
            logger.error(
                f"Error fetching snow summary for {resort_id}/{elevation_level}: {e}"
            )
            return None

    def update_summary(
        self,
        resort_id: str,
        elevation_level: str,
        last_freeze_date: str | None,
        snowfall_since_freeze_cm: float,
        total_season_snowfall_cm: float,
        last_updated: str,
        season_start_date: str | None = None,
    ) -> bool:
        """Update the snow summary with latest data.

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)
            last_freeze_date: ISO timestamp of last freeze event (or None)
            snowfall_since_freeze_cm: Accumulated snow since last freeze
            total_season_snowfall_cm: Total snowfall this season
            last_updated: ISO timestamp of this update
            season_start_date: When tracking started (YYYY-MM-DD format)

        Returns:
            True if update successful, False otherwise
        """
        try:
            item = {
                "resort_id": resort_id,
                "elevation_level": elevation_level,
                "snowfall_since_freeze_cm": Decimal(
                    str(round(snowfall_since_freeze_cm, 2))
                ),
                "total_season_snowfall_cm": Decimal(
                    str(round(total_season_snowfall_cm, 2))
                ),
                "last_updated": last_updated,
            }

            if last_freeze_date:
                item["last_freeze_date"] = last_freeze_date

            if season_start_date:
                item["season_start_date"] = season_start_date

            self.table.put_item(Item=item)
            logger.debug(
                f"Updated snow summary for {resort_id}/{elevation_level}: "
                f"freeze={last_freeze_date}, snow_since_freeze={snowfall_since_freeze_cm}cm"
            )
            return True

        except ClientError as e:
            logger.error(
                f"Error updating snow summary for {resort_id}/{elevation_level}: {e}"
            )
            return False

    def record_freeze_event(
        self,
        resort_id: str,
        elevation_level: str,
        freeze_date: str,
    ) -> bool:
        """Record a new freeze event, which resets the accumulation.

        When a freeze event is detected:
        1. Update last_freeze_date to the new freeze date
        2. Reset snowfall_since_freeze_cm to 0
        3. Keep total_season_snowfall_cm unchanged (it accumulates all season)

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)
            freeze_date: ISO timestamp of the freeze event

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Use UpdateItem to atomically update just the freeze date and reset accumulation
            self.table.update_item(
                Key={
                    "resort_id": resort_id,
                    "elevation_level": elevation_level,
                },
                UpdateExpression=(
                    "SET last_freeze_date = :freeze_date, "
                    "snowfall_since_freeze_cm = :zero, "
                    "last_updated = :now"
                ),
                ExpressionAttributeValues={
                    ":freeze_date": freeze_date,
                    ":zero": Decimal("0"),
                    ":now": datetime.now(UTC).isoformat(),
                },
            )
            logger.info(
                f"Recorded freeze event for {resort_id}/{elevation_level} at {freeze_date}"
            )
            return True

        except ClientError as e:
            logger.error(
                f"Error recording freeze event for {resort_id}/{elevation_level}: {e}"
            )
            return False

    def add_snowfall(
        self,
        resort_id: str,
        elevation_level: str,
        new_snowfall_cm: float,
    ) -> bool:
        """Add new snowfall to both accumulators.

        This is used when snowfall is detected but no freeze event occurred.
        Adds to both snowfall_since_freeze_cm and total_season_snowfall_cm.

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)
            new_snowfall_cm: New snowfall amount to add

        Returns:
            True if update successful, False otherwise
        """
        if new_snowfall_cm <= 0:
            return True  # Nothing to add

        try:
            self.table.update_item(
                Key={
                    "resort_id": resort_id,
                    "elevation_level": elevation_level,
                },
                UpdateExpression=(
                    "SET snowfall_since_freeze_cm = if_not_exists(snowfall_since_freeze_cm, :zero) + :snow, "
                    "total_season_snowfall_cm = if_not_exists(total_season_snowfall_cm, :zero) + :snow, "
                    "last_updated = :now"
                ),
                ExpressionAttributeValues={
                    ":snow": Decimal(str(round(new_snowfall_cm, 2))),
                    ":zero": Decimal("0"),
                    ":now": datetime.now(UTC).isoformat(),
                },
            )
            logger.debug(
                f"Added {new_snowfall_cm}cm snowfall for {resort_id}/{elevation_level}"
            )
            return True

        except ClientError as e:
            logger.error(
                f"Error adding snowfall for {resort_id}/{elevation_level}: {e}"
            )
            return False

    def get_or_create_summary(
        self,
        resort_id: str,
        elevation_level: str,
    ) -> dict:
        """Get existing summary or create a new one with defaults.

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)

        Returns:
            dict with summary data (existing or newly created defaults)
        """
        existing = self.get_summary(resort_id, elevation_level)
        if existing:
            return existing

        # Create default summary
        now = datetime.now(UTC)
        default_summary = {
            "resort_id": resort_id,
            "elevation_level": elevation_level,
            "last_freeze_date": None,
            "snowfall_since_freeze_cm": 0.0,
            "total_season_snowfall_cm": 0.0,
            "season_start_date": now.strftime("%Y-%m-%d"),
            "last_updated": now.isoformat(),
        }

        # Try to save the default
        self.update_summary(
            resort_id=resort_id,
            elevation_level=elevation_level,
            last_freeze_date=None,
            snowfall_since_freeze_cm=0.0,
            total_season_snowfall_cm=0.0,
            last_updated=now.isoformat(),
            season_start_date=now.strftime("%Y-%m-%d"),
        )

        return default_summary

    def _convert_decimals(self, item: dict) -> dict:
        """Convert Decimal values to floats for easier use.

        Args:
            item: DynamoDB item with potential Decimal values

        Returns:
            dict with Decimals converted to floats
        """
        result = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, dict):
                result[key] = self._convert_decimals(value)
            else:
                result[key] = value
        return result

    def reset_for_new_season(
        self,
        resort_id: str,
        elevation_level: str,
        season_start_date: str,
    ) -> bool:
        """Reset summary for a new season.

        Clears all accumulation data and sets a new season start date.

        Args:
            resort_id: The resort identifier
            elevation_level: The elevation level (base, mid, top)
            season_start_date: New season start date (YYYY-MM-DD)

        Returns:
            True if reset successful, False otherwise
        """
        try:
            self.table.put_item(
                Item={
                    "resort_id": resort_id,
                    "elevation_level": elevation_level,
                    "last_freeze_date": None,
                    "snowfall_since_freeze_cm": Decimal("0"),
                    "total_season_snowfall_cm": Decimal("0"),
                    "season_start_date": season_start_date,
                    "last_updated": datetime.now(UTC).isoformat(),
                }
            )
            logger.info(
                f"Reset snow summary for {resort_id}/{elevation_level} "
                f"for new season starting {season_start_date}"
            )
            return True

        except ClientError as e:
            logger.error(
                f"Error resetting snow summary for {resort_id}/{elevation_level}: {e}"
            )
            return False
