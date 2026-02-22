package com.powderchaserapp.android.util

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "user_preferences")

enum class TemperatureUnit { CELSIUS, FAHRENHEIT }
enum class DistanceUnit { METRIC, IMPERIAL }
enum class SnowDepthUnit { CENTIMETERS, INCHES }

data class UnitPreferences(
    val temperature: TemperatureUnit = TemperatureUnit.CELSIUS,
    val distance: DistanceUnit = DistanceUnit.METRIC,
    val snowDepth: SnowDepthUnit = SnowDepthUnit.CENTIMETERS,
) {
    val useMetricTemp: Boolean get() = temperature == TemperatureUnit.CELSIUS
    val useMetricDistance: Boolean get() = distance == DistanceUnit.METRIC
    val useMetricSnow: Boolean get() = snowDepth == SnowDepthUnit.CENTIMETERS
}

@Singleton
class UserPreferencesRepository @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.dataStore

    companion object {
        private val TEMPERATURE_UNIT = stringPreferencesKey("temperature_unit")
        private val DISTANCE_UNIT = stringPreferencesKey("distance_unit")
        private val SNOW_DEPTH_UNIT = stringPreferencesKey("snow_depth_unit")
        private val FAVORITE_RESORTS = stringSetPreferencesKey("favorite_resorts")
        private val ONBOARDING_COMPLETE = booleanPreferencesKey("onboarding_complete")
        private val SELECTED_ENVIRONMENT = stringPreferencesKey("selected_environment")
        private val HIDDEN_REGIONS = stringSetPreferencesKey("hidden_regions")
    }

    val unitPreferences: Flow<UnitPreferences> = dataStore.data.map { prefs ->
        UnitPreferences(
            temperature = when (prefs[TEMPERATURE_UNIT]) {
                "fahrenheit" -> TemperatureUnit.FAHRENHEIT
                else -> TemperatureUnit.CELSIUS
            },
            distance = when (prefs[DISTANCE_UNIT]) {
                "imperial" -> DistanceUnit.IMPERIAL
                else -> DistanceUnit.METRIC
            },
            snowDepth = when (prefs[SNOW_DEPTH_UNIT]) {
                "inches" -> SnowDepthUnit.INCHES
                else -> SnowDepthUnit.CENTIMETERS
            },
        )
    }

    val favoriteResorts: Flow<Set<String>> = dataStore.data.map { prefs ->
        prefs[FAVORITE_RESORTS] ?: emptySet()
    }

    val isOnboardingComplete: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[ONBOARDING_COMPLETE] ?: false
    }

    val selectedEnvironment: Flow<String> = dataStore.data.map { prefs ->
        prefs[SELECTED_ENVIRONMENT] ?: "prod"
    }

    val hiddenRegions: Flow<Set<String>> = dataStore.data.map { prefs ->
        prefs[HIDDEN_REGIONS] ?: emptySet()
    }

    suspend fun setTemperatureUnit(unit: TemperatureUnit) {
        dataStore.edit { prefs ->
            prefs[TEMPERATURE_UNIT] = when (unit) {
                TemperatureUnit.CELSIUS -> "celsius"
                TemperatureUnit.FAHRENHEIT -> "fahrenheit"
            }
        }
    }

    suspend fun setDistanceUnit(unit: DistanceUnit) {
        dataStore.edit { prefs ->
            prefs[DISTANCE_UNIT] = when (unit) {
                DistanceUnit.METRIC -> "metric"
                DistanceUnit.IMPERIAL -> "imperial"
            }
        }
    }

    suspend fun setSnowDepthUnit(unit: SnowDepthUnit) {
        dataStore.edit { prefs ->
            prefs[SNOW_DEPTH_UNIT] = when (unit) {
                SnowDepthUnit.CENTIMETERS -> "centimeters"
                SnowDepthUnit.INCHES -> "inches"
            }
        }
    }

    suspend fun toggleFavorite(resortId: String) {
        dataStore.edit { prefs ->
            val current = prefs[FAVORITE_RESORTS]?.toMutableSet() ?: mutableSetOf()
            if (current.contains(resortId)) {
                current.remove(resortId)
            } else {
                current.add(resortId)
            }
            prefs[FAVORITE_RESORTS] = current
        }
    }

    suspend fun isFavorite(resortId: String): Boolean {
        var result = false
        dataStore.edit { prefs ->
            result = prefs[FAVORITE_RESORTS]?.contains(resortId) ?: false
        }
        return result
    }

    suspend fun setOnboardingComplete(complete: Boolean) {
        dataStore.edit { prefs ->
            prefs[ONBOARDING_COMPLETE] = complete
        }
    }

    suspend fun setEnvironment(env: String) {
        dataStore.edit { prefs ->
            prefs[SELECTED_ENVIRONMENT] = env
        }
    }

    suspend fun setHiddenRegions(regions: Set<String>) {
        dataStore.edit { prefs ->
            prefs[HIDDEN_REGIONS] = regions
        }
    }

    suspend fun clearAll() {
        dataStore.edit { it.clear() }
    }
}
