package com.powderchaserapp.android.ui.screens.bestsnow

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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.R
import com.powderchaserapp.android.data.api.PowderChaserApi
import com.powderchaserapp.android.data.api.ResortRecommendation
import com.powderchaserapp.android.service.LocationService
import com.powderchaserapp.android.ui.theme.SnowColors
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.util.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.roundToInt

data class BestSnowUiState(
    val globalRecommendations: List<ResortRecommendation> = emptyList(),
    val nearbyRecommendations: List<ResortRecommendation> = emptyList(),
    val isLoading: Boolean = true,
    val isLoadingNearby: Boolean = false,
    val error: String? = null,
    val selectedTab: Int = 0,
    val unitPreferences: UnitPreferences = UnitPreferences(),
)

@HiltViewModel
class BestSnowViewModel @Inject constructor(
    private val api: PowderChaserApi,
    private val locationService: LocationService,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(BestSnowUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadBestConditions()
        observePreferences()
    }

    private fun observePreferences() {
        viewModelScope.launch {
            userPreferencesRepository.unitPreferences.collect { prefs ->
                _uiState.update { it.copy(unitPreferences = prefs) }
            }
        }
    }

    fun loadBestConditions() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            try {
                val response = api.getBestConditions(limit = 20)
                _uiState.update { it.copy(globalRecommendations = response.recommendations, isLoading = false) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun loadNearby() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingNearby = true) }
            try {
                val location = locationService.getCurrentLocation()
                if (location != null) {
                    val response = api.getRecommendations(
                        lat = location.latitude,
                        lng = location.longitude,
                        limit = 20,
                    )
                    _uiState.update { it.copy(nearbyRecommendations = response.recommendations, isLoadingNearby = false) }
                } else {
                    _uiState.update { it.copy(isLoadingNearby = false) }
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoadingNearby = false) }
            }
        }
    }

    fun selectTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
        if (tab == 1 && _uiState.value.nearbyRecommendations.isEmpty()) {
            loadNearby()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BestSnowScreen(
    onResortClick: (String) -> Unit,
    viewModel: BestSnowViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val units = uiState.unitPreferences

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_best_snow)) }) },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = uiState.selectedTab) {
                Tab(
                    selected = uiState.selectedTab == 0,
                    onClick = { viewModel.selectTab(0) },
                ) {
                    Text(stringResource(R.string.best_globally), modifier = Modifier.padding(12.dp))
                }
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.selectTab(1) },
                ) {
                    Text(stringResource(R.string.near_you), modifier = Modifier.padding(12.dp))
                }
            }

            val recommendations = if (uiState.selectedTab == 0) uiState.globalRecommendations else uiState.nearbyRecommendations
            val isLoading = if (uiState.selectedTab == 0) uiState.isLoading else uiState.isLoadingNearby

            when {
                isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                uiState.error != null && uiState.selectedTab == 0 -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(uiState.error!!, color = MaterialTheme.colorScheme.error)
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(onClick = { viewModel.loadBestConditions() }) {
                                Text(stringResource(R.string.retry))
                            }
                        }
                    }
                }
                recommendations.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.Terrain,
                                contentDescription = null,
                                modifier = Modifier.size(48.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                stringResource(R.string.no_recommendations),
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                else -> {
                    LazyColumn {
                        items(recommendations, key = { it.resort.id }) { rec ->
                            RecommendationCard(
                                rec = rec,
                                units = units,
                                showDistance = uiState.selectedTab == 1,
                                onClick = { onResortClick(rec.resort.id) },
                            )
                        }
                        item { Spacer(modifier = Modifier.height(16.dp)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun RecommendationCard(
    rec: ResortRecommendation,
    units: UnitPreferences,
    showDistance: Boolean,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = countryCodeToFlag(rec.resort.country),
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        rec.resort.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        rec.resort.displayLocation,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Surface(
                        color = snowQualityColor(rec.snowQuality).copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Column(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                text = rec.quality.displayName,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = snowQualityColor(rec.snowQuality),
                            )
                            rec.snowScore?.let { score ->
                                Text(
                                    "$score",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = snowQualityColor(rec.snowQuality),
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Data chips
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Thermostat, contentDescription = null, modifier = Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        UnitConversions.formatTemperature(rec.currentTempCelsius, units.useMetricTemp),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
                if (rec.freshSnowCm > 0) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.AcUnit, contentDescription = null, modifier = Modifier.size(14.dp), tint = SnowColors.IceBlue)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            UnitConversions.formatSnowShort(rec.freshSnowCm, units.useMetricSnow),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = SnowColors.IceBlue,
                        )
                    }
                }
                if (showDistance && rec.distanceKm > 0) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.NearMe, contentDescription = null, modifier = Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            UnitConversions.formatDistance(rec.distanceKm, units.useMetricDistance),
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                }
            }

            // Reason
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                rec.reason,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
