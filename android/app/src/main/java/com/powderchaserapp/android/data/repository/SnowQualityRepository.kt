package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import com.powderchaserapp.android.data.db.dao.BatchQualityDao
import com.powderchaserapp.android.data.db.dao.SnowQualityDao
import com.powderchaserapp.android.data.db.entity.CachedBatchQuality
import com.powderchaserapp.android.data.db.entity.CachedSnowQuality
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SnowQualityRepository @Inject constructor(
    private val api: PowderChaserApi,
    private val snowQualityDao: SnowQualityDao,
    private val batchQualityDao: BatchQualityDao,
    private val json: Json,
) {
    suspend fun getSnowQuality(resortId: String, forceRefresh: Boolean = false): Result<SnowQualitySummary> {
        if (!forceRefresh) {
            val cached = snowQualityDao.getById(resortId)
            if (cached != null && !cached.isExpired()) {
                return try {
                    Result.success(json.decodeFromString<SnowQualitySummary>(cached.jsonData))
                } catch (_: Exception) {
                    fetchAndCacheQuality(resortId)
                }
            }
        }
        return fetchAndCacheQuality(resortId)
    }

    suspend fun getBatchSnowQuality(
        resortIds: List<String>,
        forceRefresh: Boolean = false,
    ): Result<Map<String, SnowQualitySummaryLight>> {
        if (!forceRefresh) {
            val cached = batchQualityDao.getByIds(resortIds)
            if (cached.isNotEmpty() && cached.none { it.isExpired() } && cached.size == resortIds.size) {
                return try {
                    val result = cached.associate {
                        val quality = json.decodeFromString<SnowQualitySummaryLight>(it.jsonData)
                        quality.resortId to quality
                    }
                    Result.success(result)
                } catch (_: Exception) {
                    fetchAndCacheBatchQuality(resortIds)
                }
            }
        }
        return fetchAndCacheBatchQuality(resortIds)
    }

    private suspend fun fetchAndCacheQuality(resortId: String): Result<SnowQualitySummary> {
        return try {
            val quality = api.getSnowQuality(resortId)
            snowQualityDao.upsert(
                CachedSnowQuality(
                    resortId = resortId,
                    jsonData = json.encodeToString(quality),
                )
            )
            Result.success(quality)
        } catch (e: Exception) {
            val cached = snowQualityDao.getById(resortId)
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

    private suspend fun fetchAndCacheBatchQuality(
        resortIds: List<String>,
    ): Result<Map<String, SnowQualitySummaryLight>> {
        return try {
            val idsString = resortIds.joinToString(",")
            val response = api.getBatchSnowQuality(idsString)
            val entities = response.results.map { (_, quality) ->
                CachedBatchQuality(
                    resortId = quality.resortId,
                    jsonData = json.encodeToString(quality),
                )
            }
            batchQualityDao.upsertAll(entities)
            Result.success(response.results)
        } catch (e: Exception) {
            // Fall back to cache
            val cached = batchQualityDao.getByIds(resortIds)
            if (cached.isNotEmpty()) {
                try {
                    val result = cached.associate {
                        val quality = json.decodeFromString<SnowQualitySummaryLight>(it.jsonData)
                        quality.resortId to quality
                    }
                    Result.success(result)
                } catch (_: Exception) {
                    Result.failure(e)
                }
            } else {
                Result.failure(e)
            }
        }
    }

    suspend fun clearCache() {
        snowQualityDao.deleteAll()
        batchQualityDao.deleteAll()
    }
}
