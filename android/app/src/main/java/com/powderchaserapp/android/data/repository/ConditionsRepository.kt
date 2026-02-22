package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import com.powderchaserapp.android.data.db.dao.ConditionDao
import com.powderchaserapp.android.data.db.entity.CachedCondition
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ConditionsRepository @Inject constructor(
    private val api: PowderChaserApi,
    private val conditionDao: ConditionDao,
    private val json: Json,
) {
    suspend fun getConditions(resortId: String, forceRefresh: Boolean = false): Result<List<WeatherCondition>> {
        if (!forceRefresh) {
            val cached = conditionDao.getById(resortId)
            if (cached != null && !cached.isExpired()) {
                return try {
                    val response = json.decodeFromString<ConditionsResponse>(cached.jsonData)
                    Result.success(response.conditions)
                } catch (_: Exception) {
                    fetchAndCacheConditions(resortId)
                }
            }
        }
        return fetchAndCacheConditions(resortId)
    }

    suspend fun getBatchConditions(resortIds: List<String>): Result<Map<String, List<WeatherCondition>>> {
        return try {
            val idsString = resortIds.joinToString(",")
            val response = api.getBatchConditions(idsString)
            val result = response.results.mapValues { it.value.conditions }
            Result.success(result)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun fetchAndCacheConditions(resortId: String): Result<List<WeatherCondition>> {
        return try {
            val response = api.getConditions(resortId)
            conditionDao.upsert(
                CachedCondition(
                    resortId = resortId,
                    jsonData = json.encodeToString(response),
                )
            )
            Result.success(response.conditions)
        } catch (e: Exception) {
            // Fall back to cache
            val cached = conditionDao.getById(resortId)
            if (cached != null) {
                try {
                    val response = json.decodeFromString<ConditionsResponse>(cached.jsonData)
                    Result.success(response.conditions)
                } catch (_: Exception) {
                    Result.failure(e)
                }
            } else {
                Result.failure(e)
            }
        }
    }

    suspend fun clearCache() {
        conditionDao.deleteAll()
    }
}
