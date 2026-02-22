package com.powderchaserapp.android.ui.screens.favorites

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.util.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FavoritesUiState(
    val allResorts: List<Resort> = emptyList(),
    val favoriteIds: Set<String> = emptySet(),
    val qualityMap: Map<String, SnowQualitySummaryLight> = emptyMap(),
    val isLoading: Boolean = true,
    val unitPreferences: UnitPreferences = UnitPreferences(),
) {
    val favoriteResorts: List<Resort>
        get() = allResorts.filter { it.id in favoriteIds }
            .sortedBy { qualityMap[it.id]?.overallSnowQuality?.sortOrder ?: 99 }
}

@HiltViewModel
class FavoritesViewModel @Inject constructor(
    private val resortRepository: ResortRepository,
    private val snowQualityRepository: SnowQualityRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(FavoritesUiState())
    val uiState = _uiState.asStateFlow()

    init {
        observeFavorites()
        loadResorts()
        observePreferences()
    }

    private fun observeFavorites() {
        viewModelScope.launch {
            userPreferencesRepository.favoriteResorts.collect { favs ->
                _uiState.update { it.copy(favoriteIds = favs) }
            }
        }
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
                    _uiState.update { it.copy(allResorts = resorts, isLoading = false) }
                    snowQualityRepository.getBatchSnowQuality(resorts.map { it.id }).onSuccess { qm ->
                        _uiState.update { it.copy(qualityMap = qm) }
                    }
                }
            }
        }
    }

    fun removeFavorite(resortId: String) {
        viewModelScope.launch {
            userPreferencesRepository.toggleFavorite(resortId)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FavoritesScreen(
    onResortClick: (String) -> Unit,
    onCompareClick: () -> Unit,
    viewModel: FavoritesViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val favorites = uiState.favoriteResorts

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.tab_favorites)) },
                actions = {
                    if (favorites.size >= 2) {
                        IconButton(onClick = onCompareClick) {
                            Icon(Icons.Default.Compare, contentDescription = stringResource(R.string.compare))
                        }
                    }
                },
            )
        },
    ) { padding ->
        when {
            uiState.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }
            }
            favorites.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(32.dp),
                    ) {
                        Icon(
                            Icons.Default.FavoriteBorder,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            stringResource(R.string.no_favorites_yet),
                            style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.no_favorites_description),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        FilledTonalButton(onClick = { /* nav to resorts handled externally */ }) {
                            Text(stringResource(R.string.browse_resorts))
                        }
                    }
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding),
                ) {
                    // Summary card
                    item {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.primaryContainer,
                            ),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                horizontalArrangement = Arrangement.SpaceEvenly,
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        "${favorites.size}",
                                        style = MaterialTheme.typography.headlineMedium,
                                        fontWeight = FontWeight.Bold,
                                    )
                                    Text(
                                        stringResource(R.string.tab_favorites),
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                                val excellentCount = favorites.count {
                                    uiState.qualityMap[it.id]?.overallSnowQuality?.sortOrder == 1
                                }
                                if (excellentCount > 0) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text(
                                            "$excellentCount",
                                            style = MaterialTheme.typography.headlineMedium,
                                            fontWeight = FontWeight.Bold,
                                        )
                                        Text(
                                            stringResource(R.string.quality_excellent),
                                            style = MaterialTheme.typography.bodySmall,
                                        )
                                    }
                                }
                            }
                        }
                    }

                    items(favorites, key = { it.id }) { resort ->
                        val quality = uiState.qualityMap[resort.id]
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 4.dp)
                                .clickable { onResortClick(resort.id) },
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
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
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        resort.displayLocation,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    if (quality?.temperatureC != null) {
                                        Text(
                                            UnitConversions.formatTemperature(quality.temperatureC, uiState.unitPreferences.useMetricTemp),
                                            style = MaterialTheme.typography.bodySmall,
                                        )
                                    }
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
                                                text = snowQuality.displayName,
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
                        }
                    }

                    item { Spacer(modifier = Modifier.height(16.dp)) }
                }
            }
        }
    }
}
