package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import com.powderchaserapp.android.data.db.dao.TimelineDao
import com.powderchaserapp.android.data.db.entity.CachedTimeline
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TimelineRepository @Inject constructor(
    private val api: PowderChaserApi,
    private val timelineDao: TimelineDao,
    private val json: Json,
) {
    suspend fun getTimeline(
        resortId: String,
        elevation: String = "mid",
        forceRefresh: Boolean = false,
    ): Result<TimelineResponse> {
        val cacheKey = CachedTimeline.makeCacheKey(resortId, elevation)

        if (!forceRefresh) {
            val cached = timelineDao.getByCacheKey(cacheKey)
            if (cached != null && !cached.isExpired()) {
                return try {
                    Result.success(json.decodeFromString<TimelineResponse>(cached.jsonData))
                } catch (_: Exception) {
                    fetchAndCacheTimeline(resortId, elevation, cacheKey)
                }
            }
        }
        return fetchAndCacheTimeline(resortId, elevation, cacheKey)
    }

    private suspend fun fetchAndCacheTimeline(
        resortId: String,
        elevation: String,
        cacheKey: String,
    ): Result<TimelineResponse> {
        return try {
            val response = api.getTimeline(resortId, elevation)
            timelineDao.upsert(
                CachedTimeline(
                    cacheKey = cacheKey,
                    resortId = resortId,
                    elevation = elevation,
                    jsonData = json.encodeToString(response),
                )
            )
            Result.success(response)
        } catch (e: Exception) {
            val cached = timelineDao.getByCacheKey(cacheKey)
            if (cached != null) {
                try {
                    Result.success(json.decodeFromString(cached.jsonData))
                } catch (_: Exception) {
                    Result.failure(e)
                }
            } else {
                Result.failure(e)
            }
        }
    }

    suspend fun clearCache() {
        timelineDao.deleteAll()
    }
}
