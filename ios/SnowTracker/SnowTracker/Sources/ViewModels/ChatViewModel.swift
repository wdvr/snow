import Foundation
import os.log

private let chatLog = Logger(subsystem: "com.snowtracker.app", category: "Chat")

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var conversations: [ChatConversation] = []
    @Published var isLoading = false
    @Published var isSending = false
    @Published var errorMessage: String?
    @Published var currentConversationId: String?
    @Published var showConversationList = false

    private let apiClient = APIClient.shared

    // MARK: - Send Message

    func sendMessage(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        isSending = true
        errorMessage = nil

        // Add the user message optimistically
        let userMessage = ChatMessage(
            id: UUID().uuidString,
            role: .user,
            content: trimmed,
            createdAt: Date()
        )
        messages.append(userMessage)

        do {
            let response = try await apiClient.sendChatMessage(trimmed, conversationId: currentConversationId)
            currentConversationId = response.conversationId

            // Add assistant response
            let assistantMessage = ChatMessage(
                id: response.messageId,
                role: .assistant,
                content: response.response,
                createdAt: Date()
            )
            messages.append(assistantMessage)
            chatLog.debug("Chat response received for conversation \(response.conversationId)")
        } catch {
            chatLog.error("Failed to send chat message: \(error)")
            errorMessage = error.localizedDescription
            // Remove the optimistic user message on failure
            messages.removeAll { $0.id == userMessage.id }
        }

        isSending = false
    }

    // MARK: - Load Conversations

    func loadConversations() async {
        isLoading = true
        errorMessage = nil

        do {
            conversations = try await apiClient.getConversations()
            chatLog.debug("Loaded \(self.conversations.count) conversations")
        } catch {
            chatLog.error("Failed to load conversations: \(error)")
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    // MARK: - Load Conversation Messages

    func loadConversation(_ conversationId: String) async {
        isLoading = true
        errorMessage = nil
        currentConversationId = conversationId

        do {
            messages = try await apiClient.getConversation(conversationId)
            chatLog.debug("Loaded \(self.messages.count) messages for conversation \(conversationId)")
        } catch {
            chatLog.error("Failed to load conversation \(conversationId): \(error)")
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    // MARK: - Delete Conversation

    func deleteConversation(_ conversationId: String) async {
        do {
            try await apiClient.deleteConversation(conversationId)
            conversations.removeAll { $0.id == conversationId }
            if currentConversationId == conversationId {
                startNewConversation()
            }
            chatLog.debug("Deleted conversation \(conversationId)")
        } catch {
            chatLog.error("Failed to delete conversation \(conversationId): \(error)")
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Start New Conversation

    func startNewConversation() {
        currentConversationId = nil
        messages = []
        errorMessage = nil
    }
}
