import Foundation
import KeychainSwift
import UIKit
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

    /// The message ID currently being streamed
    @Published var streamingMessageId: String?
    /// The text displayed so far during streaming
    @Published var displayedText: String = ""
    /// Status message shown during tool execution (e.g. "Checking conditions...")
    @Published var statusMessage: String?
    /// Tools currently being executed
    @Published var activeTools: [String] = []

    /// Whether a message is currently being streamed
    var isStreaming: Bool { streamingMessageId != nil }

    /// The full text of the message being streamed (used for skip in non-SSE mode)
    private var fullStreamingText: String = ""
    /// The words of the full text, split for progressive reveal
    private var streamingWords: [String] = []
    /// Current word index during streaming
    private var streamingWordIndex: Int = 0
    /// The streaming task, so it can be cancelled on skip
    private var streamingTask: Task<Void, Never>?

    private let apiClient = APIClient.shared
    private let streamService = ChatStreamService.shared

    /// User location for contextual chat responses (set by ChatView from LocationManager)
    var userLatitude: Double?
    var userLongitude: Double?

    // MARK: - Guest Auth

    /// Ensure we have a valid auth token before making chat API calls.
    /// Guest users skip backend auth during sign-in, so we authenticate them
    /// lazily on first chat use to get a proper JWT token.
    private func ensureAuthenticated() async throws {
        let keychain = KeychainSwift()
        if keychain.get(AuthenticationService.Keys.authToken) != nil {
            return // Already have a token
        }

        // No token — check if this is a guest user and authenticate with backend
        let authService = AuthenticationService.shared
        if authService.isAuthenticated,
           authService.currentUser?.provider == .guest {
            chatLog.info("Guest user has no token, authenticating with backend")
            let deviceId = keychain.get("com.snowtracker.userIdentifier") ?? UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            let response = try await apiClient.authenticateAsGuest(deviceId: deviceId)
            keychain.set(response.accessToken, forKey: AuthenticationService.Keys.authToken)
            keychain.set(response.refreshToken, forKey: AuthenticationService.Keys.refreshToken)
            chatLog.info("Guest backend auth successful, tokens stored")
        }
    }

    // MARK: - Send Message

    func sendMessage(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        isSending = true
        errorMessage = nil
        statusMessage = nil
        activeTools = []

        // Ensure guest users have valid auth tokens before making API calls
        do {
            try await ensureAuthenticated()
        } catch {
            chatLog.error("Failed to authenticate for chat: \(error)")
            errorMessage = "Please sign in to use chat."
            isSending = false
            return
        }

        // Add the user message optimistically
        let userMessage = ChatMessage(
            id: UUID().uuidString,
            role: .user,
            content: trimmed,
            createdAt: Date()
        )
        messages.append(userMessage)

        // Try SSE streaming first if available
        if streamService.isStreamingAvailable {
            do {
                try await sendMessageViaStream(trimmed)
                return
            } catch {
                chatLog.warning("Stream failed, falling back to REST: \(error)")
                // Fall through to REST
            }
        }

        // Fallback: non-streaming REST call
        do {
            let response = try await sendWithAutoRefresh(trimmed)
            currentConversationId = response.conversationId

            let assistantMessage = ChatMessage(
                id: response.messageId,
                role: .assistant,
                content: response.response,
                createdAt: Date()
            )
            messages.append(assistantMessage)
            isSending = false

            // Start progressive text reveal for REST responses
            await startLocalStreaming(messageId: response.messageId, fullText: response.response)
            chatLog.debug("Chat response received for conversation \(response.conversationId)")
        } catch APIError.unauthorized {
            chatLog.error("Chat unauthorized after refresh attempt")
            errorMessage = "Please sign in again to use chat."
            let errorResponse = ChatMessage(
                id: UUID().uuidString,
                role: .assistant,
                content: "Your session has expired. Please sign out and sign in again to continue chatting.",
                createdAt: Date()
            )
            messages.append(errorResponse)
            isSending = false
        } catch {
            chatLog.error("Failed to send chat message: \(error)")
            errorMessage = "Failed to send message. Check your connection and try again."
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

    // MARK: - SSE Streaming

    private func sendMessageViaStream(_ text: String) async throws {
        var currentSegmentId = "stream-\(UUID().uuidString)"
        var currentSegmentText = ""
        var finalMessageId = ""
        var finalConversationId = ""

        // Add first placeholder assistant message
        messages.append(ChatMessage(
            id: currentSegmentId,
            role: .assistant,
            content: "",
            createdAt: Date()
        ))

        let stream = streamService.sendMessageStream(
            message: text,
            conversationId: currentConversationId,
            latitude: userLatitude,
            longitude: userLongitude
        )

        do {
            for try await event in stream {
                switch event.type {
                case .status:
                    statusMessage = event.message

                case .toolStart:
                    // If we have accumulated text, finalize it as a separate "thinking" bubble
                    if !currentSegmentText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        if let index = messages.firstIndex(where: { $0.id == currentSegmentId }) {
                            messages[index] = ChatMessage(
                                id: currentSegmentId,
                                role: .assistant,
                                content: currentSegmentText,
                                createdAt: Date(),
                                isIntermediate: true
                            )
                        }
                        streamingMessageId = nil
                        displayedText = ""
                        currentSegmentText = ""
                        currentSegmentId = "stream-\(UUID().uuidString)"
                    } else {
                        // No text accumulated — remove empty placeholder
                        messages.removeAll { $0.id == currentSegmentId }
                        currentSegmentId = "stream-\(UUID().uuidString)"
                    }

                    statusMessage = event.message ?? "Running \(event.tool ?? "tool")..."
                    if let tool = event.tool {
                        activeTools.append(tool)
                    }

                case .toolDone:
                    if let tool = event.tool {
                        activeTools.removeAll { $0 == tool }
                    }

                case .textDelta:
                    let delta = event.text ?? ""
                    // Create placeholder for new segment if needed
                    if !messages.contains(where: { $0.id == currentSegmentId }) {
                        messages.append(ChatMessage(
                            id: currentSegmentId,
                            role: .assistant,
                            content: "",
                            createdAt: Date()
                        ))
                    }
                    currentSegmentText += delta
                    statusMessage = nil
                    if let index = messages.firstIndex(where: { $0.id == currentSegmentId }) {
                        messages[index] = ChatMessage(
                            id: currentSegmentId,
                            role: .assistant,
                            content: currentSegmentText,
                            createdAt: Date()
                        )
                    }
                    displayedText = currentSegmentText
                    streamingMessageId = currentSegmentId

                case .done:
                    finalMessageId = event.messageId ?? ""
                    finalConversationId = event.conversationId ?? ""

                case .error:
                    throw ChatStreamError.serverError(event.message ?? "Chat error")
                }
            }
        } catch {
            isSending = false
            statusMessage = nil
            activeTools = []
            streamingMessageId = nil
            displayedText = ""
            if currentSegmentText.isEmpty {
                messages.removeAll { $0.id == currentSegmentId }
            }
            throw error
        }

        // Finalize the last segment
        if currentSegmentText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            messages.removeAll { $0.id == currentSegmentId }
            chatLog.warning("Stream completed with empty final segment")
        } else if !finalMessageId.isEmpty {
            // Update the last segment with the real message ID from backend
            if let index = messages.firstIndex(where: { $0.id == currentSegmentId }) {
                messages[index] = ChatMessage(
                    id: finalMessageId,
                    role: .assistant,
                    content: currentSegmentText,
                    createdAt: Date()
                )
            }
        }

        if !finalConversationId.isEmpty, currentConversationId == nil {
            currentConversationId = finalConversationId
        }

        isSending = false
        statusMessage = nil
        activeTools = []
        streamingMessageId = nil
        displayedText = ""
        chatLog.debug("Stream complete for conversation \(finalConversationId)")
    }

    // MARK: - Auto Token Refresh

    /// Try sending a chat message; on 401, refresh the token and retry once.
    private func sendWithAutoRefresh(_ text: String) async throws -> ChatResponse {
        do {
            return try await apiClient.sendChatMessage(text, conversationId: currentConversationId, latitude: userLatitude, longitude: userLongitude)
        } catch APIError.unauthorized {
            chatLog.info("Chat got 401, attempting token refresh")
            let keychain = KeychainSwift()
            guard let refreshToken = keychain.get(AuthenticationService.Keys.refreshToken) else {
                throw APIError.unauthorized
            }
            do {
                let authResponse = try await apiClient.refreshAuthTokens(refreshToken: refreshToken)
                keychain.set(authResponse.accessToken, forKey: AuthenticationService.Keys.authToken)
                keychain.set(authResponse.refreshToken, forKey: AuthenticationService.Keys.refreshToken)
                chatLog.info("Token refreshed successfully, retrying chat")
                return try await apiClient.sendChatMessage(text, conversationId: currentConversationId, latitude: userLatitude, longitude: userLongitude)
            } catch {
                chatLog.error("Token refresh failed: \(error)")
                throw APIError.unauthorized
            }
        }
    }

    // MARK: - Local Streaming (Progressive Text Reveal for REST)

    /// Start progressive text reveal for a message (~30 words/second)
    private func startLocalStreaming(messageId: String, fullText: String) async {
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
            try await ensureAuthenticated()
            conversations = try await apiClient.getConversations()
            chatLog.debug("Loaded \(self.conversations.count) conversations")
        } catch APIError.unauthorized {
            // Try refreshing the token once
            chatLog.info("Conversations got 401, attempting token refresh")
            let keychain = KeychainSwift()
            if let refreshToken = keychain.get(AuthenticationService.Keys.refreshToken) {
                do {
                    let authResponse = try await apiClient.refreshAuthTokens(refreshToken: refreshToken)
                    keychain.set(authResponse.accessToken, forKey: AuthenticationService.Keys.authToken)
                    keychain.set(authResponse.refreshToken, forKey: AuthenticationService.Keys.refreshToken)
                    conversations = try await apiClient.getConversations()
                    chatLog.debug("Loaded \(self.conversations.count) conversations after token refresh")
                } catch {
                    chatLog.error("Token refresh failed for conversations: \(error)")
                    errorMessage = "Please sign in again to view chat history."
                }
            } else {
                errorMessage = "Please sign in to view chat history."
            }
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
            try await ensureAuthenticated()
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
