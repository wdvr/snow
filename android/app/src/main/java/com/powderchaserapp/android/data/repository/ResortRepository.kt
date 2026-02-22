package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import com.powderchaserapp.android.data.db.dao.ResortDao
import com.powderchaserapp.android.data.db.entity.CachedResort
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ResortRepository @Inject constructor(
    private val api: PowderChaserApi,
    private val resortDao: ResortDao,
    private val json: Json,
) {
    fun getResorts(forceRefresh: Boolean = false): Flow<Result<List<Resort>>> = flow {
        // Try cache first
        if (!forceRefresh) {
            val cached = resortDao.getAll()
            if (cached.isNotEmpty() && !cached.first().isExpired()) {
                val resorts = cached.mapNotNull { safeDecodeResort(it.jsonData) }
                if (resorts.isNotEmpty()) {
                    emit(Result.success(resorts))
                    return@flow
                }
            }
        }

        // Fetch from network
        try {
            val response = api.getResorts()
            val resorts = response.resorts

            // Cache results
            val cachedEntities = resorts.map {
                CachedResort(
                    resortId = it.id,
                    jsonData = json.encodeToString(it),
                )
            }
            resortDao.upsertAll(cachedEntities)

            emit(Result.success(resorts))
        } catch (e: Exception) {
            // Fall back to cache on network error
            val cached = resortDao.getAll()
            if (cached.isNotEmpty()) {
                val resorts = cached.mapNotNull { safeDecodeResort(it.jsonData) }
                emit(Result.success(resorts))
            } else {
                emit(Result.failure(e))
            }
        }
    }

    suspend fun getResort(id: String): Result<Resort> {
        // Try cache
        val cached = resortDao.getById(id)
        if (cached != null && !cached.isExpired()) {
            val resort = safeDecodeResort(cached.jsonData)
            if (resort != null) return Result.success(resort)
        }

        return try {
            val resort = api.getResort(id)
            resortDao.upsert(CachedResort(resortId = resort.id, jsonData = json.encodeToString(resort)))
            Result.success(resort)
        } catch (e: Exception) {
            if (cached != null) {
                val resort = safeDecodeResort(cached.jsonData)
                if (resort != null) return Result.success(resort)
            }
            Result.failure(e)
        }
    }

    suspend fun getNearbyResorts(
        lat: Double,
        lon: Double,
        radius: Double = 200.0,
        limit: Int = 20,
    ): Result<NearbyResortsResponse> {
        return try {
            Result.success(api.getNearbyResorts(lat, lon, radius, limit))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun clearCache() {
        resortDao.deleteAll()
    }

    private fun safeDecodeResort(jsonData: String): Resort? {
        return try {
            json.decodeFromString<Resort>(jsonData)
        } catch (_: Exception) {
            null
        }
    }
}
