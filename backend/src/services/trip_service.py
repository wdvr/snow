"""Trip planning service."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError

from models.trip import (
    Trip,
    TripAlert,
    TripAlertType,
    TripConditionSnapshot,
    TripCreate,
    TripStatus,
    TripUpdate,
)
from models.weather import SnowQuality
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb


class TripService:
    """Service for managing ski trip planning."""

    # Auto-delete completed/cancelled trips after 1 year
    COMPLETED_TRIP_TTL_DAYS = 365

    def __init__(self, table, resort_service=None, weather_service=None):
        """Initialize the trip service.

        Args:
            table: DynamoDB table for trips
            resort_service: Optional ResortService for validating resorts
            weather_service: Optional WeatherService for getting conditions
        """
        self.table = table
        self.resort_service = resort_service
        self.weather_service = weather_service

    def create_trip(self, user_id: str, trip_data: TripCreate) -> Trip:
        """Create a new trip.

        Args:
            user_id: ID of the user creating the trip
            trip_data: Trip creation data

        Returns:
            Created Trip object

        Raises:
            ValueError: If resort doesn't exist
            Exception: On database errors
        """
        # Validate resort exists and get name
        resort_name = trip_data.resort_id  # Default to ID if service not available
        if self.resort_service:
            resort = self.resort_service.get_resort(trip_data.resort_id)
            if not resort:
                raise ValueError(f"Resort {trip_data.resort_id} not found")
            resort_name = resort.name

        # Get current conditions for snapshot
        conditions_snapshot = None
        if self.weather_service:
            conditions_snapshot = self._create_conditions_snapshot(trip_data.resort_id)

        # Create trip
        now = datetime.now(UTC).isoformat()
        trip = Trip(
            trip_id=str(uuid.uuid4()),
            user_id=user_id,
            resort_id=trip_data.resort_id,
            resort_name=resort_name,
            start_date=trip_data.start_date,
            end_date=trip_data.end_date,
            status=TripStatus.PLANNED,
            notes=trip_data.notes,
            party_size=trip_data.party_size,
            conditions_at_creation=conditions_snapshot,
            latest_conditions=conditions_snapshot,
            alerts=[],
            alert_preferences=trip_data.alert_preferences or {
                "powder_alerts": True,
                "warm_spell_warnings": True,
                "condition_updates": True,
                "trip_reminders": True,
            },
            created_at=now,
            updated_at=now,
        )

        # Save to database
        try:
            item = trip.model_dump()
            item = prepare_for_dynamodb(item)
            self.table.put_item(Item=item)
            return trip
        except ClientError as e:
            raise Exception(f"Failed to create trip: {str(e)}")

    def get_trip(self, trip_id: str, user_id: str) -> Trip | None:
        """Get a trip by ID.

        Args:
            trip_id: Trip ID
            user_id: User ID (for authorization)

        Returns:
            Trip object or None if not found
        """
        try:
            response = self.table.get_item(
                Key={"trip_id": trip_id, "user_id": user_id}
            )
            item = response.get("Item")
            if not item:
                return None

            parsed = parse_from_dynamodb(item)
            return Trip(**parsed)
        except ClientError as e:
            raise Exception(f"Failed to get trip: {str(e)}")

    def get_user_trips(
        self,
        user_id: str,
        status: TripStatus | None = None,
        include_past: bool = True,
    ) -> list[Trip]:
        """Get all trips for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            include_past: Whether to include past trips

        Returns:
            List of Trip objects sorted by start_date
        """
        try:
            # Query by user_id (GSI)
            response = self.table.query(
                IndexName="UserIdIndex",
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
            )

            trips = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                trip = Trip(**parsed)

                # Apply filters
                if status and trip.status != status:
                    continue
                if not include_past and trip.is_past:
                    continue

                trips.append(trip)

            # Sort by start_date (upcoming first)
            trips.sort(key=lambda t: t.start_date)
            return trips

        except ClientError as e:
            raise Exception(f"Failed to get trips: {str(e)}")

    def update_trip(
        self,
        trip_id: str,
        user_id: str,
        update_data: TripUpdate,
    ) -> Trip:
        """Update a trip.

        Args:
            trip_id: Trip ID
            user_id: User ID (for authorization)
            update_data: Fields to update

        Returns:
            Updated Trip object

        Raises:
            ValueError: If trip not found
            Exception: On database errors
        """
        # Get existing trip
        trip = self.get_trip(trip_id, user_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)

        for field, value in update_dict.items():
            setattr(trip, field, value)

        trip.updated_at = datetime.now(UTC).isoformat()

        # Set TTL for completed/cancelled trips
        if trip.status in (TripStatus.COMPLETED, TripStatus.CANCELLED):
            ttl_time = datetime.now(UTC) + timedelta(days=self.COMPLETED_TRIP_TTL_DAYS)
            trip.ttl = int(ttl_time.timestamp())

        # Save
        try:
            item = trip.model_dump()
            item = prepare_for_dynamodb(item)
            self.table.put_item(Item=item)
            return trip
        except ClientError as e:
            raise Exception(f"Failed to update trip: {str(e)}")

    def delete_trip(self, trip_id: str, user_id: str) -> bool:
        """Delete a trip.

        Args:
            trip_id: Trip ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        try:
            self.table.delete_item(
                Key={"trip_id": trip_id, "user_id": user_id},
                ConditionExpression="attribute_exists(trip_id)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise Exception(f"Failed to delete trip: {str(e)}")

    def add_alert(
        self,
        trip_id: str,
        user_id: str,
        alert_type: TripAlertType,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> TripAlert:
        """Add an alert to a trip.

        Args:
            trip_id: Trip ID
            user_id: User ID
            alert_type: Type of alert
            message: Alert message
            data: Additional alert data

        Returns:
            Created TripAlert
        """
        trip = self.get_trip(trip_id, user_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        alert = TripAlert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            message=message,
            created_at=datetime.now(UTC).isoformat(),
            is_read=False,
            data=data or {},
        )

        trip.alerts.append(alert)
        trip.updated_at = datetime.now(UTC).isoformat()

        # Save
        item = trip.model_dump()
        item = prepare_for_dynamodb(item)
        self.table.put_item(Item=item)

        return alert

    def mark_alerts_read(self, trip_id: str, user_id: str, alert_ids: list[str] | None = None) -> int:
        """Mark alerts as read.

        Args:
            trip_id: Trip ID
            user_id: User ID
            alert_ids: Specific alert IDs to mark (None = all)

        Returns:
            Number of alerts marked as read
        """
        trip = self.get_trip(trip_id, user_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        count = 0
        for alert in trip.alerts:
            if alert_ids is None or alert.alert_id in alert_ids:
                if not alert.is_read:
                    alert.is_read = True
                    count += 1

        if count > 0:
            trip.updated_at = datetime.now(UTC).isoformat()
            item = trip.model_dump()
            item = prepare_for_dynamodb(item)
            self.table.put_item(Item=item)

        return count

    def update_trip_conditions(self, trip_id: str, user_id: str) -> Trip:
        """Update the latest conditions for a trip.

        Args:
            trip_id: Trip ID
            user_id: User ID

        Returns:
            Updated Trip with new conditions snapshot
        """
        trip = self.get_trip(trip_id, user_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        if self.weather_service:
            old_conditions = trip.latest_conditions
            new_conditions = self._create_conditions_snapshot(trip.resort_id)

            if new_conditions:
                trip.latest_conditions = new_conditions
                trip.updated_at = datetime.now(UTC).isoformat()

                # Check for significant changes and add alerts
                self._check_condition_changes(trip, old_conditions, new_conditions)

                # Save
                item = trip.model_dump()
                item = prepare_for_dynamodb(item)
                self.table.put_item(Item=item)

        return trip

    def get_upcoming_trips_for_alerts(self, days_ahead: int = 7) -> list[Trip]:
        """Get all trips starting within the specified days for alert processing.

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming trips
        """
        # This would require a GSI on start_date for efficient querying
        # For now, scan and filter (not ideal for large datasets)
        try:
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            future = (datetime.now(UTC) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

            response = self.table.scan(
                FilterExpression="start_date >= :today AND start_date <= :future AND #s = :planned",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":today": today,
                    ":future": future,
                    ":planned": TripStatus.PLANNED.value,
                },
            )

            trips = []
            for item in response.get("Items", []):
                parsed = parse_from_dynamodb(item)
                trips.append(Trip(**parsed))

            return trips

        except ClientError as e:
            raise Exception(f"Failed to get upcoming trips: {str(e)}")

    def _create_conditions_snapshot(self, resort_id: str) -> TripConditionSnapshot | None:
        """Create a conditions snapshot for a resort."""
        if not self.weather_service:
            return None

        try:
            conditions = self.weather_service.get_conditions_for_resort(resort_id, hours_back=6)
            if not conditions:
                return None

            # Aggregate conditions
            qualities = [c.snow_quality for c in conditions]
            fresh_snow = sum(c.snowfall_after_freeze_cm or c.fresh_snow_cm for c in conditions) / len(conditions)
            predicted = max((c.predicted_snow_72h_cm or 0) for c in conditions)
            temps = [c.current_temp_celsius for c in conditions]

            # Get best quality
            quality_ranks = {
                SnowQuality.EXCELLENT: 6,
                SnowQuality.GOOD: 5,
                SnowQuality.FAIR: 4,
                SnowQuality.POOR: 3,
                SnowQuality.BAD: 2,
                SnowQuality.HORRIBLE: 1,
                SnowQuality.UNKNOWN: 0,
            }
            best_quality = max(qualities, key=lambda q: quality_ranks.get(q, 0))

            return TripConditionSnapshot(
                timestamp=datetime.now(UTC).isoformat(),
                snow_quality=best_quality.value if hasattr(best_quality, "value") else str(best_quality),
                fresh_snow_cm=round(fresh_snow, 1),
                predicted_snow_cm=round(predicted, 1),
                temperature_celsius=round(sum(temps) / len(temps), 1) if temps else None,
            )

        except Exception:
            return None

    def _check_condition_changes(
        self,
        trip: Trip,
        old: TripConditionSnapshot | None,
        new: TripConditionSnapshot | None,
    ) -> None:
        """Check for significant condition changes and add alerts."""
        if not old or not new:
            return

        # Check alert preferences
        prefs = trip.alert_preferences

        # Powder alert: significant new snow
        if prefs.get("powder_alerts", True):
            snow_increase = new.fresh_snow_cm - old.fresh_snow_cm
            if snow_increase >= 10:
                self.add_alert(
                    trip.trip_id,
                    trip.user_id,
                    TripAlertType.POWDER_ALERT,
                    f"Fresh powder alert! {snow_increase:.0f}cm of new snow at {trip.resort_name}",
                    {"snow_increase_cm": snow_increase},
                )
            elif new.predicted_snow_cm >= 20 and old.predicted_snow_cm < 20:
                self.add_alert(
                    trip.trip_id,
                    trip.user_id,
                    TripAlertType.POWDER_ALERT,
                    f"Big storm coming! {new.predicted_snow_cm:.0f}cm predicted before your trip",
                    {"predicted_cm": new.predicted_snow_cm},
                )

        # Warm spell warning
        if prefs.get("warm_spell_warnings", True):
            if (
                old.temperature_celsius is not None
                and new.temperature_celsius is not None
                and new.temperature_celsius >= 3
                and old.temperature_celsius < 3
            ):
                self.add_alert(
                    trip.trip_id,
                    trip.user_id,
                    TripAlertType.WARM_SPELL,
                    f"Warm spell warning: {new.temperature_celsius:.0f}°C at {trip.resort_name}. Conditions may become icy.",
                    {"temperature_celsius": new.temperature_celsius},
                )

        # Condition changes
        if prefs.get("condition_updates", True):
            quality_ranks = {
                "excellent": 6, "good": 5, "fair": 4,
                "poor": 3, "bad": 2, "horrible": 1, "unknown": 0,
            }
            old_rank = quality_ranks.get(old.snow_quality, 0)
            new_rank = quality_ranks.get(new.snow_quality, 0)

            if new_rank - old_rank >= 2:  # Significant improvement
                self.add_alert(
                    trip.trip_id,
                    trip.user_id,
                    TripAlertType.CONDITIONS_IMPROVED,
                    f"Conditions improved at {trip.resort_name}! Now rated {new.snow_quality}",
                    {"old_quality": old.snow_quality, "new_quality": new.snow_quality},
                )
            elif old_rank - new_rank >= 2:  # Significant degradation
                self.add_alert(
                    trip.trip_id,
                    trip.user_id,
                    TripAlertType.CONDITIONS_DEGRADED,
                    f"Conditions changed at {trip.resort_name}: now rated {new.snow_quality}",
                    {"old_quality": old.snow_quality, "new_quality": new.snow_quality},
                )
