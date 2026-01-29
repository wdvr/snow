"""Tests for TripService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from models.trip import (
    Trip,
    TripAlertType,
    TripConditionSnapshot,
    TripCreate,
    TripStatus,
    TripUpdate,
)
from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition
from services.trip_service import TripService


class TestTripService:
    """Test cases for TripService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = Mock()
        table.put_item.return_value = {}
        table.get_item.return_value = {"Item": None}
        table.query.return_value = {"Items": []}
        table.delete_item.return_value = {}
        table.scan.return_value = {"Items": []}
        return table

    @pytest.fixture
    def mock_resort_service(self):
        """Create a mock ResortService."""
        from models.resort import ElevationLevel, ElevationPoint, Resort

        mock_resort = Resort(
            resort_id="big-white",
            name="Big White Ski Resort",
            country="CA",
            region="BC",
            elevation_points=[
                ElevationPoint(
                    level=ElevationLevel.MID,
                    elevation_meters=1800,
                    elevation_feet=5906,
                    latitude=49.7200,
                    longitude=-118.9300,
                ),
            ],
            timezone="America/Vancouver",
        )
        service = Mock()
        service.get_resort.return_value = mock_resort
        return service

    @pytest.fixture
    def mock_weather_service(self):
        """Create a mock WeatherService."""
        service = Mock()
        service.get_conditions_for_resort.return_value = [
            WeatherCondition(
                resort_id="big-white",
                elevation_level="mid",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=-5.0,
                min_temp_celsius=-10.0,
                max_temp_celsius=-2.0,
                snowfall_24h_cm=10.0,
                snowfall_48h_cm=20.0,
                snowfall_72h_cm=30.0,
                predicted_snow_72h_cm=15.0,
                snowfall_after_freeze_cm=10.0,
                snow_quality=SnowQuality.EXCELLENT,
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=10.0,
                data_source="test",
                source_confidence=ConfidenceLevel.HIGH,
            )
        ]
        return service

    @pytest.fixture
    def trip_service(self, mock_table, mock_resort_service, mock_weather_service):
        """Create a TripService with mocked dependencies."""
        return TripService(
            table=mock_table,
            resort_service=mock_resort_service,
            weather_service=mock_weather_service,
        )

    @pytest.fixture
    def sample_trip_create(self):
        """Create sample trip creation data."""
        future_date = (datetime.now(UTC) + timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = (datetime.now(UTC) + timedelta(days=12)).strftime("%Y-%m-%d")
        return TripCreate(
            resort_id="big-white",
            start_date=future_date,
            end_date=end_date,
            notes="Excited for this trip!",
            party_size=4,
        )

    @pytest.fixture
    def sample_trip_data(self):
        """Create sample trip data as stored in DynamoDB."""
        future_date = (datetime.now(UTC) + timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = (datetime.now(UTC) + timedelta(days=12)).strftime("%Y-%m-%d")
        return {
            "trip_id": "test-trip-123",
            "user_id": "test-user-456",
            "resort_id": "big-white",
            "resort_name": "Big White Ski Resort",
            "start_date": future_date,
            "end_date": end_date,
            "status": "planned",
            "notes": "Test trip",
            "party_size": 2,
            "conditions_at_creation": {
                "timestamp": "2026-01-20T10:00:00Z",
                "snow_quality": "excellent",
                "fresh_snow_cm": 10.0,
                "predicted_snow_cm": 15.0,
                "temperature_celsius": -5.0,
            },
            "latest_conditions": {
                "timestamp": "2026-01-20T10:00:00Z",
                "snow_quality": "excellent",
                "fresh_snow_cm": 10.0,
                "predicted_snow_cm": 15.0,
                "temperature_celsius": -5.0,
            },
            "alerts": [],
            "alert_preferences": {
                "powder_alerts": True,
                "warm_spell_warnings": True,
                "condition_updates": True,
                "trip_reminders": True,
            },
            "created_at": "2026-01-20T08:00:00Z",
            "updated_at": "2026-01-20T08:00:00Z",
        }

    def test_create_trip_success(
        self, trip_service, mock_table, mock_resort_service, sample_trip_create
    ):
        """Test successful trip creation."""
        trip = trip_service.create_trip("test-user-456", sample_trip_create)

        assert trip.user_id == "test-user-456"
        assert trip.resort_id == "big-white"
        assert trip.resort_name == "Big White Ski Resort"
        assert trip.status == TripStatus.PLANNED
        assert trip.party_size == 4
        assert trip.notes == "Excited for this trip!"
        mock_table.put_item.assert_called_once()
        mock_resort_service.get_resort.assert_called_once_with("big-white")

    def test_create_trip_captures_conditions(
        self, trip_service, mock_weather_service, sample_trip_create
    ):
        """Test that trip creation captures current conditions."""
        trip = trip_service.create_trip("test-user", sample_trip_create)

        assert trip.conditions_at_creation is not None
        assert trip.conditions_at_creation.snow_quality == "excellent"
        assert trip.conditions_at_creation.fresh_snow_cm == 10.0
        mock_weather_service.get_conditions_for_resort.assert_called()

    def test_create_trip_resort_not_found(
        self, trip_service, mock_resort_service, sample_trip_create
    ):
        """Test trip creation fails when resort doesn't exist."""
        mock_resort_service.get_resort.return_value = None

        with pytest.raises(ValueError, match="not found"):
            trip_service.create_trip("test-user", sample_trip_create)

    def test_create_trip_db_error(self, trip_service, mock_table, sample_trip_create):
        """Test handling of database errors during trip creation."""
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Error"}},
            "put_item",
        )

        with pytest.raises(Exception, match="Failed to create trip"):
            trip_service.create_trip("test-user", sample_trip_create)

    def test_get_trip_success(self, trip_service, mock_table, sample_trip_data):
        """Test successful trip retrieval."""
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        trip = trip_service.get_trip("test-trip-123", "test-user-456")

        assert trip is not None
        assert trip.trip_id == "test-trip-123"
        assert trip.user_id == "test-user-456"
        mock_table.get_item.assert_called_once_with(
            Key={"trip_id": "test-trip-123", "user_id": "test-user-456"}
        )

    def test_get_trip_not_found(self, trip_service, mock_table):
        """Test trip retrieval when trip doesn't exist."""
        mock_table.get_item.return_value = {}

        trip = trip_service.get_trip("non-existent", "test-user")

        assert trip is None

    def test_get_user_trips_success(self, trip_service, mock_table, sample_trip_data):
        """Test successful retrieval of user trips."""
        mock_table.query.return_value = {"Items": [sample_trip_data]}

        trips = trip_service.get_user_trips("test-user-456")

        assert len(trips) == 1
        assert trips[0].trip_id == "test-trip-123"
        mock_table.query.assert_called_once()

    def test_get_user_trips_with_status_filter(
        self, trip_service, mock_table, sample_trip_data
    ):
        """Test filtering trips by status."""
        mock_table.query.return_value = {"Items": [sample_trip_data]}

        # Filter for COMPLETED (sample is PLANNED)
        trips = trip_service.get_user_trips(
            "test-user-456", status=TripStatus.COMPLETED
        )

        # Should be empty since sample is PLANNED
        assert len(trips) == 0

    def test_get_user_trips_exclude_past(self, trip_service, mock_table):
        """Test excluding past trips."""
        past_date = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%d")
        past_trip = {
            "trip_id": "past-trip",
            "user_id": "test-user",
            "resort_id": "big-white",
            "resort_name": "Big White",
            "start_date": past_date,
            "end_date": past_date,
            "status": "completed",
            "party_size": 1,
            "alerts": [],
            "alert_preferences": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        mock_table.query.return_value = {"Items": [past_trip]}

        trips = trip_service.get_user_trips("test-user", include_past=False)

        assert len(trips) == 0

    def test_update_trip_success(self, trip_service, mock_table, sample_trip_data):
        """Test successful trip update."""
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        update = TripUpdate(notes="Updated notes", party_size=6)
        trip = trip_service.update_trip("test-trip-123", "test-user-456", update)

        assert trip.notes == "Updated notes"
        assert trip.party_size == 6
        assert mock_table.put_item.call_count == 1

    def test_update_trip_status_to_completed(
        self, trip_service, mock_table, sample_trip_data
    ):
        """Test updating trip status to completed sets TTL."""
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        update = TripUpdate(status=TripStatus.COMPLETED)
        trip = trip_service.update_trip("test-trip-123", "test-user-456", update)

        assert trip.status == TripStatus.COMPLETED
        assert trip.ttl is not None

    def test_update_trip_not_found(self, trip_service, mock_table):
        """Test updating non-existent trip."""
        mock_table.get_item.return_value = {}

        update = TripUpdate(notes="New notes")
        with pytest.raises(ValueError, match="not found"):
            trip_service.update_trip("non-existent", "test-user", update)

    def test_delete_trip_success(self, trip_service, mock_table):
        """Test successful trip deletion."""
        result = trip_service.delete_trip("test-trip-123", "test-user-456")

        assert result is True
        mock_table.delete_item.assert_called_once()

    def test_delete_trip_not_found(self, trip_service, mock_table):
        """Test deleting non-existent trip."""
        mock_table.delete_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Not found",
                }
            },
            "delete_item",
        )

        result = trip_service.delete_trip("non-existent", "test-user")

        assert result is False

    def test_add_alert_success(self, trip_service, mock_table, sample_trip_data):
        """Test adding an alert to a trip."""
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        alert = trip_service.add_alert(
            trip_id="test-trip-123",
            user_id="test-user-456",
            alert_type=TripAlertType.POWDER_ALERT,
            message="Fresh powder incoming!",
            data={"snow_cm": 20},
        )

        assert alert.alert_type == TripAlertType.POWDER_ALERT
        assert alert.message == "Fresh powder incoming!"
        assert alert.is_read is False
        assert "snow_cm" in alert.data

    def test_mark_alerts_read(self, trip_service, mock_table, sample_trip_data):
        """Test marking alerts as read."""
        # Add an alert to the trip data
        sample_trip_data["alerts"] = [
            {
                "alert_id": "alert-1",
                "alert_type": "powder_alert",
                "message": "Snow!",
                "created_at": "2026-01-20T10:00:00Z",
                "is_read": False,
                "data": {},
            },
            {
                "alert_id": "alert-2",
                "alert_type": "warm_spell",
                "message": "Warming!",
                "created_at": "2026-01-20T11:00:00Z",
                "is_read": False,
                "data": {},
            },
        ]
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        # Mark all as read
        count = trip_service.mark_alerts_read("test-trip-123", "test-user-456")

        assert count == 2

    def test_mark_specific_alerts_read(
        self, trip_service, mock_table, sample_trip_data
    ):
        """Test marking specific alerts as read."""
        sample_trip_data["alerts"] = [
            {
                "alert_id": "alert-1",
                "alert_type": "powder_alert",
                "message": "Snow!",
                "created_at": "2026-01-20T10:00:00Z",
                "is_read": False,
                "data": {},
            },
            {
                "alert_id": "alert-2",
                "alert_type": "warm_spell",
                "message": "Warming!",
                "created_at": "2026-01-20T11:00:00Z",
                "is_read": False,
                "data": {},
            },
        ]
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        # Mark only alert-1 as read
        count = trip_service.mark_alerts_read(
            "test-trip-123", "test-user-456", alert_ids=["alert-1"]
        )

        assert count == 1

    def test_update_trip_conditions(
        self, trip_service, mock_table, mock_weather_service, sample_trip_data
    ):
        """Test updating trip conditions."""
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        trip = trip_service.update_trip_conditions("test-trip-123", "test-user-456")

        assert trip.latest_conditions is not None
        mock_weather_service.get_conditions_for_resort.assert_called()

    def test_trip_properties(self):
        """Test Trip model computed properties."""
        # Use local time to match days_until_trip property calculation
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        trip = Trip(
            trip_id="test",
            user_id="user",
            resort_id="resort",
            resort_name="Resort",
            start_date=future_date,
            end_date=end_date,
            status=TripStatus.PLANNED,
            party_size=1,
            alerts=[],
            alert_preferences={},
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )

        assert trip.days_until_trip == 5
        assert trip.trip_duration_days == 3
        assert trip.is_upcoming is True
        assert trip.is_past is False

    def test_trip_create_validation(self):
        """Test TripCreate validation."""
        # Valid dates
        trip = TripCreate(
            resort_id="test",
            start_date="2026-02-01",
            end_date="2026-02-03",
        )
        assert trip.start_date == "2026-02-01"

        # Invalid date format
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TripCreate(
                resort_id="test",
                start_date="02-01-2026",  # Wrong format
                end_date="2026-02-03",
            )

        # End before start
        with pytest.raises(ValueError, match="End date must be on or after"):
            TripCreate(
                resort_id="test",
                start_date="2026-02-05",
                end_date="2026-02-01",  # Before start
            )

    def test_condition_change_alerts(
        self, trip_service, mock_table, mock_weather_service, sample_trip_data
    ):
        """Test that significant condition changes trigger alerts."""
        # Set up initial conditions with warm temps
        sample_trip_data["latest_conditions"]["temperature_celsius"] = -5.0
        sample_trip_data["latest_conditions"]["snow_quality"] = "fair"
        mock_table.get_item.return_value = {"Item": sample_trip_data}

        # Mock new conditions with warming (above ice threshold)
        mock_weather_service.get_conditions_for_resort.return_value = [
            WeatherCondition(
                resort_id="big-white",
                elevation_level="mid",
                timestamp=datetime.now(UTC).isoformat(),
                current_temp_celsius=5.0,  # Above threshold
                min_temp_celsius=0.0,
                max_temp_celsius=7.0,
                snowfall_24h_cm=0.0,
                snowfall_48h_cm=0.0,
                snowfall_72h_cm=0.0,
                snowfall_after_freeze_cm=0.0,
                snow_quality=SnowQuality.BAD,  # Degraded
                confidence_level=ConfidenceLevel.HIGH,
                fresh_snow_cm=0.0,
                data_source="test",
                source_confidence=ConfidenceLevel.HIGH,
            )
        ]

        trip = trip_service.update_trip_conditions("test-trip-123", "test-user-456")

        # Should have generated a warm spell alert
        has_warm_alert = any(
            alert.alert_type == TripAlertType.WARM_SPELL for alert in trip.alerts
        )
        assert has_warm_alert or trip.latest_conditions.temperature_celsius > 3

    def test_get_upcoming_trips_for_alerts(
        self, trip_service, mock_table, sample_trip_data
    ):
        """Test retrieving trips for alert processing."""
        mock_table.scan.return_value = {"Items": [sample_trip_data]}

        trips = trip_service.get_upcoming_trips_for_alerts(days_ahead=14)

        assert len(trips) == 1
        mock_table.scan.assert_called_once()
