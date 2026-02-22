package com.powderchaserapp.android.ui.screens.resortmap

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
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
import com.powderchaserapp.android.data.api.Resort
import com.powderchaserapp.android.data.api.SnowQualitySummaryLight
import com.powderchaserapp.android.data.repository.ResortRepository
import com.powderchaserapp.android.data.repository.SnowQualityRepository
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.util.*
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MapUiState(
    val resorts: List<Resort> = emptyList(),
    val qualityMap: Map<String, SnowQualitySummaryLight> = emptyMap(),
    val isLoading: Boolean = true,
    val selectedResort: Resort? = null,
    val selectedQuality: SnowQualitySummaryLight? = null,
    val unitPreferences: UnitPreferences = UnitPreferences(),
)

@HiltViewModel
class ResortMapViewModel @Inject constructor(
    private val resortRepository: ResortRepository,
    private val snowQualityRepository: SnowQualityRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(MapUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadResorts()
        observePreferences()
    }

    private fun observePreferences() {
        viewModelScope.launch {
            userPreferencesRepository.unitPreferences.collect { prefs ->
                _uiState.update { it.copy(unitPreferences = prefs) }
            }
        }
    }

    private fun loadResorts() {
        viewModelScope.launch {
            resortRepository.getResorts().collect { result ->
                result.onSuccess { resorts ->
                    _uiState.update { it.copy(resorts = resorts, isLoading = false) }
                    snowQualityRepository.getBatchSnowQuality(resorts.map { it.id }).onSuccess { quality ->
                        _uiState.update { it.copy(qualityMap = quality) }
                    }
                }
            }
        }
    }

    fun selectResort(resort: Resort) {
        _uiState.update {
            it.copy(
                selectedResort = resort,
                selectedQuality = it.qualityMap[resort.id],
            )
        }
    }

    fun clearSelection() {
        _uiState.update { it.copy(selectedResort = null, selectedQuality = null) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResortMapScreen(
    onResortClick: (String) -> Unit,
    viewModel: ResortMapViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val units = uiState.unitPreferences

    if (uiState.isLoading) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }

    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(LatLng(46.8, 8.2), 4f)
    }

    Box(modifier = Modifier.fillMaxSize()) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = cameraPositionState,
        ) {
            uiState.resorts.forEach { resort ->
                val point = resort.midElevation ?: resort.baseElevation ?: return@forEach
                val quality = uiState.qualityMap[resort.id]

                // Map quality to marker color
                val hue = quality?.let {
                    when (it.overallSnowQuality.value) {
                        "excellent" -> BitmapDescriptorFactory.HUE_GREEN
                        "good" -> BitmapDescriptorFactory.HUE_GREEN + 30f
                        "fair" -> BitmapDescriptorFactory.HUE_ORANGE
                        "poor" -> BitmapDescriptorFactory.HUE_ORANGE
                        "slushy" -> BitmapDescriptorFactory.HUE_YELLOW
                        "bad" -> BitmapDescriptorFactory.HUE_RED
                        "horrible" -> BitmapDescriptorFactory.HUE_VIOLET
                        else -> BitmapDescriptorFactory.HUE_AZURE
                    }
                } ?: BitmapDescriptorFactory.HUE_AZURE

                Marker(
                    state = MarkerState(position = LatLng(point.latitude, point.longitude)),
                    title = resort.name,
                    snippet = quality?.overallSnowQuality?.displayName ?: stringResource(R.string.loading),
                    icon = BitmapDescriptorFactory.defaultMarker(hue),
                    onClick = {
                        viewModel.selectResort(resort)
                        false // show info window
                    },
                )
            }
        }

        // Resort count badge
        Surface(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(16.dp),
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
            shape = MaterialTheme.shapes.small,
            shadowElevation = 2.dp,
        ) {
            Text(
                stringResource(R.string.resorts_count, uiState.resorts.size),
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                style = MaterialTheme.typography.labelMedium,
            )
        }

        // Bottom sheet for selected resort
        uiState.selectedResort?.let { resort ->
            val quality = uiState.selectedQuality
            Card(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(16.dp)
                    .clickable { onResortClick(resort.id) },
                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = countryCodeToFlag(resort.country),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                resort.name,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                resort.displayLocation,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (quality != null) {
                            val snowQuality = quality.overallSnowQuality
                            Surface(
                                color = snowQualityColor(snowQuality.value).copy(alpha = 0.15f),
                                shape = MaterialTheme.shapes.small,
                            ) {
                                Column(
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                ) {
                                    Text(
                                        snowQuality.displayName,
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = snowQualityColor(snowQuality.value),
                                    )
                                    quality.snowScore?.let { score ->
                                        Text(
                                            "$score",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = snowQualityColor(snowQuality.value),
                                        )
                                    }
                                }
                            }
                        }
                    }

                    if (quality != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            quality.temperatureC?.let { temp ->
                                Text(
                                    UnitConversions.formatTemperature(temp, units.useMetricTemp),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            quality.snowfallFreshCm?.let { fresh ->
                                if (fresh > 0) {
                                    Text(
                                        "${stringResource(R.string.fresh)}: ${UnitConversions.formatSnowShort(fresh, units.useMetricSnow)}",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.view_full_details),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}
