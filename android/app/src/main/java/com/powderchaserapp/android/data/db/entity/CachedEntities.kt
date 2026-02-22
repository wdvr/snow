package com.powderchaserapp.android.data.db.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cached_resorts")
data class CachedResort(
    @PrimaryKey
    @ColumnInfo(name = "resort_id")
    val resortId: String,

    @ColumnInfo(name = "json_data")
    val jsonData: String,

    @ColumnInfo(name = "cached_at")
    val cachedAt: Long = System.currentTimeMillis(),
) {
    companion object {
        const val TTL_MS = 24 * 60 * 60 * 1000L // 24 hours
    }

    fun isExpired(): Boolean = System.currentTimeMillis() - cachedAt > TTL_MS
}

@Entity(tableName = "cached_conditions")
data class CachedCondition(
    @PrimaryKey
    @ColumnInfo(name = "resort_id")
    val resortId: String,

    @ColumnInfo(name = "json_data")
    val jsonData: String,

    @ColumnInfo(name = "cached_at")
    val cachedAt: Long = System.currentTimeMillis(),
) {
    companion object {
        const val TTL_MS = 30 * 60 * 1000L // 30 minutes
    }

    fun isExpired(): Boolean = System.currentTimeMillis() - cachedAt > TTL_MS
}

@Entity(tableName = "cached_snow_quality")
data class CachedSnowQuality(
    @PrimaryKey
    @ColumnInfo(name = "resort_id")
    val resortId: String,

    @ColumnInfo(name = "json_data")
    val jsonData: String,

    @ColumnInfo(name = "cached_at")
    val cachedAt: Long = System.currentTimeMillis(),
) {
    companion object {
        const val TTL_MS = 60 * 60 * 1000L // 1 hour
    }

    fun isExpired(): Boolean = System.currentTimeMillis() - cachedAt > TTL_MS
}

@Entity(tableName = "cached_timelines")
data class CachedTimeline(
    @PrimaryKey
    @ColumnInfo(name = "cache_key")
    val cacheKey: String, // resortId_elevation

    @ColumnInfo(name = "resort_id")
    val resortId: String,

    @ColumnInfo(name = "elevation")
    val elevation: String,

    @ColumnInfo(name = "json_data")
    val jsonData: String,

    @ColumnInfo(name = "cached_at")
    val cachedAt: Long = System.currentTimeMillis(),
) {
    companion object {
        const val TTL_MS = 60 * 60 * 1000L // 1 hour

        fun makeCacheKey(resortId: String, elevation: String): String =
            "${resortId}_$elevation"
    }

    fun isExpired(): Boolean = System.currentTimeMillis() - cachedAt > TTL_MS
}

@Entity(tableName = "cached_batch_quality")
data class CachedBatchQuality(
    @PrimaryKey
    @ColumnInfo(name = "resort_id")
    val resortId: String,

    @ColumnInfo(name = "json_data")
    val jsonData: String,

    @ColumnInfo(name = "cached_at")
    val cachedAt: Long = System.currentTimeMillis(),
) {
    companion object {
        const val TTL_MS = 60 * 60 * 1000L // 1 hour
    }

    fun isExpired(): Boolean = System.currentTimeMillis() - cachedAt > TTL_MS
}
