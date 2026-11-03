package com.powderchaserapp.android.data.repository

import android.os.Build
import com.powderchaserapp.android.BuildConfig
import com.powderchaserapp.android.data.api.PowderChaserApi
import com.powderchaserapp.android.util.ResortEditSuggestion
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FeedbackRepository @Inject constructor(
    private val api: PowderChaserApi,
) {
    /** Submit a "Suggest an Edit" for a resort. POST /api/v1/feedback needs no sign-in. */
    suspend fun submitResortEdit(
        resortId: String,
        resortName: String,
        section: String,
        suggestion: String,
    ): Result<Unit> {
        return try {
            api.submitFeedback(
                ResortEditSuggestion.build(
                    resortId = resortId,
                    resortName = resortName,
                    section = section,
                    suggestion = suggestion,
                    appVersion = BuildConfig.VERSION_NAME,
                    buildNumber = BuildConfig.VERSION_CODE.toString(),
                    deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}",
                    osVersion = Build.VERSION.RELEASE ?: "unknown",
                ),
            )
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
