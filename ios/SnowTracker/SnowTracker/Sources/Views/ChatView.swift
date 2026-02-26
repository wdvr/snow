import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @ObservedObject private var locationManager = LocationManager.shared
    @StateObject private var viewModel = ChatViewModel()
    @State private var messageText = ""
    @State private var sendTrigger = 0
    @State private var selectedResort: Resort?
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if viewModel.messages.isEmpty && !viewModel.isLoading {
                    emptyStateView
                } else {
                    messageListView
                }

                inputBar
            }
            .navigationTitle("Ask AI")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        Task {
                            await viewModel.loadConversations()
                        }
                        viewModel.showConversationList = true
                    } label: {
                        Image(systemName: "clock.arrow.circlepath")
                    }
                    .accessibilityLabel("Conversation history")
                    .accessibilityIdentifier(AccessibilityID.Chat.historyButton)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.startNewConversation()
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }
                    .accessibilityLabel("New conversation")
                    .accessibilityIdentifier(AccessibilityID.Chat.newConversationButton)
                }
            }
            .sheet(isPresented: $viewModel.showConversationList) {
                ConversationListView(viewModel: viewModel)
            }
            .sheet(item: $selectedResort) { resort in
                NavigationStack {
                    ResortDetailView(resort: resort)
                        .environmentObject(snowConditionsManager)
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            }
            .onAppear {
                AnalyticsService.shared.trackScreen("AskAI", screenClass: "ChatView")
                updateViewModelLocation()
            }
            .onChange(of: locationManager.userLocation) { _, _ in
                updateViewModelLocation()
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("AskAI")
            }
        }
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer()
                    .frame(height: 40)

                Image(systemName: "bubble.left.and.text.bubble.right")
                    .font(.system(size: 56))
                    .foregroundStyle(.blue.opacity(0.6))

                Text("Ask about snow conditions")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .accessibilityIdentifier(AccessibilityID.Chat.emptyState)

                Text("Get personalized recommendations, condition updates, and ski trip advice.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)

                VStack(spacing: 12) {
                    SuggestionChip(text: "Best snow within 500 miles") {
                        sendSuggestion("Where's the best snow within 500 miles of me right now?")
                    }
                    SuggestionChip(text: "Cheap resorts within 6h drive") {
                        sendSuggestion("What are the cheapest ski resorts within a 6 hour drive from me with decent snow right now?")
                    }
                    SuggestionChip(text: "Non-Epic resorts under $150/day") {
                        sendSuggestion("Show me non-Epic pass resorts with good snow conditions where a day pass is under $150")
                    }
                    SuggestionChip(text: "Compare Whistler vs Jackson Hole") {
                        sendSuggestion("Compare current conditions at Whistler and Jackson Hole in a table")
                    }
                }
                .padding(.top, 8)

                Spacer()
            }
            .frame(maxWidth: .infinity)
        }
    }

    // MARK: - Message List

    private var messageListView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 16) {
                    ForEach(viewModel.messages) { message in
                        let isCurrentlyStreaming = viewModel.streamingMessageId == message.id
                        let text = isCurrentlyStreaming
                            ? viewModel.displayedText
                            : message.content

                        // Don't show empty bubbles (e.g. failed AI responses with no content)
                        if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isCurrentlyStreaming {
                            MessageBubbleView(
                                message: message,
                                isStreaming: isCurrentlyStreaming,
                                displayedText: text,
                                resorts: snowConditionsManager.resorts,
                                conditions: snowConditionsManager.conditions,
                                summaries: snowConditionsManager.snowQualitySummaries,
                                onTapToSkip: {
                                    viewModel.skipStreaming()
                                },
                                onResortTap: { resort in
                                    selectedResort = resort
                                }
                            )
                            .id(message.id)
                        }
                    }

                    if viewModel.isSending {
                        if viewModel.statusMessage != nil || !viewModel.activeTools.isEmpty {
                            ToolStatusView(
                                statusMessage: viewModel.statusMessage,
                                activeTools: viewModel.activeTools
                            )
                            .id("tool-status")
                        } else if !viewModel.isStreaming {
                            TypingIndicatorView()
                                .id("typing-indicator")
                        }
                    }

                    if let error = viewModel.errorMessage {
                        ErrorBannerView(message: error) {
                            viewModel.errorMessage = nil
                            if let lastUserMessage = viewModel.messages.last(where: { $0.isFromUser }) {
                                Task {
                                    await viewModel.sendMessage(lastUserMessage.content)
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 12)
            }
            .onChange(of: viewModel.messages.count) { _, _ in
                scrollToBottom(proxy: proxy)
            }
            .onChange(of: viewModel.isSending) { _, _ in
                scrollToBottom(proxy: proxy)
            }
            .onChange(of: viewModel.displayedText) { _, _ in
                // Scroll as streaming text is revealed
                if viewModel.isStreaming, let messageId = viewModel.streamingMessageId {
                    withAnimation(.easeOut(duration: 0.15)) {
                        proxy.scrollTo(messageId, anchor: .bottom)
                    }
                }
            }
            .onChange(of: viewModel.statusMessage) { _, _ in
                scrollToBottom(proxy: proxy)
            }
            .onChange(of: viewModel.activeTools.count) { _, _ in
                scrollToBottom(proxy: proxy)
            }
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        VStack(spacing: 0) {
            Divider()

            HStack(alignment: .bottom, spacing: 12) {
                TextField("Ask about conditions...", text: $messageText, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .focused($isTextFieldFocused)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .accessibilityIdentifier(AccessibilityID.Chat.messageInput)
                    .onSubmit {
                        sendCurrentMessage()
                    }

                Button {
                    sendCurrentMessage()
                } label: {
                    if viewModel.isSending {
                        ProgressView()
                            .frame(width: 32, height: 32)
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 32))
                            .foregroundStyle(canSend ? .blue : .gray.opacity(0.4))
                    }
                }
                .disabled(!canSend)
                .sensoryFeedback(.impact, trigger: sendTrigger)
                .accessibilityLabel(viewModel.isSending ? "Sending message" : "Send message")
                .accessibilityIdentifier(AccessibilityID.Chat.sendButton)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color(.systemBackground))
        }
    }

    // MARK: - Helpers

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !viewModel.isSending
    }

    private func sendCurrentMessage() {
        let text = messageText
        messageText = ""
        sendTrigger += 1
        Task {
            await viewModel.sendMessage(text)
        }
    }

    private func sendSuggestion(_ text: String) {
        sendTrigger += 1
        Task {
            await viewModel.sendMessage(text)
        }
    }

    private func updateViewModelLocation() {
        viewModel.userLatitude = locationManager.userLocation?.coordinate.latitude
        viewModel.userLongitude = locationManager.userLocation?.coordinate.longitude
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.3)) {
            if viewModel.isSending {
                if viewModel.statusMessage != nil || !viewModel.activeTools.isEmpty {
                    proxy.scrollTo("tool-status", anchor: .bottom)
                } else {
                    proxy.scrollTo("typing-indicator", anchor: .bottom)
                }
            } else if let lastMessage = viewModel.messages.last {
                proxy.scrollTo(lastMessage.id, anchor: .bottom)
            }
        }
    }
}

// MARK: - Message Content Parsing

private enum ChatContentSegment {
    case text(String)
    case resortCards([String])
}

private func parseChatContent(_ text: String) -> [ChatContentSegment] {
    let pattern = #"\[\[resort:([a-z0-9-]+)\]\]"#
    guard let regex = try? NSRegularExpression(pattern: pattern) else {
        return [.text(text)]
    }

    var segments: [ChatContentSegment] = []
    let lines = text.components(separatedBy: "\n")
    var textLines: [String] = []
    var resortIds: [String] = []

    for line in lines {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        let range = NSRange(trimmed.startIndex..., in: trimmed)
        if let match = regex.firstMatch(in: trimmed, range: range),
           let idRange = Range(match.range(at: 1), in: trimmed) {
            // Flush any accumulated text
            if !textLines.isEmpty {
                let joined = textLines.joined(separator: "\n")
                if !joined.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    segments.append(.text(joined))
                }
                textLines = []
            }
            resortIds.append(String(trimmed[idRange]))
        } else {
            // Flush any accumulated resort IDs
            if !resortIds.isEmpty {
                segments.append(.resortCards(resortIds))
                resortIds = []
            }
            textLines.append(line)
        }
    }

    // Flush remaining
    if !resortIds.isEmpty {
        segments.append(.resortCards(resortIds))
    }
    if !textLines.isEmpty {
        let joined = textLines.joined(separator: "\n")
        if !joined.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            segments.append(.text(joined))
        }
    }

    return segments
}

// MARK: - Message Bubble

private struct MessageBubbleView: View {
    let message: ChatMessage
    let isStreaming: Bool
    let displayedText: String
    let resorts: [Resort]
    let conditions: [String: [WeatherCondition]]
    let summaries: [String: SnowQualitySummaryLight]
    let onTapToSkip: () -> Void
    let onResortTap: (Resort) -> Void

    var body: some View {
        HStack {
            if message.isFromUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: message.isFromUser ? .trailing : .leading, spacing: 8) {
                if message.isFromUser || message.isIntermediate {
                    textBubble(displayedText)
                } else {
                    // Parse for resort cards
                    let segments = parseChatContent(displayedText)
                    ForEach(Array(segments.enumerated()), id: \.offset) { _, segment in
                        switch segment {
                        case .text(let text):
                            textBubble(text, isAssistant: true)
                        case .resortCards(let ids):
                            ChatResortCarousel(
                                resortIds: ids,
                                resorts: resorts,
                                conditions: conditions,
                                summaries: summaries,
                                onResortTap: onResortTap
                            )
                        }
                    }
                }

                if isStreaming {
                    Text("Tap to skip")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                        .padding(.leading, 4)
                        .transition(.opacity)
                }
            }
            .contentShape(Rectangle())
            .onTapGesture {
                if isStreaming {
                    onTapToSkip()
                }
            }

            if !message.isFromUser {
                Spacer(minLength: 60)
            }
        }
    }

    @ViewBuilder
    private func textBubble(_ text: String, isAssistant: Bool = false) -> some View {
        Group {
            if message.isFromUser {
                Text(text)
                    .font(.body)
                    .foregroundStyle(.white)
            } else if message.isIntermediate {
                Text(text)
                    .font(.body)
                    .italic()
                    .foregroundStyle(.secondary)
            } else {
                MarkdownTextView(text, foregroundColor: .primary)
                    .font(.body)
            }
        }
        .textSelection(.enabled)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            message.isFromUser
                ? Color.blue
                : message.isIntermediate
                    ? Color(.tertiarySystemBackground)
                    : Color(.secondarySystemBackground)
        )
        .clipShape(RoundedRectangle(cornerRadius: 18))
    }
}

// MARK: - Resort Card Carousel

private struct ChatResortCarousel: View {
    let resortIds: [String]
    let resorts: [Resort]
    let conditions: [String: [WeatherCondition]]
    let summaries: [String: SnowQualitySummaryLight]
    let onResortTap: (Resort) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(resortIds, id: \.self) { resortId in
                    if let resort = resorts.first(where: { $0.id == resortId }) {
                        ChatResortCard(
                            resort: resort,
                            condition: bestCondition(for: resortId),
                            quality: summaries[resortId]?.overallSnowQuality
                        ) {
                            onResortTap(resort)
                        }
                    }
                }
            }
        }
    }

    private func bestCondition(for resortId: String) -> WeatherCondition? {
        let resortConditions = conditions[resortId] ?? []
        return resortConditions.first { $0.elevationLevel == "mid" }
            ?? resortConditions.first { $0.elevationLevel == "top" }
            ?? resortConditions.first
    }
}

private struct ChatResortCard: View {
    let resort: Resort
    let condition: WeatherCondition?
    let quality: SnowQuality?
    let onTap: () -> Void

    private var displayQuality: SnowQuality {
        condition?.snowQuality ?? quality ?? .unknown
    }

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 6) {
                // Quality badge
                HStack {
                    Text(displayQuality.displayName)
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(displayQuality.color, in: Capsule())

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                // Resort name
                Text(resort.name)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                // Stats
                HStack(spacing: 12) {
                    if let condition {
                        if condition.freshSnowCm > 0 {
                            Label(String(format: "%.0fcm", condition.freshSnowCm), systemImage: "snowflake")
                                .font(.caption)
                                .foregroundStyle(.blue)
                        }
                        Label(String(format: "%.0f°", condition.currentTempCelsius), systemImage: "thermometer.medium")
                            .font(.caption)
                            .foregroundStyle(condition.currentTempCelsius > 0 ? .orange : .cyan)
                        if let depth = condition.snowDepthCm, depth > 0 {
                            Label(String(format: "%.0fcm base", depth), systemImage: "ruler")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    } else {
                        Text("Loading...")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                // Country/region
                Text(resort.countryName)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            .padding(12)
            .frame(width: 180)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .strokeBorder(displayQuality.color.opacity(0.3), lineWidth: 1.5)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Tool Status View

private struct ToolStatusView: View {
    let statusMessage: String?
    let activeTools: [String]

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 6) {
                if let status = statusMessage {
                    HStack(spacing: 8) {
                        ProgressView()
                            .controlSize(.small)
                        Text(status)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                if !activeTools.isEmpty {
                    HStack(spacing: 6) {
                        ForEach(activeTools, id: \.self) { tool in
                            HStack(spacing: 4) {
                                Image(systemName: "wrench.and.screwdriver")
                                    .font(.caption2)
                                Text(tool)
                                    .font(.caption)
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.blue.opacity(0.1))
                            .foregroundStyle(.blue)
                            .clipShape(Capsule())
                        }
                    }
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18))

            Spacer(minLength: 60)
        }
        .accessibilityLabel(statusMessage ?? "Processing")
    }
}

// MARK: - Typing Indicator

private struct TypingIndicatorView: View {
    @State private var dotOffset: CGFloat = 0

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(Color.gray)
                        .frame(width: 8, height: 8)
                        .offset(y: animatingDot(index: index) ? -4 : 0)
                        .animation(
                            .easeInOut(duration: 0.4)
                            .repeatForever(autoreverses: true)
                            .delay(Double(index) * 0.15),
                            value: dotOffset
                        )
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18))
            .onAppear {
                dotOffset = 1
            }
            .accessibilityLabel("AI is typing")

            Spacer(minLength: 60)
        }
    }

    private func animatingDot(index: Int) -> Bool {
        dotOffset > 0
    }
}

// MARK: - Suggestion Chip

private struct SuggestionChip: View {
    let text: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: "sparkles")
                    .font(.caption)
                Text(text)
                    .font(.subheadline)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 20))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(text)
    }
}

// MARK: - Error Banner

private struct ErrorBannerView: View {
    let message: String
    var onRetry: (() -> Void)?

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
            if let onRetry {
                Spacer()
                Button {
                    onRetry()
                } label: {
                    Label("Retry", systemImage: "arrow.clockwise")
                        .font(.caption)
                        .fontWeight(.medium)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Conversation List

private struct ConversationListView: View {
    @ObservedObject var viewModel: ChatViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.conversations.isEmpty && !viewModel.isLoading {
                    ContentUnavailableView(
                        "No Conversations",
                        systemImage: "bubble.left.and.text.bubble.right",
                        description: Text("Start a new conversation to get AI-powered snow condition insights.")
                    )
                } else {
                    List {
                        ForEach(viewModel.conversations) { conversation in
                            Button {
                                Task {
                                    await viewModel.loadConversation(conversation.id)
                                }
                                dismiss()
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(conversation.title)
                                        .font(.headline)
                                        .foregroundStyle(.primary)
                                        .lineLimit(2)

                                    HStack {
                                        if let count = conversation.messageCount {
                                            Text("\(count) messages")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        if let date = conversation.lastMessageAt {
                                            Text(date, style: .relative)
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        }
                        .onDelete { offsets in
                            let conversationsToDelete = offsets.map { viewModel.conversations[$0] }
                            for conversation in conversationsToDelete {
                                Task {
                                    await viewModel.deleteConversation(conversation.id)
                                }
                            }
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Conversations")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.startNewConversation()
                        dismiss()
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            .overlay {
                if viewModel.isLoading {
                    ProgressView()
                }
            }
        }
    }
}

#Preview("Chat - Empty") {
    ChatView()
}

#Preview("Chat - Conversations") {
    ChatView()
}
