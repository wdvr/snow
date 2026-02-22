package com.powderchaserapp.android.ui.screens.conditionreport

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.data.api.ConditionReport
import com.powderchaserapp.android.data.api.ConditionType
import com.powderchaserapp.android.data.api.ElevationLevel
import com.powderchaserapp.android.data.repository.ConditionReportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ConditionReportUiState(
    val reports: List<ConditionReport> = emptyList(),
    val isLoading: Boolean = true,
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val submitSuccess: Boolean = false,
    val selectedConditionType: ConditionType = ConditionType.POWDER,
    val selectedScore: Int = 7,
    val selectedElevation: ElevationLevel = ElevationLevel.MID,
    val comment: String = "",
)

@HiltViewModel
class ConditionReportViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val conditionReportRepository: ConditionReportRepository,
) : ViewModel() {
    private val resortId: String = savedStateHandle["resortId"] ?: ""

    private val _uiState = MutableStateFlow(ConditionReportUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadReports()
    }

    fun loadReports() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            conditionReportRepository.getConditionReports(resortId).fold(
                onSuccess = { response ->
                    _uiState.update { it.copy(reports = response.reports, isLoading = false) }
                },
                onFailure = { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message) }
                },
            )
        }
    }

    fun submitReport() {
        viewModelScope.launch {
            val state = _uiState.value
            _uiState.update { it.copy(isSubmitting = true, error = null) }
            conditionReportRepository.submitConditionReport(
                resortId = resortId,
                conditionType = state.selectedConditionType.value,
                score = state.selectedScore,
                comment = state.comment.ifBlank { null },
                elevationLevel = state.selectedElevation.value,
            ).fold(
                onSuccess = {
                    _uiState.update { it.copy(isSubmitting = false, submitSuccess = true) }
                    loadReports()
                },
                onFailure = { e ->
                    _uiState.update { it.copy(isSubmitting = false, error = e.message) }
                },
            )
        }
    }

    fun setConditionType(type: ConditionType) {
        _uiState.update { it.copy(selectedConditionType = type) }
    }

    fun setScore(score: Int) {
        _uiState.update { it.copy(selectedScore = score) }
    }

    fun setElevation(level: ElevationLevel) {
        _uiState.update { it.copy(selectedElevation = level) }
    }

    fun setComment(comment: String) {
        _uiState.update { it.copy(comment = comment) }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ConditionReportScreen(
    resortId: String,
    onBackClick: () -> Unit,
    viewModel: ConditionReportViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Condition Reports") },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            // Submit form
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Submit Report", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.height(12.dp))

                        // Condition type chips
                        Text("Condition Type", style = MaterialTheme.typography.labelMedium)
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            ConditionType.entries.forEach { type ->
                                FilterChip(
                                    selected = uiState.selectedConditionType == type,
                                    onClick = { viewModel.setConditionType(type) },
                                    label = { Text(type.displayName) },
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // Elevation
                        Text("Elevation", style = MaterialTheme.typography.labelMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            ElevationLevel.entries.forEach { level ->
                                FilterChip(
                                    selected = uiState.selectedElevation == level,
                                    onClick = { viewModel.setElevation(level) },
                                    label = { Text(level.displayName) },
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // Score slider
                        Text("Score: ${uiState.selectedScore}/10", style = MaterialTheme.typography.labelMedium)
                        Slider(
                            value = uiState.selectedScore.toFloat(),
                            onValueChange = { viewModel.setScore(it.toInt()) },
                            valueRange = 1f..10f,
                            steps = 8,
                        )

                        // Comment
                        OutlinedTextField(
                            value = uiState.comment,
                            onValueChange = { viewModel.setComment(it) },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Comment (optional)") },
                            maxLines = 3,
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Button(
                            onClick = { viewModel.submitReport() },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !uiState.isSubmitting,
                        ) {
                            if (uiState.isSubmitting) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            } else {
                                Text("Submit Report")
                            }
                        }

                        uiState.error?.let {
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            // Existing reports
            item {
                Text("Recent Reports", style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(vertical = 8.dp))
            }

            if (uiState.isLoading) {
                item {
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            } else {
                items(uiState.reports, key = { it.reportId }) { report ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text(report.conditionType.replaceFirstChar { it.uppercase() },
                                    style = MaterialTheme.typography.titleSmall)
                                Text("${report.score}/10", style = MaterialTheme.typography.titleSmall)
                            }
                            report.comment?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall)
                            }
                            Text(
                                "${report.userName ?: "Anonymous"} - ${report.elevationLevel ?: ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
}
