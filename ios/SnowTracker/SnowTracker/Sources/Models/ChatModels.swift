import Foundation

struct ChatMessage: Codable, Identifiable {
    let id: String
    let role: ChatRole
    let content: String
    let createdAt: Date?

    enum ChatRole: String, Codable {
        case user, assistant
    }

    var isFromUser: Bool { role == .user }

    enum CodingKeys: String, CodingKey {
        case id = "message_id"
        case role, content
        case createdAt = "created_at"
    }
}

struct ChatConversation: Codable, Identifiable {
    let id: String
    let title: String
    let lastMessageAt: Date?
    let messageCount: Int?

    enum CodingKeys: String, CodingKey {
        case id = "conversation_id"
        case title
        case lastMessageAt = "last_message_at"
        case messageCount = "message_count"
    }
}

struct ChatRequest: Encodable {
    let message: String
    let conversationId: String?
    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
    }
}

struct ChatResponse: Codable {
    let conversationId: String
    let response: String
    let messageId: String
    enum CodingKeys: String, CodingKey {
        case conversationId = "conversation_id"
        case response
        case messageId = "message_id"
    }
}
