package com.powderchaserapp.android.data.repository

import com.powderchaserapp.android.data.api.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ChatRepository @Inject constructor(
    private val api: PowderChaserApi,
) {
    suspend fun sendMessage(message: String, conversationId: String? = null): Result<ChatResponse> {
        return try {
            val response = api.sendChatMessage(ChatRequest(message, conversationId))
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getConversations(): Result<List<ChatConversation>> {
        return try {
            val response = api.getConversations()
            Result.success(response.conversations)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getConversationMessages(conversationId: String): Result<List<ChatMessage>> {
        return try {
            val response = api.getConversationMessages(conversationId)
            Result.success(response.messages)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteConversation(conversationId: String): Result<Unit> {
        return try {
            api.deleteConversation(conversationId)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
