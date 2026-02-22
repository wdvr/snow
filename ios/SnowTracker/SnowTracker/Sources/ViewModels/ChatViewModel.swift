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

    // MARK: - Streaming State

    /// The message ID currently being streamed (progressive text reveal)
    @Published var streamingMessageId: String?
    /// The text displayed so far during streaming
    @Published var displayedText: String = ""

    /// Whether a message is currently being progressively revealed
    var isStreaming: Bool { streamingMessageId != nil }

    /// The full text of the message being streamed (used for skip)
    private var fullStreamingText: String = ""
    /// The words of the full text, split for progressive reveal
    private var streamingWords: [String] = []
    /// Current word index during streaming
    private var streamingWordIndex: Int = 0
    /// The streaming task, so it can be cancelled on skip
    private var streamingTask: Task<Void, Never>?

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

            // Add assistant response with empty content initially
            let assistantMessage = ChatMessage(
                id: response.messageId,
                role: .assistant,
                content: response.response,
                createdAt: Date()
            )
            messages.append(assistantMessage)
            isSending = false

            // Start progressive text reveal
            await startStreaming(messageId: response.messageId, fullText: response.response)
            chatLog.debug("Chat response received for conversation \(response.conversationId)")
        } catch {
            chatLog.error("Failed to send chat message: \(error)")
            errorMessage = "Failed to send message. Check your connection and try again."
            // Add an error message from assistant so the user sees what happened
            let errorResponse = ChatMessage(
                id: UUID().uuidString,
                role: .assistant,
                content: "Sorry, I couldn't process your request right now. Please try again.",
                createdAt: Date()
            )
            messages.append(errorResponse)
            isSending = false
        }
    }

    // MARK: - Streaming

    /// Start progressive text reveal for a message (~30 words/second)
    private func startStreaming(messageId: String, fullText: String) async {
        fullStreamingText = fullText
        streamingWords = fullText.splitKeepingSeparators()
        streamingWordIndex = 0
        displayedText = ""
        streamingMessageId = messageId

        // ~30 words/second = ~33ms per word
        let delayNanoseconds: UInt64 = 33_000_000

        streamingTask = Task { [weak self] in
            guard let self else { return }

            while self.streamingWordIndex < self.streamingWords.count {
                guard !Task.isCancelled else { return }

                self.streamingWordIndex += 1
                self.displayedText = self.streamingWords.prefix(self.streamingWordIndex).joined()

                do {
                    try await Task.sleep(nanoseconds: delayNanoseconds)
                } catch {
                    // Task was cancelled (user tapped to skip)
                    return
                }
            }

            // Streaming complete
            self.finishStreaming()
        }
    }

    /// Skip the streaming animation and show the full text immediately
    func skipStreaming() {
        guard isStreaming else { return }
        streamingTask?.cancel()
        streamingTask = nil
        displayedText = fullStreamingText
        finishStreaming()
    }

    /// Clean up streaming state
    private func finishStreaming() {
        streamingMessageId = nil
        displayedText = ""
        fullStreamingText = ""
        streamingWords = []
        streamingWordIndex = 0
        streamingTask = nil
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
        streamingTask?.cancel()
        finishStreaming()
        currentConversationId = nil
        messages = []
        errorMessage = nil
    }
}

// MARK: - String Splitting Helper

extension String {
    /// Split the string into words while keeping whitespace/punctuation attached,
    /// so joining the result exactly reproduces the original string.
    func splitKeepingSeparators() -> [String] {
        var result: [String] = []
        var current = ""

        for char in self {
            if char == " " || char == "\n" {
                current.append(char)
                result.append(current)
                current = ""
            } else {
                current.append(char)
            }
        }

        if !current.isEmpty {
            result.append(current)
        }

        return result
    }
}
