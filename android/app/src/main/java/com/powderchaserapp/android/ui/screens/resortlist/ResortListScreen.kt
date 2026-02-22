package com.powderchaserapp.android.ui.screens.resortlist

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.R
import com.powderchaserapp.android.data.api.Resort
import com.powderchaserapp.android.data.api.SnowQualitySummaryLight
import com.powderchaserapp.android.data.repository.ResortRepository
import com.powderchaserapp.android.data.repository.SnowQualityRepository
import com.powderchaserapp.android.ui.theme.SnowColors
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.util.UnitConversions
import com.powderchaserapp.android.util.UserPreferencesRepository
import com.powderchaserapp.android.util.UnitPreferences
import com.powderchaserapp.android.util.countryCodeToFlag
import com.powderchaserapp.android.util.regionDisplayName
import com.powderchaserapp.android.util.inferRegion
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.roundToInt

data class ResortListUiState(
    val resorts: List<Resort> = emptyList(),
    val qualityMap: Map<String, SnowQualitySummaryLight> = emptyMap(),
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val searchQuery: String = "",
    val sortBy: SortOption = SortOption.QUALITY,
    val selectedRegion: String? = null,
    val selectedPass: PassFilter = PassFilter.ALL,
    val unitPreferences: UnitPreferences = UnitPreferences(),
)

enum class SortOption(val displayName: String) {
    NAME("Name"),
    QUALITY("Quality"),
    FRESH_SNOW("Fresh Snow"),
    SNOW_DEPTH("Depth"),
    PREDICTED("Predicted"),
    TEMPERATURE("Temp"),
    COUNTRY("Country"),
}

enum class PassFilter(val displayName: String) {
    ALL("All"),
    EPIC("Epic"),
    IKON("Ikon"),
}

@HiltViewModel
class ResortListViewModel @Inject constructor(
    private val resortRepository: ResortRepository,
    private val snowQualityRepository: SnowQualityRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(ResortListUiState())
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

    fun loadResorts(forceRefresh: Boolean = false) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = !forceRefresh, isRefreshing = forceRefresh) }
            resortRepository.getResorts(forceRefresh).collect { result ->
                result.fold(
                    onSuccess = { resorts ->
                        _uiState.update { it.copy(resorts = resorts, isLoading = false, isRefreshing = false, error = null) }
                        loadQuality(resorts.map { it.id })
                    },
                    onFailure = { error ->
                        _uiState.update { it.copy(isLoading = false, isRefreshing = false, error = error.message) }
                    },
                )
            }
        }
    }

    private fun loadQuality(resortIds: List<String>) {
        viewModelScope.launch {
            snowQualityRepository.getBatchSnowQuality(resortIds).onSuccess { qualityMap ->
                _uiState.update { it.copy(qualityMap = qualityMap) }
            }
        }
    }

    fun onSearchQueryChange(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
    }

    fun onSortChange(sort: SortOption) {
        _uiState.update { it.copy(sortBy = sort) }
    }

    fun onRegionChange(region: String?) {
        _uiState.update { it.copy(selectedRegion = region) }
    }

    fun onPassFilterChange(pass: PassFilter) {
        _uiState.update { it.copy(selectedPass = pass) }
    }

    fun refresh() = loadResorts(forceRefresh = true)

    val availableRegions: List<String>
        get() {
            val state = _uiState.value
            return state.resorts
                .map { inferRegion(it.country, it.region) }
                .distinct()
                .sorted()
        }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResortListScreen(
    onResortClick: (String) -> Unit,
    viewModel: ResortListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    val filteredResorts = remember(
        uiState.resorts, uiState.searchQuery, uiState.sortBy,
        uiState.qualityMap, uiState.selectedRegion, uiState.selectedPass,
    ) {
        uiState.resorts
            .filter { resort ->
                // Search filter
                val matchesSearch = uiState.searchQuery.isEmpty() ||
                    resort.name.contains(uiState.searchQuery, ignoreCase = true) ||
                    resort.region.contains(uiState.searchQuery, ignoreCase = true) ||
                    resort.country.contains(uiState.searchQuery, ignoreCase = true) ||
                    resort.countryName.contains(uiState.searchQuery, ignoreCase = true)

                // Region filter
                val matchesRegion = uiState.selectedRegion == null ||
                    inferRegion(resort.country, resort.region) == uiState.selectedRegion

                // Pass filter
                val matchesPass = when (uiState.selectedPass) {
                    PassFilter.ALL -> true
                    PassFilter.EPIC -> resort.epicPass != null
                    PassFilter.IKON -> resort.ikonPass != null
                }

                matchesSearch && matchesRegion && matchesPass
            }
            .sortedWith(
                when (uiState.sortBy) {
                    SortOption.NAME -> compareBy { it.name }
                    SortOption.QUALITY -> compareBy {
                        uiState.qualityMap[it.id]?.overallSnowQuality?.sortOrder ?: 99
                    }
                    SortOption.FRESH_SNOW -> compareByDescending {
                        uiState.qualityMap[it.id]?.snowfallFreshCm ?: 0.0
                    }
                    SortOption.SNOW_DEPTH -> compareByDescending {
                        uiState.qualityMap[it.id]?.snowDepthCm ?: 0.0
                    }
                    SortOption.PREDICTED -> compareByDescending {
                        uiState.qualityMap[it.id]?.predictedSnow48hCm ?: 0.0
                    }
                    SortOption.TEMPERATURE -> compareBy {
                        uiState.qualityMap[it.id]?.temperatureC ?: 100.0
                    }
                    SortOption.COUNTRY -> compareBy<Resort> { it.country }.thenBy { it.name }
                },
            )
    }

    val resortCount = filteredResorts.size

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.snow_resorts))
                        if (resortCount > 0) {
                            Text(
                                stringResource(R.string.resorts_count, resortCount),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            // Search bar
            OutlinedTextField(
                value = uiState.searchQuery,
                onValueChange = viewModel::onSearchQueryChange,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                placeholder = { Text(stringResource(R.string.search_resorts_hint)) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                trailingIcon = {
                    if (uiState.searchQuery.isNotEmpty()) {
                        IconButton(onClick = { viewModel.onSearchQueryChange("") }) {
                            Icon(Icons.Default.Clear, contentDescription = null)
                        }
                    }
                },
                singleLine = true,
            )

            // Pass filter chips
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                PassFilter.entries.forEach { pass ->
                    FilterChip(
                        selected = uiState.selectedPass == pass,
                        onClick = { viewModel.onPassFilterChange(pass) },
                        label = { Text(pass.displayName) },
                    )
                }
            }

            // Region filter chips (horizontal scroll)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = uiState.selectedRegion == null,
                    onClick = { viewModel.onRegionChange(null) },
                    label = { Text(stringResource(R.string.all_regions)) },
                )
                viewModel.availableRegions.forEach { region ->
                    FilterChip(
                        selected = uiState.selectedRegion == region,
                        onClick = {
                            viewModel.onRegionChange(
                                if (uiState.selectedRegion == region) null else region,
                            )
                        },
                        label = { Text(regionDisplayName(region)) },
                    )
                }
            }

            // Sort options (horizontal scroll)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SortOption.entries.forEach { option ->
                    FilterChip(
                        selected = uiState.sortBy == option,
                        onClick = { viewModel.onSortChange(option) },
                        label = { Text(option.displayName) },
                        leadingIcon = if (uiState.sortBy == option) {
                            { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                        } else null,
                    )
                }
            }

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                uiState.error != null && filteredResorts.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(uiState.error!!, color = MaterialTheme.colorScheme.error)
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(onClick = { viewModel.refresh() }) {
                                Text(stringResource(R.string.retry))
                            }
                        }
                    }
                }
                filteredResorts.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.SearchOff,
                                contentDescription = null,
                                modifier = Modifier.size(48.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                stringResource(R.string.no_resorts_found),
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                else -> {
                    PullToRefreshBox(
                        isRefreshing = uiState.isRefreshing,
                        onRefresh = { viewModel.refresh() },
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        LazyColumn(modifier = Modifier.fillMaxSize()) {
                            items(filteredResorts, key = { it.id }) { resort ->
                                ResortListItem(
                                    resort = resort,
                                    quality = uiState.qualityMap[resort.id],
                                    unitPreferences = uiState.unitPreferences,
                                    onClick = { onResortClick(resort.id) },
                                )
                            }
                            item { Spacer(modifier = Modifier.height(16.dp)) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ResortListItem(
    resort: Resort,
    quality: SnowQualitySummaryLight?,
    unitPreferences: UnitPreferences,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // Flag + name + location
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = countryCodeToFlag(resort.country),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = resort.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Text(
                        text = resort.displayLocation,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                // Quality badge
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
                                text = snowQuality.displayName,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = snowQualityColor(snowQuality.value),
                            )
                            quality.snowScore?.let { score ->
                                Text(
                                    text = "$score",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = snowQualityColor(snowQuality.value),
                                )
                            }
                        }
                    }
                }
            }

            // Snow data row
            if (quality != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    // Temperature
                    quality.temperatureC?.let { temp ->
                        SnowDataChip(
                            icon = Icons.Default.Thermostat,
                            value = UnitConversions.formatTemperature(temp, unitPreferences.useMetricTemp),
                        )
                    }
                    // Fresh snow
                    quality.snowfallFreshCm?.let { fresh ->
                        if (fresh > 0) {
                            SnowDataChip(
                                icon = Icons.Default.AcUnit,
                                value = UnitConversions.formatSnowShort(fresh, unitPreferences.useMetricSnow),
                                highlight = fresh >= 10,
                            )
                        }
                    }
                    // 24h snowfall
                    quality.snowfall24hCm?.let { snow24 ->
                        if (snow24 > 0) {
                            SnowDataChip(
                                icon = Icons.Default.Grain,
                                value = "24h: ${UnitConversions.formatSnowShort(snow24, unitPreferences.useMetricSnow)}",
                            )
                        }
                    }
                    // Predicted snow
                    quality.predictedSnow48hCm?.let { predicted ->
                        if (predicted > 0) {
                            SnowDataChip(
                                icon = Icons.Default.WbSunny,
                                value = "+${UnitConversions.formatSnowShort(predicted, unitPreferences.useMetricSnow)}",
                                highlight = predicted >= 15,
                            )
                        }
                    }
                }
            }

            // Pass badges
            if (resort.epicPass != null || resort.ikonPass != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    resort.epicPass?.let {
                        Surface(
                            color = MaterialTheme.colorScheme.secondaryContainer,
                            shape = MaterialTheme.shapes.extraSmall,
                        ) {
                            Text(
                                text = "Epic",
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSecondaryContainer,
                            )
                        }
                    }
                    resort.ikonPass?.let {
                        Surface(
                            color = MaterialTheme.colorScheme.tertiaryContainer,
                            shape = MaterialTheme.shapes.extraSmall,
                        ) {
                            Text(
                                text = "Ikon",
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onTertiaryContainer,
                            )
                        }
                    }
                }
            }

            // Explanation text
            quality?.explanation?.let { explanation ->
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = explanation,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun SnowDataChip(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    value: String,
    highlight: Boolean = false,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(14.dp),
            tint = if (highlight) SnowColors.IceBlue else MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = if (highlight) FontWeight.Bold else FontWeight.Normal,
            color = if (highlight) SnowColors.IceBlue else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
