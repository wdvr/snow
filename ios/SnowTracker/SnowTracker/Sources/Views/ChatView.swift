import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @ObservedObject private var locationManager = LocationManager.shared
    @StateObject private var viewModel = ChatViewModel()
    @State private var messageText = ""
    @State private var sendTrigger = 0
    @State private var selectedResort: Resort?
    @State private var visibleSuggestions: [ChatSuggestion] = []
    @State private var allSuggestionsLoaded: [ChatSuggestion] = []
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
                loadSuggestions()
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
                    ForEach(visibleSuggestions) { suggestion in
                        SuggestionChip(text: suggestion.label) {
                            sendSuggestion(suggestion.prompt)
                        }
                    }
                }
                .padding(.top, 8)
                .onAppear {
                    if visibleSuggestions.isEmpty {
                        let pool = allSuggestionsLoaded.isEmpty
                            ? Self.fallbackSuggestions
                            : allSuggestionsLoaded
                        visibleSuggestions = Array(pool.shuffled().prefix(4))
                    }
                }

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

                        // Skip intermediate "thinking" messages — tool status already handles this
                        if message.isIntermediate {
                            EmptyView()
                        } else if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isCurrentlyStreaming {
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
            .scrollDismissesKeyboard(.interactively)
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
        isTextFieldFocused = false
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

    // MARK: - Suggestions Data

    private struct ChatSuggestion: Identifiable {
        let id = UUID()
        let label: String
        let prompt: String
    }

    /// Hardcoded fallback suggestions used when the API is unavailable
    private static let fallbackSuggestions: [ChatSuggestion] = [
        ChatSuggestion(label: "Best snow within 500 miles", prompt: "Where's the best snow within 500 miles of me right now?"),
        ChatSuggestion(label: "Cheap resorts within 6h drive", prompt: "What are the cheapest ski resorts within a 6 hour drive from me with decent snow right now?"),
        ChatSuggestion(label: "Non-Epic resorts under $150/day", prompt: "Show me non-Epic pass resorts with good snow conditions where a day pass is under $150"),
        ChatSuggestion(label: "Compare Whistler vs Jackson Hole", prompt: "Compare current conditions at Whistler and Jackson Hole in a table"),
        ChatSuggestion(label: "Best powder in the Rockies", prompt: "Which resort in the Rockies has the best powder conditions right now?"),
        ChatSuggestion(label: "Family-friendly with good snow", prompt: "What are some family-friendly resorts with good snow and lots of green runs?"),
        ChatSuggestion(label: "Top 5 resorts globally right now", prompt: "What are the top 5 resorts with the best snow conditions anywhere in the world right now?"),
        ChatSuggestion(label: "Ikon Pass best conditions", prompt: "Which Ikon Pass resorts have the best snow conditions right now?"),
        ChatSuggestion(label: "Snow forecast this week", prompt: "Which resorts near me are getting the most snow this week?"),
        ChatSuggestion(label: "Hidden gems with fresh powder", prompt: "Show me lesser-known resorts that got fresh snow in the last 24 hours"),
        ChatSuggestion(label: "Best in the Alps right now", prompt: "What are the best ski resorts in the Alps right now? Compare their conditions."),
        ChatSuggestion(label: "Deepest snowpack", prompt: "Which resorts have the deepest snowpack right now?"),
        ChatSuggestion(label: "Weekend trip under $100/day", prompt: "Plan me a weekend ski trip — resorts under $100/day with good snow within driving distance"),
        ChatSuggestion(label: "Japan snow conditions", prompt: "How are conditions at the Japanese resorts right now? Is it still powder season?"),
        ChatSuggestion(label: "Warmest resort with good snow", prompt: "Which resort has the warmest temperatures while still having good snow quality?"),
        ChatSuggestion(label: "Epic vs Ikon conditions", prompt: "Compare the best Epic Pass resort vs the best Ikon Pass resort right now"),
    ]

    // MARK: - Dynamic Suggestion Loading

    /// Fetch suggestions from the API and interpolate tokens with user context
    private func loadSuggestions() {
        Task {
            do {
                let items = try await APIClient.shared.getChatSuggestions()
                let interpolated = items.compactMap { item -> ChatSuggestion? in
                    interpolateSuggestion(item)
                }
                await MainActor.run {
                    allSuggestionsLoaded = interpolated
                    // Refresh visible suggestions if they were showing fallbacks
                    if !allSuggestionsLoaded.isEmpty {
                        visibleSuggestions = Array(allSuggestionsLoaded.shuffled().prefix(4))
                    }
                }
            } catch {
                // Fall back to hardcoded suggestions silently
            }
        }
    }

    /// Replace interpolation tokens in a suggestion with real data from the user's context.
    /// Returns nil if a required token cannot be resolved (e.g. {resort_name} but no favorites).
    private func interpolateSuggestion(_ item: ChatSuggestionItem) -> ChatSuggestion? {
        var text = item.text
        let favoriteResorts = snowConditionsManager.resorts
            .filter { userPreferencesManager.favoriteResorts.contains($0.id) }
        let nearbyResorts = nearbyResortsSorted()

        // {resort_name} — pick from favorites first, then nearby, then any resort
        if text.contains("{resort_name}") {
            guard let resort = favoriteResorts.randomElement()
                    ?? nearbyResorts.first
                    ?? snowConditionsManager.resorts.randomElement() else {
                return nil
            }
            text = text.replacingOccurrences(of: "{resort_name}", with: resort.name)
        }

        // {resort_name_2} — pick a second resort different from the first one used
        if text.contains("{resort_name_2}") {
            // Find the resort name already substituted to avoid duplicating
            let usedName = favoriteResorts.first?.name
                ?? nearbyResorts.first?.name
                ?? snowConditionsManager.resorts.first?.name
            let pool = (favoriteResorts + nearbyResorts + snowConditionsManager.resorts)
                .filter { $0.name != usedName }
            guard let secondResort = pool.first else {
                return nil
            }
            text = text.replacingOccurrences(of: "{resort_name_2}", with: secondResort.name)
        }

        // {nearby_city} — use nearest resort's city, or a known city
        if text.contains("{nearby_city}") {
            let city = nearbyResorts.compactMap(\.city).first
                ?? favoriteResorts.compactMap(\.city).first
                ?? snowConditionsManager.resorts.compactMap(\.city).first
            guard let resolvedCity = city else {
                return nil
            }
            text = text.replacingOccurrences(of: "{nearby_city}", with: resolvedCity)
        }

        // {region} — use nearest resort's region display name
        if text.contains("{region}") {
            let region = nearbyResorts.first?.regionDisplayName
                ?? favoriteResorts.first?.regionDisplayName
                ?? snowConditionsManager.resorts.first?.regionDisplayName
            guard let resolvedRegion = region, !resolvedRegion.isEmpty else {
                return nil
            }
            text = text.replacingOccurrences(of: "{region}", with: resolvedRegion)
        }

        // Use a truncated version for the chip label
        let label = text.count > 50 ? String(text.prefix(47)) + "..." : text
        return ChatSuggestion(label: label, prompt: text)
    }

    /// Resorts sorted by distance from the user's current location
    private func nearbyResortsSorted() -> [Resort] {
        guard let userLocation = locationManager.userLocation else { return [] }
        return snowConditionsManager.resorts
            .sorted { $0.distance(from: userLocation) < $1.distance(from: userLocation) }
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

/// Strip hallucinated tool call XML blocks from AI responses
private func cleanToolCallArtifacts(_ text: String) -> String {
    // Remove <tool_call>...</tool_call> and <tool_response>...</tool_response> blocks
    var cleaned = text
    let patterns = [
        #"<tool_call>\s*\{[^}]*\}\s*</tool_call>"#,
        #"<tool_response>\s*\{[\s\S]*?\}\s*</tool_response>"#,
        #"<tool_call>[\s\S]*?</tool_call>"#,
        #"<tool_response>[\s\S]*?</tool_response>"#,
    ]
    for pattern in patterns {
        if let regex = try? NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators]) {
            cleaned = regex.stringByReplacingMatches(
                in: cleaned,
                range: NSRange(cleaned.startIndex..., in: cleaned),
                withTemplate: ""
            )
        }
    }
    // Clean up multiple blank lines left behind
    while cleaned.contains("\n\n\n") {
        cleaned = cleaned.replacingOccurrences(of: "\n\n\n", with: "\n\n")
    }
    return cleaned.trimmingCharacters(in: .whitespacesAndNewlines)
}

private func parseChatContent(_ text: String) -> [ChatContentSegment] {
    let cleaned = cleanToolCallArtifacts(text)
    let pattern = #"\[\[resort:([a-z0-9-]+)\]\]"#
    guard let regex = try? NSRegularExpression(pattern: pattern) else {
        return [.text(cleaned)]
    }

    var segments: [ChatContentSegment] = []
    let lines = cleaned.components(separatedBy: "\n")
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
                if message.isFromUser {
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
            HStack(spacing: 12) {
                ForEach(resortIds, id: \.self) { resortId in
                    if let resort = resorts.first(where: { $0.id == resortId }) {
                        ChatResortCard(
                            resort: resort,
                            condition: bestCondition(for: resortId),
                            summary: summaries[resortId]
                        ) {
                            onResortTap(resort)
                        }
                    }
                }
            }
            .padding(.vertical, 4)
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
    let summary: SnowQualitySummaryLight?
    let onTap: () -> Void

    private var displayQuality: SnowQuality {
        condition?.snowQuality ?? summary?.overallSnowQuality ?? .unknown
    }

    private var snowScore: Int? {
        condition?.snowScore ?? summary?.snowScore
    }

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 0) {
                // Top: quality gradient header
                ZStack(alignment: .topLeading) {
                    LinearGradient(
                        colors: [displayQuality.color, displayQuality.color.opacity(0.6)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                    .frame(height: 56)

                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(displayQuality.displayName.uppercased())
                                .font(.caption2)
                                .fontWeight(.heavy)
                                .foregroundStyle(.white)
                            if let score = snowScore {
                                Text("\(score)/100")
                                    .font(.system(.title3, design: .rounded))
                                    .fontWeight(.bold)
                                    .foregroundStyle(.white)
                            }
                        }
                        Spacer()
                        Image(systemName: displayQuality.icon)
                            .font(.title2)
                            .foregroundStyle(.white.opacity(0.7))
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }

                // Body content
                VStack(alignment: .leading, spacing: 8) {
                    // Resort name
                    Text(resort.name)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)

                    // Location
                    Text(resort.displayLocation)
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    // Weather stats row
                    weatherStatsRow

                    // Trail difficulty bar
                    if hasTrailData {
                        trailDifficultyBar
                    }

                    // Price + Pass row
                    priceAndPassRow
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
            }
            .frame(width: 200)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .strokeBorder(displayQuality.color.opacity(0.3), lineWidth: 1.5)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Weather Stats

    @ViewBuilder
    private var weatherStatsRow: some View {
        HStack(spacing: 10) {
            if let condition {
                if condition.displayFreshSnowCm > 0 {
                    statItem(
                        icon: condition.snowfall24hCm >= 0.5 ? "cloud.snow" : "snowflake",
                        value: condition.snowfall24hCm >= 0.5
                            ? String(format: "%.0f cm/24h", condition.snowfall24hCm)
                            : String(format: "%.0f cm", condition.freshSnowCm),
                        color: .blue
                    )
                }
                statItem(
                    icon: "thermometer.medium",
                    value: String(format: "%.0f\u{00B0}", condition.currentTempCelsius),
                    color: condition.currentTempCelsius > 0 ? .orange : .cyan
                )
                if let depth = condition.snowDepthCm, depth > 0 {
                    statItem(
                        icon: "ruler",
                        value: String(format: "%.0f cm", depth),
                        color: .secondary
                    )
                }
            } else if let summary {
                if let fresh = summary.snowfallFreshCm, fresh > 0 {
                    statItem(icon: "snowflake", value: String(format: "%.0f cm", fresh), color: .blue)
                }
                if let temp = summary.temperatureC {
                    statItem(
                        icon: "thermometer.medium",
                        value: String(format: "%.0f\u{00B0}", temp),
                        color: temp > 0 ? .orange : .cyan
                    )
                }
            } else {
                Text("No data")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func statItem(icon: String, value: String, color: Color) -> some View {
        HStack(spacing: 2) {
            Image(systemName: icon)
                .font(.system(size: 9))
                .foregroundStyle(color)
            Text(value)
                .font(.caption2)
                .foregroundStyle(color)
        }
    }

    // MARK: - Trail Difficulty Bar

    private var hasTrailData: Bool {
        resort.greenRunsPct != nil || resort.blueRunsPct != nil || resort.blackRunsPct != nil
    }

    private var trailDifficultyBar: some View {
        let green = Double(resort.greenRunsPct ?? 0)
        let blue = Double(resort.blueRunsPct ?? 0)
        let black = Double(resort.blackRunsPct ?? 0)
        let dblack = Double(resort.doubleBlackRunsPct ?? 0)
        let total = max(green + blue + black + dblack, 1)

        return GeometryReader { geo in
            HStack(spacing: 1) {
                if green > 0 {
                    Rectangle()
                        .fill(Color.green)
                        .frame(width: geo.size.width * green / total)
                }
                if blue > 0 {
                    Rectangle()
                        .fill(Color.blue)
                        .frame(width: geo.size.width * blue / total)
                }
                if black > 0 {
                    Rectangle()
                        .fill(Color(.label))
                        .frame(width: geo.size.width * black / total)
                }
                if dblack > 0 {
                    Rectangle()
                        .fill(Color(.label))
                        .frame(width: geo.size.width * dblack / total)
                        .overlay(
                            // Double diamond pattern
                            HStack(spacing: 1) {
                                ForEach(0..<2, id: \.self) { _ in
                                    Image(systemName: "diamond.fill")
                                        .font(.system(size: 4))
                                        .foregroundStyle(.white)
                                }
                            }
                        )
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 2))
        }
        .frame(height: 6)
    }

    // MARK: - Price & Pass

    @ViewBuilder
    private var priceAndPassRow: some View {
        HStack(spacing: 6) {
            // Price
            if let minPrice = resort.dayTicketPriceMinUsd {
                if let maxPrice = resort.dayTicketPriceMaxUsd, maxPrice != minPrice {
                    Text("$\(minPrice)-\(maxPrice)")
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundStyle(.primary)
                } else {
                    Text("$\(minPrice)")
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundStyle(.primary)
                }
            }

            Spacer()

            // Pass badges
            if resort.epicPass != nil {
                passBadge("Epic", color: .blue)
            }
            if resort.ikonPass != nil {
                passBadge("Ikon", color: .orange)
            }
            if resort.indyPass != nil {
                passBadge("Indy", color: .green)
            }
        }
    }

    private func passBadge(_ name: String, color: Color) -> some View {
        Text(name)
            .font(.system(size: 8, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(color, in: Capsule())
    }
}

// MARK: - Tool Status View

private struct ToolStatusView: View {
    let statusMessage: String?
    let activeTools: [String]

    var body: some View {
        HStack {
            HStack(spacing: 10) {
                ProgressView()
                    .controlSize(.small)

                VStack(alignment: .leading, spacing: 4) {
                    if let status = statusMessage {
                        Text(status)
                            .font(.subheadline)
                            .foregroundStyle(.primary)
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
