package com.powderchaserapp.android.ui.screens.notifications

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.data.api.NotificationSettings
import com.powderchaserapp.android.data.api.NotificationSettingsUpdate
import com.powderchaserapp.android.data.api.PowderChaserApi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class NotificationSettingsUiState(
    val settings: NotificationSettings = NotificationSettings(),
    val isLoading: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class NotificationSettingsViewModel @Inject constructor(
    private val api: PowderChaserApi,
) : ViewModel() {
    private val _uiState = MutableStateFlow(NotificationSettingsUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadSettings()
    }

    fun loadSettings() {
        viewModelScope.launch {
            try {
                val settings = api.getNotificationSettings()
                _uiState.update { it.copy(settings = settings, isLoading = false) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun updateSetting(update: NotificationSettingsUpdate) {
        viewModelScope.launch {
            try {
                api.updateNotificationSettings(update)
                loadSettings()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationSettingsScreen(
    onBackClick: () -> Unit,
    viewModel: NotificationSettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Notifications") },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState()),
        ) {
            val s = uiState.settings

            SwitchListItem(
                title = "All Notifications",
                checked = s.notificationsEnabled,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(notificationsEnabled = it))
                },
            )

            HorizontalDivider()

            Text(
                "Alert Types",
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                color = MaterialTheme.colorScheme.primary,
            )

            SwitchListItem(
                title = "Fresh Snow Alerts",
                subtitle = "Get notified when fresh snow falls",
                checked = s.freshSnowAlerts,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(freshSnowAlerts = it))
                },
            )
            SwitchListItem(
                title = "Powder Alerts",
                subtitle = "Deep powder day notifications",
                checked = s.powderAlerts,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(powderAlerts = it))
                },
            )
            SwitchListItem(
                title = "Thaw-Freeze Alerts",
                subtitle = "Ice formation warnings",
                checked = s.thawFreezeAlerts,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(thawFreezeAlerts = it))
                },
            )
            SwitchListItem(
                title = "Event Alerts",
                subtitle = "Resort events and openings",
                checked = s.eventAlerts,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(eventAlerts = it))
                },
            )
            SwitchListItem(
                title = "Weekly Summary",
                subtitle = "Weekly conditions digest",
                checked = s.weeklySummary,
                onCheckedChange = {
                    viewModel.updateSetting(NotificationSettingsUpdate(weeklySummary = it))
                },
            )
        }
    }
}

@Composable
private fun SwitchListItem(
    title: String,
    subtitle: String? = null,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = subtitle?.let { { Text(it) } },
        trailingContent = {
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        },
    )
}
