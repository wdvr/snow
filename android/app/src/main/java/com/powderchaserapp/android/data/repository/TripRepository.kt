package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TripRepository @Inject constructor(
    private val api: PowderChaserApi,
) {
    suspend fun getTrips(status: String? = null, includePast: Boolean = true): Result<List<Trip>> {
        return try {
            val response = api.getTrips(status, includePast)
            Result.success(response.trips)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createTrip(request: TripCreateRequest): Result<Trip> {
        return try {
            Result.success(api.createTrip(request))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateTrip(tripId: String, update: TripUpdateRequest): Result<Trip> {
        return try {
            Result.success(api.updateTrip(tripId, update))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteTrip(tripId: String): Result<Unit> {
        return try {
            api.deleteTrip(tripId)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
