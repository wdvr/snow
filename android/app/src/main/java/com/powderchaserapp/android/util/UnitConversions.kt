package com.powderchaserapp.android.util

import kotlin.math.roundToInt

/**
 * Unit conversion and formatting utilities matching the iOS counterparts.
 */
object UnitConversions {

    // =========================================================================
    // Temperature
    // =========================================================================

    fun celsiusToFahrenheit(celsius: Double): Double = celsius * 9.0 / 5.0 + 32.0

    fun formatTemperature(celsius: Double, useMetric: Boolean): String {
        return if (useMetric) {
            "${celsius.roundToInt()}\u00B0C"
        } else {
            "${celsiusToFahrenheit(celsius).roundToInt()}\u00B0F"
        }
    }

    // =========================================================================
    // Distance
    // =========================================================================

    fun kmToMiles(km: Double): Double = km * 0.621371

    fun formatDistance(km: Double, useMetric: Boolean): String {
        return if (useMetric) {
            when {
                km < 1 -> "${(km * 1000).roundToInt()} m"
                km < 10 -> String.format("%.1f km", km)
                else -> "${km.roundToInt()} km"
            }
        } else {
            val miles = kmToMiles(km)
            when {
                miles < 1 -> String.format("%.1f mi", miles)
                miles < 10 -> String.format("%.1f mi", miles)
                else -> "${miles.roundToInt()} mi"
            }
        }
    }

    // =========================================================================
    // Snow Depth
    // =========================================================================

    fun cmToInches(cm: Double): Double = cm / 2.54

    fun formatSnow(cm: Double, useMetric: Boolean): String {
        return if (useMetric) {
            when {
                cm < 1 && cm > 0 -> String.format("%.1f cm", cm)
                else -> "${cm.roundToInt()} cm"
            }
        } else {
            val inches = cmToInches(cm)
            when {
                inches < 1 && inches > 0 -> String.format("%.1f\"", inches)
                else -> "${inches.roundToInt()}\""
            }
        }
    }

    fun formatSnowShort(cm: Double, useMetric: Boolean): String {
        return if (useMetric) {
            "${cm.roundToInt()}cm"
        } else {
            "${cmToInches(cm).roundToInt()}\""
        }
    }

    // =========================================================================
    // Wind Speed
    // =========================================================================

    fun kmhToMph(kmh: Double): Double = kmh * 0.621371

    fun formatWindSpeed(kmh: Double, useMetric: Boolean): String {
        return if (useMetric) {
            "${kmh.roundToInt()} km/h"
        } else {
            "${kmhToMph(kmh).roundToInt()} mph"
        }
    }

    // =========================================================================
    // Elevation
    // =========================================================================

    fun metersToFeet(meters: Double): Double = meters * 3.28084

    fun formatElevation(meters: Double, useMetric: Boolean): String {
        return if (useMetric) {
            "${meters.roundToInt()}m"
        } else {
            "${metersToFeet(meters).roundToInt()}ft"
        }
    }
}
