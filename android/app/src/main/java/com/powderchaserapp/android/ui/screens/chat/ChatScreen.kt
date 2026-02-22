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

private val suggestionChips = listOf(
    "What's the best resort for powder right now?",
    "Which resorts have fresh snow?",
    "Where should I ski this weekend?",
    "Compare conditions in the Alps vs Rockies",
)

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

                            // Suggestion chips
                            suggestionChips.forEach { suggestion ->
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
            Text(
                text = message.content,
                modifier = Modifier.padding(12.dp),
                color = if (isUser) {
                    MaterialTheme.colorScheme.onPrimary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}
