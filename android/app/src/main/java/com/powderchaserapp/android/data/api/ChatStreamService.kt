package com.powderchaserapp.android.data.api

import android.util.Log
import com.powderchaserapp.android.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "ChatStreamService"

// =============================================================================
// SSE Event Types
// =============================================================================

@Serializable
enum class ChatStreamEventType {
    @SerialName("status") STATUS,
    @SerialName("tool_start") TOOL_START,
    @SerialName("tool_done") TOOL_DONE,
    @SerialName("text_delta") TEXT_DELTA,
    @SerialName("done") DONE,
    @SerialName("error") ERROR,
}

@Serializable
data class ChatStreamEvent(
    val type: ChatStreamEventType,
    val message: String? = null,
    val tool: String? = null,
    val text: String? = null,
    @SerialName("conversation_id") val conversationId: String? = null,
    @SerialName("message_id") val messageId: String? = null,
    @SerialName("duration_ms") val durationMs: Int? = null,
)

// =============================================================================
// Service
// =============================================================================

@Singleton
class ChatStreamService @Inject constructor(
    private val tokenStore: SecureTokenStore,
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    // Separate OkHttp client with longer timeouts for streaming
    private val streamClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    /** Whether SSE streaming is available for the current build config. */
    val isStreamingAvailable: Boolean
        get() = getStreamUrl() != null

    private fun getStreamUrl(): String? {
        val baseUrl = BuildConfig.API_BASE_URL
        return when {
            baseUrl.contains("staging") ->
                "https://h5yv2vpzlchdpbvnf2ddc6v5xu0lmztp.lambda-url.us-west-2.on.aws/"
            baseUrl.contains("api.powderchaserapp.com") && !baseUrl.contains("dev.") && !baseUrl.contains("staging.") ->
                "https://z3s2kwjc2cs6zhhgui3jmus5e40igoyr.lambda-url.us-west-2.on.aws/"
            else -> null // dev has no streaming
        }
    }

    /**
     * Send a chat message via SSE streaming.
     * Returns a Flow of ChatStreamEvent.
     */
    fun sendMessageStream(
        message: String,
        conversationId: String?,
    ): Flow<ChatStreamEvent> = callbackFlow {
        val url = getStreamUrl() ?: run {
            close(IllegalStateException("Streaming not available"))
            return@callbackFlow
        }

        val bodyMap = buildMap<String, String> {
            put("message", message)
            conversationId?.let { put("conversation_id", it) }
        }
        val bodyJson = json.encodeToString(
            kotlinx.serialization.serializer<Map<String, String>>(),
            bodyMap,
        )

        val request = Request.Builder()
            .url(url)
            .post(bodyJson.toRequestBody("application/json".toMediaType()))
            .apply {
                tokenStore.accessToken?.let { token ->
                    addHeader("Authorization", "Bearer $token")
                }
                addHeader("Accept", "text/event-stream")
            }
            .build()

        val call = streamClient.newCall(request)

        withContext(Dispatchers.IO) {
            try {
                val response = call.execute()

                if (!response.isSuccessful) {
                    close(Exception("HTTP ${response.code}: ${response.message}"))
                    return@withContext
                }

                val body = response.body ?: run {
                    close(Exception("Empty response body"))
                    return@withContext
                }

                val reader = BufferedReader(InputStreamReader(body.byteStream()))
                var line: String?

                while (reader.readLine().also { line = it } != null) {
                    val currentLine = line ?: continue

                    // SSE format: "data: {json}\n"
                    if (!currentLine.startsWith("data: ")) continue
                    val jsonString = currentLine.removePrefix("data: ")

                    try {
                        val event = json.decodeFromString<ChatStreamEvent>(jsonString)
                        trySend(event)

                        if (event.type == ChatStreamEventType.ERROR) {
                            close(Exception(event.message ?: "Server error"))
                            return@withContext
                        }
                        if (event.type == ChatStreamEventType.DONE) {
                            close()
                            return@withContext
                        }
                    } catch (e: Exception) {
                        Log.w(TAG, "Failed to parse SSE event: $jsonString", e)
                    }
                }

                close()
            } catch (e: Exception) {
                close(e)
            }
        }

        awaitClose {
            call.cancel()
        }
    }
}
