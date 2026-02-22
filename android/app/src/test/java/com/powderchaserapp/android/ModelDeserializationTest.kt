package com.powderchaserapp.android

import com.powderchaserapp.android.data.api.*
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class ModelDeserializationTest {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
    }

    @Test
    fun `deserialize resort from JSON`() {
        val jsonStr = """
        {
            "resort_id": "big-white",
            "name": "Big White Ski Resort",
            "country": "CA",
            "region": "BC",
            "elevation_points": [
                {
                    "level": "base",
                    "elevation_meters": 1508.0,
                    "elevation_feet": 4947.0,
                    "latitude": 49.7167,
                    "longitude": -118.9333
                },
                {
                    "level": "mid",
                    "elevation_meters": 1800.0,
                    "elevation_feet": 5906.0,
                    "latitude": 49.72,
                    "longitude": -118.93
                },
                {
                    "level": "top",
                    "elevation_meters": 2319.0,
                    "elevation_feet": 7608.0,
                    "latitude": 49.7233,
                    "longitude": -118.9267
                }
            ],
            "timezone": "America/Vancouver",
            "official_website": "https://www.bigwhite.com",
            "epic_pass": "7 days",
            "ikon_pass": null,
            "weather_sources": ["weatherapi"],
            "green_runs_pct": 18,
            "blue_runs_pct": 56,
            "black_runs_pct": 26
        }
        """.trimIndent()

        val resort = json.decodeFromString<Resort>(jsonStr)
        assertEquals("big-white", resort.id)
        assertEquals("Big White Ski Resort", resort.name)
        assertEquals("CA", resort.country)
        assertEquals("BC", resort.region)
        assertEquals(3, resort.elevationPoints.size)
        assertEquals("America/Vancouver", resort.timezone)
        assertEquals("7 days", resort.epicPass)
        assertNull(resort.ikonPass)
        assertEquals("Canada", resort.countryName)
        assertEquals("BC, Canada", resort.displayLocation)
        assertNotNull(resort.baseElevation)
        assertNotNull(resort.midElevation)
        assertNotNull(resort.topElevation)
        assertEquals(ElevationLevel.BASE, resort.baseElevation?.level)
    }

    @Test
    fun `deserialize snow quality summary light`() {
        val jsonStr = """
        {
            "resort_id": "whistler",
            "overall_quality": "excellent",
            "snow_score": 85,
            "explanation": "Fresh powder conditions",
            "last_updated": "2026-01-20T10:00:00Z",
            "temperature_c": -8.0,
            "snowfall_fresh_cm": 25.0,
            "snowfall_24h_cm": 20.0,
            "snow_depth_cm": 150.0,
            "predicted_snow_48h_cm": 30.0
        }
        """.trimIndent()

        val quality = json.decodeFromString<SnowQualitySummaryLight>(jsonStr)
        assertEquals("whistler", quality.resortId)
        assertEquals(SnowQuality.EXCELLENT, quality.overallSnowQuality)
        assertEquals(85, quality.snowScore)
        assertEquals(-8.0, quality.temperatureC!!, 0.001)
    }

    @Test
    fun `snow quality temperature override at 15C`() {
        val quality = SnowQualitySummaryLight(
            resortId = "test",
            overallQuality = "good",
            temperatureC = 15.0,
        )
        assertEquals(SnowQuality.HORRIBLE, quality.overallSnowQuality)
    }

    @Test
    fun `snow quality no override below 15C`() {
        val quality = SnowQualitySummaryLight(
            resortId = "test",
            overallQuality = "good",
            temperatureC = 14.9,
        )
        assertEquals(SnowQuality.GOOD, quality.overallSnowQuality)
    }

    @Test
    fun `deserialize timeline point`() {
        val jsonStr = """
        {
            "date": "2026-01-20",
            "time_label": "morning",
            "hour": 9,
            "timestamp": "2026-01-20T09:00:00Z",
            "temperature_c": -5.0,
            "wind_speed_kmh": 15.0,
            "snowfall_cm": 5.0,
            "snow_depth_cm": 120.0,
            "snow_quality": "good",
            "quality_score": 4.5,
            "snow_score": 70,
            "explanation": "Light snow",
            "weather_code": 71,
            "weather_description": "Light snow",
            "is_forecast": false
        }
        """.trimIndent()

        val point = json.decodeFromString<TimelinePoint>(jsonStr)
        assertEquals("2026-01-20", point.date)
        assertEquals("AM", point.timeDisplay)
        assertEquals(-5.0, point.temperatureC, 0.001)
        assertEquals(SnowQuality.GOOD, point.snowQuality)
        assertFalse(point.isForecast)
    }

    @Test
    fun `deserialize weather condition`() {
        val jsonStr = """
        {
            "resort_id": "big-white",
            "elevation_level": "top",
            "timestamp": "2026-01-20T10:00:00Z",
            "current_temp_celsius": -8.0,
            "min_temp_celsius": -12.0,
            "max_temp_celsius": -4.0,
            "snowfall_24h_cm": 20.0,
            "snowfall_48h_cm": 35.0,
            "snowfall_72h_cm": 40.0,
            "snow_depth_cm": 150.0,
            "hours_above_ice_threshold": 0.0,
            "max_consecutive_warm_hours": 0.0,
            "snow_quality": "excellent",
            "quality_score": 5.8,
            "confidence_level": "high",
            "fresh_snow_cm": 18.5,
            "data_source": "weatherapi",
            "source_confidence": "high"
        }
        """.trimIndent()

        val condition = json.decodeFromString<WeatherCondition>(jsonStr)
        assertEquals("big-white", condition.resortId)
        assertEquals("top", condition.elevationLevel)
        assertEquals(-8.0, condition.currentTempCelsius, 0.001)
        assertEquals(SnowQuality.EXCELLENT, condition.snowQuality)
        assertEquals(ConfidenceLevel.HIGH, condition.confidenceLevel)
        assertEquals(18.5, condition.freshSnowCm, 0.001)
        assertNotNull(condition.snowScore)
        assertEquals(96, condition.snowScore) // (5.8 - 1.0) / 5.0 * 100 = 96
    }

    @Test
    fun `deserialize chat response`() {
        val jsonStr = """
        {
            "conversation_id": "conv-123",
            "response": "The conditions at Whistler are excellent today!",
            "message_id": "msg-456"
        }
        """.trimIndent()

        val response = json.decodeFromString<ChatResponse>(jsonStr)
        assertEquals("conv-123", response.conversationId)
        assertEquals("msg-456", response.messageId)
    }

    @Test
    fun `deserialize auth response`() {
        val jsonStr = """
        {
            "user": {
                "user_id": "user-123",
                "email": null,
                "first_name": null,
                "last_name": null,
                "provider": "guest",
                "is_new_user": true
            },
            "access_token": "eyJhbGci...",
            "refresh_token": "refresh-abc",
            "token_type": "bearer",
            "expires_in": 3600
        }
        """.trimIndent()

        val response = json.decodeFromString<AuthResponse>(jsonStr)
        assertEquals("user-123", response.user.userId)
        assertEquals("Guest", response.user.displayName)
        assertTrue(response.user.isNewUser)
        assertEquals("guest", response.user.provider)
    }

    @Test
    fun `deserialize trip with alerts`() {
        val jsonStr = """
        {
            "trip_id": "trip-123",
            "user_id": "user-1",
            "resort_id": "whistler",
            "resort_name": "Whistler Blackcomb",
            "start_date": "2026-02-15",
            "end_date": "2026-02-18",
            "status": "planned",
            "party_size": 4,
            "alerts": [
                {
                    "alert_id": "alert-1",
                    "alert_type": "powder_alert",
                    "message": "30cm fresh powder expected!",
                    "created_at": "2026-02-14T10:00:00Z",
                    "is_read": false
                }
            ],
            "alert_preferences": {"powder_alert": true},
            "created_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z"
        }
        """.trimIndent()

        val trip = json.decodeFromString<Trip>(jsonStr)
        assertEquals("trip-123", trip.tripId)
        assertEquals("Whistler Blackcomb", trip.resortName)
        assertEquals(TripStatus.PLANNED, trip.tripStatus)
        assertEquals(4, trip.partySize)
        assertEquals(1, trip.alerts.size)
        assertEquals(1, trip.unreadAlertCount)
    }

    @Test
    fun `deserialize condition report`() {
        val jsonStr = """
        {
            "report_id": "rpt-1",
            "resort_id": "whistler",
            "user_id": "user-1",
            "condition_type": "powder",
            "score": 9,
            "comment": "Epic powder day!",
            "elevation_level": "top",
            "created_at": "2026-01-20T14:00:00Z",
            "user_name": "SkiLover"
        }
        """.trimIndent()

        val report = json.decodeFromString<ConditionReport>(jsonStr)
        assertEquals("rpt-1", report.reportId)
        assertEquals(9, report.score)
        assertEquals("Epic", report.scoreLabel)
        assertEquals("powder", report.conditionType)
    }

    @Test
    fun `deserialize snow history response`() {
        val jsonStr = """
        {
            "resort_id": "whistler",
            "history": [
                {
                    "date": "2026-01-20",
                    "snowfall_24h_cm": 15.0,
                    "snow_depth_cm": 200.0,
                    "temp_min_c": -10.0,
                    "temp_max_c": -2.0,
                    "quality_score": 4.5,
                    "snow_quality": "good"
                }
            ],
            "season_summary": {
                "total_snowfall_cm": 500.0,
                "snow_days": 45,
                "avg_quality_score": 4.2,
                "days_tracked": 60
            }
        }
        """.trimIndent()

        val response = json.decodeFromString<SnowHistoryResponse>(jsonStr)
        assertEquals("whistler", response.resortId)
        assertEquals(1, response.history.size)
        assertEquals(500.0, response.seasonSummary.totalSnowfallCm, 0.001)
        assertEquals(45, response.seasonSummary.snowDays)
    }

    @Test
    fun `snow quality enum sort order`() {
        assertEquals(1, SnowQuality.EXCELLENT.sortOrder)
        assertEquals(7, SnowQuality.HORRIBLE.sortOrder)
        assertEquals(99, SnowQuality.UNKNOWN.sortOrder)
    }

    @Test
    fun `confidence level percentages`() {
        assertEquals(95, ConfidenceLevel.VERY_HIGH.percentage)
        assertEquals(30, ConfidenceLevel.VERY_LOW.percentage)
    }
}
