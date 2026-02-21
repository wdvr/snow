"""Daily snow history service for tracking snowfall over time."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DailyHistoryService:
    """Service for managing daily snow history records."""

    def __init__(self, table):
        self.table = table

    def record_daily_snapshot(
        self,
        resort_id: str,
        date: str,  # YYYY-MM-DD
        snowfall_24h_cm: float,
        snow_depth_cm: float | None,
        temp_min_c: float,
        temp_max_c: float,
        quality_score: float | None,
        snow_quality: str,
        wind_speed_kmh: float | None = None,
    ) -> bool:
        """Record or update the daily snapshot for a resort.

        Uses put_item - if a record for this date already exists,
        it will be updated with the latest data (processor runs hourly).
        """
        try:
            item: dict[str, Any] = {
                "resort_id": resort_id,
                "date": date,
                "snowfall_24h_cm": Decimal(str(round(snowfall_24h_cm, 1))),
                "temp_min_c": Decimal(str(round(temp_min_c, 1))),
                "temp_max_c": Decimal(str(round(temp_max_c, 1))),
                "snow_quality": snow_quality,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            if snow_depth_cm is not None:
                item["snow_depth_cm"] = Decimal(str(round(snow_depth_cm, 1)))
            if quality_score is not None:
                item["quality_score"] = Decimal(str(round(quality_score, 2)))
            if wind_speed_kmh is not None:
                item["wind_speed_kmh"] = Decimal(str(round(wind_speed_kmh, 1)))

            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"Error recording daily snapshot for {resort_id}/{date}: {e}")
            return False

    def get_history(
        self,
        resort_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 90,
    ) -> list[dict]:
        """Get daily history for a resort within a date range.

        Args:
            resort_id: Resort identifier
            start_date: Start date (YYYY-MM-DD), defaults to 90 days ago
            end_date: End date (YYYY-MM-DD), defaults to today
            limit: Max records to return

        Returns:
            List of daily history records, sorted by date ascending
        """
        try:
            if not start_date:
                from datetime import timedelta

                start_date = (datetime.now(UTC) - timedelta(days=limit)).strftime(
                    "%Y-%m-%d"
                )

            if end_date:
                key_condition = Key("resort_id").eq(resort_id) & Key("date").between(
                    start_date, end_date
                )
            else:
                key_condition = Key("resort_id").eq(resort_id) & Key("date").gte(
                    start_date
                )

            response = self.table.query(
                KeyConditionExpression=key_condition,
                ScanIndexForward=True,  # Ascending by date
                Limit=limit,
            )

            items = response.get("Items", [])
            return [self._convert_decimals(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying history for {resort_id}: {e}")
            return []

    def get_season_summary(self, resort_id: str, season_start: str) -> dict:
        """Get season summary statistics.

        Args:
            resort_id: Resort identifier
            season_start: Season start date (YYYY-MM-DD), e.g. "2025-10-01"

        Returns:
            dict with season stats: total_snowfall, snow_days, avg_quality, etc.
        """
        history = self.get_history(resort_id, start_date=season_start, limit=365)

        if not history:
            return {
                "total_snowfall_cm": 0,
                "snow_days": 0,
                "avg_quality_score": None,
                "best_day": None,
                "days_tracked": 0,
            }

        total_snow = sum(d.get("snowfall_24h_cm", 0) for d in history)
        snow_days = sum(1 for d in history if d.get("snowfall_24h_cm", 0) >= 1.0)
        quality_scores = [d["quality_score"] for d in history if d.get("quality_score")]
        avg_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else None
        )

        best_day = (
            max(history, key=lambda d: d.get("snowfall_24h_cm", 0)) if history else None
        )

        return {
            "total_snowfall_cm": round(total_snow, 1),
            "snow_days": snow_days,
            "avg_quality_score": (round(avg_quality, 2) if avg_quality else None),
            "best_day": best_day,
            "days_tracked": len(history),
        }

    def _convert_decimals(self, item: dict) -> dict:
        """Convert DynamoDB Decimal values to Python float."""
        result = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, dict):
                result[key] = self._convert_decimals(value)
            else:
                result[key] = value
        return result
