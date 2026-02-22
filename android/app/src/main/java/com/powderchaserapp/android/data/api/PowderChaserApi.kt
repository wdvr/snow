package com.powderchaserapp.android.data.api

import retrofit2.http.*

interface PowderChaserApi {

    // =========================================================================
    // Resorts
    // =========================================================================

    @GET("api/v1/resorts")
    suspend fun getResorts(
        @Query("region") region: String? = null,
        @Query("country") country: String? = null,
    ): ResortsResponse

    @GET("api/v1/resorts/{id}")
    suspend fun getResort(@Path("id") id: String): Resort

    @GET("api/v1/resorts/nearby")
    suspend fun getNearbyResorts(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("radius") radius: Double = 200.0,
        @Query("limit") limit: Int = 20,
    ): NearbyResortsResponse

    // =========================================================================
    // Conditions
    // =========================================================================

    @GET("api/v1/resorts/{id}/conditions")
    suspend fun getConditions(@Path("id") resortId: String): ConditionsResponse

    @GET("api/v1/conditions/batch")
    suspend fun getBatchConditions(
        @Query("resort_ids") resortIds: String,
    ): BatchConditionsResponse

    // =========================================================================
    // Snow Quality
    // =========================================================================

    @GET("api/v1/resorts/{id}/snow-quality")
    suspend fun getSnowQuality(@Path("id") resortId: String): SnowQualitySummary

    @GET("api/v1/snow-quality/batch")
    suspend fun getBatchSnowQuality(
        @Query("resort_ids") resortIds: String,
    ): BatchSnowQualityResponse

    // =========================================================================
    // Timeline
    // =========================================================================

    @GET("api/v1/resorts/{id}/timeline")
    suspend fun getTimeline(
        @Path("id") resortId: String,
        @Query("elevation") elevation: String = "mid",
    ): TimelineResponse

    // =========================================================================
    // History
    // =========================================================================

    @GET("api/v1/resorts/{id}/history")
    suspend fun getSnowHistory(
        @Path("id") resortId: String,
        @Query("season") season: String? = null,
    ): SnowHistoryResponse

    // =========================================================================
    // Recommendations (auth required)
    // =========================================================================

    @GET("api/v1/recommendations")
    suspend fun getRecommendations(
        @Query("lat") lat: Double,
        @Query("lng") lng: Double,
        @Query("radius") radius: Double = 500.0,
        @Query("limit") limit: Int = 10,
        @Query("min_quality") minQuality: String? = null,
    ): RecommendationsResponse

    @GET("api/v1/recommendations/best")
    suspend fun getBestConditions(
        @Query("limit") limit: Int = 10,
        @Query("min_quality") minQuality: String? = null,
    ): RecommendationsResponse

    // =========================================================================
    // Auth
    // =========================================================================

    @POST("api/v1/auth/guest")
    suspend fun authenticateAsGuest(@Body request: GuestAuthRequest): AuthResponse

    @POST("api/v1/auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): AuthResponse

    @GET("api/v1/auth/me")
    suspend fun getCurrentUser(): AuthenticatedUserInfo

    // =========================================================================
    // User Preferences (auth required)
    // =========================================================================

    @GET("api/v1/user/preferences")
    suspend fun getUserPreferences(): UserPreferences

    @PUT("api/v1/user/preferences")
    suspend fun updateUserPreferences(@Body preferences: UserPreferences)

    // =========================================================================
    // Trips (auth required)
    // =========================================================================

    @POST("api/v1/trips")
    suspend fun createTrip(@Body request: TripCreateRequest): Trip

    @GET("api/v1/trips")
    suspend fun getTrips(
        @Query("status") status: String? = null,
        @Query("include_past") includePast: Boolean = true,
    ): TripsResponse

    @PUT("api/v1/trips/{id}")
    suspend fun updateTrip(
        @Path("id") tripId: String,
        @Body update: TripUpdateRequest,
    ): Trip

    @DELETE("api/v1/trips/{id}")
    suspend fun deleteTrip(@Path("id") tripId: String)

    // =========================================================================
    // Chat (auth required)
    // =========================================================================

    @POST("api/v1/chat")
    suspend fun sendChatMessage(@Body request: ChatRequest): ChatResponse

    @GET("api/v1/chat/conversations")
    suspend fun getConversations(): ChatConversationsResponse

    @GET("api/v1/chat/conversations/{id}")
    suspend fun getConversationMessages(@Path("id") conversationId: String): ChatMessagesResponse

    @DELETE("api/v1/chat/conversations/{id}")
    suspend fun deleteConversation(@Path("id") conversationId: String)

    // =========================================================================
    // Condition Reports
    // =========================================================================

    @POST("api/v1/resorts/{id}/condition-reports")
    suspend fun submitConditionReport(
        @Path("id") resortId: String,
        @Body request: SubmitConditionReportRequest,
    )

    @GET("api/v1/resorts/{id}/condition-reports")
    suspend fun getConditionReports(
        @Path("id") resortId: String,
        @Query("limit") limit: Int = 10,
    ): ConditionReportsResponse

    // =========================================================================
    // Feedback
    // =========================================================================

    @POST("api/v1/feedback")
    suspend fun submitFeedback(@Body feedback: FeedbackSubmission)

    // =========================================================================
    // Device Tokens & Notifications (auth required)
    // =========================================================================

    @POST("api/v1/user/device-tokens")
    suspend fun registerDeviceToken(@Body request: DeviceTokenRequest)

    @GET("api/v1/user/notification-settings")
    suspend fun getNotificationSettings(): NotificationSettings

    @PUT("api/v1/user/notification-settings")
    suspend fun updateNotificationSettings(@Body settings: NotificationSettingsUpdate)
}
