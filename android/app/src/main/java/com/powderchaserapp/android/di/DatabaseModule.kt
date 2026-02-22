package com.powderchaserapp.android.di

import android.content.Context
import androidx.room.Room
import com.powderchaserapp.android.data.db.AppDatabase
import com.powderchaserapp.android.data.db.dao.*
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            AppDatabase.DATABASE_NAME,
        )
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideResortDao(db: AppDatabase): ResortDao = db.resortDao()

    @Provides
    fun provideConditionDao(db: AppDatabase): ConditionDao = db.conditionDao()

    @Provides
    fun provideSnowQualityDao(db: AppDatabase): SnowQualityDao = db.snowQualityDao()

    @Provides
    fun provideTimelineDao(db: AppDatabase): TimelineDao = db.timelineDao()

    @Provides
    fun provideBatchQualityDao(db: AppDatabase): BatchQualityDao = db.batchQualityDao()
}
