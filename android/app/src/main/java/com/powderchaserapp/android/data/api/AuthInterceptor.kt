package com.powderchaserapp.android.data.api

import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

/**
 * OkHttp interceptor that adds Bearer token from SecureTokenStore.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenStore: SecureTokenStore,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = tokenStore.accessToken

        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .header("Content-Type", "application/json")
                .build()
        } else {
            original.newBuilder()
                .header("Content-Type", "application/json")
                .build()
        }

        return chain.proceed(request)
    }
}

/**
 * OkHttp authenticator that handles 401 responses by refreshing the token.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenStore: SecureTokenStore,
    private val apiProvider: ApiProvider,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // Don't retry if already attempted refresh
        if (response.request.header("X-Retry-Auth") != null) {
            return null
        }

        val refreshToken = tokenStore.refreshToken ?: return null

        return try {
            // Use a separate API instance to avoid circular dependency
            val refreshApi = apiProvider.getRefreshApi()
            val call = refreshApi.refreshToken(RefreshTokenRequest(refreshToken))
            val refreshResponse = call.execute()

            if (refreshResponse.isSuccessful && refreshResponse.body() != null) {
                val authResponse = refreshResponse.body()!!
                tokenStore.saveAuthResponse(authResponse)

                response.request.newBuilder()
                    .header("Authorization", "Bearer ${authResponse.accessToken}")
                    .header("X-Retry-Auth", "true")
                    .build()
            } else {
                // Refresh failed, clear tokens
                tokenStore.clearTokens()
                null
            }
        } catch (e: Exception) {
            tokenStore.clearTokens()
            null
        }
    }
}

/**
 * Provider for creating a separate Retrofit instance for token refresh.
 * This avoids circular dependency with the main API that uses the authenticator.
 */
interface ApiProvider {
    fun getRefreshApi(): RefreshApi
}

/**
 * Minimal API interface for token refresh only.
 */
interface RefreshApi {
    @retrofit2.http.POST("api/v1/auth/refresh")
    fun refreshToken(@retrofit2.http.Body request: RefreshTokenRequest): retrofit2.Call<AuthResponse>
}
