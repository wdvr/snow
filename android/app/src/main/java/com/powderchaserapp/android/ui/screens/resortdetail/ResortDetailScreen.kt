package com.powderchaserapp.android.ui.screens.resortdetail

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.R
import com.powderchaserapp.android.data.api.*
import com.powderchaserapp.android.data.repository.*
import com.powderchaserapp.android.ui.components.ResortLogo
import com.powderchaserapp.android.ui.theme.SnowColors
import com.powderchaserapp.android.ui.theme.snowQualityColor
import com.powderchaserapp.android.ui.theme.visibilityCategoryColor
import com.powderchaserapp.android.util.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.roundToInt

data class ResortDetailUiState(
    val resort: Resort? = null,
    val conditions: List<WeatherCondition> = emptyList(),
    val snowQuality: SnowQualitySummary? = null,
    val timeline: TimelineResponse? = null,
    val selectedElevation: ElevationLevel = ElevationLevel.MID,
    val isFavorite: Boolean = false,
    val isLoading: Boolean = true,
    val error: String? = null,
    val unitPreferences: UnitPreferences = UnitPreferences(),
)

@HiltViewModel
class ResortDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val resortRepository: ResortRepository,
    private val conditionsRepository: ConditionsRepository,
    private val snowQualityRepository: SnowQualityRepository,
    private val timelineRepository: TimelineRepository,
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val resortId: String = savedStateHandle["resortId"] ?: ""

    private val _uiState = MutableStateFlow(ResortDetailUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadResortDetail()
        observePreferences()
        observeFavorite()
    }

    private fun observePreferences() {
        viewModelScope.launch {
            userPreferencesRepository.unitPreferences.collect { prefs ->
                _uiState.update { it.copy(unitPreferences = prefs) }
            }
        }
    }

    private fun observeFavorite() {
        viewModelScope.launch {
            userPreferencesRepository.favoriteResorts.collect { favs ->
                _uiState.update { it.copy(isFavorite = resortId in favs) }
            }
        }
    }

    fun loadResortDetail() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            resortRepository.getResort(resortId).fold(
                onSuccess = { resort -> _uiState.update { it.copy(resort = resort) } },
                onFailure = { e -> _uiState.update { it.copy(error = e.message) } },
            )

            conditionsRepository.getConditions(resortId).onSuccess { conditions ->
                _uiState.update { it.copy(conditions = conditions) }
            }

            snowQualityRepository.getSnowQuality(resortId).onSuccess { quality ->
                _uiState.update { it.copy(snowQuality = quality) }
            }

            timelineRepository.getTimeline(resortId).onSuccess { timeline ->
                _uiState.update { it.copy(timeline = timeline) }
            }

            _uiState.update { it.copy(isLoading = false) }
        }
    }

    fun selectElevation(level: ElevationLevel) {
        _uiState.update { it.copy(selectedElevation = level) }
        viewModelScope.launch {
            timelineRepository.getTimeline(resortId, level.value).onSuccess { timeline ->
                _uiState.update { it.copy(timeline = timeline) }
            }
        }
    }

    fun toggleFavorite() {
        viewModelScope.launch {
            userPreferencesRepository.toggleFavorite(resortId)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResortDetailScreen(
    resortId: String,
    onBackClick: () -> Unit,
    onChatClick: () -> Unit,
    onConditionReportClick: () -> Unit,
    viewModel: ResortDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val units = uiState.unitPreferences

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.resort?.name ?: stringResource(R.string.loading)) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    // Share button
                    IconButton(onClick = {
                        uiState.resort?.let { resort ->
                            val shareText = buildString {
                                append("${resort.name}")
                                uiState.snowQuality?.let { q ->
                                    append(" - ${q.overallSnowQuality.displayName}")
                                    q.overallSnowScore?.let { append(" ($it/100)") }
                                }
                                // Add conditions from selected elevation
                                val cond = uiState.conditions.firstOrNull {
                                    it.elevationLevel == uiState.selectedElevation.value
                                }
                                cond?.let { c ->
                                    append("\n${UnitConversions.formatTemperature(c.currentTempCelsius, units.useMetricTemp)}")
                                    if (c.freshSnowCm > 0) {
                                        append(" | Fresh: ${UnitConversions.formatSnowShort(c.freshSnowCm, units.useMetricSnow)}")
                                    }
                                    c.snowDepthCm?.let { depth ->
                                        if (depth > 0) append(" | Depth: ${UnitConversions.formatSnowShort(depth, units.useMetricSnow)}")
                                    }
                                    c.predictedSnow48hCm?.let { pred ->
                                        if (pred > 0) append(" | 48h forecast: ${UnitConversions.formatSnowShort(pred, units.useMetricSnow)}")
                                    }
                                }
                                resort.officialWebsite?.let { append("\n$it") }
                            }
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, shareText)
                            }
                            context.startActivity(Intent.createChooser(intent, null))
                        }
                    }) {
                        Icon(Icons.Default.Share, contentDescription = stringResource(R.string.share))
                    }
                    // Favorite button
                    IconButton(onClick = { viewModel.toggleFavorite() }) {
                        Icon(
                            if (uiState.isFavorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                            contentDescription = null,
                            tint = if (uiState.isFavorite) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                        )
                    }
                    // Chat
                    IconButton(onClick = onChatClick) {
                        Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = stringResource(R.string.ask_ai))
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
            uiState.error != null && uiState.resort == null -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(uiState.error!!, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadResortDetail() }) {
                            Text(stringResource(R.string.retry))
                        }
                    }
                }
            }
            else -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .verticalScroll(rememberScrollState()),
                ) {
                    // Resort header card
                    uiState.resort?.let { resort ->
                        ResortHeaderCard(resort, uiState.snowQuality, units)
                    }

                    // Elevation picker
                    ElevationPicker(
                        selected = uiState.selectedElevation,
                        onSelect = { viewModel.selectElevation(it) },
                        resort = uiState.resort,
                        units = units,
                    )

                    // Snow quality card
                    uiState.snowQuality?.let { quality ->
                        SnowQualityCard(quality, uiState.selectedElevation, units)
                    }

                    // Current conditions card
                    val selectedCondition = uiState.conditions.firstOrNull {
                        it.elevationLevel == uiState.selectedElevation.value
                    }
                    selectedCondition?.let { condition ->
                        CurrentConditionsCard(condition, units)
                    }

                    // Snow details card (24h/48h/72h)
                    selectedCondition?.let { condition ->
                        SnowDetailsCard(condition, units)
                    }

                    // Fresh snow chart (7-day daily snowfall bars)
                    uiState.timeline?.let { timeline ->
                        FreshSnowChart(
                            timeline = timeline,
                            condition = selectedCondition,
                            units = units,
                        )
                    }

                    // Predictions card
                    selectedCondition?.let { condition ->
                        PredictionsCard(condition, units)
                    }

                    // Weather details card
                    selectedCondition?.let { condition ->
                        WeatherDetailsCard(condition, units)
                    }

                    // Data sources card (transparency)
                    selectedCondition?.let { condition ->
                        DataSourcesCard(condition, units)
                    }

                    // Run difficulty
                    uiState.resort?.let { resort ->
                        if (resort.greenRunsPct != null || resort.blueRunsPct != null || resort.blackRunsPct != null) {
                            RunDifficultyCard(resort)
                        }
                    }

                    // Trail map link
                    uiState.resort?.trailMapUrl?.let { trailMapUrl ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 4.dp)
                                .clickable {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(trailMapUrl))
                                    context.startActivity(intent)
                                },
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(Icons.Default.Map, contentDescription = null)
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(
                                    "View Trail Map",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }

                    // Timeline / 7-day forecast placeholder
                    uiState.timeline?.let { timeline ->
                        TimelineCard(timeline, units)
                    }

                    // All elevations summary
                    if (uiState.snowQuality != null && uiState.snowQuality!!.elevations.size > 1) {
                        AllElevationsSummaryCard(uiState.snowQuality!!, units)
                    }

                    // Visit website
                    uiState.resort?.officialWebsite?.let { website ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 4.dp),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(Icons.Default.Language, contentDescription = null)
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(
                                    stringResource(R.string.visit_website),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }

                    // Condition report button
                    OutlinedButton(
                        onClick = onConditionReportClick,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                    ) {
                        Icon(Icons.Default.Edit, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(stringResource(R.string.condition_reports))
                    }

                    Spacer(modifier = Modifier.height(32.dp))
                }
            }
        }
    }
}

@Composable
private fun ResortHeaderCard(resort: Resort, quality: SnowQualitySummary?, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                ResortLogo(
                    resortName = resort.name,
                    officialWebsite = resort.officialWebsite,
                    size = 44.dp,
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = countryCodeToFlag(resort.country),
                    style = MaterialTheme.typography.headlineMedium,
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(resort.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(
                        resort.displayLocation,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    // Elevation range
                    val baseElev = resort.baseElevation?.elevationMeters
                    val topElev = resort.topElevation?.elevationMeters
                    if (baseElev != null && topElev != null) {
                        Text(
                            "${UnitConversions.formatElevation(baseElev, units.useMetricDistance)} - ${UnitConversions.formatElevation(topElev, units.useMetricDistance)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            // Quality + score
            quality?.let { q ->
                Spacer(modifier = Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        color = snowQualityColor(q.overallQuality).copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = q.overallSnowQuality.displayName,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = snowQualityColor(q.overallQuality),
                        )
                    }
                    q.overallSnowScore?.let { score ->
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("$score/100", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    }
                }
            }

            // Pass badges
            if (resort.epicPass != null || resort.ikonPass != null || resort.indyPass != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    resort.epicPass?.let {
                        AssistChip(onClick = {}, label = { Text("Epic: $it") })
                    }
                    resort.ikonPass?.let {
                        AssistChip(onClick = {}, label = { Text("Ikon: $it") })
                    }
                    resort.indyPass?.let {
                        AssistChip(
                            onClick = {},
                            label = { Text("Indy: $it") },
                            colors = AssistChipDefaults.assistChipColors(
                                containerColor = SnowColors.IndyGreen.copy(alpha = 0.15f),
                                labelColor = SnowColors.IndyGreen,
                            ),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ElevationPicker(
    selected: ElevationLevel,
    onSelect: (ElevationLevel) -> Unit,
    resort: Resort? = null,
    units: UnitPreferences = UnitPreferences(),
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ElevationLevel.entries.forEach { level ->
            val color = when (level) {
                ElevationLevel.BASE -> SnowColors.ElevationBase
                ElevationLevel.MID -> SnowColors.ElevationMid
                ElevationLevel.TOP -> SnowColors.ElevationTop
            }
            val elevMeters = resort?.elevationPoint(level)?.elevationMeters
            val elevLabel = if (elevMeters != null) {
                "${level.displayName} ${UnitConversions.formatElevation(elevMeters, units.useMetricDistance)}"
            } else {
                level.displayName
            }
            FilterChip(
                selected = selected == level,
                onClick = { onSelect(level) },
                label = { Text(elevLabel) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = color.copy(alpha = 0.2f),
                    selectedLabelColor = color,
                ),
            )
        }
    }
}

@Composable
private fun SnowQualityCard(quality: SnowQualitySummary, elevation: ElevationLevel, units: UnitPreferences) {
    val elevSummary = quality.elevations[elevation.value]
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.snow_quality), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))

            if (elevSummary != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        color = snowQualityColor(elevSummary.quality).copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = elevSummary.snowQuality.displayName,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = snowQualityColor(elevSummary.quality),
                        )
                    }
                    elevSummary.snowScore?.let { score ->
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("$score/100", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                    }
                }
                elevSummary.explanation?.let { explanation ->
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = explanation,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                // Overall
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        color = snowQualityColor(quality.overallQuality).copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = quality.overallSnowQuality.displayName,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = snowQualityColor(quality.overallQuality),
                        )
                    }
                    quality.overallSnowScore?.let { score ->
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("$score/100", style = MaterialTheme.typography.bodyMedium)
                    }
                }
                quality.overallExplanation?.let { explanation ->
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(explanation, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun CurrentConditionsCard(condition: WeatherCondition, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.current_conditions), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                ConditionItem(
                    stringResource(R.string.temp),
                    UnitConversions.formatTemperature(condition.currentTempCelsius, units.useMetricTemp),
                )
                ConditionItem(
                    stringResource(R.string.fresh),
                    UnitConversions.formatSnowShort(condition.freshSnowCm, units.useMetricSnow),
                )
                ConditionItem(
                    stringResource(R.string.snowfall_24h),
                    UnitConversions.formatSnowShort(condition.snowfall24hCm, units.useMetricSnow),
                )
                condition.snowDepthCm?.let { depth ->
                    ConditionItem(
                        stringResource(R.string.snow_depth),
                        UnitConversions.formatSnowShort(depth, units.useMetricSnow),
                    )
                }
            }
            condition.weatherDescription?.let { desc ->
                Spacer(modifier = Modifier.height(8.dp))
                Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun SnowDetailsCard(condition: WeatherCondition, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.recent_snowfall), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(12.dp))

            // Snowfall amounts
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                SnowAmountItem(
                    stringResource(R.string.snowfall_24h),
                    condition.snowfall24hCm,
                    units.useMetricSnow,
                )
                SnowAmountItem(
                    stringResource(R.string.snowfall_48h),
                    condition.snowfall48hCm,
                    units.useMetricSnow,
                )
                SnowAmountItem(
                    stringResource(R.string.snowfall_72h),
                    condition.snowfall72hCm,
                    units.useMetricSnow,
                )
            }

            // Thaw/freeze info
            condition.lastFreezeThawHoursAgo?.let { hours ->
                Spacer(modifier = Modifier.height(12.dp))
                HorizontalDivider()
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column {
                        Text(
                            stringResource(R.string.last_thaw_freeze),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            "${hours.roundToInt()}h ago",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            stringResource(R.string.snow_since_freeze),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            UnitConversions.formatSnow(condition.snowSinceFreeze, units.useMetricSnow),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                if (condition.currentlyWarming == true) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        color = SnowColors.SunsetOrange.copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = stringResource(R.string.warming),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = SnowColors.SunsetOrange,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PredictionsCard(condition: WeatherCondition, units: UnitPreferences) {
    val p24 = condition.predictedSnow24hCm
    val p48 = condition.predictedSnow48hCm
    val p72 = condition.predictedSnow72hCm
    if (p24 == null && p48 == null && p72 == null) return

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.snow_forecast), style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.weight(1f))
                // Storm badge
                val totalPredicted = (p24 ?: 0.0) + (p48 ?: 0.0) + (p72 ?: 0.0)
                if (totalPredicted >= 30) {
                    Surface(
                        color = SnowColors.IceBlue.copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = stringResource(R.string.heavy_snowfall_expected),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = SnowColors.IceBlue,
                        )
                    }
                } else if (totalPredicted > 0) {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = stringResource(R.string.light_snow_expected),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                p24?.let {
                    SnowAmountItem(stringResource(R.string.next_24h), it, units.useMetricSnow)
                }
                p48?.let {
                    SnowAmountItem(stringResource(R.string.next_48h), it, units.useMetricSnow)
                }
                p72?.let {
                    SnowAmountItem(stringResource(R.string.next_72h), it, units.useMetricSnow)
                }
            }
        }
    }
}

@Composable
private fun WeatherDetailsCard(condition: WeatherCondition, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.weather_details), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(12.dp))

            WeatherRow(stringResource(R.string.min_temp), UnitConversions.formatTemperature(condition.minTempCelsius, units.useMetricTemp))
            WeatherRow(stringResource(R.string.max_temp), UnitConversions.formatTemperature(condition.maxTempCelsius, units.useMetricTemp))
            condition.humidityPercent?.let {
                WeatherRow(stringResource(R.string.humidity), "${it.roundToInt()}%")
            }
            condition.windSpeedKmh?.let {
                WeatherRow(stringResource(R.string.wind), UnitConversions.formatWindSpeed(it, units.useMetricDistance))
            }
            condition.windGustKmh?.let { gust ->
                WeatherRow(stringResource(R.string.wind_gusts), UnitConversions.formatWindSpeed(gust, units.useMetricDistance))
            }
            condition.maxWindGust24h?.let { maxGust ->
                WeatherRow(stringResource(R.string.max_gust_24h), UnitConversions.formatWindSpeed(maxGust, units.useMetricDistance))
            }

            // Visibility warning
            condition.visibilityM?.let { vis ->
                if (vis < 5000) {
                    val category = visibilityCategory(vis)
                    val visColor = visibilityCategoryColor(category)
                    Spacer(modifier = Modifier.height(8.dp))
                    HorizontalDivider()
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.semantics {
                            contentDescription = "Visibility ${category.label}, ${formatVisibility(vis, units.useMetricDistance)}"
                        },
                    ) {
                        Icon(
                            Icons.Default.Cloud,
                            contentDescription = null,
                            tint = visColor,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "${stringResource(R.string.visibility)}: ${category.label}",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium,
                                color = visColor,
                            )
                            Text(
                                text = formatVisibility(vis, units.useMetricDistance),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            condition.minVisibility24hM?.let { minVis ->
                                if (minVis < vis) {
                                    Text(
                                        text = stringResource(R.string.low_today, formatVisibility(minVis, units.useMetricDistance)),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun WeatherRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun RunDifficultyCard(resort: Resort) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.run_difficulty), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(12.dp))

            val green = resort.greenRunsPct ?: 0
            val blue = resort.blueRunsPct ?: 0
            val black = resort.blackRunsPct ?: 0
            val total = green + blue + black
            if (total > 0) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(24.dp)
                        .clip(RoundedCornerShape(12.dp)),
                ) {
                    if (green > 0) {
                        Box(
                            modifier = Modifier
                                .weight(green.toFloat())
                                .fillMaxHeight()
                                .background(SnowColors.ElevationBase),
                        )
                    }
                    if (blue > 0) {
                        Box(
                            modifier = Modifier
                                .weight(blue.toFloat())
                                .fillMaxHeight()
                                .background(SnowColors.ElevationMid),
                        )
                    }
                    if (black > 0) {
                        Box(
                            modifier = Modifier
                                .weight(black.toFloat())
                                .fillMaxHeight()
                                .background(SnowColors.ElevationTop),
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    DifficultyLabel("Green", green, SnowColors.ElevationBase)
                    DifficultyLabel("Blue", blue, SnowColors.ElevationMid)
                    DifficultyLabel("Black", black, SnowColors.ElevationTop)
                }
            }
        }
    }
}

@Composable
private fun DifficultyLabel(name: String, pct: Int, color: androidx.compose.ui.graphics.Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(color),
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text("$name $pct%", style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun TimelineCard(timeline: TimelineResponse, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.seven_day_forecast), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "${timeline.timeline.size} data points at ${timeline.elevationLevel} (${UnitConversions.formatElevation(timeline.elevationMeters.toDouble(), units.useMetricDistance)})",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(8.dp))

            // Summary of daily forecasts
            val dailyGroups = timeline.timeline.groupBy { it.date }
            dailyGroups.entries.take(7).forEach { (date, points) ->
                val minTemp = points.minOf { it.temperatureC }
                val maxTemp = points.maxOf { it.temperatureC }
                val totalSnow = points.sumOf { it.snowfallCm }
                val bestQuality = points.minByOrNull { it.snowQuality.sortOrder }?.snowQuality
                val maxGust = points.mapNotNull { it.windGustKmh }.maxOrNull()
                val minVisibility = points.mapNotNull { it.visibilityM }.minOrNull()

                Column(modifier = Modifier.padding(vertical = 2.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = date.takeLast(5),
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.width(50.dp),
                        )
                        bestQuality?.let { q ->
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(snowQualityColor(q.value)),
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "${UnitConversions.formatTemperature(minTemp, units.useMetricTemp)} / ${UnitConversions.formatTemperature(maxTemp, units.useMetricTemp)}",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f),
                        )
                        if (totalSnow > 0) {
                            Icon(Icons.Default.AcUnit, contentDescription = stringResource(R.string.fresh), modifier = Modifier.size(12.dp), tint = SnowColors.IceBlue)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                UnitConversions.formatSnowShort(totalSnow, units.useMetricSnow),
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Bold,
                                color = SnowColors.IceBlue,
                            )
                        }
                    }

                    // Wind gust and visibility indicators
                    val notableGust = maxGust?.takeIf { it >= 50 }
                    val lowVisibility = minVisibility?.takeIf { it < 5000 }
                    if (notableGust != null || lowVisibility != null) {
                        Row(
                            modifier = Modifier.padding(start = 50.dp, top = 2.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            notableGust?.let { gust ->
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.semantics {
                                        contentDescription = "Wind gusts ${UnitConversions.formatWindSpeed(gust, units.useMetricDistance)}"
                                    },
                                ) {
                                    Icon(
                                        Icons.Default.Air,
                                        contentDescription = null,
                                        modifier = Modifier.size(10.dp),
                                        tint = SnowColors.SunsetOrange,
                                    )
                                    Spacer(modifier = Modifier.width(2.dp))
                                    Text(
                                        UnitConversions.formatWindSpeed(gust, units.useMetricDistance),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = SnowColors.SunsetOrange,
                                    )
                                }
                            }
                            lowVisibility?.let { vis ->
                                val visCat = visibilityCategory(vis)
                                val visColor = visibilityCategoryColor(visCat)
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.semantics {
                                        contentDescription = "Visibility ${visCat.label}"
                                    },
                                ) {
                                    Icon(
                                        Icons.Default.Cloud,
                                        contentDescription = null,
                                        modifier = Modifier.size(10.dp),
                                        tint = visColor,
                                    )
                                    Spacer(modifier = Modifier.width(2.dp))
                                    Text(
                                        if (vis < 1000) "${vis.toInt()}m" else String.format("%.0fkm", vis / 1000),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = visColor,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AllElevationsSummaryCard(quality: SnowQualitySummary, units: UnitPreferences) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(stringResource(R.string.all_elevations), style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(12.dp))

            quality.elevations.forEach { (level, summary) ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    val color = when (level) {
                        "base" -> SnowColors.ElevationBase
                        "mid" -> SnowColors.ElevationMid
                        "top" -> SnowColors.ElevationTop
                        else -> MaterialTheme.colorScheme.onSurface
                    }
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(color),
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = level.replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.width(48.dp),
                    )
                    Surface(
                        color = snowQualityColor(summary.quality).copy(alpha = 0.15f),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = summary.snowQuality.displayName,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = snowQualityColor(summary.quality),
                        )
                    }
                    Spacer(modifier = Modifier.weight(1f))
                    Text(
                        UnitConversions.formatTemperature(summary.temperatureCelsius, units.useMetricTemp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        UnitConversions.formatSnowShort(summary.freshSnowCm, units.useMetricSnow),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun ConditionItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun DataSourcesCard(condition: WeatherCondition, units: UnitPreferences) {
    val details = condition.sourceDetails ?: return
    if (details.sourceCount <= 0) return

    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Expandable header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Default.CellTower,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "Data Sources",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )

                // Confidence badge
                Surface(
                    color = sourceConfidenceColor(condition.sourceConfidence).copy(alpha = 0.15f),
                    shape = MaterialTheme.shapes.small,
                ) {
                    Text(
                        text = condition.sourceConfidence.displayName,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = sourceConfidenceColor(condition.sourceConfidence),
                    )
                }

                Spacer(modifier = Modifier.width(8.dp))
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = if (expanded) "Collapse" else "Expand",
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (expanded) {
                Spacer(modifier = Modifier.height(12.dp))

                // Merge method info
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Settings,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        formatMergeMethod(details.mergeMethod),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            "${details.sourceCount} sources",
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))
                HorizontalDivider()
                Spacer(modifier = Modifier.height(8.dp))

                // Per-source details: sorted consensus first, then included, outlier, no_data
                val sortedSources = details.sources.entries.sortedBy { sourceStatusOrder(it.value.status) }
                sortedSources.forEach { (sourceName, info) ->
                    SourceRow(sourceName, info, units)
                }
            }
        }
    }
}

@Composable
private fun SourceRow(sourceName: String, info: SourceInfo, units: UnitPreferences) {
    val isExcluded = info.status == "outlier" || info.status == "no_data"
    val statusColor = sourceStatusColor(info.status)

    Column(modifier = Modifier.padding(vertical = 3.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Status icon
            Icon(
                when (info.status) {
                    "consensus" -> Icons.Default.CheckCircle
                    "outlier" -> Icons.Default.Cancel
                    "included" -> Icons.Default.Circle
                    "no_data" -> Icons.Default.RemoveCircle
                    else -> Icons.Default.Circle
                },
                contentDescription = info.status,
                tint = statusColor,
                modifier = Modifier.size(16.dp),
            )
            Spacer(modifier = Modifier.width(10.dp))

            // Source name
            Text(
                sourceName,
                style = MaterialTheme.typography.bodySmall,
                color = if (isExcluded) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.weight(1f),
                maxLines = 1,
            )

            // Reported value
            if (info.snowfall24hCm != null) {
                Text(
                    UnitConversions.formatSnowShort(info.snowfall24hCm, units.useMetricSnow),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = if (isExcluded) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                )
            } else {
                Text(
                    if (info.status == "no_data") "N/A" else "No data",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            // Status label badge
            Surface(
                color = statusColor.copy(alpha = 0.1f),
                shape = MaterialTheme.shapes.small,
            ) {
                Text(
                    text = sourceStatusLabel(info.status),
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Medium,
                    color = statusColor,
                )
            }
        }

        // Reason text
        info.reason?.let { reason ->
            Text(
                reason,
                style = MaterialTheme.typography.labelSmall,
                color = if (isExcluded) SnowColors.SunsetOrange else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 26.dp, top = 2.dp),
            )
        }
    }
}

private fun formatMergeMethod(method: String): String = when (method) {
    "outlier_detection" -> "Outlier Detection"
    "weighted_average" -> "Weighted Average"
    "simple_average" -> "Simple Average"
    "single_source" -> "Single Source"
    else -> method.replace("_", " ").replaceFirstChar { it.uppercase() }
}

private fun sourceStatusOrder(status: String): Int = when (status) {
    "consensus" -> 0
    "included" -> 1
    "outlier" -> 2
    "no_data" -> 3
    else -> 4
}

private fun sourceStatusLabel(status: String): String = when (status) {
    "consensus" -> "Consensus"
    "outlier" -> "Excluded"
    "included" -> "Included"
    "no_data" -> "Unavailable"
    else -> status.replaceFirstChar { it.uppercase() }
}

@Composable
private fun sourceStatusColor(status: String): androidx.compose.ui.graphics.Color = when (status) {
    "consensus" -> SnowColors.QualityGood
    "outlier" -> SnowColors.SunsetOrange
    "included" -> MaterialTheme.colorScheme.primary
    "no_data" -> MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
private fun sourceConfidenceColor(confidence: ConfidenceLevel): androidx.compose.ui.graphics.Color = when (confidence) {
    ConfidenceLevel.VERY_HIGH -> SnowColors.QualityExcellent
    ConfidenceLevel.HIGH -> SnowColors.QualityGood
    ConfidenceLevel.MEDIUM -> SnowColors.QualityMediocre
    ConfidenceLevel.LOW -> SnowColors.SunsetOrange
    ConfidenceLevel.VERY_LOW -> SnowColors.QualityBad
}

@Composable
private fun SnowAmountItem(label: String, cm: Double, useMetric: Boolean) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            UnitConversions.formatSnow(cm, useMetric),
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = if (cm >= 10) SnowColors.IceBlue else MaterialTheme.colorScheme.onSurface,
        )
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
