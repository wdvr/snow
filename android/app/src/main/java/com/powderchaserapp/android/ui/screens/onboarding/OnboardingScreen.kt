package com.powderchaserapp.android.ui.screens.onboarding

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

data class RegionOption(
    val id: String,
    val name: String,
    val description: String,
)

val regions = listOf(
    RegionOption("na_west", "NA West Coast", "BC, WA, OR, CA"),
    RegionOption("na_rockies", "NA Rockies", "AB, CO, UT, WY, MT"),
    RegionOption("na_east", "NA East", "VT, ME, NH, QC"),
    RegionOption("alps", "Alps", "FR, CH, AT, IT"),
    RegionOption("scandinavia", "Scandinavia", "NO, SE"),
    RegionOption("japan", "Japan", "Hokkaido, Honshu"),
    RegionOption("oceania", "Oceania", "NZ, AU"),
    RegionOption("south_america", "South America", "CL, AR"),
)

@HiltViewModel
class OnboardingViewModel @Inject constructor() : ViewModel() {
    private val _selectedRegions = MutableStateFlow<Set<String>>(emptySet())
    val selectedRegions = _selectedRegions.asStateFlow()

    fun toggleRegion(regionId: String) {
        _selectedRegions.value = if (regionId in _selectedRegions.value) {
            _selectedRegions.value - regionId
        } else {
            _selectedRegions.value + regionId
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

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Select Regions") })
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
        ) {
            Text(
                text = "Which regions are you interested in?",
                style = MaterialTheme.typography.bodyLarge,
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
                        onClick = { viewModel.toggleRegion(region.id) },
                        label = {
                            Column {
                                Text(region.name, style = MaterialTheme.typography.titleSmall)
                                Text(
                                    region.description,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Button(
                onClick = onComplete,
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.CenterHorizontally),
            ) {
                Text(if (selectedRegions.isEmpty()) "Skip" else "Continue")
            }
        }
    }
}
