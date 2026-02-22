"""Service for managing user-submitted condition reports."""

import logging
from datetime import UTC, datetime, timedelta

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from ulid import ULID

from models.condition_report import (
    ConditionReport,
    ConditionReportRequest,
    ConditionReportResponse,
    ConditionType,
)
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb

logger = logging.getLogger(__name__)

# Reports expire after 1 year
REPORT_TTL_DAYS = 365

# Rate limit: max reports per user per resort per day
MAX_REPORTS_PER_DAY = 5


class ConditionReportService:
    """Service for submitting and querying user condition reports."""

    def __init__(self, table):
        """Initialize the condition report service.

        Args:
            table: DynamoDB table for condition reports
        """
        self.table = table

    def submit_report(
        self, resort_id: str, user_id: str, request: ConditionReportRequest
    ) -> ConditionReport:
        """Submit a new condition report.

        Args:
            resort_id: ID of the resort
            user_id: ID of the user submitting the report
            request: The condition report request data

        Returns:
            Created ConditionReport object

        Raises:
            ValueError: If rate limit is exceeded
            Exception: On database errors
        """
        # Check rate limit
        if self._is_rate_limited(resort_id, user_id):
            raise ValueError(
                f"Rate limit exceeded: maximum {MAX_REPORTS_PER_DAY} reports per day per resort"
            )

        now = datetime.now(UTC)
        report = ConditionReport(
            resort_id=resort_id,
            report_id=str(ULID()),
            user_id=user_id,
            condition_type=request.condition_type,
            score=request.score,
            comment=request.comment,
            elevation_level=request.elevation_level,
            created_at=now.isoformat(),
            expires_at=int((now + timedelta(days=REPORT_TTL_DAYS)).timestamp()),
        )

        try:
            item = report.model_dump()
            # Serialize enum to its value for DynamoDB
            item["condition_type"] = report.condition_type.value
            item = prepare_for_dynamodb(item)
            self.table.put_item(Item=item)
            return report
        except ClientError as e:
            logger.error("Failed to submit condition report: %s", e)
            raise Exception(f"Failed to submit condition report: {e}")

    def get_reports_for_resort(
        self, resort_id: str, limit: int = 20
    ) -> list[ConditionReport]:
        """Get recent condition reports for a resort.

        Args:
            resort_id: ID of the resort
            limit: Maximum number of reports to return

        Returns:
            List of ConditionReport objects, sorted by most recent first
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key("resort_id").eq(resort_id),
                ScanIndexForward=False,  # Most recent first (descending by report_id/ULID)
                Limit=limit,
            )

            reports = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                reports.append(ConditionReport(**parsed))

            return reports

        except ClientError as e:
            logger.error("Failed to get reports for resort %s: %s", resort_id, e)
            raise Exception(f"Failed to get reports: {e}")

    def get_reports_by_user(
        self, user_id: str, limit: int = 50
    ) -> list[ConditionReport]:
        """Get condition reports submitted by a specific user.

        Args:
            user_id: ID of the user
            limit: Maximum number of reports to return

        Returns:
            List of ConditionReport objects, sorted by most recent first
        """
        try:
            response = self.table.query(
                IndexName="UserIdIndex",
                KeyConditionExpression=Key("user_id").eq(user_id),
                ScanIndexForward=False,
                Limit=limit,
            )

            reports = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                reports.append(ConditionReport(**parsed))

            return reports

        except ClientError as e:
            logger.error("Failed to get reports for user %s: %s", user_id, e)
            raise Exception(f"Failed to get user reports: {e}")

    def delete_report(self, resort_id: str, report_id: str, user_id: str) -> bool:
        """Delete a condition report (only by the user who submitted it).

        Args:
            resort_id: ID of the resort
            report_id: ID of the report to delete
            user_id: ID of the user requesting deletion (must be the author)

        Returns:
            True if deleted, False if not found or not authorized
        """
        try:
            self.table.delete_item(
                Key={"resort_id": resort_id, "report_id": report_id},
                ConditionExpression="attribute_exists(report_id) AND user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            logger.error("Failed to delete condition report: %s", e)
            raise Exception(f"Failed to delete condition report: {e}")

    def get_report_summary(self, resort_id: str) -> dict:
        """Get a summary of recent condition reports for a resort.

        Computes average score, most common condition type, and report count
        from the last 7 days.

        Args:
            resort_id: ID of the resort

        Returns:
            Dictionary with summary statistics:
            - average_score: float or None
            - most_common_type: str or None
            - report_count: int
            - last_7_days: bool (always True, indicates the time window)
        """
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        cutoff_iso = seven_days_ago.isoformat()

        try:
            # Query all reports for this resort (ULID sort key is time-ordered)
            response = self.table.query(
                KeyConditionExpression=Key("resort_id").eq(resort_id),
                ScanIndexForward=False,
            )

            # Filter to last 7 days
            recent_reports = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                if parsed.get("created_at", "") >= cutoff_iso:
                    recent_reports.append(parsed)

            if not recent_reports:
                return {
                    "average_score": None,
                    "most_common_type": None,
                    "report_count": 0,
                    "last_7_days": True,
                }

            # Calculate average score
            scores = [r["score"] for r in recent_reports]
            avg_score = round(sum(scores) / len(scores), 1)

            # Find most common condition type
            type_counts: dict[str, int] = {}
            for r in recent_reports:
                ct = r.get("condition_type", "")
                type_counts[ct] = type_counts.get(ct, 0) + 1

            most_common = max(type_counts, key=type_counts.get)

            return {
                "average_score": avg_score,
                "most_common_type": most_common,
                "report_count": len(recent_reports),
                "last_7_days": True,
            }

        except ClientError as e:
            logger.error("Failed to get report summary for %s: %s", resort_id, e)
            raise Exception(f"Failed to get report summary: {e}")

    def _is_rate_limited(self, resort_id: str, user_id: str) -> bool:
        """Check if the user has exceeded the daily report limit for a resort.

        Args:
            resort_id: ID of the resort
            user_id: ID of the user

        Returns:
            True if rate limited, False otherwise
        """
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_iso = today_start.isoformat()

        try:
            # Query reports for this resort, then filter by user and date
            response = self.table.query(
                KeyConditionExpression=Key("resort_id").eq(resort_id),
                FilterExpression="user_id = :uid AND created_at >= :today",
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":today": today_iso,
                },
                # Use higher limit to account for DynamoDB filter behavior
                # DynamoDB applies Limit BEFORE FilterExpression
                Limit=100,
            )

            count = len(response.get("Items", []))
            return count >= MAX_REPORTS_PER_DAY

        except ClientError:
            # If we can't check, allow the report (fail open)
            logger.warning(
                "Failed to check rate limit for user %s at resort %s",
                user_id,
                resort_id,
            )
            return False
