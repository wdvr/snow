package com.powderchaserapp.android.ui.screens.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.BuildConfig
import com.powderchaserapp.android.R
import com.powderchaserapp.android.data.repository.AuthRepository
import com.powderchaserapp.android.util.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val unitPreferences: UnitPreferences = UnitPreferences(),
    val selectedEnvironment: String = "prod",
    val showDevSettings: Boolean = false,
    val cacheCleared: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(SettingsUiState(
        showDevSettings = BuildConfig.DEBUG,
    ))
    val uiState = _uiState.asStateFlow()

    init {
        observePreferences()
    }

    private fun observePreferences() {
        viewModelScope.launch {
            userPreferencesRepository.unitPreferences.collect { prefs ->
                _uiState.update { it.copy(unitPreferences = prefs) }
            }
        }
        viewModelScope.launch {
            userPreferencesRepository.selectedEnvironment.collect { env ->
                _uiState.update { it.copy(selectedEnvironment = env) }
            }
        }
    }

    fun setTemperatureUnit(unit: TemperatureUnit) {
        viewModelScope.launch { userPreferencesRepository.setTemperatureUnit(unit) }
    }

    fun setDistanceUnit(unit: DistanceUnit) {
        viewModelScope.launch { userPreferencesRepository.setDistanceUnit(unit) }
    }

    fun setSnowDepthUnit(unit: SnowDepthUnit) {
        viewModelScope.launch { userPreferencesRepository.setSnowDepthUnit(unit) }
    }

    fun setEnvironment(env: String) {
        viewModelScope.launch { userPreferencesRepository.setEnvironment(env) }
    }

    fun clearCache() {
        viewModelScope.launch {
            // In a real implementation, clear Room database here
            _uiState.update { it.copy(cacheCleared = true) }
        }
    }

    fun signOut() {
        authRepository.signOut()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNotificationSettingsClick: () -> Unit,
    onSignOut: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    var showTempPicker by remember { mutableStateOf(false) }
    var showDistancePicker by remember { mutableStateOf(false) }
    var showSnowPicker by remember { mutableStateOf(false) }
    var showEnvPicker by remember { mutableStateOf(false) }
    var showClearCacheDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_settings)) }) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState()),
        ) {
            // ============= Units =============
            SectionHeader(stringResource(R.string.units))

            ListItem(
                headlineContent = { Text(stringResource(R.string.temperature)) },
                supportingContent = {
                    Text(
                        when (uiState.unitPreferences.temperature) {
                            TemperatureUnit.CELSIUS -> stringResource(R.string.celsius)
                            TemperatureUnit.FAHRENHEIT -> stringResource(R.string.fahrenheit)
                        },
                    )
                },
                leadingContent = { Icon(Icons.Default.Thermostat, contentDescription = null) },
                modifier = Modifier.clickable { showTempPicker = true },
            )

            ListItem(
                headlineContent = { Text(stringResource(R.string.distance)) },
                supportingContent = {
                    Text(
                        when (uiState.unitPreferences.distance) {
                            DistanceUnit.METRIC -> stringResource(R.string.metric_km)
                            DistanceUnit.IMPERIAL -> stringResource(R.string.imperial_mi)
                        },
                    )
                },
                leadingContent = { Icon(Icons.Default.Straighten, contentDescription = null) },
                modifier = Modifier.clickable { showDistancePicker = true },
            )

            ListItem(
                headlineContent = { Text(stringResource(R.string.snow_depth)) },
                supportingContent = {
                    Text(
                        when (uiState.unitPreferences.snowDepth) {
                            SnowDepthUnit.CENTIMETERS -> stringResource(R.string.centimeters)
                            SnowDepthUnit.INCHES -> stringResource(R.string.inches)
                        },
                    )
                },
                leadingContent = { Icon(Icons.Default.AcUnit, contentDescription = null) },
                modifier = Modifier.clickable { showSnowPicker = true },
            )

            HorizontalDivider()

            // ============= Notifications =============
            SectionHeader(stringResource(R.string.notifications))

            ListItem(
                headlineContent = { Text(stringResource(R.string.notifications)) },
                supportingContent = { Text(stringResource(R.string.fresh_snow_alerts)) },
                leadingContent = { Icon(Icons.Default.Notifications, contentDescription = null) },
                modifier = Modifier.clickable(onClick = onNotificationSettingsClick),
            )

            HorizontalDivider()

            // ============= Data & Storage =============
            SectionHeader(stringResource(R.string.data_storage))

            ListItem(
                headlineContent = { Text(stringResource(R.string.clear_offline_cache)) },
                leadingContent = { Icon(Icons.Default.DeleteSweep, contentDescription = null) },
                modifier = Modifier.clickable { showClearCacheDialog = true },
            )

            HorizontalDivider()

            // ============= Support =============
            SectionHeader(stringResource(R.string.support))

            ListItem(
                headlineContent = { Text(stringResource(R.string.send_feedback)) },
                leadingContent = { Icon(Icons.Default.Feedback, contentDescription = null) },
                modifier = Modifier.clickable { /* Navigate to feedback */ },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.privacy_policy)) },
                leadingContent = { Icon(Icons.Default.Policy, contentDescription = null) },
                modifier = Modifier.clickable { /* Open URL */ },
            )
            ListItem(
                headlineContent = { Text(stringResource(R.string.terms_of_service)) },
                leadingContent = { Icon(Icons.Default.Description, contentDescription = null) },
                modifier = Modifier.clickable { /* Open URL */ },
            )

            HorizontalDivider()

            // ============= About =============
            SectionHeader(stringResource(R.string.about))

            ListItem(
                headlineContent = { Text(stringResource(R.string.app_version)) },
                supportingContent = { Text("${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})") },
                leadingContent = { Icon(Icons.Default.Info, contentDescription = null) },
            )

            // ============= Developer Settings =============
            if (uiState.showDevSettings) {
                HorizontalDivider()
                SectionHeader(stringResource(R.string.developer_settings))

                ListItem(
                    headlineContent = { Text(stringResource(R.string.environment)) },
                    supportingContent = { Text(uiState.selectedEnvironment) },
                    leadingContent = { Icon(Icons.Default.DeveloperMode, contentDescription = null) },
                    modifier = Modifier.clickable { showEnvPicker = true },
                )
            }

            HorizontalDivider()

            // ============= Sign Out =============
            ListItem(
                headlineContent = {
                    Text(stringResource(R.string.sign_out), color = MaterialTheme.colorScheme.error)
                },
                leadingContent = {
                    Icon(
                        Icons.AutoMirrored.Filled.ExitToApp,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error,
                    )
                },
                modifier = Modifier.clickable {
                    viewModel.signOut()
                    onSignOut()
                },
            )

            Spacer(modifier = Modifier.height(32.dp))
        }
    }

    // Temperature picker dialog
    if (showTempPicker) {
        AlertDialog(
            onDismissRequest = { showTempPicker = false },
            title = { Text(stringResource(R.string.temperature)) },
            text = {
                Column {
                    TemperatureUnit.entries.forEach { unit ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    viewModel.setTemperatureUnit(unit)
                                    showTempPicker = false
                                }
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(
                                selected = uiState.unitPreferences.temperature == unit,
                                onClick = {
                                    viewModel.setTemperatureUnit(unit)
                                    showTempPicker = false
                                },
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                when (unit) {
                                    TemperatureUnit.CELSIUS -> stringResource(R.string.celsius)
                                    TemperatureUnit.FAHRENHEIT -> stringResource(R.string.fahrenheit)
                                },
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showTempPicker = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    // Distance picker dialog
    if (showDistancePicker) {
        AlertDialog(
            onDismissRequest = { showDistancePicker = false },
            title = { Text(stringResource(R.string.distance)) },
            text = {
                Column {
                    DistanceUnit.entries.forEach { unit ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    viewModel.setDistanceUnit(unit)
                                    showDistancePicker = false
                                }
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(
                                selected = uiState.unitPreferences.distance == unit,
                                onClick = {
                                    viewModel.setDistanceUnit(unit)
                                    showDistancePicker = false
                                },
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                when (unit) {
                                    DistanceUnit.METRIC -> stringResource(R.string.metric_km)
                                    DistanceUnit.IMPERIAL -> stringResource(R.string.imperial_mi)
                                },
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showDistancePicker = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    // Snow depth picker dialog
    if (showSnowPicker) {
        AlertDialog(
            onDismissRequest = { showSnowPicker = false },
            title = { Text(stringResource(R.string.snow_depth)) },
            text = {
                Column {
                    SnowDepthUnit.entries.forEach { unit ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    viewModel.setSnowDepthUnit(unit)
                                    showSnowPicker = false
                                }
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(
                                selected = uiState.unitPreferences.snowDepth == unit,
                                onClick = {
                                    viewModel.setSnowDepthUnit(unit)
                                    showSnowPicker = false
                                },
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                when (unit) {
                                    SnowDepthUnit.CENTIMETERS -> stringResource(R.string.centimeters)
                                    SnowDepthUnit.INCHES -> stringResource(R.string.inches)
                                },
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showSnowPicker = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    // Environment picker dialog
    if (showEnvPicker) {
        AlertDialog(
            onDismissRequest = { showEnvPicker = false },
            title = { Text(stringResource(R.string.environment)) },
            text = {
                Column {
                    listOf("dev", "staging", "prod").forEach { env ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    viewModel.setEnvironment(env)
                                    showEnvPicker = false
                                }
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(
                                selected = uiState.selectedEnvironment == env,
                                onClick = {
                                    viewModel.setEnvironment(env)
                                    showEnvPicker = false
                                },
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(env.replaceFirstChar { it.uppercase() })
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showEnvPicker = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    // Clear cache dialog
    if (showClearCacheDialog) {
        AlertDialog(
            onDismissRequest = { showClearCacheDialog = false },
            title = { Text(stringResource(R.string.clear_offline_cache)) },
            text = { Text("This will remove all cached data. Fresh data will be downloaded next time.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.clearCache()
                    showClearCacheDialog = false
                }) {
                    Text(stringResource(R.string.delete), color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearCacheDialog = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.titleSmall,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        color = MaterialTheme.colorScheme.primary,
    )
}
