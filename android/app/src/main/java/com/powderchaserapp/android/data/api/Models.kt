package com.powderchaserapp.android.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// =============================================================================
// MARK: - Enums
// =============================================================================

@Serializable
enum class ElevationLevel(val value: String) {
    @SerialName("base") BASE("base"),
    @SerialName("mid") MID("mid"),
    @SerialName("top") TOP("top");

    val displayName: String
        get() = when (this) {
            BASE -> "Base"
            MID -> "Mid"
            TOP -> "Top"
        }
}

@Serializable
enum class SnowQuality(val value: String) {
    @SerialName("excellent") EXCELLENT("excellent"),
    @SerialName("good") GOOD("good"),
    @SerialName("fair") FAIR("fair"),
    @SerialName("poor") POOR("poor"),
    @SerialName("slushy") SLUSHY("slushy"),
    @SerialName("bad") BAD("bad"),
    @SerialName("horrible") HORRIBLE("horrible"),
    @SerialName("unknown") UNKNOWN("unknown");

    val displayName: String
        get() = when (this) {
            EXCELLENT -> "Excellent"
            GOOD -> "Good"
            FAIR -> "Fair"
            POOR -> "Soft"
            SLUSHY -> "Slushy"
            BAD -> "Icy"
            HORRIBLE -> "Not Skiable"
            UNKNOWN -> "Unknown"
        }

    val sortOrder: Int
        get() = when (this) {
            EXCELLENT -> 1
            GOOD -> 2
            FAIR -> 3
            POOR -> 4
            SLUSHY -> 5
            BAD -> 6
            HORRIBLE -> 7
            UNKNOWN -> 99
        }

    val description: String
        get() = when (this) {
            EXCELLENT -> "Fresh powder, perfect conditions"
            GOOD -> "Good snow with minimal ice"
            FAIR -> "Some ice formation present"
            POOR -> "Soft, thawing snow - warming conditions"
            SLUSHY -> "Slushy, wet snow - actively thawing"
            BAD -> "Icy surface, no fresh snow"
            HORRIBLE -> "Not skiable, dangerous conditions"
            UNKNOWN -> "Conditions unknown"
        }
}

@Serializable
enum class ConfidenceLevel(val value: String) {
    @SerialName("very_high") VERY_HIGH("very_high"),
    @SerialName("high") HIGH("high"),
    @SerialName("medium") MEDIUM("medium"),
    @SerialName("low") LOW("low"),
    @SerialName("very_low") VERY_LOW("very_low");

    val displayName: String
        get() = when (this) {
            VERY_HIGH -> "Very High"
            HIGH -> "High"
            MEDIUM -> "Medium"
            LOW -> "Low"
            VERY_LOW -> "Very Low"
        }

    val percentage: Int
        get() = when (this) {
            VERY_HIGH -> 95
            HIGH -> 85
            MEDIUM -> 70
            LOW -> 50
            VERY_LOW -> 30
        }
}

@Serializable
enum class ConditionType(val value: String) {
    @SerialName("powder") POWDER("powder"),
    @SerialName("packed_powder") PACKED_POWDER("packed_powder"),
    @SerialName("soft") SOFT("soft"),
    @SerialName("ice") ICE("ice"),
    @SerialName("crud") CRUD("crud"),
    @SerialName("spring") SPRING("spring"),
    @SerialName("hardpack") HARDPACK("hardpack"),
    @SerialName("windblown") WINDBLOWN("windblown");

    val displayName: String
        get() = when (this) {
            POWDER -> "Powder"
            PACKED_POWDER -> "Packed Powder"
            SOFT -> "Soft"
            ICE -> "Ice"
            CRUD -> "Crud"
            SPRING -> "Spring"
            HARDPACK -> "Hardpack"
            WINDBLOWN -> "Windblown"
        }
}

@Serializable
enum class TripStatus {
    @SerialName("planned") PLANNED,
    @SerialName("active") ACTIVE,
    @SerialName("completed") COMPLETED,
    @SerialName("cancelled") CANCELLED;
}

@Serializable
enum class TripAlertType(val value: String) {
    @SerialName("powder_alert") POWDER_ALERT("powder_alert"),
    @SerialName("warm_spell") WARM_SPELL("warm_spell"),
    @SerialName("conditions_improved") CONDITIONS_IMPROVED("conditions_improved"),
    @SerialName("conditions_degraded") CONDITIONS_DEGRADED("conditions_degraded"),
    @SerialName("trip_reminder") TRIP_REMINDER("trip_reminder");

    val displayName: String
        get() = when (this) {
            POWDER_ALERT -> "Powder Alert"
            WARM_SPELL -> "Warm Spell Warning"
            CONDITIONS_IMPROVED -> "Conditions Improved"
            CONDITIONS_DEGRADED -> "Conditions Degraded"
            TRIP_REMINDER -> "Trip Reminder"
        }
}

@Serializable
enum class ChatRole {
    @SerialName("user") USER,
    @SerialName("assistant") ASSISTANT;
}

// =============================================================================
// MARK: - Resort Models
// =============================================================================

@Serializable
data class ElevationPoint(
    val level: ElevationLevel,
    @SerialName("elevation_meters") val elevationMeters: Double,
    @SerialName("elevation_feet") val elevationFeet: Double,
    val latitude: Double,
    val longitude: Double,
    @SerialName("weather_station_id") val weatherStationId: String? = null,
)

@Serializable
data class Resort(
    @SerialName("resort_id") val id: String,
    val name: String,
    val country: String,
    val region: String,
    @SerialName("elevation_points") val elevationPoints: List<ElevationPoint>,
    val timezone: String,
    @SerialName("official_website") val officialWebsite: String? = null,
    @SerialName("trail_map_url") val trailMapUrl: String? = null,
    @SerialName("green_runs_pct") val greenRunsPct: Int? = null,
    @SerialName("blue_runs_pct") val blueRunsPct: Int? = null,
    @SerialName("black_runs_pct") val blackRunsPct: Int? = null,
    @SerialName("epic_pass") val epicPass: String? = null,
    @SerialName("ikon_pass") val ikonPass: String? = null,
    @SerialName("weather_sources") val weatherSources: List<String> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
) {
    val displayLocation: String
        get() = "$region, $countryName"

    val countryName: String
        get() = when (country.uppercase()) {
            "CA" -> "Canada"
            "US" -> "United States"
            "FR" -> "France"
            "CH" -> "Switzerland"
            "AT" -> "Austria"
            "IT" -> "Italy"
            "JP" -> "Japan"
            "NZ" -> "New Zealand"
            "AU" -> "Australia"
            "CL" -> "Chile"
            "DE" -> "Germany"
            "NO" -> "Norway"
            "SE" -> "Sweden"
            else -> country
        }

    val baseElevation: ElevationPoint?
        get() = elevationPoints.firstOrNull { it.level == ElevationLevel.BASE }

    val midElevation: ElevationPoint?
        get() = elevationPoints.firstOrNull { it.level == ElevationLevel.MID }

    val topElevation: ElevationPoint?
        get() = elevationPoints.firstOrNull { it.level == ElevationLevel.TOP }

    fun elevationPoint(level: ElevationLevel): ElevationPoint? =
        elevationPoints.firstOrNull { it.level == level }
}

// =============================================================================
// MARK: - Weather Condition
// =============================================================================

@Serializable
data class WeatherCondition(
    @SerialName("resort_id") val resortId: String,
    @SerialName("elevation_level") val elevationLevel: String,
    val timestamp: String,
    @SerialName("current_temp_celsius") val currentTempCelsius: Double,
    @SerialName("min_temp_celsius") val minTempCelsius: Double,
    @SerialName("max_temp_celsius") val maxTempCelsius: Double,
    @SerialName("snowfall_24h_cm") val snowfall24hCm: Double,
    @SerialName("snowfall_48h_cm") val snowfall48hCm: Double,
    @SerialName("snowfall_72h_cm") val snowfall72hCm: Double,
    @SerialName("snow_depth_cm") val snowDepthCm: Double? = null,
    @SerialName("predicted_snow_24h_cm") val predictedSnow24hCm: Double? = null,
    @SerialName("predicted_snow_48h_cm") val predictedSnow48hCm: Double? = null,
    @SerialName("predicted_snow_72h_cm") val predictedSnow72hCm: Double? = null,
    @SerialName("hours_above_ice_threshold") val hoursAboveIceThreshold: Double,
    @SerialName("max_consecutive_warm_hours") val maxConsecutiveWarmHours: Double,
    @SerialName("snowfall_after_freeze_cm") val snowfallAfterFreezeCm: Double? = null,
    @SerialName("hours_since_last_snowfall") val hoursSinceLastSnowfall: Double? = null,
    @SerialName("last_freeze_thaw_hours_ago") val lastFreezeThawHoursAgo: Double? = null,
    @SerialName("currently_warming") val currentlyWarming: Boolean? = null,
    @SerialName("humidity_percent") val humidityPercent: Double? = null,
    @SerialName("wind_speed_kmh") val windSpeedKmh: Double? = null,
    @SerialName("weather_description") val weatherDescription: String? = null,
    @SerialName("snow_quality") val snowQuality: SnowQuality,
    @SerialName("quality_score") val qualityScore: Double? = null,
    @SerialName("confidence_level") val confidenceLevel: ConfidenceLevel,
    @SerialName("fresh_snow_cm") val freshSnowCm: Double,
    @SerialName("data_source") val dataSource: String,
    @SerialName("source_confidence") val sourceConfidence: ConfidenceLevel,
) {
    val currentTempFahrenheit: Double
        get() = currentTempCelsius * 9.0 / 5.0 + 32.0

    val snowScore: Int?
        get() {
            val score = qualityScore ?: return null
            return ((score - 1.0) / 5.0 * 100).toInt().coerceIn(0, 100)
        }

    val snowSinceFreeze: Double
        get() = snowfallAfterFreezeCm ?: freshSnowCm

    val elevationLevelEnum: ElevationLevel?
        get() = try {
            ElevationLevel.entries.firstOrNull { it.value == elevationLevel }
        } catch (_: Exception) {
            null
        }
}

// =============================================================================
// MARK: - Snow Quality Summary
// =============================================================================

@Serializable
data class SnowQualitySummary(
    @SerialName("resort_id") val resortId: String,
    val elevations: Map<String, ElevationSummary>,
    @SerialName("overall_quality") val overallQuality: String,
    @SerialName("overall_snow_score") val overallSnowScore: Int? = null,
    @SerialName("overall_explanation") val overallExplanation: String? = null,
    @SerialName("last_updated") val lastUpdated: String? = null,
) {
    val overallSnowQuality: SnowQuality
        get() = try {
            SnowQuality.entries.firstOrNull { it.value == overallQuality } ?: SnowQuality.UNKNOWN
        } catch (_: Exception) {
            SnowQuality.UNKNOWN
        }
}

@Serializable
data class ElevationSummary(
    val quality: String,
    @SerialName("snow_score") val snowScore: Int? = null,
    @SerialName("fresh_snow_cm") val freshSnowCm: Double,
    val confidence: String,
    @SerialName("temperature_celsius") val temperatureCelsius: Double,
    @SerialName("snowfall_24h_cm") val snowfall24hCm: Double,
    val explanation: String? = null,
    val timestamp: String,
) {
    val snowQuality: SnowQuality
        get() = try {
            SnowQuality.entries.firstOrNull { it.value == quality } ?: SnowQuality.UNKNOWN
        } catch (_: Exception) {
            SnowQuality.UNKNOWN
        }

    val confidenceLevel: ConfidenceLevel
        get() = try {
            ConfidenceLevel.entries.firstOrNull { it.value == confidence } ?: ConfidenceLevel.MEDIUM
        } catch (_: Exception) {
            ConfidenceLevel.MEDIUM
        }
}

@Serializable
data class SnowQualitySummaryLight(
    @SerialName("resort_id") val resortId: String,
    @SerialName("overall_quality") val overallQuality: String,
    @SerialName("snow_score") val snowScore: Int? = null,
    val explanation: String? = null,
    @SerialName("last_updated") val lastUpdated: String? = null,
    @SerialName("temperature_c") val temperatureC: Double? = null,
    @SerialName("snowfall_fresh_cm") val snowfallFreshCm: Double? = null,
    @SerialName("snowfall_24h_cm") val snowfall24hCm: Double? = null,
    @SerialName("snow_depth_cm") val snowDepthCm: Double? = null,
    @SerialName("predicted_snow_48h_cm") val predictedSnow48hCm: Double? = null,
) {
    /**
     * Snow quality with frontend temperature override.
     * If temperatureC >= 15.0, override quality to "horrible".
     */
    val overallSnowQuality: SnowQuality
        get() {
            val baseQuality = try {
                SnowQuality.entries.firstOrNull { it.value == overallQuality } ?: SnowQuality.UNKNOWN
            } catch (_: Exception) {
                SnowQuality.UNKNOWN
            }

            // Only override at summer temperatures (>= 15C) where no snow can exist
            if (temperatureC != null && temperatureC >= 15.0) {
                return SnowQuality.HORRIBLE
            }

            return baseQuality
        }

    val rawSnowQuality: SnowQuality
        get() = try {
            SnowQuality.entries.firstOrNull { it.value == overallQuality } ?: SnowQuality.UNKNOWN
        } catch (_: Exception) {
            SnowQuality.UNKNOWN
        }
}

// =============================================================================
// MARK: - Timeline
// =============================================================================

@Serializable
data class TimelinePoint(
    val date: String,
    @SerialName("time_label") val timeLabel: String,
    val hour: Int,
    val timestamp: String,
    @SerialName("temperature_c") val temperatureC: Double,
    @SerialName("wind_speed_kmh") val windSpeedKmh: Double? = null,
    @SerialName("snowfall_cm") val snowfallCm: Double,
    @SerialName("snow_depth_cm") val snowDepthCm: Double? = null,
    @SerialName("snow_quality") val snowQuality: SnowQuality,
    @SerialName("quality_score") val qualityScore: Double? = null,
    @SerialName("snow_score") val snowScore: Int? = null,
    val explanation: String? = null,
    @SerialName("weather_code") val weatherCode: Int? = null,
    @SerialName("weather_description") val weatherDescription: String? = null,
    @SerialName("is_forecast") val isForecast: Boolean,
) {
    val timeDisplay: String
        get() = when (timeLabel) {
            "morning" -> "AM"
            "midday" -> "Noon"
            "afternoon" -> "PM"
            else -> timeLabel
        }
}

@Serializable
data class TimelineResponse(
    val timeline: List<TimelinePoint>,
    @SerialName("elevation_level") val elevationLevel: String,
    @SerialName("elevation_meters") val elevationMeters: Int,
    @SerialName("resort_id") val resortId: String,
)

// =============================================================================
// MARK: - Chat Models
// =============================================================================

@Serializable
data class ChatMessage(
    @SerialName("message_id") val id: String,
    val role: ChatRole,
    val content: String,
    @SerialName("created_at") val createdAt: String? = null,
) {
    val isFromUser: Boolean get() = role == ChatRole.USER
}

@Serializable
data class ChatConversation(
    @SerialName("conversation_id") val id: String,
    val title: String,
    @SerialName("last_message_at") val lastMessageAt: String? = null,
    @SerialName("message_count") val messageCount: Int? = null,
)

@Serializable
data class ChatRequest(
    val message: String,
    @SerialName("conversation_id") val conversationId: String? = null,
)

@Serializable
data class ChatResponse(
    @SerialName("conversation_id") val conversationId: String,
    val response: String,
    @SerialName("message_id") val messageId: String,
)

// =============================================================================
// MARK: - Condition Reports
// =============================================================================

@Serializable
data class ConditionReport(
    @SerialName("report_id") val reportId: String,
    @SerialName("resort_id") val resortId: String,
    @SerialName("user_id") val userId: String,
    @SerialName("condition_type") val conditionType: String,
    val score: Int,
    val comment: String? = null,
    @SerialName("elevation_level") val elevationLevel: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("user_name") val userName: String? = null,
) {
    val scoreLabel: String
        get() = when (score) {
            in 1..2 -> "Terrible"
            in 3..4 -> "Poor"
            in 5..6 -> "Fair"
            in 7..8 -> "Good"
            in 9..10 -> "Epic"
            else -> "Unknown"
        }
}

@Serializable
data class ConditionReportSummary(
    @SerialName("total_reports") val totalReports: Int,
    @SerialName("average_score") val averageScore: Double? = null,
    @SerialName("dominant_condition") val dominantCondition: String? = null,
    @SerialName("reports_last_24h") val reportsLast24h: Int,
)

@Serializable
data class ConditionReportsResponse(
    val reports: List<ConditionReport>,
    val summary: ConditionReportSummary? = null,
)

@Serializable
data class SubmitConditionReportRequest(
    @SerialName("condition_type") val conditionType: String,
    val score: Int,
    val comment: String? = null,
    @SerialName("elevation_level") val elevationLevel: String? = null,
)

// =============================================================================
// MARK: - Trip Models
// =============================================================================

@Serializable
data class Trip(
    @SerialName("trip_id") val tripId: String,
    @SerialName("user_id") val userId: String,
    @SerialName("resort_id") val resortId: String,
    @SerialName("resort_name") val resortName: String,
    @SerialName("start_date") val startDate: String,
    @SerialName("end_date") val endDate: String,
    val status: String,
    val notes: String? = null,
    @SerialName("party_size") val partySize: Int,
    @SerialName("conditions_at_creation") val conditionsAtCreation: TripConditionSnapshot? = null,
    @SerialName("latest_conditions") val latestConditions: TripConditionSnapshot? = null,
    val alerts: List<TripAlert> = emptyList(),
    @SerialName("alert_preferences") val alertPreferences: Map<String, Boolean> = emptyMap(),
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
) {
    val tripStatus: TripStatus
        get() = try {
            TripStatus.entries.firstOrNull { it.name.lowercase() == status } ?: TripStatus.PLANNED
        } catch (_: Exception) {
            TripStatus.PLANNED
        }

    val unreadAlertCount: Int
        get() = alerts.count { !it.isRead }
}

@Serializable
data class TripConditionSnapshot(
    val timestamp: String,
    @SerialName("snow_quality") val snowQuality: String,
    @SerialName("fresh_snow_cm") val freshSnowCm: Double,
    @SerialName("predicted_snow_cm") val predictedSnowCm: Double,
    @SerialName("temperature_celsius") val temperatureCelsius: Double? = null,
) {
    val quality: SnowQuality
        get() = try {
            SnowQuality.entries.firstOrNull { it.value == snowQuality } ?: SnowQuality.UNKNOWN
        } catch (_: Exception) {
            SnowQuality.UNKNOWN
        }
}

@Serializable
data class TripAlert(
    @SerialName("alert_id") val alertId: String,
    @SerialName("alert_type") val alertType: String,
    val message: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("is_read") val isRead: Boolean,
)

@Serializable
data class TripCreateRequest(
    @SerialName("resort_id") val resortId: String,
    @SerialName("start_date") val startDate: String,
    @SerialName("end_date") val endDate: String,
    val notes: String? = null,
    @SerialName("party_size") val partySize: Int,
    @SerialName("alert_preferences") val alertPreferences: Map<String, Boolean>? = null,
)

@Serializable
data class TripUpdateRequest(
    @SerialName("start_date") val startDate: String? = null,
    @SerialName("end_date") val endDate: String? = null,
    val notes: String? = null,
    @SerialName("party_size") val partySize: Int? = null,
    val status: String? = null,
    @SerialName("alert_preferences") val alertPreferences: Map<String, Boolean>? = null,
)

@Serializable
data class TripsResponse(
    val trips: List<Trip>,
    val count: Int,
)

// =============================================================================
// MARK: - Auth Models
// =============================================================================

@Serializable
data class GuestAuthRequest(
    @SerialName("device_id") val deviceId: String,
)

@Serializable
data class RefreshTokenRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class AuthResponse(
    val user: AuthenticatedUserInfo,
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("expires_in") val expiresIn: Int,
)

@Serializable
data class AuthenticatedUserInfo(
    @SerialName("user_id") val userId: String,
    val email: String? = null,
    @SerialName("first_name") val firstName: String? = null,
    @SerialName("last_name") val lastName: String? = null,
    val provider: String? = null,
    @SerialName("is_new_user") val isNewUser: Boolean,
) {
    val displayName: String
        get() {
            if (firstName != null && lastName != null) return "$firstName $lastName"
            if (firstName != null) return firstName
            if (email != null) return email
            return "Guest"
        }
}

// =============================================================================
// MARK: - Recommendations
// =============================================================================

@Serializable
data class RecommendationsResponse(
    val recommendations: List<ResortRecommendation>,
    @SerialName("search_center") val searchCenter: SearchLocation? = null,
    @SerialName("search_radius_km") val searchRadiusKm: Double? = null,
    @SerialName("generated_at") val generatedAt: String,
)

@Serializable
data class SearchLocation(
    val latitude: Double,
    val longitude: Double,
)

@Serializable
data class ResortRecommendation(
    val resort: Resort,
    @SerialName("distance_km") val distanceKm: Double,
    @SerialName("distance_miles") val distanceMiles: Double,
    @SerialName("snow_quality") val snowQuality: String,
    @SerialName("snow_score") val snowScore: Int? = null,
    @SerialName("quality_score") val qualityScore: Double,
    @SerialName("distance_score") val distanceScore: Double,
    @SerialName("combined_score") val combinedScore: Double,
    @SerialName("fresh_snow_cm") val freshSnowCm: Double,
    @SerialName("predicted_snow_72h_cm") val predictedSnow72hCm: Double,
    @SerialName("current_temp_celsius") val currentTempCelsius: Double,
    @SerialName("confidence_level") val confidenceLevel: String,
    val reason: String,
    @SerialName("elevation_conditions") val elevationConditions: Map<String, ElevationConditionSummary> = emptyMap(),
) {
    val quality: SnowQuality
        get() = try {
            SnowQuality.entries.firstOrNull { it.value == snowQuality } ?: SnowQuality.UNKNOWN
        } catch (_: Exception) {
            SnowQuality.UNKNOWN
        }
}

@Serializable
data class ElevationConditionSummary(
    val quality: String,
    @SerialName("temp_celsius") val tempCelsius: Double,
    @SerialName("fresh_snow_cm") val freshSnowCm: Double,
    @SerialName("snowfall_24h_cm") val snowfall24hCm: Double,
    @SerialName("predicted_24h_cm") val predicted24hCm: Double,
)

// =============================================================================
// MARK: - Snow History
// =============================================================================

@Serializable
data class DailySnowHistory(
    val date: String,
    @SerialName("snowfall_24h_cm") val snowfall24hCm: Double,
    @SerialName("snow_depth_cm") val snowDepthCm: Double? = null,
    @SerialName("temp_min_c") val tempMinC: Double,
    @SerialName("temp_max_c") val tempMaxC: Double,
    @SerialName("quality_score") val qualityScore: Double? = null,
    @SerialName("snow_quality") val snowQuality: String? = null,
)

@Serializable
data class SeasonSummary(
    @SerialName("total_snowfall_cm") val totalSnowfallCm: Double,
    @SerialName("snow_days") val snowDays: Int,
    @SerialName("avg_quality_score") val avgQualityScore: Double? = null,
    @SerialName("best_day") val bestDay: DailySnowHistory? = null,
    @SerialName("days_tracked") val daysTracked: Int,
)

@Serializable
data class SnowHistoryResponse(
    @SerialName("resort_id") val resortId: String,
    val history: List<DailySnowHistory>,
    @SerialName("season_summary") val seasonSummary: SeasonSummary,
)

// =============================================================================
// MARK: - Notification Settings
// =============================================================================

@Serializable
data class NotificationSettings(
    @SerialName("notifications_enabled") val notificationsEnabled: Boolean = true,
    @SerialName("fresh_snow_alerts") val freshSnowAlerts: Boolean = true,
    @SerialName("event_alerts") val eventAlerts: Boolean = true,
    @SerialName("thaw_freeze_alerts") val thawFreezeAlerts: Boolean = true,
    @SerialName("powder_alerts") val powderAlerts: Boolean = true,
    @SerialName("weekly_summary") val weeklySummary: Boolean = true,
    @SerialName("default_snow_threshold_cm") val defaultSnowThresholdCm: Double = 5.0,
    @SerialName("powder_snow_threshold_cm") val powderSnowThresholdCm: Double = 15.0,
    @SerialName("grace_period_hours") val gracePeriodHours: Int = 12,
    @SerialName("resort_settings") val resortSettings: Map<String, ResortNotificationSettings> = emptyMap(),
    @SerialName("last_notified") val lastNotified: Map<String, String> = emptyMap(),
)

@Serializable
data class ResortNotificationSettings(
    @SerialName("fresh_snow_enabled") val freshSnowEnabled: Boolean = true,
    @SerialName("fresh_snow_threshold_cm") val freshSnowThresholdCm: Double? = null,
    @SerialName("event_notifications_enabled") val eventNotificationsEnabled: Boolean = true,
    @SerialName("powder_alerts_enabled") val powderAlertsEnabled: Boolean = true,
    @SerialName("powder_threshold_cm") val powderThresholdCm: Double? = null,
)

@Serializable
data class NotificationSettingsUpdate(
    @SerialName("notifications_enabled") val notificationsEnabled: Boolean? = null,
    @SerialName("fresh_snow_alerts") val freshSnowAlerts: Boolean? = null,
    @SerialName("event_alerts") val eventAlerts: Boolean? = null,
    @SerialName("thaw_freeze_alerts") val thawFreezeAlerts: Boolean? = null,
    @SerialName("powder_alerts") val powderAlerts: Boolean? = null,
    @SerialName("weekly_summary") val weeklySummary: Boolean? = null,
    @SerialName("default_snow_threshold_cm") val defaultSnowThresholdCm: Double? = null,
    @SerialName("powder_snow_threshold_cm") val powderSnowThresholdCm: Double? = null,
    @SerialName("grace_period_hours") val gracePeriodHours: Int? = null,
)

// =============================================================================
// MARK: - User Preferences
// =============================================================================

@Serializable
data class UserPreferences(
    @SerialName("user_id") val userId: String,
    @SerialName("favorite_resorts") val favoriteResorts: List<String> = emptyList(),
    @SerialName("notification_preferences") val notificationPreferences: Map<String, Boolean> = emptyMap(),
    @SerialName("preferred_units") val preferredUnits: Map<String, String> = emptyMap(),
    @SerialName("quality_threshold") val qualityThreshold: String = "fair",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
)

// =============================================================================
// MARK: - Feedback
// =============================================================================

@Serializable
data class FeedbackSubmission(
    val subject: String,
    val message: String,
    val email: String? = null,
    @SerialName("app_version") val appVersion: String,
    @SerialName("build_number") val buildNumber: String,
    @SerialName("device_model") val deviceModel: String,
    @SerialName("os_version") val osVersion: String,
)

// =============================================================================
// MARK: - Device Token
// =============================================================================

@Serializable
data class DeviceTokenRequest(
    @SerialName("device_id") val deviceId: String,
    val token: String,
    val platform: String,
    @SerialName("app_version") val appVersion: String? = null,
)

// =============================================================================
// MARK: - Nearby Resorts
// =============================================================================

@Serializable
data class NearbyResortsResponse(
    val resorts: List<NearbyResortResult>,
    val count: Int,
    @SerialName("search_center") val searchCenter: SearchCenter,
    @SerialName("search_radius_km") val searchRadiusKm: Double,
)

@Serializable
data class NearbyResortResult(
    val resort: Resort,
    @SerialName("distance_km") val distanceKm: Double,
    @SerialName("distance_miles") val distanceMiles: Double,
)

@Serializable
data class SearchCenter(
    val latitude: Double,
    val longitude: Double,
)

// =============================================================================
// MARK: - Batch API Responses
// =============================================================================

@Serializable
data class ResortsResponse(
    val resorts: List<Resort>,
)

@Serializable
data class ConditionsResponse(
    val conditions: List<WeatherCondition>,
    @SerialName("last_updated") val lastUpdated: String? = null,
    @SerialName("resort_id") val resortId: String? = null,
)

@Serializable
data class BatchConditionsResponse(
    val results: Map<String, ResortConditionsResult>,
    @SerialName("last_updated") val lastUpdated: String? = null,
    @SerialName("resort_count") val resortCount: Int,
)

@Serializable
data class ResortConditionsResult(
    val conditions: List<WeatherCondition>,
    val error: String? = null,
)

@Serializable
data class BatchSnowQualityResponse(
    val results: Map<String, SnowQualitySummaryLight>,
    @SerialName("last_updated") val lastUpdated: String,
    @SerialName("resort_count") val resortCount: Int,
)

@Serializable
data class ChatConversationsResponse(
    val conversations: List<ChatConversation>,
)

@Serializable
data class ChatMessagesResponse(
    val messages: List<ChatMessage>,
)
