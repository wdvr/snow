import Foundation
import KeychainSwift
import os.log

private let streamLog = Logger(subsystem: "com.snowtracker.app", category: "ChatStream")

/// SSE event types from the streaming chat Lambda
enum ChatStreamEventType: String, Codable {
    case status
    case toolStart = "tool_start"
    case toolDone = "tool_done"
    case textDelta = "text_delta"
    case done
    case error
}

/// A single SSE event from the chat stream
struct ChatStreamEvent: Codable {
    let type: ChatStreamEventType
    let message: String?
    let tool: String?
    let input: [String: AnyCodable]?
    let durationMs: Int?
    let text: String?
    let conversationId: String?
    let messageId: String?

    enum CodingKeys: String, CodingKey {
        case type, message, tool, input, text
        case durationMs = "duration_ms"
        case conversationId = "conversation_id"
        case messageId = "message_id"
    }
}

/// Callback-based interface for streaming chat events
protocol ChatStreamDelegate: AnyObject {
    @MainActor func chatStreamDidReceiveStatus(_ message: String)
    @MainActor func chatStreamDidStartTool(_ tool: String, message: String?)
    @MainActor func chatStreamDidFinishTool(_ tool: String)
    @MainActor func chatStreamDidReceiveTextDelta(_ text: String)
    @MainActor func chatStreamDidComplete(conversationId: String, messageId: String)
    @MainActor func chatStreamDidFail(_ error: Error)
}

/// Service for consuming SSE chat streams from the Lambda Function URL
final class ChatStreamService {
    static let shared = ChatStreamService()
    private init() {}

    /// Whether streaming is available for the current environment
    @MainActor
    var isStreamingAvailable: Bool {
        AppConfiguration.shared.selectedEnvironment.chatStreamURL != nil
    }

    /// Send a message via SSE streaming. Returns an async throwing stream of events.
    func sendMessageStream(
        message: String,
        conversationId: String?,
        latitude: Double? = nil,
        longitude: Double? = nil
    ) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    try await performStream(message: message, conversationId: conversationId, latitude: latitude, longitude: longitude, continuation: continuation)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    private func performStream(
        message: String,
        conversationId: String?,
        latitude: Double?,
        longitude: Double?,
        continuation: AsyncThrowingStream<ChatStreamEvent, Error>.Continuation
    ) async throws {
        let streamURL = await MainActor.run { AppConfiguration.shared.selectedEnvironment.chatStreamURL }
        guard let url = streamURL else {
            throw ChatStreamError.streamingNotAvailable
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add auth token
        let token = KeychainSwift().get("com.snowtracker.authToken")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Build request body
        var body: [String: Any] = ["message": message]
        if let conversationId {
            body["conversation_id"] = conversationId
        }
        if let latitude {
            body["latitude"] = latitude
        }
        if let longitude {
            body["longitude"] = longitude
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        request.timeoutInterval = 120

        let (bytes, response) = try await URLSession.shared.bytes(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ChatStreamError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw ChatStreamError.httpError(httpResponse.statusCode)
        }

        let decoder = JSONDecoder()
        var dataBuffer = Data()

        for try await byte in bytes {
            dataBuffer.append(byte)

            // Process complete lines (delimited by newline bytes)
            while let newlineIndex = dataBuffer.firstIndex(of: UInt8(ascii: "\n")) {
                let lineData = dataBuffer[dataBuffer.startIndex..<newlineIndex]
                dataBuffer.removeSubrange(dataBuffer.startIndex...newlineIndex)

                guard let line = String(data: Data(lineData), encoding: .utf8) else { continue }
                guard line.hasPrefix("data: ") else { continue }
                let jsonString = String(line.dropFirst(6))
                guard let jsonData = jsonString.data(using: .utf8) else { continue }

                do {
                    let event = try decoder.decode(ChatStreamEvent.self, from: jsonData)
                    if event.type == .error {
                        continuation.finish(throwing: ChatStreamError.serverError(event.message ?? "Unknown error"))
                        return
                    }
                    continuation.yield(event)
                    if event.type == .done {
                        continuation.finish()
                        return
                    }
                } catch {
                    streamLog.warning("Failed to parse SSE event: \(jsonString)")
                }
            }
        }

        continuation.finish()
    }
}

enum ChatStreamError: Error, LocalizedError {
    case streamingNotAvailable
    case invalidResponse
    case httpError(Int)
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .streamingNotAvailable:
            return "Streaming is not available"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let code):
            return "Server error: \(code)"
        case .serverError(let message):
            return message
        }
    }
}
