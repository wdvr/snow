package com.powderchaserapp.android.ui.screens.chat

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.R
import com.powderchaserapp.android.data.api.ChatConversation
import com.powderchaserapp.android.data.api.ChatMessage
import com.powderchaserapp.android.data.api.ChatRole
import com.powderchaserapp.android.data.repository.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val conversationId: String? = null,
    val conversations: List<ChatConversation> = emptyList(),
    val isSending: Boolean = false,
    val isLoadingConversations: Boolean = false,
    val showConversationList: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState = _uiState.asStateFlow()

    fun sendMessage(text: String) {
        if (text.isBlank()) return
        viewModelScope.launch {
            val userMessage = ChatMessage(
                id = "local-${System.currentTimeMillis()}",
                role = ChatRole.USER,
                content = text,
            )
            _uiState.update {
                it.copy(
                    messages = it.messages + userMessage,
                    isSending = true,
                    error = null,
                )
            }

            chatRepository.sendMessage(text, _uiState.value.conversationId).fold(
                onSuccess = { response ->
                    val assistantMessage = ChatMessage(
                        id = response.messageId,
                        role = ChatRole.ASSISTANT,
                        content = response.response,
                    )
                    _uiState.update {
                        it.copy(
                            messages = it.messages + assistantMessage,
                            conversationId = response.conversationId,
                            isSending = false,
                        )
                    }
                },
                onFailure = { e ->
                    _uiState.update { it.copy(isSending = false, error = e.message) }
                },
            )
        }
    }

    fun startNewConversation() {
        _uiState.update { it.copy(messages = emptyList(), conversationId = null, error = null) }
    }

    fun loadConversations() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingConversations = true) }
            chatRepository.getConversations().fold(
                onSuccess = { conversations ->
                    _uiState.update { it.copy(conversations = conversations, isLoadingConversations = false) }
                },
                onFailure = {
                    _uiState.update { it.copy(isLoadingConversations = false) }
                },
            )
        }
    }

    fun loadConversation(conversationId: String) {
        viewModelScope.launch {
            chatRepository.getConversationMessages(conversationId).fold(
                onSuccess = { messages ->
                    _uiState.update {
                        it.copy(
                            messages = messages,
                            conversationId = conversationId,
                            showConversationList = false,
                        )
                    }
                },
                onFailure = { /* ignore */ },
            )
        }
    }

    fun toggleConversationList() {
        val showing = !_uiState.value.showConversationList
        _uiState.update { it.copy(showConversationList = showing) }
        if (showing) loadConversations()
    }
}

private val allSuggestions = listOf(
    "What's the best resort for powder right now?",
    "Which resorts have fresh snow?",
    "Where should I ski this weekend?",
    "Compare conditions in the Alps vs Rockies",
    "Best snow within 500 miles of Denver",
    "Cheap resorts within 6h drive of Salt Lake City",
    "Non-Epic resorts under $150/day",
    "Compare Whistler vs Jackson Hole",
    "Best conditions in Japan right now?",
    "Which Ikon Pass resorts have the most snow?",
    "Hidden gem resorts with great powder",
    "Family-friendly resorts with good conditions",
    "Best resorts for beginners with fresh snow",
    "What's the snowpack like in the Rockies?",
    "Which resorts are expecting a storm this week?",
    "Best Epic Pass resorts to visit right now",
)

/** 4 random suggestions, reshuffled each composition. */
@Composable
private fun rememberSuggestionChips(): List<String> {
    return remember { allSuggestions.shuffled().take(4) }
}

/** Strip tool_call/tool_response XML blocks from assistant messages. */
private fun stripToolCalls(text: String): String {
    return text
        .replace(Regex("<tool_call>.*?</tool_call>", RegexOption.DOT_MATCHES_ALL), "")
        .replace(Regex("<tool_response>.*?</tool_response>", RegexOption.DOT_MATCHES_ALL), "")
        .trim()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onBackClick: () -> Unit,
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.ask_ai)) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.startNewConversation() }) {
                        Icon(Icons.Default.AddComment, contentDescription = stringResource(R.string.new_conversation))
                    }
                    IconButton(onClick = { viewModel.toggleConversationList() }) {
                        Icon(Icons.Default.History, contentDescription = stringResource(R.string.conversation_history))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            // Conversation list overlay
            if (uiState.showConversationList) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            stringResource(R.string.conversation_history),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        if (uiState.isLoadingConversations) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp).align(Alignment.CenterHorizontally))
                        } else if (uiState.conversations.isEmpty()) {
                            Text(
                                "No previous conversations",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            uiState.conversations.take(10).forEach { conv ->
                                TextButton(
                                    onClick = { viewModel.loadConversation(conv.id) },
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text(
                                        conv.title,
                                        modifier = Modifier.weight(1f),
                                        maxLines = 1,
                                    )
                                }
                            }
                        }
                    }
                }
            }

            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                state = listState,
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (uiState.messages.isEmpty()) {
                    item {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Icon(
                                Icons.Default.AutoAwesome,
                                contentDescription = null,
                                modifier = Modifier.size(48.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                stringResource(R.string.ask_about_conditions),
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(24.dp))

                            // Suggestion chips (4 random from pool of 16)
                            val suggestions = rememberSuggestionChips()
                            suggestions.forEach { suggestion ->
                                SuggestionChip(
                                    onClick = {
                                        viewModel.sendMessage(suggestion)
                                    },
                                    label = { Text(suggestion, maxLines = 1) },
                                    modifier = Modifier.padding(vertical = 2.dp),
                                )
                            }
                        }
                    }
                }
                items(uiState.messages, key = { it.id }) { message ->
                    ChatBubble(message)
                }
                if (uiState.isSending) {
                    item {
                        Row(
                            modifier = Modifier.padding(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(stringResource(R.string.thinking), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            uiState.error?.let {
                Text(
                    it,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text(stringResource(R.string.ask_conditions_hint)) },
                    singleLine = true,
                )
                Spacer(modifier = Modifier.width(8.dp))
                IconButton(
                    onClick = {
                        viewModel.sendMessage(inputText)
                        inputText = ""
                    },
                    enabled = inputText.isNotBlank() && !uiState.isSending,
                ) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
                }
            }
        }
    }
}

@Composable
private fun ChatBubble(message: ChatMessage) {
    val isUser = message.isFromUser
    val displayText = if (isUser) message.content else stripToolCalls(message.content)

    // Skip empty messages (can happen after stripping tool calls)
    if (displayText.isBlank()) return

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            color = if (isUser) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            },
            shape = MaterialTheme.shapes.medium,
            modifier = Modifier.widthIn(max = 300.dp),
        ) {
            if (isUser) {
                Text(
                    text = displayText,
                    modifier = Modifier.padding(12.dp),
                    color = MaterialTheme.colorScheme.onPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            } else {
                MarkdownText(
                    text = displayText,
                    modifier = Modifier.padding(12.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Simple markdown rendering: bold, italic, headers, lists, and tables. */
@Composable
private fun MarkdownText(
    text: String,
    modifier: Modifier = Modifier,
    color: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onSurface,
) {
    val annotated = remember(text) {
        val builder = androidx.compose.ui.text.AnnotatedString.Builder()
        val lines = text.split("\n")

        for ((i, line) in lines.withIndex()) {
            if (i > 0) builder.append("\n")

            when {
                // Headers
                line.startsWith("### ") -> {
                    builder.pushStyle(
                        androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold),
                    )
                    builder.append(line.removePrefix("### "))
                    builder.pop()
                }
                line.startsWith("## ") -> {
                    builder.pushStyle(
                        androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold),
                    )
                    builder.append(line.removePrefix("## "))
                    builder.pop()
                }
                line.startsWith("# ") -> {
                    builder.pushStyle(
                        androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold),
                    )
                    builder.append(line.removePrefix("# "))
                    builder.pop()
                }
                // Bullet lists
                line.trimStart().startsWith("- ") || line.trimStart().startsWith("* ") -> {
                    val indent = line.length - line.trimStart().length
                    repeat(indent / 2) { builder.append("  ") }
                    builder.append("\u2022 ")
                    appendInlineMarkdown(builder, line.trimStart().removePrefix("- ").removePrefix("* "))
                }
                // Numbered lists
                line.trimStart().matches(Regex("^\\d+\\.\\s.*")) -> {
                    builder.append(line.trimStart())
                }
                // Table separator rows (skip)
                line.trimStart().matches(Regex("^\\|[-|: ]+\\|$")) -> {
                    // Skip separator rows
                }
                else -> {
                    appendInlineMarkdown(builder, line)
                }
            }
        }
        builder.toAnnotatedString()
    }

    Text(
        text = annotated,
        modifier = modifier,
        style = MaterialTheme.typography.bodyMedium,
        color = color,
    )
}

/** Append text with inline bold (**text**) and italic (*text*) handling. */
private fun appendInlineMarkdown(
    builder: androidx.compose.ui.text.AnnotatedString.Builder,
    text: String,
) {
    var remaining = text
    val boldRegex = Regex("\\*\\*(.+?)\\*\\*")
    val italicRegex = Regex("\\*(.+?)\\*")

    while (remaining.isNotEmpty()) {
        val boldMatch = boldRegex.find(remaining)
        val italicMatch = italicRegex.find(remaining)

        // Find the earliest match
        val earliest = listOfNotNull(boldMatch, italicMatch).minByOrNull { it.range.first }

        if (earliest == null) {
            builder.append(remaining)
            break
        }

        // Append text before the match
        if (earliest.range.first > 0) {
            builder.append(remaining.substring(0, earliest.range.first))
        }

        if (earliest == boldMatch) {
            builder.pushStyle(
                androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold),
            )
            builder.append(earliest.groupValues[1])
            builder.pop()
        } else {
            builder.pushStyle(
                androidx.compose.ui.text.SpanStyle(
                    fontStyle = androidx.compose.ui.text.font.FontStyle.Italic,
                ),
            )
            builder.append(earliest.groupValues[1])
            builder.pop()
        }

        remaining = remaining.substring(earliest.range.last + 1)
    }
}
