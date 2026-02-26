package com.powderchaserapp.android.ui.screens.resortmap

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
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
import com.powderchaserapp.android.data.api.SnowQuality
import com.powderchaserapp.android.data.api.SnowQualitySummaryLight
import com.powderchaserapp.android.data.api.TimelineResponse
import com.powderchaserapp.android.data.repository.ResortRepository
import com.powderchaserapp.android.data.repository.SnowQualityRepository
import com.powderchaserapp.android.data.repository.TimelineRepository
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.util.*
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.*
import com.google.maps.android.compose.clustering.Clustering
import com.google.maps.android.clustering.ClusterItem
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

// =============================================================================
// Region Presets
// =============================================================================

data class RegionPreset(
    val id: String,
    val label: String,
    val center: LatLng,
    val zoom: Float,
)

val regionPresets = listOf(
    RegionPreset("all", "Show All", LatLng(30.0, 0.0), 2f),
    RegionPreset("na_west", "NA West", LatLng(48.5, -121.5), 5.5f),
    RegionPreset("na_rockies", "Rockies", LatLng(40.6, -111.5), 5f),
    RegionPreset("na_east", "NA East", LatLng(44.5, -72.0), 6f),
    RegionPreset("alps", "Alps", LatLng(46.8, 10.0), 6f),
    RegionPreset("scandinavia", "Scandinavia", LatLng(62.0, 15.0), 5f),
    RegionPreset("japan", "Japan", LatLng(37.0, 139.0), 6f),
    RegionPreset("oceania", "Oceania", LatLng(-42.0, 170.0), 5.5f),
    RegionPreset("south_america", "S. America", LatLng(-33.5, -70.0), 6f),
)

// =============================================================================
// Cluster Item Wrapper
// =============================================================================

data class ResortClusterItem(
    val resort: Resort,
    val quality: SnowQualitySummaryLight?,
    val latLng: LatLng,
) : ClusterItem {
    override fun getPosition(): LatLng = latLng
    override fun getTitle(): String = resort.name
    override fun getSnippet(): String? = quality?.overallSnowQuality?.displayName
    override fun getZIndex(): Float = 0f
}

// =============================================================================
// ViewModel
// =============================================================================

enum class MapDisplayStyle(val label: String) {
    NORMAL("Standard"),
    SATELLITE("Satellite"),
    TERRAIN("Terrain"),
}

data class ForecastDay(
    val date: LocalDate,
    val label: String,
    val isToday: Boolean,
)

data class MapUiState(
    val resorts: List<Resort> = emptyList(),
    val qualityMap: Map<String, SnowQualitySummaryLight> = emptyMap(),
    val isLoading: Boolean = true,
    val selectedResort: Resort? = null,
    val selectedQuality: SnowQualitySummaryLight? = null,
    val unitPreferences: UnitPreferences = UnitPreferences(),
    val mapStyle: MapDisplayStyle = MapDisplayStyle.NORMAL,
    val selectedRegion: String = "na_rockies",
    // Forecast mode
    val forecastDays: List<ForecastDay> = emptyList(),
    val selectedForecastDate: LocalDate? = null, // null = show current conditions
    val forecastQualityMap: Map<String, SnowQuality> = emptyMap(), // resortId -> quality for selected date
    val isForecastLoading: Boolean = false,
)

@HiltViewModel
class ResortMapViewModel @Inject constructor(
    private val resortRepository: ResortRepository,
    private val snowQualityRepository: SnowQualityRepository,
    private val timelineRepository: TimelineRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(MapUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadResorts()
        observePreferences()
        initForecastDays()
    }

    private fun initForecastDays() {
        val today = LocalDate.now()
        val dayFormat = DateTimeFormatter.ofPattern("EEE")
        val days = (0..7).map { offset ->
            val date = today.plusDays(offset.toLong())
            ForecastDay(
                date = date,
                label = if (offset == 0) "Today" else date.format(dayFormat),
                isToday = offset == 0,
            )
        }
        _uiState.update { it.copy(forecastDays = days) }
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
                    val allResults = mutableMapOf<String, SnowQualitySummaryLight>()
                    for (chunk in resorts.map { it.id }.chunked(200)) {
                        snowQualityRepository.getBatchSnowQuality(chunk).onSuccess { qualityMap ->
                            allResults.putAll(qualityMap)
                        }
                    }
                    if (allResults.isNotEmpty()) {
                        _uiState.update { it.copy(qualityMap = allResults) }
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

    fun setMapStyle(style: MapDisplayStyle) {
        _uiState.update { it.copy(mapStyle = style) }
    }

    fun setRegion(regionId: String) {
        _uiState.update { it.copy(selectedRegion = regionId) }
    }

    fun selectForecastDate(date: LocalDate?) {
        if (date == null || date == LocalDate.now()) {
            // Reset to current conditions
            _uiState.update { it.copy(selectedForecastDate = null, forecastQualityMap = emptyMap()) }
            return
        }
        _uiState.update { it.copy(selectedForecastDate = date, isForecastLoading = true) }
        loadForecastForDate(date)
    }

    private fun loadForecastForDate(date: LocalDate) {
        viewModelScope.launch {
            val dateStr = date.toString() // "2026-02-28"
            val forecastMap = mutableMapOf<String, SnowQuality>()
            // Load timelines for a sample of resorts (first 50 to avoid overloading)
            val resorts = _uiState.value.resorts.take(50)
            for (resort in resorts) {
                try {
                    timelineRepository.getTimeline(resort.id, "mid").onSuccess { timeline ->
                        // Find the best quality point for the selected date
                        val dayPoints = timeline.timeline.filter { it.date == dateStr }
                        val bestQuality = dayPoints.minByOrNull { it.snowQuality.sortOrder }?.snowQuality
                        if (bestQuality != null) {
                            forecastMap[resort.id] = bestQuality
                        }
                    }
                } catch (_: Exception) { /* skip failed resorts */ }
            }
            _uiState.update {
                it.copy(forecastQualityMap = forecastMap, isForecastLoading = false)
            }
        }
    }
}

// =============================================================================
// Map Screen Composable
// =============================================================================

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

    // Default to NA Rockies
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(LatLng(40.6, -111.5), 5f)
    }

    // Map type from style selection
    val mapType = when (uiState.mapStyle) {
        MapDisplayStyle.NORMAL -> MapType.NORMAL
        MapDisplayStyle.SATELLITE -> MapType.SATELLITE
        MapDisplayStyle.TERRAIN -> MapType.TERRAIN
    }
    val mapProperties = MapProperties(mapType = mapType)

    // Whether we're in forecast mode
    val isForecastMode = uiState.selectedForecastDate != null

    // Build cluster items
    val clusterItems = remember(uiState.resorts, uiState.qualityMap, uiState.forecastQualityMap, isForecastMode) {
        uiState.resorts.mapNotNull { resort ->
            val point = resort.midElevation ?: resort.baseElevation ?: return@mapNotNull null
            ResortClusterItem(
                resort = resort,
                quality = uiState.qualityMap[resort.id],
                latLng = LatLng(point.latitude, point.longitude),
            )
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = cameraPositionState,
            properties = mapProperties,
            onMapClick = { viewModel.clearSelection() },
        ) {
            Clustering(
                items = clusterItems,
                onClusterClick = { cluster ->
                    // Zoom into the cluster bounds
                    val builder = LatLngBounds.builder()
                    cluster.items.forEach { builder.include(it.position) }
                    cameraPositionState.move(
                        CameraUpdateFactory.newLatLngBounds(builder.build(), 100)
                    )
                    true
                },
                onClusterItemClick = { item ->
                    viewModel.selectResort(item.resort)
                    false
                },
                clusterItemContent = { item ->
                    // Custom marker content for individual items
                    // Use forecast quality if in forecast mode, otherwise current
                    val forecastQuality = if (isForecastMode) uiState.forecastQualityMap[item.resort.id] else null
                    val quality = item.quality
                    val markerColor = forecastQuality?.let { snowQualityColor(it.value) }
                        ?: quality?.let { snowQualityColor(it.overallSnowQuality.value) }
                        ?: MaterialTheme.colorScheme.primary
                    Surface(
                        color = markerColor,
                        shape = MaterialTheme.shapes.small,
                        shadowElevation = 2.dp,
                    ) {
                        Text(
                            text = forecastQuality?.displayName?.take(3)
                                ?: quality?.snowScore?.toString() ?: "",
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = androidx.compose.ui.graphics.Color.White,
                        )
                    }
                },
                clusterContent = { cluster ->
                    // Custom cluster badge showing count
                    Surface(
                        color = MaterialTheme.colorScheme.primary,
                        shape = MaterialTheme.shapes.medium,
                        shadowElevation = 4.dp,
                    ) {
                        Text(
                            text = "${cluster.size}",
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    }
                },
            )
        }

        // Region presets chip row at top
        Column(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 8.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                regionPresets.forEach { preset ->
                    FilterChip(
                        selected = uiState.selectedRegion == preset.id,
                        onClick = {
                            viewModel.setRegion(preset.id)
                            cameraPositionState.move(
                                CameraUpdateFactory.newLatLngZoom(preset.center, preset.zoom)
                            )
                        },
                        label = { Text(preset.label, style = MaterialTheme.typography.labelSmall) },
                        colors = FilterChipDefaults.filterChipColors(
                            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
                        ),
                        elevation = FilterChipDefaults.filterChipElevation(elevation = 2.dp),
                    )
                }
            }

            // Forecast date chips
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 8.dp, vertical = 0.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(
                    Icons.Default.CalendarMonth,
                    contentDescription = "Forecast",
                    modifier = Modifier
                        .size(20.dp)
                        .align(Alignment.CenterVertically),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.width(4.dp))
                uiState.forecastDays.forEach { day ->
                    val isSelected = if (day.isToday) {
                        uiState.selectedForecastDate == null
                    } else {
                        uiState.selectedForecastDate == day.date
                    }
                    FilterChip(
                        selected = isSelected,
                        onClick = {
                            viewModel.selectForecastDate(if (day.isToday) null else day.date)
                        },
                        label = {
                            Text(
                                day.label,
                                style = MaterialTheme.typography.labelSmall,
                            )
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
                        ),
                        elevation = FilterChipDefaults.filterChipElevation(elevation = 2.dp),
                    )
                }
            }

            // Forecast banner
            if (isForecastMode) {
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = MaterialTheme.shapes.small,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (uiState.isForecastLoading) {
                            CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        Text(
                            text = if (uiState.isForecastLoading) {
                                "Loading forecast..."
                            } else {
                                val dateFormat = DateTimeFormatter.ofPattern("EEEE, MMM d")
                                "Showing forecast for ${uiState.selectedForecastDate?.format(dateFormat)}"
                            },
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                        )
                    }
                }
            }
        }

        // Resort count badge (bottom-left)
        Surface(
            modifier = Modifier
                .align(Alignment.BottomStart)
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

        // Map style toggle (top-right, below chips)
        var showStyleMenu by remember { mutableStateOf(false) }
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 56.dp, end = 8.dp),
        ) {
            Surface(
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
                shape = MaterialTheme.shapes.small,
                shadowElevation = 2.dp,
            ) {
                IconButton(onClick = { showStyleMenu = !showStyleMenu }) {
                    Icon(Icons.Default.Layers, contentDescription = "Map style")
                }
            }
            DropdownMenu(
                expanded = showStyleMenu,
                onDismissRequest = { showStyleMenu = false },
            ) {
                MapDisplayStyle.entries.forEach { style ->
                    DropdownMenuItem(
                        text = {
                            Text(
                                style.label,
                                fontWeight = if (style == uiState.mapStyle) FontWeight.Bold else FontWeight.Normal,
                            )
                        },
                        onClick = {
                            viewModel.setMapStyle(style)
                            showStyleMenu = false
                        },
                        leadingIcon = {
                            if (style == uiState.mapStyle) {
                                Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(18.dp))
                            }
                        },
                    )
                }
            }
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
