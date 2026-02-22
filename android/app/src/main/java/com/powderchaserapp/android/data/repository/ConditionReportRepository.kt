package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ConditionReportRepository @Inject constructor(
    private val api: PowderChaserApi,
) {
    suspend fun getConditionReports(
        resortId: String,
        limit: Int = 10,
    ): Result<ConditionReportsResponse> {
        return try {
            Result.success(api.getConditionReports(resortId, limit))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun submitConditionReport(
        resortId: String,
        conditionType: String,
        score: Int,
        comment: String? = null,
        elevationLevel: String? = null,
    ): Result<Unit> {
        return try {
            api.submitConditionReport(
                resortId,
                SubmitConditionReportRequest(conditionType, score, comment, elevationLevel),
            )
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
