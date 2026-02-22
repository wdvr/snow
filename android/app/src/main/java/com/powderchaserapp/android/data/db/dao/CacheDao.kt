package com.powderchaserapp.android.data.db.dao

import androidx.room.*
import com.powderchaserapp.android.data.db.entity.*

@Dao
interface ResortDao {
    @Query("SELECT * FROM cached_resorts")
    suspend fun getAll(): List<CachedResort>

    @Query("SELECT * FROM cached_resorts WHERE resort_id = :resortId")
    suspend fun getById(resortId: String): CachedResort?

    @Upsert
    suspend fun upsert(resort: CachedResort)

    @Upsert
    suspend fun upsertAll(resorts: List<CachedResort>)

    @Query("DELETE FROM cached_resorts")
    suspend fun deleteAll()

    @Query("DELETE FROM cached_resorts WHERE cached_at < :expiryTime")
    suspend fun deleteExpired(expiryTime: Long)
}

@Dao
interface ConditionDao {
    @Query("SELECT * FROM cached_conditions WHERE resort_id = :resortId")
    suspend fun getById(resortId: String): CachedCondition?

    @Upsert
    suspend fun upsert(condition: CachedCondition)

    @Query("DELETE FROM cached_conditions")
    suspend fun deleteAll()

    @Query("DELETE FROM cached_conditions WHERE cached_at < :expiryTime")
    suspend fun deleteExpired(expiryTime: Long)
}

@Dao
interface SnowQualityDao {
    @Query("SELECT * FROM cached_snow_quality WHERE resort_id = :resortId")
    suspend fun getById(resortId: String): CachedSnowQuality?

    @Upsert
    suspend fun upsert(quality: CachedSnowQuality)

    @Query("DELETE FROM cached_snow_quality")
    suspend fun deleteAll()

    @Query("DELETE FROM cached_snow_quality WHERE cached_at < :expiryTime")
    suspend fun deleteExpired(expiryTime: Long)
}

@Dao
interface TimelineDao {
    @Query("SELECT * FROM cached_timelines WHERE cache_key = :cacheKey")
    suspend fun getByCacheKey(cacheKey: String): CachedTimeline?

    @Upsert
    suspend fun upsert(timeline: CachedTimeline)

    @Query("DELETE FROM cached_timelines")
    suspend fun deleteAll()

    @Query("DELETE FROM cached_timelines WHERE cached_at < :expiryTime")
    suspend fun deleteExpired(expiryTime: Long)
}

@Dao
interface BatchQualityDao {
    @Query("SELECT * FROM cached_batch_quality WHERE resort_id = :resortId")
    suspend fun getById(resortId: String): CachedBatchQuality?

    @Query("SELECT * FROM cached_batch_quality WHERE resort_id IN (:resortIds)")
    suspend fun getByIds(resortIds: List<String>): List<CachedBatchQuality>

    @Upsert
    suspend fun upsert(quality: CachedBatchQuality)

    @Upsert
    suspend fun upsertAll(qualities: List<CachedBatchQuality>)

    @Query("DELETE FROM cached_batch_quality")
    suspend fun deleteAll()

    @Query("DELETE FROM cached_batch_quality WHERE cached_at < :expiryTime")
    suspend fun deleteExpired(expiryTime: Long)
}
