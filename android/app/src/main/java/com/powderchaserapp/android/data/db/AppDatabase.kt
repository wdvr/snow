package com.powderchaserapp.android.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.powderchaserapp.android.data.db.dao.*
import com.powderchaserapp.android.data.db.entity.*

@Database(
    entities = [
        CachedResort::class,
        CachedCondition::class,
        CachedSnowQuality::class,
        CachedTimeline::class,
        CachedBatchQuality::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun resortDao(): ResortDao
    abstract fun conditionDao(): ConditionDao
    abstract fun snowQualityDao(): SnowQualityDao
    abstract fun timelineDao(): TimelineDao
    abstract fun batchQualityDao(): BatchQualityDao

    companion object {
        const val DATABASE_NAME = "powder_chaser_db"
    }
}
