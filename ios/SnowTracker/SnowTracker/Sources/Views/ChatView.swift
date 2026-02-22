import SwiftUI

struct ChatView: View {
    @StateObject private var viewModel = ChatViewModel()
    @State private var messageText = ""
    @State private var sendTrigger = 0
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
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.startNewConversation()
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            .sheet(isPresented: $viewModel.showConversationList) {
                ConversationListView(viewModel: viewModel)
            }
            .onAppear {
                AnalyticsService.shared.trackScreen("AskAI", screenClass: "ChatView")
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

                Text("Get personalized recommendations, condition updates, and ski trip advice.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)

                VStack(spacing: 12) {
                    SuggestionChip(text: "Best powder near me?") {
                        sendSuggestion("Best powder near me?")
                    }
                    SuggestionChip(text: "How's Whistler today?") {
                        sendSuggestion("How's Whistler today?")
                    }
                    SuggestionChip(text: "Where should I ski this weekend?") {
                        sendSuggestion("Where should I ski this weekend?")
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
                        MessageBubbleView(
                            message: message,
                            isStreaming: viewModel.streamingMessageId == message.id,
                            displayedText: viewModel.streamingMessageId == message.id
                                ? viewModel.displayedText
                                : message.content,
                            onTapToSkip: {
                                viewModel.skipStreaming()
                            }
                        )
                        .id(message.id)
                    }

                    if viewModel.isSending {
                        TypingIndicatorView()
                            .id("typing-indicator")
                    }

                    if let error = viewModel.errorMessage {
                        ErrorBannerView(message: error)
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

    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.3)) {
            if viewModel.isSending {
                proxy.scrollTo("typing-indicator", anchor: .bottom)
            } else if let lastMessage = viewModel.messages.last {
                proxy.scrollTo(lastMessage.id, anchor: .bottom)
            }
        }
    }
}

// MARK: - Message Bubble

private struct MessageBubbleView: View {
    let message: ChatMessage
    let isStreaming: Bool
    let displayedText: String
    let onTapToSkip: () -> Void

    var body: some View {
        HStack {
            if message.isFromUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: message.isFromUser ? .trailing : .leading, spacing: 4) {
                Text(displayedText)
                    .font(.body)
                    .foregroundStyle(message.isFromUser ? .white : .primary)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(
                        message.isFromUser
                            ? Color.blue
                            : Color(.secondarySystemBackground)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 18))

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
    }
}

// MARK: - Error Banner

private struct ErrorBannerView: View {
    let message: String

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
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
