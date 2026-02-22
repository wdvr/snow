package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: PowderChaserApi,
    private val tokenStore: SecureTokenStore,
) {
    val isLoggedIn: Boolean get() = tokenStore.isLoggedIn
    val userId: String? get() = tokenStore.userId

    suspend fun authenticateAsGuest(): Result<AuthResponse> {
        return try {
            val deviceId = tokenStore.deviceId ?: UUID.randomUUID().toString().also {
                tokenStore.deviceId = it
            }
            val response = api.authenticateAsGuest(GuestAuthRequest(deviceId))
            tokenStore.saveAuthResponse(response)
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun refreshToken(): Result<AuthResponse> {
        val refreshToken = tokenStore.refreshToken ?: return Result.failure(
            IllegalStateException("No refresh token available")
        )
        return try {
            val response = api.refreshToken(RefreshTokenRequest(refreshToken))
            tokenStore.saveAuthResponse(response)
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCurrentUser(): Result<AuthenticatedUserInfo> {
        return try {
            Result.success(api.getCurrentUser())
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun signOut() {
        tokenStore.clearTokens()
    }
}
