package com.powderchaserapp.android.ui.screens.onboarding

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.powderchaserapp.android.util.UserPreferencesRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RegionOption(
    val id: String,
    val name: String,
    val description: String,
    val emoji: String,
)

val regions = listOf(
    RegionOption("na_west", "NA West Coast", "BC, WA, OR, CA", ""),
    RegionOption("na_rockies", "NA Rockies", "AB, CO, UT, WY, MT", ""),
    RegionOption("na_east", "NA East", "VT, ME, NH, QC", ""),
    RegionOption("alps", "Alps", "FR, CH, AT, IT", ""),
    RegionOption("scandinavia", "Scandinavia", "NO, SE, FI", ""),
    RegionOption("japan", "Japan", "Hokkaido, Honshu", ""),
    RegionOption("oceania", "Oceania", "NZ, AU", ""),
    RegionOption("south_america", "South America", "CL, AR", ""),
)

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val userPreferencesRepository: UserPreferencesRepository,
) : ViewModel() {
    private val _selectedRegions = MutableStateFlow<Set<String>>(emptySet())
    val selectedRegions = _selectedRegions.asStateFlow()

    private val _currentStep = MutableStateFlow(0)
    val currentStep = _currentStep.asStateFlow()

    fun toggleRegion(regionId: String) {
        _selectedRegions.value = if (regionId in _selectedRegions.value) {
            _selectedRegions.value - regionId
        } else {
            _selectedRegions.value + regionId
        }
    }

    fun nextStep() {
        _currentStep.value++
    }

    fun completeOnboarding(onComplete: () -> Unit) {
        viewModelScope.launch {
            // Save hidden regions = all regions NOT selected
            val allRegionIds = regions.map { it.id }.toSet()
            val hiddenRegions = allRegionIds - _selectedRegions.value
            if (_selectedRegions.value.isNotEmpty()) {
                userPreferencesRepository.setHiddenRegions(hiddenRegions)
            }
            userPreferencesRepository.setOnboardingComplete(true)
            onComplete()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val selectedRegions by viewModel.selectedRegions.collectAsState()
    val currentStep by viewModel.currentStep.collectAsState()

    Scaffold { padding ->
        when (currentStep) {
            0 -> WelcomeStep(
                onNext = { viewModel.nextStep() },
                modifier = Modifier.padding(padding),
            )
            1 -> RegionSelectionStep(
                selectedRegions = selectedRegions,
                onToggleRegion = { viewModel.toggleRegion(it) },
                onComplete = { viewModel.completeOnboarding(onComplete) },
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun WelcomeStep(
    onNext: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            Icons.Default.Terrain,
            contentDescription = null,
            modifier = Modifier.size(80.dp),
            tint = MaterialTheme.colorScheme.primary,
        )
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            "Powder Chaser",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            "Real-time snow quality tracking for 1000+ ski resorts worldwide",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(32.dp))

        // Feature highlights
        FeatureHighlight(
            icon = Icons.Default.AcUnit,
            title = "Snow Quality Scores",
            description = "ML-powered quality ratings from champagne powder to icy conditions",
        )
        Spacer(modifier = Modifier.height(16.dp))
        FeatureHighlight(
            icon = Icons.Default.Map,
            title = "Interactive Map",
            description = "See conditions at every resort, color-coded by quality",
        )
        Spacer(modifier = Modifier.height(16.dp))
        FeatureHighlight(
            icon = Icons.Default.AutoAwesome,
            title = "AI-Powered Chat",
            description = "Ask about conditions, compare resorts, get personalized recommendations",
        )

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = onNext,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Get Started")
        }
    }
}

@Composable
private fun FeatureHighlight(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    description: String,
) {
    Row(
        verticalAlignment = Alignment.Top,
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(28.dp),
            tint = MaterialTheme.colorScheme.primary,
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun RegionSelectionStep(
    selectedRegions: Set<String>,
    onToggleRegion: (String) -> Unit,
    onComplete: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            "Select Your Regions",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Choose the ski regions you're interested in. You can always change this later.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(modifier = Modifier.height(16.dp))

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(regions) { region ->
                val selected = region.id in selectedRegions
                FilterChip(
                    selected = selected,
                    onClick = { onToggleRegion(region.id) },
                    label = {
                        Column(modifier = Modifier.padding(vertical = 4.dp)) {
                            Text(region.name, style = MaterialTheme.typography.titleSmall)
                            Text(
                                region.description,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    },
                    leadingIcon = if (selected) {
                        {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    } else null,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        if (selectedRegions.isNotEmpty()) {
            Text(
                "${selectedRegions.size} region${if (selectedRegions.size > 1) "s" else ""} selected",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            )
            Spacer(modifier = Modifier.height(8.dp))
        }

        Button(
            onClick = onComplete,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (selectedRegions.isEmpty()) "Skip for Now" else "Continue")
        }
    }
}
