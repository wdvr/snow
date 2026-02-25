import Foundation

struct ChatMessage: Codable, Identifiable {
    let id: String
    let role: ChatRole
    let content: String
    let createdAt: Date?
    /// Intermediate "thinking" message emitted between tool calls during streaming.
    var isIntermediate: Bool

    enum ChatRole: String, Codable {
        case user, assistant
    }

    var isFromUser: Bool { role == .user }

    init(id: String, role: ChatRole, content: String, createdAt: Date?, isIntermediate: Bool = false) {
        self.id = id
        self.role = role
        self.content = content
        self.createdAt = createdAt
        self.isIntermediate = isIntermediate
    }

    enum CodingKeys: String, CodingKey {
        case id = "message_id"
        case role, content
        case createdAt = "created_at"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        role = try container.decode(ChatRole.self, forKey: .role)
        content = try container.decode(String.self, forKey: .content)
        isIntermediate = false
        // Backend returns ISO 8601 strings; JSONDecoder's default expects Double
        if let dateStr = try? container.decodeIfPresent(String.self, forKey: .createdAt) {
            createdAt = Self.parseDate(dateStr)
        } else {
            createdAt = try? container.decodeIfPresent(Date.self, forKey: .createdAt)
        }
    }

    private static let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let isoFormatterBasic: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func parseDate(_ str: String) -> Date? {
        isoFormatter.date(from: str) ?? isoFormatterBasic.date(from: str)
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

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        title = try container.decode(String.self, forKey: .title)
        messageCount = try container.decodeIfPresent(Int.self, forKey: .messageCount)
        if let dateStr = try? container.decodeIfPresent(String.self, forKey: .lastMessageAt) {
            lastMessageAt = ChatMessage.parseDate(dateStr)
        } else {
            lastMessageAt = try? container.decodeIfPresent(Date.self, forKey: .lastMessageAt)
        }
    }
}

struct ChatRequest: Encodable {
    let message: String
    let conversationId: String?
    let latitude: Double?
    let longitude: Double?
    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case latitude
        case longitude
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
